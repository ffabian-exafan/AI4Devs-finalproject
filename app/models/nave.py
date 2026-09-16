"""Nave (unidad de desglose del presupuesto)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.asignacion import Asignacion
    from app.models.contrato import Contrato
    from app.models.proyecto import Proyecto
    from app.models.tarea import Tarea


class Nave(Base):
    __tablename__ = "nave"

    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(
        ForeignKey("proyecto.id"),
        nullable=False,
        index=True,
    )
    codigo: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(512), nullable=False)
    importe_presupuestado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    proyecto: Mapped[Proyecto] = relationship(back_populates="naves")
    tareas: Mapped[list[Tarea]] = relationship(back_populates="nave")
    contratos: Mapped[list[Contrato]] = relationship(back_populates="nave")
    asignaciones: Mapped[list[Asignacion]] = relationship(back_populates="nave")
