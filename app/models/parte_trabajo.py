"""Parte de trabajo de la mano de obra propia. Pendiente hasta que una persona confirma."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.linea_mano_obra import LineaManoObra


class ParteTrabajo(Base):
    __tablename__ = "parte_trabajo"
    __table_args__ = (
        CheckConstraint(
            "estado_revision IN ('pendiente', 'confirmada')",
            name="parte_trabajo_estado",
        ),
        CheckConstraint(
            "("
            "estado_revision = 'pendiente'"
            ") OR ("
            "estado_revision = 'confirmada' "
            "AND horas IS NOT NULL "
            "AND precio_hora_aplicado IS NOT NULL "
            "AND importe IS NOT NULL "
            "AND confirmada_en IS NOT NULL"
            ")",
            name="parte_trabajo_confirmado",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    linea_mano_obra_id: Mapped[int] = mapped_column(
        ForeignKey("linea_mano_obra.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fichero_origen: Mapped[str] = mapped_column(String(512), nullable=False)
    ruta_almacen: Mapped[str] = mapped_column(String(1024), nullable=False)
    es_escaneado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    horas: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fecha: Mapped[date | None] = mapped_column(Date, nullable=True)
    tiene_anotacion_manual: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    aviso: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_revision: Mapped[str] = mapped_column(String(50), nullable=False)
    precio_hora_aplicado: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    importe: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    confirmada_por: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    linea: Mapped[LineaManoObra] = relationship(back_populates="partes")
