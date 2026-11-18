"""Marca de inversión del sujeto pasivo en la obra.

Revision ID: 0016_inversion_sujeto_pasivo
Revises: 0015_registro_accion
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_inversion_sujeto_pasivo"
down_revision: Union[str, Sequence[str], None] = "0015_registro_accion"
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
)

_CODIGOS_ANTERIORES = _CODIGOS[:-2]


def upgrade() -> None:
    op.add_column(
        "proyecto",
        sa.Column(
            "inversion_sujeto_pasivo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("proyecto", sa.Column("ruta_carta_isp", sa.String(1024), nullable=True))
    op.add_column("proyecto", sa.Column("fichero_carta_isp", sa.String(512), nullable=True))
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
    op.drop_column("proyecto", "fichero_carta_isp")
    op.drop_column("proyecto", "ruta_carta_isp")
    op.drop_column("proyecto", "inversion_sujeto_pasivo")
