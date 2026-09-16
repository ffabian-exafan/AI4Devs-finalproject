"""Esquema: enlace contrato ↔ apartado de presupuesto.

Revision ID: 0002_contrato_tarea_apartado
Revises: 0001_esquema_inicial
Create Date: 2026-09-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_contrato_tarea_apartado"
down_revision: Union[str, Sequence[str], None] = "0001_esquema_inicial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contrato",
        sa.Column("tarea_apartado_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_contrato_tarea_apartado_id",
        "contrato",
        "tarea",
        ["tarea_apartado_id"],
        ["id"],
    )
    op.create_index(
        "ix_contrato_tarea_apartado_id",
        "contrato",
        ["tarea_apartado_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_contrato_tarea_apartado_id", table_name="contrato")
    op.drop_constraint("fk_contrato_tarea_apartado_id", "contrato", type_="foreignkey")
    op.drop_column("contrato", "tarea_apartado_id")
