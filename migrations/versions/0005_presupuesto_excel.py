"""Presupuesto Excel Expertis: formato, montaje y contraste con el cliente.

Revision ID: 0005_presupuesto_excel
Revises: 0004_desviaciones_partida
Create Date: 2026-10-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_presupuesto_excel"
down_revision: Union[str, Sequence[str], None] = "0004_desviaciones_partida"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "presupuesto",
        sa.Column(
            "formato",
            sa.String(length=50),
            nullable=False,
            server_default="pdf_cliente",
        ),
    )
    op.add_column(
        "tarea",
        sa.Column(
            "es_montaje",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("tarea", sa.Column("descuento_pct", sa.Numeric(8, 4), nullable=True))
    op.add_column("tarea", sa.Column("referencia", sa.String(length=255), nullable=True))
    op.add_column(
        "tarea", sa.Column("referencia_alt", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "tarea",
        sa.Column("importe_contrato_cliente", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tarea", "importe_contrato_cliente")
    op.drop_column("tarea", "referencia_alt")
    op.drop_column("tarea", "referencia")
    op.drop_column("tarea", "descuento_pct")
    op.drop_column("tarea", "es_montaje")
    op.drop_column("presupuesto", "formato")
