"""Ruta en disco de los documentos subidos.

Revision ID: 0006_ruta_almacen_documento
Revises: 0005_presupuesto_excel
Create Date: 2026-10-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_ruta_almacen_documento"
down_revision: Union[str, Sequence[str], None] = "0005_presupuesto_excel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "presupuesto",
        sa.Column("ruta_almacen", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "contrato",
        sa.Column("ruta_almacen", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "factura",
        sa.Column("ruta_almacen", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("factura", "ruta_almacen")
    op.drop_column("contrato", "ruta_almacen")
    op.drop_column("presupuesto", "ruta_almacen")
