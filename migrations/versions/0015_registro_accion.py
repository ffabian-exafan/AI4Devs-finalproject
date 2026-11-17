"""Tabla inmutable del registro de acciones.

Revision ID: 0015_registro_accion
Revises: 0014_linea_pdf_manual
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_registro_accion"
down_revision: Union[str, Sequence[str], None] = "0014_linea_pdf_manual"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registro_accion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ocurrido_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("nombre_en_el_momento", sa.String(length=255), nullable=False),
        sa.Column("accion", sa.String(length=40), nullable=False),
        sa.Column("tipo_documento", sa.String(length=32), nullable=True),
        sa.Column("documento_id", sa.Integer(), nullable=True),
        sa.Column("etiqueta", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "accion IN ("
            "'confirmar_revision', 'confirmar_factura', "
            "'confirmar_importe_cliente', 'confirmar_importes_cliente', "
            "'confirmar_solo_gestion', 'borrar_proyecto', 'borrar_contrato', "
            "'borrar_factura', 'borrar_linea', 'inicio_sesion'"
            ")",
            name="registro_accion_codigo",
        ),
        sa.CheckConstraint(
            "("
            "accion = 'inicio_sesion' AND tipo_documento IS NULL "
            "AND documento_id IS NULL AND etiqueta IS NULL"
            ") OR ("
            "accion <> 'inicio_sesion' AND tipo_documento IS NOT NULL "
            "AND documento_id IS NOT NULL AND etiqueta IS NOT NULL"
            ")",
            name="registro_accion_documento",
        ),
    )
    op.create_index("ix_registro_accion_ocurrido_en", "registro_accion", ["ocurrido_en"])
    op.create_index("ix_registro_accion_usuario_id", "registro_accion", ["usuario_id"])
    op.create_index("ix_registro_accion_accion", "registro_accion", ["accion"])
    op.create_index(
        "ix_registro_accion_documento",
        "registro_accion",
        ["tipo_documento", "documento_id"],
    )
    op.execute(
        """
        CREATE FUNCTION registro_accion_rechazar_cambio()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'La fila del registro no se puede modificar';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER registro_accion_bloquear
        BEFORE UPDATE OR DELETE ON registro_accion
        FOR EACH ROW
        EXECUTE FUNCTION registro_accion_rechazar_cambio();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS registro_accion_bloquear ON registro_accion")
    op.execute("DROP FUNCTION IF EXISTS registro_accion_rechazar_cambio()")
    op.drop_table("registro_accion")