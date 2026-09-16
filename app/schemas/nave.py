"""Schemas de nave."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tipos import Money


class NaveCreate(BaseModel):
    proyecto_id: int
    codigo: str = Field(min_length=1, max_length=50)
    descripcion: str = Field(min_length=1, max_length=512)
    importe_presupuestado: Money


class NaveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proyecto_id: int
    codigo: str
    descripcion: str
    importe_presupuestado: Money
