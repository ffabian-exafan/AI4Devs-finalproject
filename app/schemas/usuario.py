"""Schemas de usuario."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# jefe_obra | administracion | direccion | superadministrador — docs/readme.md, entidad USUARIO
ROLES = ("jefe_obra", "administracion", "direccion", "superadministrador")


def _email_normalizado(valor: str) -> str:
    return valor.strip().lower()


def _rol_conocido(valor: str) -> str:
    if valor not in ROLES:
        raise ValueError(
            "El rol tiene que ser jefe de obra, administración, dirección o superadministrador."
        )
    return valor


class UsuarioCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    email: EmailStr
    rol: str = Field(min_length=1, max_length=50)
    # [VERIFICAR] El readme no fija la longitud mínima. Ocho caracteres para no guardar claves vacías.
    password: str = Field(min_length=8, max_length=255)

    @field_validator("nombre")
    @classmethod
    def nombre_limpio(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre no puede estar vacío.")
        return limpio

    @field_validator("email")
    @classmethod
    def email_minusculas(cls, valor: str) -> str:
        return _email_normalizado(valor)

    @field_validator("rol")
    @classmethod
    def rol_valido(cls, valor: str) -> str:
        return _rol_conocido(valor)


class UsuarioUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    rol: str | None = Field(default=None, min_length=1, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=255)

    @field_validator("nombre")
    @classmethod
    def nombre_limpio(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre no puede estar vacío.")
        return limpio

    @field_validator("email")
    @classmethod
    def email_minusculas(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        return _email_normalizado(valor)

    @field_validator("rol")
    @classmethod
    def rol_valido(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        return _rol_conocido(valor)


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: EmailStr
    rol: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def email_minusculas(cls, valor: str) -> str:
        return _email_normalizado(valor)
