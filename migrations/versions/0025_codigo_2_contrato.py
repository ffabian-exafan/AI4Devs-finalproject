"""Segundo código de contrato en obras de pedidos de compra.

Revision ID: 0025_codigo_2_contrato
Revises: 0024_confirmar_pedido
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_codigo_2_contrato"
down_revision: Union[str, Sequence[str], None] = "0024_confirmar_pedido"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contrato", sa.Column("codigo_2", sa.String(length=16), nullable=True))
    op.create_index("uq_contrato_codigo_2", "contrato", ["codigo_2"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_contrato_codigo_2", table_name="contrato")
    op.drop_column("contrato", "codigo_2")
