"""Explicación al enlazar un apartado del contrato que no está en el Excel.

Revision ID: 0011_explicacion_apartado_contrato
Revises: 0010_contrato_varios_apartados
Create Date: 2026-11-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_explica_apartado"
down_revision: Union[str, Sequence[str], None] = "0010_contrato_varios_apartados"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contrato_apartado",
        sa.Column("explicacion", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contrato_apartado", "explicacion")
