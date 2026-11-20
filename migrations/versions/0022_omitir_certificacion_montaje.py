"""Marca de que el sello verde de montaje no es necesario.

Revision ID: 0022_verde_opcional
Revises: 0021_certificacion_montaje
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_verde_opcional"
down_revision: Union[str, Sequence[str], None] = "0021_certificacion_montaje"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CODIGOS = (
    "confirmar_revision",
    "confirmar_factura",
    "certificar_montaje",
    "omitir_certificacion_montaje",
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

_CODIGOS_ANTERIORES = tuple(
    codigo for codigo in _CODIGOS if codigo != "omitir_certificacion_montaje"
)


def upgrade() -> None:
    op.add_column(
        "factura",
        sa.Column(
            "certificacion_montaje_omitida",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
    op.drop_column("factura", "certificacion_montaje_omitida")
