"""Salida del barrido y de la bandeja de facturas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BandejaFacturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_fichero: str
    mes_carpeta: int | None
    estado: str
    aviso: str | None
    aviso_mes: str | None
    aviso_codigo: str | None
    es_escaneada: bool
    nif_detectado: str | None
    numero: str | None
    fecha_emision: date | None
    total: Decimal | None
    codigo_contrato: str | None
    factura_id: int | None
    leido_en: datetime


class BarridoOut(BaseModel):
    nuevos: int
    ya_vistos: int
    omitidos: int
    errores: int
    aviso: str | None = None
