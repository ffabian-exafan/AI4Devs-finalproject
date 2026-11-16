"""Schemas del casado contrato ↔ apartado (sugerencia y confirmación)."""

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class ApartadoManualIn(BaseModel):
    """Nombre, importe y explicación sobre una línea del PDF del cliente que no está en el Excel."""

    linea_id: int = Field(ge=1)
    nombre: str
    importe: Decimal
    explicacion: str

    @model_validator(mode="after")
    def exigir_texto(self) -> "ApartadoManualIn":
        self.nombre = self.nombre.strip()
        self.explicacion = self.explicacion.strip()
        if len(self.nombre) < 2:
            raise ValueError("Indica el nombre del apartado")
        if len(self.explicacion) < 5:
            raise ValueError("La explicación del apartado es obligatoria")
        if self.importe <= 0:
            raise ValueError("El importe del apartado tiene que ser mayor que cero")
        self.importe = self.importe.quantize(Decimal("0.01"))
        return self


class ExplicacionEnlaceIn(BaseModel):
    """Explicación de un apartado del contrato que no está en el Excel."""

    tarea_id: int = Field(ge=1)
    explicacion: str

    @model_validator(mode="after")
    def exigir_texto(self) -> "ExplicacionEnlaceIn":
        self.explicacion = self.explicacion.strip()
        if len(self.explicacion) < 5:
            raise ValueError("La explicación del apartado es obligatoria")
        return self


class SugerenciaApartadoOut(BaseModel):
    """Candidato de apartado de presupuesto para un contrato (no persistido)."""

    tarea_id: int
    codigo: str
    descripcion: str
    confianza: Decimal = Field(ge=0, le=1)
    motivo: str


class EnlazarApartadoIn(BaseModel):
    """Body de POST .../enlazar-apartado. Validación Pydantic en backend.

    `tarea_apartado_ids` es el conjunto. `tarea_apartado_id` sigue valiendo
    para enlazar un solo apartado.
    """

    tarea_apartado_id: int | None = Field(default=None, ge=1)
    tarea_apartado_ids: list[int] = Field(default_factory=list)
    explicaciones: list[ExplicacionEnlaceIn] = Field(default_factory=list)
    apartados_nuevos: list[ApartadoManualIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def unir_ids(self) -> "EnlazarApartadoIn":
        ids: list[int] = []
        for raw in self.tarea_apartado_ids:
            if raw < 1:
                raise ValueError("El id de apartado tiene que ser positivo")
            if raw not in ids:
                ids.append(raw)
        if self.tarea_apartado_id is not None and self.tarea_apartado_id not in ids:
            ids.insert(0, self.tarea_apartado_id)
        if not ids and not self.apartados_nuevos:
            raise ValueError("Indica al menos un apartado")
        self.tarea_apartado_ids = ids
        self.tarea_apartado_id = ids[0] if ids else None
        return self


class ApartadoEnlazadoOut(BaseModel):
    tarea_apartado_id: int
    codigo_apartado: str
    descripcion_apartado: str


class EnlazarApartadoOut(BaseModel):
    contrato_id: int
    tarea_apartado_id: int
    codigo_apartado: str
    descripcion_apartado: str
    apartados: list[ApartadoEnlazadoOut] = Field(default_factory=list)


class DesenlazarApartadoOut(BaseModel):
    contrato_id: int
    tarea_apartado_id: int | None = None
