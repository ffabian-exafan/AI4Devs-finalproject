"""Fila inmutable de un gesto de persona."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ACCIONES = (
    "confirmar_revision",
    "confirmar_factura",
    "confirmar_importe_cliente",
    "confirmar_importes_cliente",
    "confirmar_solo_gestion",
    "borrar_proyecto",
    "borrar_contrato",
    "borrar_factura",
    "borrar_linea",
    "inicio_sesion",
    "marcar_isp",
    "quitar_isp",
)


class RegistroAccion(Base):
    __tablename__ = "registro_accion"
    __table_args__ = (
        CheckConstraint(
            "accion IN (" + ", ".join(f"'{codigo}'" for codigo in ACCIONES) + ")",
            name="registro_accion_codigo",
        ),
        CheckConstraint(
            "("
            "accion = 'inicio_sesion' "
            "AND tipo_documento IS NULL "
            "AND documento_id IS NULL "
            "AND etiqueta IS NULL"
            ") OR ("
            "accion <> 'inicio_sesion' "
            "AND tipo_documento IS NOT NULL "
            "AND documento_id IS NOT NULL "
            "AND etiqueta IS NOT NULL"
            ")",
            name="registro_accion_documento",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nombre_en_el_momento: Mapped[str] = mapped_column(String(255), nullable=False)
    accion: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    tipo_documento: Mapped[str | None] = mapped_column(String(32), nullable=True)
    documento_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etiqueta: Mapped[str | None] = mapped_column(String(255), nullable=True)