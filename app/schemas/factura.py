"""Schemas de factura, líneas e ingesta."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.tipos import Money


class LineaFacturaCreate(BaseModel):
    descripcion: str = Field(min_length=1)
    importe: Money
    # embedding lo calcula el servicio de casado; no entra por API


class LineaFacturaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    factura_id: int
    descripcion: str
    importe: Money
    # embedding omitido a propósito: uso interno del casado semántico


class FacturaCreate(BaseModel):
    proyecto_id: int | None = None
    contratista_id: int
    contrato_id: int | None = None
    numero: str = Field(min_length=1, max_length=100)
    fecha_emision: date | None = None
    base_imponible: Money
    iva: Money
    irpf: Money = Decimal("0")
    retencion_garantia: Money = Decimal("0")
    total: Money
    # ordinaria | anticipo | certificacion
    tipo: str = Field(min_length=1, max_length=50)
    fichero_origen: str = Field(min_length=1, max_length=512)
    es_escaneada: bool = False
    # pendiente | revisada | confirmada
    estado_revision: str = Field(min_length=1, max_length=50)
    lineas: list[LineaFacturaCreate] = Field(default_factory=list)


class FacturaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proyecto_id: int | None
    contratista_id: int
    contrato_id: int | None
    numero: str
    fecha_emision: date | None
    base_imponible: Money
    iva: Money
    irpf: Money
    retencion_garantia: Money
    total: Money
    tipo: str
    fichero_origen: str
    es_escaneada: bool
    estado_revision: str
    lineas: list[LineaFacturaRead] = Field(default_factory=list)


class FacturaImportacionOut(BaseModel):
    """Respuesta de POST /facturas."""

    factura_id: int
    contratista_nif: str
    contrato_id: int | None
    estado_revision: str
    requiere_revision: bool = True


class ContratoCandidatoFacturaOut(BaseModel):
    id: int
    contratista_nombre: str
    precio_total: Money


class FacturaResumenOut(BaseModel):
    id: int
    proyecto_id: int
    numero: str
    fecha_emision: date | None
    contratista_nombre: str
    contratista_nif: str
    contrato_id: int | None
    total: Money
    tipo: str
    es_escaneada: bool
    estado_revision: str


class FacturaRevisionOut(FacturaResumenOut):
    base_imponible: Money
    iva: Money
    irpf: Money
    retencion_garantia: Money
    fichero_origen: str
    lineas: list[LineaFacturaRead] = Field(default_factory=list)
    contratos_candidatos: list[ContratoCandidatoFacturaOut] = Field(
        default_factory=list
    )


class LineaFacturaRevisionIn(BaseModel):
    id: int | None = None
    descripcion: str = Field(min_length=1)
    importe: Money


class ConfirmarFacturaIn(BaseModel):
    numero: str = Field(min_length=1, max_length=100)
    fecha_emision: date | None = None
    base_imponible: Money
    iva: Money
    irpf: Money = Decimal("0")
    retencion_garantia: Money = Decimal("0")
    total: Money
    tipo: str = Field(pattern="^(ordinaria|anticipo|certificacion)$")
    contrato_id: int | None = Field(default=None, ge=1)
    lineas: list[LineaFacturaRevisionIn] = Field(default_factory=list)

    @field_validator("numero")
    @classmethod
    def numero_no_vacio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El número de factura no puede estar vacío")
        return value


class ConfirmarFacturaOut(BaseModel):
    ok: bool
    factura_id: int
    proyecto_id: int
    contrato_id: int | None
    estado_revision: str
