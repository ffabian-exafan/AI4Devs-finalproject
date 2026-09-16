"""Schemas de control económico (GET /proyectos/{id}/control-economico)."""

from pydantic import BaseModel, Field

from app.schemas.tipos import Money


class DesvioContratistaOut(BaseModel):
    nif: str
    presupuestado: Money
    facturado: Money
    desvio: Money


class DesvioContratoOut(BaseModel):
    contrato_id: int
    contratista_nif: str
    contratado: Money
    facturado: Money
    desvio: Money


class DesvioNaveOut(BaseModel):
    nave: str
    presupuestado: Money
    gasto_estimado: Money
    es_estimacion: bool


class ControlEconomicoOut(BaseModel):
    por_contratista: list[DesvioContratistaOut] = Field(default_factory=list)
    por_contrato: list[DesvioContratoOut] = Field(default_factory=list)
    por_nave: list[DesvioNaveOut] = Field(default_factory=list)
