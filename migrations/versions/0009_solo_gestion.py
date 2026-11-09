"""Apartado de solo gestión a partir de una línea del PDF del cliente.

Revision ID: 0009_solo_gestion
Revises: 0008_propuesta_contraste
Create Date: 2026-11-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_solo_gestion"
down_revision: Union[str, Sequence[str], None] = "0008_propuesta_contraste"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tarea",
        sa.Column(
            "solo_gestion",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "linea_pdf_cliente",
        sa.Column("apartado_gestion_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_linea_pdf_cliente_apartado_gestion",
        "linea_pdf_cliente",
        "tarea",
        ["apartado_gestion_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_linea_pdf_cliente_apartado_gestion",
        "linea_pdf_cliente",
        ["apartado_gestion_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_linea_pdf_cliente_apartado_gestion",
        "linea_pdf_cliente",
        type_="unique",
    )
    op.drop_constraint(
        "fk_linea_pdf_cliente_apartado_gestion",
        "linea_pdf_cliente",
        type_="foreignkey",
    )
    op.drop_column("linea_pdf_cliente", "apartado_gestion_id")
    op.drop_column("tarea", "solo_gestion")
