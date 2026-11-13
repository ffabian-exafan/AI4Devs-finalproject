"""Un contrato de subcontrata puede enlazar varios apartados.

Revision ID: 0010_contrato_varios_apartados
Revises: 0009_solo_gestion
Create Date: 2026-11-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_contrato_varios_apartados"
down_revision: Union[str, Sequence[str], None] = "0009_solo_gestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contrato_apartado",
        sa.Column("contrato_id", sa.Integer(), nullable=False),
        sa.Column("tarea_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contrato_id"],
            ["contrato.id"],
            name="fk_contrato_apartado_contrato_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tarea_id"],
            ["tarea.id"],
            name="fk_contrato_apartado_tarea_id",
        ),
        sa.PrimaryKeyConstraint("contrato_id", "tarea_id"),
    )
    op.create_index(
        "ix_contrato_apartado_tarea_id",
        "contrato_apartado",
        ["tarea_id"],
    )
    op.execute(
        """
        INSERT INTO contrato_apartado (contrato_id, tarea_id)
        SELECT id, tarea_apartado_id
        FROM contrato
        WHERE tarea_apartado_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_contrato_apartado_tarea_id", table_name="contrato_apartado")
    op.drop_table("contrato_apartado")
