"""Schemas intermedios de extracción de presupuesto (forma/tipos)."""

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

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
    # null si el documento no trae cifra en esa fila. No se sustituye por 0.
    importe: Money | None = None
    tiene_anotacion_manual: bool = False
    # Si True, no entra en la comprobación de suma vs totales de tabla
    excluido_de_suma: bool = False
    unidad: str | None = None
    cantidad: Money | None = None
    precio_unitario: Money | None = None
    # 1.1.1 y 1.1.2 cuelgan de 1.1. El importe del presupuesto cierra en el apartado.
    subapartados: list["ApartadoExtraido"] = Field(default_factory=list)

    @model_validator(mode="after")
    def apartar_fila_sin_importe(self) -> "ApartadoExtraido":
        if self.importe is None:
            self.excluido_de_suma = True
        return self


class NaveExtraida(BaseModel):
    codigo: str
    descripcion: str
    importe_presupuestado: Money = Decimal("0")
    apartados: list[ApartadoExtraido] = Field(default_factory=list)


class DescuentoExtraido(BaseModel):
    """Descuento del cierre del presupuesto. El importe es positivo: se resta."""

    descripcion: str
    importe: Money
    es_manuscrito: bool = False


class PresupuestoExtraido(BaseModel):
    """Resultado estructurado de la extracción (antes de persistir)."""

    nombre_proyecto: str
    tipo_proyecto: str = "llave_en_mano"
    version: int = 1
    fecha: str | None = None  # ISO date si se detecta
    naves: list[NaveExtraida] = Field(default_factory=list)
    total_impreso: Money | None = None
    total_manuscrito: Money | None = None
    descuentos: list[DescuentoExtraido] = Field(default_factory=list)
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
    # [VERIFICAR] docs/readme.md no define que el modelo elija el apartado.
    # No confirma el enlace: solo alimenta la sugerencia (tarea_apartado_id sigue vacío).
    apartado_sugerido_codigo: str | None = None
    apartado_sugerido_motivo: str | None = None

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
