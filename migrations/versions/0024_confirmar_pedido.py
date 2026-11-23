"""Acción de confirmar un pedido de serie 1.

Revision ID: 0024_confirmar_pedido
Revises: 0023_pedido_compra
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0024_confirmar_pedido"
down_revision: Union[str, Sequence[str], None] = "0023_pedido_compra"
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
    "confirmar_pedido",
)

_CODIGOS_ANTERIORES = tuple(codigo for codigo in _CODIGOS if codigo != "confirmar_pedido")


def upgrade() -> None:
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
