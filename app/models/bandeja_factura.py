"""Fichero leído de la unidad de red, antes de ser una factura de una obra.

La unidad de red no se modifica. La copia vive en uploads/bandeja.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BandejaFactura(Base):
    __tablename__ = "bandeja_factura"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identidad del contenido. El nombre y la ruta pueden cambiar.
    hash_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    ruta_red: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    nombre_fichero: Mapped[str] = mapped_column(String(512), nullable=False)
    tamano: Mapped[int] = mapped_column(Integer, nullable=False)
    modificado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 1-12 si la carpeta padre es un mes. Null si está en la raíz u otra carpeta.
    mes_carpeta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    es_escaneada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # leida | error
    estado: Mapped[str] = mapped_column(String(50), nullable=False)
    # True: el siguiente barrido vuelve a leer este fichero (OCR caído, PDF a medias).
    reintentar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    aviso: Mapped[str | None] = mapped_column(Text, nullable=True)
    aviso_mes: Mapped[str | None] = mapped_column(Text, nullable=True)
    aviso_codigo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ruta_copia: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    nif_detectado: Mapped[str | None] = mapped_column(String(32), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    base_imponible: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    iva: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    irpf: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    retencion_garantia: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Código leído del PDF. El enlace con el contrato se hace después, en la obra.
    codigo_contrato: Mapped[str | None] = mapped_column(String(16), nullable=True)
    factura_id: Mapped[int | None] = mapped_column(
        ForeignKey("factura.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    leido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BarridoFactura(Base):
    __tablename__ = "barrido_factura"

    id: Mapped[int] = mapped_column(primary_key=True)
    iniciado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    terminado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nuevos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ya_vistos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    omitidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errores: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aviso: Mapped[str | None] = mapped_column(Text, nullable=True)
