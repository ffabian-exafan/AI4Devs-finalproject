"""Línea del PDF del cliente en un apartado manual del contrato.

Revision ID: 0012_linea_pdf_contrato
Revises: 0011_explica_apartado
Create Date: 2026-11-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_linea_pdf_contrato"
down_revision: Union[str, Sequence[str], None] = "0011_explica_apartado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tarea",
        sa.Column("linea_pdf_cliente_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_tarea_linea_pdf_cliente_id",
        "tarea",
        ["linea_pdf_cliente_id"],
    )
    op.create_foreign_key(
        "fk_tarea_linea_pdf_cliente_id",
        "tarea",
        "linea_pdf_cliente",
        ["linea_pdf_cliente_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tarea_linea_pdf_cliente_id", "tarea", type_="foreignkey")
    op.drop_index("ix_tarea_linea_pdf_cliente_id", table_name="tarea")
    op.drop_column("tarea", "linea_pdf_cliente_id")
