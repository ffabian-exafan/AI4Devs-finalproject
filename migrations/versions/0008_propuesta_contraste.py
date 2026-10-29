"""Propuesta de relación entre la línea del PDF y el bloque del Excel.

Revision ID: 0008_propuesta_contraste
Revises: 0007_linea_pdf_cliente
Create Date: 2026-10-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_propuesta_contraste"
down_revision: Union[str, Sequence[str], None] = "0007_linea_pdf_cliente"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "linea_pdf_cliente",
        sa.Column(
            "relacion_intentada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "linea_pdf_cliente_tarea",
        sa.Column(
            "es_sugerencia",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("linea_pdf_cliente_tarea", "es_sugerencia")
    op.drop_column("linea_pdf_cliente", "relacion_intentada")
