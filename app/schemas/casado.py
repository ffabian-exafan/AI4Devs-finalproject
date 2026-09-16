"""Schemas del casado contrato ↔ apartado (sugerencia y confirmación)."""

from decimal import Decimal

from pydantic import BaseModel, Field


class SugerenciaApartadoOut(BaseModel):
    """Candidato de apartado de presupuesto para un contrato (no persistido)."""

    tarea_id: int
    codigo: str
    descripcion: str
    confianza: Decimal = Field(ge=0, le=1)
    motivo: str


class EnlazarApartadoIn(BaseModel):
    """Body de POST .../enlazar-apartado. Validación Pydantic en backend."""

    tarea_apartado_id: int = Field(ge=1)


class EnlazarApartadoOut(BaseModel):
    contrato_id: int
    tarea_apartado_id: int
    codigo_apartado: str
    descripcion_apartado: str
