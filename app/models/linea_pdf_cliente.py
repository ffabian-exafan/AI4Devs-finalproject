"""Líneas leídas del PDF firmado con el cliente, para contrastarlas después."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LineaPdfCliente(Base):
    __tablename__ = "linea_pdf_cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    presupuesto_id: Mapped[int] = mapped_column(
        ForeignKey("presupuesto.id"),
        nullable=False,
        index=True,
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    # importe | descuento
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    codigo: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    descripcion: Mapped[str] = mapped_column(String(512), nullable=False)
    importe: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    importe_bruto: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    es_manuscrito: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True cuando ya se pidió una propuesta de bloques, aunque no hubiera ninguna clara.
    relacion_intentada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class LineaPdfClienteTarea(Base):
    """Bloque del Excel para una línea del PDF.

    es_sugerencia es una propuesta del modelo. El importe no se escribe hasta que
    una persona confirma y el enlace pasa a es_sugerencia = false.
    """

    __tablename__ = "linea_pdf_cliente_tarea"

    linea_id: Mapped[int] = mapped_column(
        ForeignKey("linea_pdf_cliente.id"),
        primary_key=True,
    )
    tarea_id: Mapped[int] = mapped_column(ForeignKey("tarea.id"), primary_key=True)
    es_sugerencia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
