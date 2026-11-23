"""Respuesta del alta de un pedido de compra."""

from decimal import Decimal

from pydantic import BaseModel, Field


class LineaPedidoOut(BaseModel):
    tarea_id: int
    codigo: str
    descripcion: str
    importe: Decimal
    estado_revision: str


class NavePedidoOut(BaseModel):
    pedido_id: int
    nave_id: int
    numero: str
    rotulo: str | None
    aviso: str | None
    estado_revision: str
    lineas: list[LineaPedidoOut] = Field(default_factory=list)


class ImportarPedidosOut(BaseModel):
    proyecto_id: int
    naves: list[NavePedidoOut]
