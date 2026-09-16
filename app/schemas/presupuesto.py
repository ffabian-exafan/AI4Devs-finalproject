"""Schemas de presupuesto e ingesta de PDF."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PresupuestoCreate(BaseModel):
    proyecto_id: int
    version: int = Field(ge=1)
    fichero_origen: str = Field(min_length=1, max_length=512)
    fecha: date | None = None
    estado_extraccion: str = Field(min_length=1, max_length=50)
    es_escaneado: bool = False


class PresupuestoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proyecto_id: int
    version: int
    fichero_origen: str
    fecha: date | None
    estado_extraccion: str
    es_escaneado: bool = False


class ImportarPresupuestoOut(BaseModel):
    """Respuesta de POST /proyectos/importar-presupuesto."""

    proyecto_id: int
    naves_detectadas: int
    partidas_detectadas: int
    requiere_revision: bool
    anotaciones_manuscritas_detectadas: int
    es_escaneado: bool = False
