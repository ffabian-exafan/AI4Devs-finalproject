"""Schemas de la pantalla de revisión humana."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.tipos import Money


class RevisionPendienteOut(BaseModel):
    proyecto_id: int
    proyecto_nombre: str
    tipo: Literal["presupuesto", "contrato"]
    documento_id: int
    fichero_origen: str
    pendientes: int
    anotaciones_manuales: int


class TareaRevisionNodo(BaseModel):
    """Nodo del árbol editable en la UI de revisión."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tarea_padre_id: int | None
    codigo: str
    nivel: str
    capitulo: str | None = None
    descripcion: str
    unidad: str | None = None
    cantidad: Money | None = None
    precio_unitario: Money | None = None
    importe_presupuestado: Money
    tiene_anotacion_manual: bool
    estado_revision: str
    hijos: list["TareaRevisionNodo"] = Field(default_factory=list)


class DocumentoRevisionOut(BaseModel):
    proyecto_id: int
    proyecto_nombre: str
    tipo: Literal["presupuesto", "contrato"]
    documento_id: int
    fichero_origen: str
    contratista_nif: str | None = None
    arbol: list[TareaRevisionNodo]


class TareaRevisionUpdate(BaseModel):
    id: int
    codigo: str = Field(min_length=1, max_length=50)
    descripcion: str = Field(min_length=1)
    capitulo: str | None = Field(default=None, max_length=255)
    unidad: str | None = Field(default=None, max_length=50)
    cantidad: Money | None = None
    precio_unitario: Money | None = None
    importe_presupuestado: Money
    # pendiente | revisada | confirmada
    estado_revision: str = Field(min_length=1, max_length=50)
    # Obligatorio true si la fila tenía anotación manuscrita
    anotacion_confirmada: bool = False


class ConfirmarRevisionIn(BaseModel):
    tipo: Literal["presupuesto", "contrato"]
    documento_id: int
    tareas: list[TareaRevisionUpdate] = Field(min_length=1)

    @model_validator(mode="after")
    def sin_pendientes_ni_manuscritos_sin_confirmar(self) -> "ConfirmarRevisionIn":
        for t in self.tareas:
            if t.estado_revision == "pendiente":
                raise ValueError(
                    f"La tarea {t.id} ({t.codigo}) sigue en estado_revision=pendiente"
                )
            if t.estado_revision not in {"revisada", "confirmada"}:
                raise ValueError(
                    f"La tarea {t.id} tiene estado_revision inválido: {t.estado_revision}"
                )
        return self


class ConfirmarRevisionOut(BaseModel):
    ok: bool
    proyecto_id: int
    tipo: Literal["presupuesto", "contrato"]
    documento_id: int
    tareas_confirmadas: int
    mensaje: str
