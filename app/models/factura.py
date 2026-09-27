"""Factura y líneas de detalle (embedding para casado semántico)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# [VERIFICAR] dimensión del embedding según el modelo que autorice Seguridad
EMBEDDING_DIM = 1536

if TYPE_CHECKING:
    from app.models.asignacion import Asignacion
    from app.models.contratista import Contratista
    from app.models.contrato import Contrato
    from app.models.proyecto import Proyecto


class Factura(Base):
    __tablename__ = "factura"

    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int | None] = mapped_column(
        ForeignKey("proyecto.id"),
        nullable=True,
        index=True,
    )
    contratista_id: Mapped[int] = mapped_column(
        ForeignKey("contratista.id"),
        nullable=False,
        index=True,
    )
    # Si la factura certifica un contrato concreto
    contrato_id: Mapped[int | None] = mapped_column(
        ForeignKey("contrato.id"),
        nullable=True,
        index=True,
    )
    numero: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    base_imponible: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    irpf: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0")
    )
    retencion_garantia: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0"),
    )
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # ordinaria | anticipo | certificacion
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    fichero_origen: Mapped[str] = mapped_column(String(512), nullable=False)
    es_escaneada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # pendiente | revisada | confirmada
    estado_revision: Mapped[str] = mapped_column(String(50), nullable=False)
    # Reclamada | Desviación aprobada | Descartada | Validada. Null si sigue abierta.
    resolucion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Otra factura ya recibida con el mismo proveedor, número e importe.
    duplicado_de_id: Mapped[int | None] = mapped_column(
        ForeignKey("factura.id"),
        nullable=True,
    )

    proyecto: Mapped[Proyecto | None] = relationship(back_populates="facturas")
    contratista: Mapped[Contratista] = relationship(back_populates="facturas")
    contrato: Mapped[Contrato | None] = relationship(back_populates="facturas")
    lineas: Mapped[list[LineaFactura]] = relationship(back_populates="factura")
    asignaciones: Mapped[list[Asignacion]] = relationship(back_populates="factura")


class LineaFactura(Base):
    __tablename__ = "linea_factura"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_id: Mapped[int] = mapped_column(
        ForeignKey("factura.id"),
        nullable=False,
        index=True,
    )
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    importe: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Comparación partida a partida. Null si la factura no trae desglose.
    cantidad: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    precio_unitario: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    tarea_id: Mapped[int | None] = mapped_column(
        ForeignKey("tarea.id"),
        nullable=True,
        index=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )

    factura: Mapped[Factura] = relationship(back_populates="lineas")
