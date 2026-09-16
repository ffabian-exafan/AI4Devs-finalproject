"""Esquema inicial: tablas del modelo de obra + extensiones vector y pg_trgm.

Revision ID: 0001_esquema_inicial
Revises:
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001_esquema_inicial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# [VERIFICAR] dimensión del embedding según el modelo que autorice Seguridad
EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("rol", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "proyecto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("estado", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "contratista",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nif", sa.String(length=20), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Índice único por nif (clave de enlace con facturas)
    op.create_index("ix_contratista_nif", "contratista", ["nif"], unique=True)

    op.create_table(
        "presupuesto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proyecto_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fichero_origen", sa.String(length=512), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=True),
        sa.Column("estado_extraccion", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["proyecto_id"], ["proyecto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_presupuesto_proyecto_id", "presupuesto", ["proyecto_id"])

    op.create_table(
        "nave",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proyecto_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("descripcion", sa.String(length=512), nullable=False),
        sa.Column("importe_presupuestado", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["proyecto_id"], ["proyecto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nave_proyecto_id", "nave", ["proyecto_id"])

    op.create_table(
        "contrato",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proyecto_id", sa.Integer(), nullable=False),
        sa.Column("nave_id", sa.Integer(), nullable=True),
        sa.Column("contratista_id", sa.Integer(), nullable=False),
        sa.Column("referencia_presupuesto", sa.String(length=255), nullable=True),
        sa.Column("precio_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("fecha_firma", sa.Date(), nullable=True),
        sa.Column("plazo_ejecucion", sa.Date(), nullable=True),
        sa.Column("condiciones_facturacion", sa.Text(), nullable=True),
        sa.Column("fichero_origen", sa.String(length=512), nullable=False),
        sa.Column("estado_extraccion", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["contratista_id"], ["contratista.id"]),
        sa.ForeignKeyConstraint(["nave_id"], ["nave.id"]),
        sa.ForeignKeyConstraint(["proyecto_id"], ["proyecto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contrato_proyecto_id", "contrato", ["proyecto_id"])
    op.create_index("ix_contrato_nave_id", "contrato", ["nave_id"])
    op.create_index("ix_contrato_contratista_id", "contrato", ["contratista_id"])

    op.create_table(
        "tarea",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nave_id", sa.Integer(), nullable=False),
        sa.Column("presupuesto_id", sa.Integer(), nullable=True),
        sa.Column("contrato_id", sa.Integer(), nullable=True),
        sa.Column("tarea_padre_id", sa.Integer(), nullable=True),
        sa.Column("contratista_id", sa.Integer(), nullable=True),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("nivel", sa.String(length=50), nullable=False),
        sa.Column("capitulo", sa.String(length=255), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("unidad", sa.String(length=50), nullable=True),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=True),
        sa.Column("precio_unitario", sa.Numeric(14, 4), nullable=True),
        sa.Column("importe_presupuestado", sa.Numeric(14, 2), nullable=False),
        sa.Column("tiene_anotacion_manual", sa.Boolean(), nullable=False),
        sa.Column("estado_revision", sa.String(length=50), nullable=False),
        sa.Column("estado", sa.String(length=50), nullable=False),
        sa.Column("avance_fisico_pct", sa.Numeric(5, 2), nullable=False),
        sa.ForeignKeyConstraint(["contratista_id"], ["contratista.id"]),
        sa.ForeignKeyConstraint(["contrato_id"], ["contrato.id"]),
        sa.ForeignKeyConstraint(["nave_id"], ["nave.id"]),
        sa.ForeignKeyConstraint(["presupuesto_id"], ["presupuesto.id"]),
        sa.ForeignKeyConstraint(["tarea_padre_id"], ["tarea.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tarea_nave_id", "tarea", ["nave_id"])
    op.create_index("ix_tarea_presupuesto_id", "tarea", ["presupuesto_id"])
    op.create_index("ix_tarea_contrato_id", "tarea", ["contrato_id"])
    op.create_index("ix_tarea_tarea_padre_id", "tarea", ["tarea_padre_id"])
    op.create_index("ix_tarea_contratista_id", "tarea", ["contratista_id"])

    op.create_table(
        "factura",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proyecto_id", sa.Integer(), nullable=True),
        sa.Column("contratista_id", sa.Integer(), nullable=False),
        sa.Column("contrato_id", sa.Integer(), nullable=True),
        sa.Column("numero", sa.String(length=100), nullable=False),
        sa.Column("fecha_emision", sa.Date(), nullable=True),
        sa.Column("base_imponible", sa.Numeric(14, 2), nullable=False),
        sa.Column("iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("irpf", sa.Numeric(14, 2), nullable=False),
        sa.Column("retencion_garantia", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("fichero_origen", sa.String(length=512), nullable=False),
        sa.Column("es_escaneada", sa.Boolean(), nullable=False),
        sa.Column("estado_revision", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["contratista_id"], ["contratista.id"]),
        sa.ForeignKeyConstraint(["contrato_id"], ["contrato.id"]),
        sa.ForeignKeyConstraint(["proyecto_id"], ["proyecto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_factura_proyecto_id", "factura", ["proyecto_id"])
    op.create_index("ix_factura_contratista_id", "factura", ["contratista_id"])
    op.create_index("ix_factura_contrato_id", "factura", ["contrato_id"])

    op.create_table(
        "linea_factura",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("factura_id", sa.Integer(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("importe", sa.Numeric(14, 2), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.ForeignKeyConstraint(["factura_id"], ["factura.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_linea_factura_factura_id", "linea_factura", ["factura_id"])

    op.create_table(
        "asignacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("factura_id", sa.Integer(), nullable=False),
        sa.Column("tarea_id", sa.Integer(), nullable=True),
        sa.Column("nave_id", sa.Integer(), nullable=True),
        sa.Column("importe_asignado", sa.Numeric(14, 2), nullable=False),
        sa.Column("metodo", sa.String(length=50), nullable=False),
        sa.Column("es_estimacion", sa.Boolean(), nullable=False),
        sa.Column("confianza", sa.Numeric(5, 4), nullable=True),
        sa.Column("revisado_por", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["factura_id"], ["factura.id"]),
        sa.ForeignKeyConstraint(["nave_id"], ["nave.id"]),
        sa.ForeignKeyConstraint(["revisado_por"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["tarea_id"], ["tarea.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asignacion_factura_id", "asignacion", ["factura_id"])
    op.create_index("ix_asignacion_tarea_id", "asignacion", ["tarea_id"])
    op.create_index("ix_asignacion_nave_id", "asignacion", ["nave_id"])
    op.create_index("ix_asignacion_revisado_por", "asignacion", ["revisado_por"])


def downgrade() -> None:
    op.drop_index("ix_asignacion_revisado_por", table_name="asignacion")
    op.drop_index("ix_asignacion_nave_id", table_name="asignacion")
    op.drop_index("ix_asignacion_tarea_id", table_name="asignacion")
    op.drop_index("ix_asignacion_factura_id", table_name="asignacion")
    op.drop_table("asignacion")

    op.drop_index("ix_linea_factura_factura_id", table_name="linea_factura")
    op.drop_table("linea_factura")

    op.drop_index("ix_factura_contrato_id", table_name="factura")
    op.drop_index("ix_factura_contratista_id", table_name="factura")
    op.drop_index("ix_factura_proyecto_id", table_name="factura")
    op.drop_table("factura")

    op.drop_index("ix_tarea_contratista_id", table_name="tarea")
    op.drop_index("ix_tarea_tarea_padre_id", table_name="tarea")
    op.drop_index("ix_tarea_contrato_id", table_name="tarea")
    op.drop_index("ix_tarea_presupuesto_id", table_name="tarea")
    op.drop_index("ix_tarea_nave_id", table_name="tarea")
    op.drop_table("tarea")

    op.drop_index("ix_contrato_contratista_id", table_name="contrato")
    op.drop_index("ix_contrato_nave_id", table_name="contrato")
    op.drop_index("ix_contrato_proyecto_id", table_name="contrato")
    op.drop_table("contrato")

    op.drop_index("ix_nave_proyecto_id", table_name="nave")
    op.drop_table("nave")

    op.drop_index("ix_presupuesto_proyecto_id", table_name="presupuesto")
    op.drop_table("presupuesto")

    op.drop_index("ix_contratista_nif", table_name="contratista")
    op.drop_table("contratista")

    op.drop_table("proyecto")
    op.drop_table("usuario")

    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
