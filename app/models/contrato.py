"""Contrato de ejecución con subcontratista (distinto de presupuesto y factura)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.contratista import Contratista
    from app.models.factura import Factura
    from app.models.nave import Nave
    from app.models.proyecto import Proyecto
    from app.models.tarea import Tarea


class Contrato(Base):
    __tablename__ = "contrato"

    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(
        ForeignKey("proyecto.id"),
        nullable=False,
        index=True,
    )
    # Nullable: un contrato puede cubrir más de una nave
    nave_id: Mapped[int | None] = mapped_column(
        ForeignKey("nave.id"),
        nullable=True,
        index=True,
    )
    contratista_id: Mapped[int] = mapped_column(
        ForeignKey("contratista.id"),
        nullable=False,
        index=True,
    )
    # Texto libre al nº de presupuesto
    referencia_presupuesto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Apartado de presupuesto enlazado tras sugerencia + confirmación humana
    tarea_apartado_id: Mapped[int | None] = mapped_column(
        ForeignKey("tarea.id"),
        nullable=True,
        index=True,
    )
    precio_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha_firma: Mapped[date | None] = mapped_column(Date, nullable=True)
    plazo_ejecucion: Mapped[date | None] = mapped_column(Date, nullable=True)
    condiciones_facturacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fichero_origen: Mapped[str] = mapped_column(String(512), nullable=False)
    estado_extraccion: Mapped[str] = mapped_column(String(50), nullable=False)
    # Sugerencia de la lectura: no confirma el enlace (eso es tarea_apartado_id).
    confianza: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motivo_sugerencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    aviso: Mapped[str | None] = mapped_column(Text, nullable=True)

    proyecto: Mapped[Proyecto] = relationship(back_populates="contratos")
    nave: Mapped[Nave | None] = relationship(back_populates="contratos")
    contratista: Mapped[Contratista] = relationship(back_populates="contratos")
    tarea_apartado: Mapped[Tarea | None] = relationship(
        back_populates="contratos_como_apartado",
        foreign_keys=[tarea_apartado_id],
    )
    tareas: Mapped[list[Tarea]] = relationship(
        back_populates="contrato",
        foreign_keys="Tarea.contrato_id",
    )
    facturas: Mapped[list[Factura]] = relationship(back_populates="contrato")
