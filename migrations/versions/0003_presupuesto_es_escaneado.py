"""Esquema: presupuesto.es_escaneado (OCR / imagen).

Revision ID: 0003_presupuesto_es_escaneado
Revises: 0002_contrato_tarea_apartado
Create Date: 2026-09-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_presupuesto_es_escaneado"
down_revision: Union[str, Sequence[str], None] = "0002_contrato_tarea_apartado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "presupuesto",
        sa.Column(
            "es_escaneado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("presupuesto", "es_escaneado")
