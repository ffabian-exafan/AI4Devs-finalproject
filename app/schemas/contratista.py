"""Schemas de contratista."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ContratistaCreate(BaseModel):
    nif: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=255)
    # interno | externo
    tipo: str = Field(min_length=1, max_length=50)
    email: EmailStr | None = None


class ContratistaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nif: str
    nombre: str
    tipo: str
    email: EmailStr | None
