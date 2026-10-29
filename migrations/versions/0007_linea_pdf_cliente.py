"""Líneas del PDF del cliente y su enlace a bloques del Excel.

Revision ID: 0007_linea_pdf_cliente
Revises: 0006_ruta_almacen_documento
Create Date: 2026-10-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_linea_pdf_cliente"
down_revision: Union[str, Sequence[str], None] = "0006_ruta_almacen_documento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "linea_pdf_cliente",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("presupuesto_id", sa.Integer(), sa.ForeignKey("presupuesto.id"), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("codigo", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("descripcion", sa.String(length=512), nullable=False),
        sa.Column("importe", sa.Numeric(14, 2), nullable=False),
        sa.Column("importe_bruto", sa.Numeric(14, 2), nullable=True),
        sa.Column("es_manuscrito", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_linea_pdf_cliente_presupuesto_id",
        "linea_pdf_cliente",
        ["presupuesto_id"],
    )
    op.create_table(
        "linea_pdf_cliente_tarea",
        sa.Column(
            "linea_id",
            sa.Integer(),
            sa.ForeignKey("linea_pdf_cliente.id"),
            primary_key=True,
        ),
        sa.Column("tarea_id", sa.Integer(), sa.ForeignKey("tarea.id"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("linea_pdf_cliente_tarea")
    op.drop_index("ix_linea_pdf_cliente_presupuesto_id", table_name="linea_pdf_cliente")
    op.drop_table("linea_pdf_cliente")
