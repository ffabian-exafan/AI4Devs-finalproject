"""Línea de mano de obra propia, añadida a mano. No es una tarea ni un contrato."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.parte_trabajo import ParteTrabajo
    from app.models.proyecto import Proyecto


class LineaManoObra(Base):
    __tablename__ = "linea_mano_obra"

    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(
        ForeignKey("proyecto.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    proyecto: Mapped[Proyecto] = relationship()
    partes: Mapped[list[ParteTrabajo]] = relationship(back_populates="linea")
