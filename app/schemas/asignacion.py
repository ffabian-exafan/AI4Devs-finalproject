"""Schemas de asignación (reparto factura → nave/tarea)."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tipos import Money


class AsignacionCreate(BaseModel):
    factura_id: int
    tarea_id: int | None = None
    nave_id: int | None = None
    importe_asignado: Money
    # manual | regla | trigram | vector | estimacion_proporcional
    metodo: str = Field(min_length=1, max_length=50)
    es_estimacion: bool = False
    confianza: Money | None = None
    revisado_por: int | None = None


class AsignacionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    factura_id: int
    tarea_id: int | None
    nave_id: int | None
    importe_asignado: Money
    metodo: str
    es_estimacion: bool
    confianza: Money | None
    revisado_por: int | None
