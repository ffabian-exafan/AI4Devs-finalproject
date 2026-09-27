"""Campos para desviación por partida, duplicados y sugerencia de contrato.

Revision ID: 0004_desviaciones_partida
Revises: 0003_presupuesto_es_escaneado
Create Date: 2026-09-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_desviaciones_partida"
down_revision: Union[str, Sequence[str], None] = "0003_presupuesto_es_escaneado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proyecto", sa.Column("codigo", sa.String(length=50), nullable=True))
    op.add_column("proyecto", sa.Column("cliente", sa.String(length=255), nullable=True))
    op.add_column("proyecto", sa.Column("ubicacion", sa.String(length=255), nullable=True))
    op.add_column("proyecto", sa.Column("especie", sa.String(length=50), nullable=True))
    op.add_column("proyecto", sa.Column("fase", sa.String(length=50), nullable=True))

    op.add_column("tarea", sa.Column("marca_duda", sa.String(length=50), nullable=True))

    op.add_column("contrato", sa.Column("confianza", sa.Integer(), nullable=True))
    op.add_column("contrato", sa.Column("motivo_sugerencia", sa.Text(), nullable=True))
    op.add_column("contrato", sa.Column("aviso", sa.Text(), nullable=True))

    op.add_column("factura", sa.Column("resolucion", sa.String(length=50), nullable=True))
    op.add_column("factura", sa.Column("duplicado_de_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_factura_duplicado_de_id",
        "factura",
        "factura",
        ["duplicado_de_id"],
        ["id"],
    )

    op.add_column("linea_factura", sa.Column("cantidad", sa.Numeric(14, 4), nullable=True))
    op.add_column(
        "linea_factura",
        sa.Column("precio_unitario", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column("linea_factura", sa.Column("tarea_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_linea_factura_tarea_id",
        "linea_factura",
        "tarea",
        ["tarea_id"],
        ["id"],
    )
    op.create_index("ix_linea_factura_tarea_id", "linea_factura", ["tarea_id"])


def downgrade() -> None:
    op.drop_index("ix_linea_factura_tarea_id", table_name="linea_factura")
    op.drop_constraint("fk_linea_factura_tarea_id", "linea_factura", type_="foreignkey")
    op.drop_column("linea_factura", "tarea_id")
    op.drop_column("linea_factura", "precio_unitario")
    op.drop_column("linea_factura", "cantidad")

    op.drop_constraint("fk_factura_duplicado_de_id", "factura", type_="foreignkey")
    op.drop_column("factura", "duplicado_de_id")
    op.drop_column("factura", "resolucion")

    op.drop_column("contrato", "aviso")
    op.drop_column("contrato", "motivo_sugerencia")
    op.drop_column("contrato", "confianza")

    op.drop_column("tarea", "marca_duda")

    op.drop_column("proyecto", "fase")
    op.drop_column("proyecto", "especie")
    op.drop_column("proyecto", "ubicacion")
    op.drop_column("proyecto", "cliente")
    op.drop_column("proyecto", "codigo")
