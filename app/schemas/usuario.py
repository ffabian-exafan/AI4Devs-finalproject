"""Schemas de usuario."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UsuarioCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    email: EmailStr
    # jefe_obra | administracion | direccion
    rol: str = Field(min_length=1, max_length=50)
    # El hash se calcula en services/; aquí solo llega la contraseña en claro
    password: str = Field(min_length=1, max_length=255)


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: EmailStr
    rol: str
