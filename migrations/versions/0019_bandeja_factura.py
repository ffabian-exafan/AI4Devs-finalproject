"""Bandeja de facturas leídas de la unidad de red.

Revision ID: 0019_bandeja_factura
Revises: 0018_sello_factura
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_bandeja_factura"
down_revision: Union[str, Sequence[str], None] = "0018_sello_factura"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bandeja_factura",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("ruta_red", sa.String(length=2048), nullable=False),
        sa.Column("nombre_fichero", sa.String(length=512), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("modificado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mes_carpeta", sa.Integer(), nullable=True),
        sa.Column("es_escaneada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("estado", sa.String(length=50), nullable=False),
        sa.Column("reintentar", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("aviso", sa.Text(), nullable=True),
        sa.Column("aviso_mes", sa.Text(), nullable=True),
        sa.Column("aviso_codigo", sa.Text(), nullable=True),
        sa.Column("ruta_copia", sa.String(length=1024), nullable=True),
        sa.Column("nif_detectado", sa.String(length=32), nullable=True),
        sa.Column("numero", sa.String(length=100), nullable=True),
        sa.Column("fecha_emision", sa.Date(), nullable=True),
        sa.Column("base_imponible", sa.Numeric(14, 2), nullable=True),
        sa.Column("iva", sa.Numeric(14, 2), nullable=True),
        sa.Column("irpf", sa.Numeric(14, 2), nullable=True),
        sa.Column("retencion_garantia", sa.Numeric(14, 2), nullable=True),
        sa.Column("total", sa.Numeric(14, 2), nullable=True),
        sa.Column("tipo", sa.String(length=50), nullable=True),
        sa.Column("codigo_contrato", sa.String(length=16), nullable=True),
        sa.Column("factura_id", sa.Integer(), nullable=True),
        sa.Column("leido_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["factura_id"], ["factura.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("hash_sha256"),
    )
    op.create_index("ix_bandeja_factura_ruta_red", "bandeja_factura", ["ruta_red"])
    op.create_index("ix_bandeja_factura_factura_id", "bandeja_factura", ["factura_id"])
    op.create_table(
        "barrido_factura",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("iniciado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nuevos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ya_vistos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("omitidos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errores", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("aviso", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("barrido_factura")
    op.drop_index("ix_bandeja_factura_factura_id", table_name="bandeja_factura")
    op.drop_index("ix_bandeja_factura_ruta_red", table_name="bandeja_factura")
    op.drop_table("bandeja_factura")
