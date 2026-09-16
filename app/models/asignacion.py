"""Asignación: reparto de importe de factura a nave o tarea."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.factura import Factura
    from app.models.nave import Nave
    from app.models.tarea import Tarea
    from app.models.usuario import Usuario


class Asignacion(Base):
    __tablename__ = "asignacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_id: Mapped[int] = mapped_column(
        ForeignKey("factura.id"),
        nullable=False,
        index=True,
    )
    tarea_id: Mapped[int | None] = mapped_column(
        ForeignKey("tarea.id"),
        nullable=True,
        index=True,
    )
    nave_id: Mapped[int | None] = mapped_column(
        ForeignKey("nave.id"),
        nullable=True,
        index=True,
    )
    importe_asignado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # manual | regla | trigram | vector | estimacion_proporcional
    metodo: Mapped[str] = mapped_column(String(50), nullable=False)
    es_estimacion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confianza: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    revisado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id"),
        nullable=True,
        index=True,
    )

    factura: Mapped[Factura] = relationship(back_populates="asignaciones")
    tarea: Mapped[Tarea | None] = relationship(back_populates="asignaciones")
    nave: Mapped[Nave | None] = relationship(back_populates="asignaciones")
    revisor: Mapped[Usuario | None] = relationship(back_populates="asignaciones_revisadas")
