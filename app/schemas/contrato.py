"""Schemas de contrato e ingesta de contrato de subcontrata."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.casado import SugerenciaApartadoOut
from app.schemas.tipos import Money


class ContratoCreate(BaseModel):
    proyecto_id: int
    nave_id: int | None = None
    contratista_id: int
    referencia_presupuesto: str | None = Field(default=None, max_length=255)
    tarea_apartado_id: int | None = None
    precio_total: Money
    fecha_firma: date | None = None
    plazo_ejecucion: date | None = None
    condiciones_facturacion: str | None = None
    fichero_origen: str = Field(min_length=1, max_length=512)
    estado_extraccion: str = Field(min_length=1, max_length=50)


class ContratoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proyecto_id: int
    nave_id: int | None
    contratista_id: int
    referencia_presupuesto: str | None
    tarea_apartado_id: int | None = None
    precio_total: Money
    fecha_firma: date | None
    plazo_ejecucion: date | None
    condiciones_facturacion: str | None
    fichero_origen: str
    estado_extraccion: str


class ImportarContratoOut(BaseModel):
    """Respuesta de POST /proyectos/{id}/importar-contrato."""

    contrato_id: int
    contratista_nif: str
    precio_total: Money
    partidas_detalle_detectadas: int
    requiere_revision: bool
    sugerencias_apartado: list[SugerenciaApartadoOut] = Field(default_factory=list)
