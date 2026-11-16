"""Casilla de manuscrito en el PDF de presupuesto.

Revision ID: 0013_presupuesto_ver_pagina
Revises: 0012_linea_pdf_contrato
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_presupuesto_ver_pagina"
down_revision: Union[str, Sequence[str], None] = "0012_linea_pdf_contrato"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "presupuesto",
        sa.Column(
            "ver_pagina",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("presupuesto", "ver_pagina")
