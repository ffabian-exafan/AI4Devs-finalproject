"""Entrada y salida de la mano de obra propia."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


def _decimales(valor: Decimal) -> int:
    exponente = valor.as_tuple().exponent
    if not isinstance(exponente, int):
        return 0
    return -exponente if exponente < 0 else 0


class PrecioHoraIn(BaseModel):
    precio_hora: Decimal

    @field_validator("precio_hora")
    @classmethod
    def positivo(cls, valor: Decimal) -> Decimal:
        if valor <= 0:
            raise ValueError("El precio por hora tiene que ser mayor que cero.")
        if _decimales(valor) > 4:
            raise ValueError("El precio por hora admite como mucho cuatro decimales.")
        return valor


class NombreLineaIn(BaseModel):
    nombre: str

    @field_validator("nombre")
    @classmethod
    def recortar(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre no puede estar vacío.")
        if len(limpio) > 255:
            raise ValueError("El nombre admite como mucho 255 caracteres.")
        return limpio


class ParteActualizarIn(BaseModel):
    horas: Decimal | None = None
    fecha: date | None = None

    @field_validator("horas")
    @classmethod
    def horas_ok(cls, valor: Decimal | None) -> Decimal | None:
        if valor is None:
            return None
        if valor <= 0:
            raise ValueError("Las horas tienen que ser mayores que cero.")
        if _decimales(valor) > 2:
            raise ValueError("Las horas admiten como mucho dos decimales.")
        return valor


class ParteManoObraOut(BaseModel):
    id: int
    archivo: str
    tiene_fichero: bool
    url_fichero: str | None
    horas: str | None
    fecha: str | None
    estado_revision: str
    es_escaneado: bool
    tiene_anotacion_manual: bool
    aviso: str | None
    precio_hora_aplicado: str | None
    importe: str | None


class LineaManoObraOut(BaseModel):
    id: int
    nombre: str
    horas: str
    acumulado: str
    partes: list[ParteManoObraOut] = Field(default_factory=list)


class ManoObraOut(BaseModel):
    precio_hora: str | None = None
    acumulado_horas: str = "0.00"
    acumulado: str = "0,00 €"
    lineas: list[LineaManoObraOut] = Field(default_factory=list)
