"""Schemas de proyecto."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.casado import SugerenciaApartadoOut
from app.schemas.presupuesto import ContrastarClienteOut
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
    # Suma de apartados raíz del presupuesto (los descuentos de cierre restan).
    presupuestado: Money = Decimal("0")
    # Solo facturas con estado_revision confirmada.
    facturado: Money = Decimal("0")


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
    unidad: str | None = None
    cantidad: Money | None = None
    precio_unitario: Money | None = None
    descuento_pct: Money | None = None
    es_montaje: bool = False
    importe_montaje: Money = Decimal("0")
    capitulo: str | None = None
    importe_contrato_cliente: Money | None = None
    nave_id: int
    nave_codigo: str
    estado_revision: str
    contrato_enlazado_id: int | None = None
    contratos: list[ContratoApartadoOut] = Field(default_factory=list)
    subapartados: list["ApartadoResumenOut"] = Field(default_factory=list)


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
    fichero_origen: str = ""
    tiene_fichero: bool = False
    sugerencias: list[SugerenciaApartadoOut] = Field(default_factory=list)


class DocumentoProyectoOut(BaseModel):
    """Fichero de presupuesto guardado (Excel o PDF del cliente)."""

    id: int
    fichero_origen: str
    formato: str
    tiene_fichero: bool = False


class ProyectoDetalleOut(ProyectoRead):
    """Proyecto con naves, apartados de presupuesto y contratos."""

    naves: list[NaveResumenOut] = Field(default_factory=list)
    apartados: list[ApartadoResumenOut] = Field(default_factory=list)
    contratos: list[ContratoResumenOut] = Field(default_factory=list)
    documentos: list[DocumentoProyectoOut] = Field(default_factory=list)
    # Null si el PDF aún no se ha leído a líneas. El fichero sigue en documentos.
    contraste_cliente: ContrastarClienteOut | None = None
