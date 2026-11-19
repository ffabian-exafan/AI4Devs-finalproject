"""Código de contrato para relacionarlo con la factura.

Revision ID: 0017_codigo_contrato
Revises: 0016_inversion_sujeto_pasivo
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_codigo_contrato"
down_revision: Union[str, Sequence[str], None] = "0016_inversion_sujeto_pasivo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contrato", sa.Column("codigo", sa.String(length=16), nullable=True))
    op.create_index("uq_contrato_codigo", "contrato", ["codigo"], unique=True)
    op.add_column(
        "factura",
        sa.Column("codigo_contrato", sa.String(length=16), nullable=True),
    )
    op.add_column("factura", sa.Column("aviso_codigo", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("factura", "aviso_codigo")
    op.drop_column("factura", "codigo_contrato")
    op.drop_index("uq_contrato_codigo", table_name="contrato")
    op.drop_column("contrato", "codigo")
