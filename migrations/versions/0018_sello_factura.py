"""Sello de confirmación en la factura.

Revision ID: 0018_sello_factura
Revises: 0017_codigo_contrato
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_sello_factura"
down_revision: Union[str, Sequence[str], None] = "0017_codigo_contrato"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "factura",
        sa.Column("referencia_alc", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "factura",
        sa.Column("confirmada_por", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "factura",
        sa.Column("confirmada_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "factura",
        sa.Column("ruta_sello", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("factura", "ruta_sello")
    op.drop_column("factura", "confirmada_en")
    op.drop_column("factura", "confirmada_por")
    op.drop_column("factura", "referencia_alc")
