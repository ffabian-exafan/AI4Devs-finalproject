"""Consulta del registro."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.registro_accion import ACCIONES


class RegistroItem(BaseModel):
    id: int
    ocurrido_en: datetime
    dia_hora: str
    nombre: str
    accion: str
    accion_etiqueta: str
    tipo_documento: str | None
    documento_id: int | None
    etiqueta: str | None


class RegistroPagina(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[RegistroItem]


class RegistroFiltro(BaseModel):
    page: int = Field(default=1, ge=1)
    usuario_id: int | None = None
    accion: str | None = None
    tipo_documento: str | None = None
    dia: str | None = None

    @field_validator("accion")
    @classmethod
    def accion_conocida(cls, valor: str | None) -> str | None:
        if valor is not None and valor not in ACCIONES:
            raise ValueError("Acción desconocida")
        return valor

    @field_validator("tipo_documento")
    @classmethod
    def tipo_conocido(cls, valor: str | None) -> str | None:
        if valor is not None and valor not in {
            "presupuesto",
            "contrato",
            "factura",
            "proyecto",
            "tarea",
        }:
            raise ValueError("Tipo de documento desconocido")
        return valor
