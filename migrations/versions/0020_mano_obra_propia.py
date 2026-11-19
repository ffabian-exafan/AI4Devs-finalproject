"""Mano de obra propia: precio por hora, línea y parte de trabajo.

Revision ID: 0020_mano_obra_propia
Revises: 0019_bandeja_factura
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_mano_obra_propia"
down_revision: Union[str, Sequence[str], None] = "0019_bandeja_factura"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CODIGOS = (
    "confirmar_revision",
    "confirmar_factura",
    "confirmar_importe_cliente",
    "confirmar_importes_cliente",
    "confirmar_solo_gestion",
    "borrar_proyecto",
    "borrar_contrato",
    "borrar_factura",
    "borrar_linea",
    "inicio_sesion",
    "marcar_isp",
    "quitar_isp",
    "guardar_precio_hora",
    "borrar_linea_mano_obra",
    "confirmar_parte",
    "borrar_parte",
)

_CODIGOS_ANTERIORES = _CODIGOS[:-4]


def upgrade() -> None:
    op.add_column("proyecto", sa.Column("precio_hora", sa.Numeric(14, 4), nullable=True))
    op.create_table(
        "linea_mano_obra",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proyecto_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["proyecto_id"], ["proyecto.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_linea_mano_obra_proyecto_id",
        "linea_mano_obra",
        ["proyecto_id"],
    )
    op.create_table(
        "parte_trabajo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("linea_mano_obra_id", sa.Integer(), nullable=False),
        sa.Column("fichero_origen", sa.String(512), nullable=False),
        sa.Column("ruta_almacen", sa.String(1024), nullable=False),
        sa.Column("es_escaneado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("horas", sa.Numeric(10, 2), nullable=True),
        sa.Column("fecha", sa.Date(), nullable=True),
        sa.Column(
            "tiene_anotacion_manual",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("aviso", sa.Text(), nullable=True),
        sa.Column("estado_revision", sa.String(50), nullable=False),
        sa.Column("precio_hora_aplicado", sa.Numeric(14, 4), nullable=True),
        sa.Column("importe", sa.Numeric(14, 2), nullable=True),
        sa.Column("confirmada_por", sa.String(255), nullable=True),
        sa.Column("confirmada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["linea_mano_obra_id"],
            ["linea_mano_obra.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "estado_revision IN ('pendiente', 'confirmada')",
            name="parte_trabajo_estado",
        ),
        sa.CheckConstraint(
            "("
            "estado_revision = 'pendiente'"
            ") OR ("
            "estado_revision = 'confirmada' "
            "AND horas IS NOT NULL "
            "AND precio_hora_aplicado IS NOT NULL "
            "AND importe IS NOT NULL "
            "AND confirmada_en IS NOT NULL"
            ")",
            name="parte_trabajo_confirmado",
        ),
    )
    op.create_index(
        "ix_parte_trabajo_linea_mano_obra_id",
        "parte_trabajo",
        ["linea_mano_obra_id"],
    )
    op.drop_constraint("registro_accion_codigo", "registro_accion", type_="check")
    op.create_check_constraint(
        "registro_accion_codigo",
        "registro_accion",
        "accion IN (" + ", ".join(f"'{codigo}'" for codigo in _CODIGOS) + ")",
    )


def downgrade() -> None:
    op.drop_constraint("registro_accion_codigo", "registro_accion", type_="check")
    op.create_check_constraint(
        "registro_accion_codigo",
        "registro_accion",
        "accion IN (" + ", ".join(f"'{codigo}'" for codigo in _CODIGOS_ANTERIORES) + ")",
    )
    op.drop_index("ix_parte_trabajo_linea_mano_obra_id", table_name="parte_trabajo")
    op.drop_table("parte_trabajo")
    op.drop_index("ix_linea_mano_obra_proyecto_id", table_name="linea_mano_obra")
    op.drop_table("linea_mano_obra")
    op.drop_column("proyecto", "precio_hora")
