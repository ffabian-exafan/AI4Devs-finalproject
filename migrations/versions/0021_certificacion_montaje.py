"""Sello verde de certificación de montaje, antes del sello azul.

Revision ID: 0021_certificacion_montaje
Revises: 0020_mano_obra_propia
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_certificacion_montaje"
down_revision: Union[str, Sequence[str], None] = "0020_mano_obra_propia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CODIGOS = (
    "confirmar_revision",
    "confirmar_factura",
    "certificar_montaje",
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

_CODIGOS_ANTERIORES = (
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


def upgrade() -> None:
    op.add_column(
        "factura",
        sa.Column("certificacion_montaje_por", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "factura",
        sa.Column("certificacion_montaje_usuario_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "factura",
        sa.Column("certificacion_montaje_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "factura",
        sa.Column("ruta_certificacion", sa.String(length=1024), nullable=True),
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
    op.drop_column("factura", "ruta_certificacion")
    op.drop_column("factura", "certificacion_montaje_en")
    op.drop_column("factura", "certificacion_montaje_usuario_id")
    op.drop_column("factura", "certificacion_montaje_por")
