"""Presupuesto (PDF de origen y su versión)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.proyecto import Proyecto
    from app.models.tarea import Tarea


class Presupuesto(Base):
    __tablename__ = "presupuesto"

    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(
        ForeignKey("proyecto.id"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    fichero_origen: Mapped[str] = mapped_column(String(512), nullable=False)
    # Ruta relativa bajo UPLOADS_DIR. Null en filas anteriores a guardar el fichero.
    ruta_almacen: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    fecha: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado_extraccion: Mapped[str] = mapped_column(String(50), nullable=False)
    # True si el origen fue imagen o PDF sin texto (pasó por OCR)
    es_escaneado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # excel_expertis | pdf_cliente. Las filas anteriores al Excel son pdf_cliente.
    formato: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pdf_cliente",
        server_default="pdf_cliente",
    )

    proyecto: Mapped[Proyecto] = relationship(back_populates="presupuestos")
    tareas: Mapped[list[Tarea]] = relationship(back_populates="presupuesto")
