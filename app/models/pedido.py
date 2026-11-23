"""Pedido de compra de serie 1. Una nave por pedido."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.nave import Nave
    from app.models.proyecto import Proyecto
    from app.models.tarea import Tarea


class Pedido(Base):
    __tablename__ = "pedido"

    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("proyecto.id"), nullable=False, index=True)
    nave_id: Mapped[int] = mapped_column(ForeignKey("nave.id"), nullable=False, unique=True)
    numero: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    rotulo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fichero_origen: Mapped[str] = mapped_column(String(512), nullable=False)
    ruta_almacen: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    estado_revision: Mapped[str] = mapped_column(String(50), nullable=False)
    aviso: Mapped[str | None] = mapped_column(Text, nullable=True)

    proyecto: Mapped[Proyecto] = relationship()
    nave: Mapped[Nave] = relationship()
    tareas: Mapped[list[Tarea]] = relationship(back_populates="pedido")
