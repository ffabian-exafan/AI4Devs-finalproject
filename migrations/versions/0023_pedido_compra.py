"""Pedido de compra de serie 1 y su nave.

Revision ID: 0023_pedido_compra
Revises: 0022_verde_opcional
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_pedido_compra"
down_revision: Union[str, Sequence[str], None] = "0022_verde_opcional"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pedido",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyecto.id"), nullable=False),
        sa.Column("nave_id", sa.Integer(), sa.ForeignKey("nave.id"), nullable=False),
        sa.Column("numero", sa.String(length=16), nullable=False),
        sa.Column("rotulo", sa.String(length=255), nullable=True),
        sa.Column("fichero_origen", sa.String(length=512), nullable=False),
        sa.Column("ruta_almacen", sa.String(length=1024), nullable=True),
        sa.Column("estado_revision", sa.String(length=50), nullable=False),
        sa.Column("aviso", sa.Text(), nullable=True),
        sa.UniqueConstraint("nave_id", name="uq_pedido_nave"),
        sa.UniqueConstraint("numero", name="uq_pedido_numero"),
    )
    op.create_index("ix_pedido_proyecto_id", "pedido", ["proyecto_id"])
    op.add_column("tarea", sa.Column("pedido_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_tarea_pedido", "tarea", "pedido", ["pedido_id"], ["id"])
    op.create_index("ix_tarea_pedido_id", "tarea", ["pedido_id"])


def downgrade() -> None:
    op.drop_index("ix_tarea_pedido_id", table_name="tarea")
    op.drop_constraint("fk_tarea_pedido", "tarea", type_="foreignkey")
    op.drop_column("tarea", "pedido_id")
    op.drop_index("ix_pedido_proyecto_id", table_name="pedido")
    op.drop_table("pedido")
