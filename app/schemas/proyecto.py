"""Schemas de proyecto."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.casado import SugerenciaApartadoOut
from app.schemas.tipos import Money


class ProyectoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    # llave_en_mano | reforma
    tipo: str = Field(min_length=1, max_length=50)
    fecha_inicio: date | None = None
    estado: str = Field(min_length=1, max_length=50)


class ProyectoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: str
    fecha_inicio: date | None
    estado: str
    created_at: datetime


class NaveResumenOut(BaseModel):
    """Nave ligera para selectores de UI (sin importes)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    descripcion: str


class ContratoApartadoOut(BaseModel):
    """Seguimiento económico de un contrato enlazado al apartado."""

    id: int
    contratista_nombre: str
    contratista_nif: str
    contratado: Money
    facturado: Money
    pendiente: Money
    porcentaje_facturado: Decimal


class ApartadoResumenOut(BaseModel):
    """Apartado de presupuesto en la lista del proyecto."""

    id: int
    codigo: str
    descripcion: str
    nivel: str
    importe_presupuestado: Money
    nave_id: int
    nave_codigo: str
    estado_revision: str
    contrato_enlazado_id: int | None = None
    contratos: list[ContratoApartadoOut] = Field(default_factory=list)


class ContratoResumenOut(BaseModel):
    """Contrato del proyecto con enlace o sugerencias."""

    id: int
    contratista_nombre: str
    contratista_nif: str
    precio_total: Money
    estado_extraccion: str
    nave_id: int | None = None
    tarea_apartado_id: int | None = None
    apartado_codigo: str | None = None
    apartado_descripcion: str | None = None
    sugerencias: list[SugerenciaApartadoOut] = Field(default_factory=list)


class ProyectoDetalleOut(ProyectoRead):
    """Proyecto con naves, apartados de presupuesto y contratos."""

    naves: list[NaveResumenOut] = Field(default_factory=list)
    apartados: list[ApartadoResumenOut] = Field(default_factory=list)
    contratos: list[ContratoResumenOut] = Field(default_factory=list)
