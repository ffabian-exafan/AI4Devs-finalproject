"""Schemas de tarea jerárquica (apartado / subapartado / partida)."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tipos import Money


class TareaCreate(BaseModel):
    nave_id: int
    presupuesto_id: int | None = None
    contrato_id: int | None = None
    tarea_padre_id: int | None = None
    contratista_id: int | None = None
    codigo: str = Field(min_length=1, max_length=50)
    # apartado | subapartado | partida
    nivel: str = Field(min_length=1, max_length=50)
    capitulo: str | None = Field(default=None, max_length=255)
    descripcion: str = Field(min_length=1)
    # Nullable: un apartado puede no tener desglose con precio unitario
    unidad: str | None = Field(default=None, max_length=50)
    cantidad: Money | None = None
    precio_unitario: Money | None = None
    importe_presupuestado: Money
    tiene_anotacion_manual: bool = False
    # pendiente | revisada | confirmada
    estado_revision: str = Field(min_length=1, max_length=50)
    # no_iniciada | en_curso | finalizada
    estado: str = Field(min_length=1, max_length=50)
    avance_fisico_pct: Money = Decimal("0")


class LineaPresupuestoIn(BaseModel):
    """Alta o corrección de una línea de presupuesto.

    [VERIFICAR] docs/readme.md no define el alta manual de una TAREA.
    """

    codigo: str = Field(min_length=1, max_length=50)
    descripcion: str = Field(min_length=1)
    importe_presupuestado: Money


class LineaPresupuestoOut(BaseModel):
    id: int
    codigo: str
    descripcion: str
    nivel: str
    importe_presupuestado: Money
    estado_revision: str


class TareaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nave_id: int
    presupuesto_id: int | None
    contrato_id: int | None
    tarea_padre_id: int | None
    contratista_id: int | None
    codigo: str
    nivel: str
    capitulo: str | None
    descripcion: str
    unidad: str | None
    cantidad: Money | None
    precio_unitario: Money | None
    importe_presupuestado: Money
    tiene_anotacion_manual: bool
    estado_revision: str
    estado: str
    avance_fisico_pct: Money
