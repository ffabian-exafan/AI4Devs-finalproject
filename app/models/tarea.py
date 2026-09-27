"""Tarea jerárquica (apartado > subapartado > partida) vía tarea_padre_id."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.asignacion import Asignacion
    from app.models.contratista import Contratista
    from app.models.contrato import Contrato
    from app.models.nave import Nave
    from app.models.presupuesto import Presupuesto


class Tarea(Base):
    __tablename__ = "tarea"

    id: Mapped[int] = mapped_column(primary_key=True)
    nave_id: Mapped[int] = mapped_column(
        ForeignKey("nave.id"),
        nullable=False,
        index=True,
    )
    # Origen si viene del presupuesto
    presupuesto_id: Mapped[int | None] = mapped_column(
        ForeignKey("presupuesto.id"),
        nullable=True,
        index=True,
    )
    # Origen si viene de un contrato de subcontrata
    contrato_id: Mapped[int | None] = mapped_column(
        ForeignKey("contrato.id"),
        nullable=True,
        index=True,
    )
    # Autorreferencia: apartado > subapartado > partida
    tarea_padre_id: Mapped[int | None] = mapped_column(
        ForeignKey("tarea.id"),
        nullable=True,
        index=True,
    )
    contratista_id: Mapped[int | None] = mapped_column(
        ForeignKey("contratista.id"),
        nullable=True,
        index=True,
    )
    # Admite numeración anidada, ej. 4.3.1
    codigo: Mapped[str] = mapped_column(String(50), nullable=False)
    # apartado | subapartado | partida
    nivel: Mapped[str] = mapped_column(String(50), nullable=False)
    capitulo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable: un apartado puede no tener desglose con precio unitario
    unidad: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cantidad: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    precio_unitario: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    importe_presupuestado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Fuerza estado_revision = pendiente cuando es true
    tiene_anotacion_manual: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Duda de lectura en la partida: "Medición" | "Unidad". Null si no hay duda.
    marca_duda: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # pendiente | revisada | confirmada
    estado_revision: Mapped[str] = mapped_column(String(50), nullable=False)
    # no_iniciada | en_curso | finalizada (avance administrativo, no físico)
    estado: Mapped[str] = mapped_column(String(50), nullable=False)
    avance_fisico_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0"),
    )

    nave: Mapped[Nave] = relationship(back_populates="tareas")
    presupuesto: Mapped[Presupuesto | None] = relationship(back_populates="tareas")
    contrato: Mapped[Contrato | None] = relationship(
        back_populates="tareas",
        foreign_keys=[contrato_id],
    )
    contratista: Mapped[Contratista | None] = relationship(back_populates="tareas")
    padre: Mapped[Tarea | None] = relationship(
        back_populates="hijos",
        remote_side="Tarea.id",
    )
    hijos: Mapped[list[Tarea]] = relationship(back_populates="padre")
    asignaciones: Mapped[list[Asignacion]] = relationship(back_populates="tarea")
    # Contratos que enlazan este apartado de presupuesto (vía CONTRATO.tarea_apartado_id)
    contratos_como_apartado: Mapped[list[Contrato]] = relationship(
        back_populates="tarea_apartado",
        foreign_keys="Contrato.tarea_apartado_id",
    )