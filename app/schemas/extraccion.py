"""Schemas intermedios de extracción de presupuesto (forma/tipos)."""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.tipos import Money


class AnotacionManuscrita(BaseModel):
    """Anotación manuscrita detectada sobre un valor impreso."""

    campo: str
    valor_impreso: str | None = None
    valor_manuscrito: str
    descripcion: str


class ApartadoExtraido(BaseModel):
    codigo: str
    capitulo: str | None = None
    descripcion: str
    importe: Money
    tiene_anotacion_manual: bool = False
    # Si True, no entra en la comprobación de suma vs totales de tabla
    excluido_de_suma: bool = False
    unidad: str | None = None
    cantidad: Money | None = None
    precio_unitario: Money | None = None


class NaveExtraida(BaseModel):
    codigo: str
    descripcion: str
    importe_presupuestado: Money = Decimal("0")
    apartados: list[ApartadoExtraido] = Field(default_factory=list)


class PresupuestoExtraido(BaseModel):
    """Resultado estructurado de la extracción (antes de persistir)."""

    nombre_proyecto: str
    tipo_proyecto: str = "llave_en_mano"
    version: int = 1
    fecha: str | None = None  # ISO date si se detecta
    naves: list[NaveExtraida] = Field(default_factory=list)
    total_impreso: Money | None = None
    total_manuscrito: Money | None = None
    anotaciones: list[AnotacionManuscrita] = Field(default_factory=list)
    sumas_cuadran: bool = False
    requiere_revision: bool = True


class NodoTareaExtraido(BaseModel):
    """Nodo del árbol de partidas de un contrato (apartado / subapartado / partida)."""

    codigo: str
    nivel: str  # apartado | subapartado | partida
    capitulo: str | None = None
    descripcion: str
    importe: Money
    unidad: str | None = None
    cantidad: Money | None = None
    precio_unitario: Money | None = None
    hijos: list["NodoTareaExtraido"] = Field(default_factory=list)


class ContratoExtraido(BaseModel):
    """Resultado estructurado de la extracción de contrato de subcontrata."""

    contratista_nif: str
    contratista_nombre: str
    contratista_tipo: str = "externo"
    referencia_presupuesto: str | None = None
    precio_total: Money
    fecha_firma: str | None = None  # ISO
    plazo_ejecucion: str | None = None  # ISO
    condiciones_facturacion: str | None = None
    # Árbol propio del contrato; no sustituye ni enlaza automáticamente al presupuesto
    arbol_tareas: list[NodoTareaExtraido] = Field(default_factory=list)
    requiere_revision: bool = True

    @property
    def partidas_detalle(self) -> int:
        """Cuenta nodos de nivel partida (desglose fino)."""

        def _contar(nodos: list[NodoTareaExtraido]) -> int:
            total = 0
            for n in nodos:
                if n.nivel == "partida":
                    total += 1
                total += _contar(n.hijos)
            return total

        return _contar(self.arbol_tareas)
