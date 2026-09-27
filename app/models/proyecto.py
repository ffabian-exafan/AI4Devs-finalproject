"""Proyecto de obra."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.contrato import Contrato
    from app.models.factura import Factura
    from app.models.nave import Nave
    from app.models.presupuesto import Presupuesto


class Proyecto(Base):
    __tablename__ = "proyecto"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    # llave_en_mano | reforma
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    fecha_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(String(50), nullable=False)
    # Cabecera de la lista de obras (handoff). Null en proyectos anteriores.
    codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cliente: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ubicacion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # porcino | avicola | bovino
    especie: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Presupuesto | Contratos | Ejecución | Cierre
    fase: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    naves: Mapped[list[Nave]] = relationship(back_populates="proyecto")
    presupuestos: Mapped[list[Presupuesto]] = relationship(back_populates="proyecto")
    contratos: Mapped[list[Contrato]] = relationship(back_populates="proyecto")
    facturas: Mapped[list[Factura]] = relationship(back_populates="proyecto")
