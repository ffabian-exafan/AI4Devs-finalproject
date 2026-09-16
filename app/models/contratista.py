"""Contratista (interno o externo). nif único para enlace con facturas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.contrato import Contrato
    from app.models.factura import Factura
    from app.models.tarea import Tarea


class Contratista(Base):
    __tablename__ = "contratista"

    id: Mapped[int] = mapped_column(primary_key=True)
    nif: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    # interno | externo
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    tareas: Mapped[list[Tarea]] = relationship(back_populates="contratista")
    contratos: Mapped[list[Contrato]] = relationship(back_populates="contratista")
    facturas: Mapped[list[Factura]] = relationship(back_populates="contratista")
