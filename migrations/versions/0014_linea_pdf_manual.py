"""Marca las líneas de importe del PDF añadidas a mano.

Revision ID: 0014_linea_pdf_manual
Revises: 0013_presupuesto_ver_pagina
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_linea_pdf_manual"
down_revision: Union[str, Sequence[str], None] = "0013_presupuesto_ver_pagina"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "linea_pdf_cliente",
        sa.Column(
            "es_manual",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("linea_pdf_cliente", "es_manual")
