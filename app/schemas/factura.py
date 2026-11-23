"""Schemas de factura, líneas e ingesta."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.tipos import Money
from app.services.codigo_contrato import validar_codigo


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
    codigo_contrato: str | None = None
    aviso_codigo: str | None = None
    estado_revision: str
    requiere_revision: bool = True


class ContratoCandidatoFacturaOut(BaseModel):
    id: int
    contratista_nombre: str
    precio_total: Money
    codigo: str | None = None
    codigo_2: str | None = None


class EnlazarContratoFacturaIn(BaseModel):
    contrato_id: int = Field(ge=1)


class CodigoFacturaIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=16)

    @field_validator("codigo")
    @classmethod
    def formato(cls, value: str) -> str:
        return validar_codigo(value)


class CodigoFacturaOut(BaseModel):
    factura_id: int
    codigo_contrato: str
    contrato_id: int | None
    aviso_codigo: str | None = None


class FacturaResumenOut(BaseModel):
    id: int
    proyecto_id: int
    numero: str
    fecha_emision: date | None
    contratista_nombre: str
    contratista_nif: str
    contrato_id: int | None
    codigo_contrato: str | None = None
    aviso_codigo: str | None = None
    contrato_etiqueta: str | None = None
    total: Money
    base_imponible: Money
    tipo: str
    es_escaneada: bool
    estado_revision: str
    tiene_fichero: bool = False
    fichero_origen: str = ""
    aviso_isp: str | None = None
    referencia_alc: str | None = None
    tiene_sello: bool = False
    tiene_certificacion_montaje: bool = False
    certificacion_montaje_por: str | None = None
    certificacion_montaje_en: datetime | None = None
    certificacion_montaje_usuario_id: int | None = None
    certificacion_montaje_omitida: bool = False


class FacturaRevisionOut(FacturaResumenOut):
    base_imponible: Money
    iva: Money
    irpf: Money
    retencion_garantia: Money
    lineas: list[LineaFacturaRead] = Field(default_factory=list)
    contratos_candidatos: list[ContratoCandidatoFacturaOut] = Field(
        default_factory=list
    )
    inversion_sujeto_pasivo: bool = False


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
    codigo_contrato: str | None = Field(default=None, max_length=16)
    referencia_alc: str = Field(min_length=1, max_length=48)
    lineas: list[LineaFacturaRevisionIn] = Field(default_factory=list)

    @field_validator("referencia_alc")
    @classmethod
    def referencia_alc_limpia(cls, value: str) -> str:
        texto = " ".join(value.replace("\n", " ").replace("\r", " ").split())
        if texto.upper().startswith("ALC/"):
            texto = texto[4:].strip()
        if not texto:
            raise ValueError("Indica la referencia ALC")
        if len(texto) > 40:
            raise ValueError("La referencia ALC admite hasta 40 caracteres")
        return texto

    @field_validator("codigo_contrato")
    @classmethod
    def codigo_si_viene(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return validar_codigo(value)

    @field_validator("numero")
    @classmethod
    def numero_no_vacio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El número de factura no puede estar vacío")
        return value


class OmitirCertificacionOut(BaseModel):
    ok: bool
    factura_id: int
    certificacion_montaje_omitida: bool = True


class CertificarMontajeOut(BaseModel):
    ok: bool
    factura_id: int
    tiene_certificacion_montaje: bool = True
    certificacion_montaje_por: str


class ConfirmarFacturaOut(BaseModel):
    ok: bool
    factura_id: int
    proyecto_id: int
    contrato_id: int | None
    estado_revision: str
    tiene_sello: bool = False
