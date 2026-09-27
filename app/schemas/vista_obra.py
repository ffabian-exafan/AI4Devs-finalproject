"""Vista de las cinco pantallas y estado que la recalcula."""

from typing import Literal

from pydantic import BaseModel, Field

Resolucion = Literal[
    "Reclamada",
    "Desviación aprobada",
    "Descartada",
    "Validada",
]


class ContratoEstadoIn(BaseModel):
    id: int
    apartado_idx: int = Field(ge=0, le=7)
    asociado: bool


class EstadoObraIn(BaseModel):
    revisados: list[bool] = Field(min_length=8, max_length=8)
    contratos: list[ContratoEstadoIn] = Field(min_length=7, max_length=7)
    resueltas: dict[str, Resolucion] = Field(default_factory=dict)


class ObraFilaOut(BaseModel):
    especie: str
    nombre: str
    meta: str
    presupuestado: str
    facturado: str
    porcentaje: str
    fase: str
    estado: str
    tono: str
    destino: str


class PasoOut(BaseModel):
    id: str
    etiqueta: str
    detalle: str
    completo: bool


class PartidaPresupuestoOut(BaseModel):
    codigo: str
    descripcion: str
    unidad: str
    medicion: str
    precio: str
    importe: str
    duda: str | None = None


class ApartadoPresupuestoOut(BaseModel):
    codigo: str
    nombre: str
    importe: str
    resumen: str
    hay_dudas: bool
    revisado: bool
    partidas: list[PartidaPresupuestoOut]


class PresupuestoVistaOut(BaseModel):
    revisados: str
    revisados_pct: str
    n_partidas: int
    n_dudas: int
    total: str
    falta_revisar: bool
    apartados: list[ApartadoPresupuestoOut]


class OpcionApartadoOut(BaseModel):
    valor: str
    etiqueta: str


class ContratoFilaOut(BaseModel):
    id: int
    gremio: str
    archivo: str
    importe: str
    apartado_idx: int
    confianza: int
    motivo: str
    aviso: str | None = None
    hay_aviso: bool
    presupuestado: str
    diferencia: str
    supera: bool
    asociado: bool


class ContratosVistaOut(BaseModel):
    pendientes: int
    sin_contrato: str
    hay_sin_contrato: bool
    opciones: list[OpcionApartadoOut]
    filas: list[ContratoFilaOut]


class AccionFacturaOut(BaseModel):
    etiqueta: str
    variante: str
    resolucion: Resolucion


class LineaFacturaOut(BaseModel):
    codigo: str
    descripcion: str
    importe: str
    facturado: str
    presupuesto: str
    acumulado: str
    mala: bool
    nota: str | None = None


class FacturaFilaOut(BaseModel):
    id: str
    proveedor: str
    numero: str
    fecha: str
    apartado: str
    importe: str
    kind: str
    estado: str
    tono: str
    diferencia: str
    es_duplicado: bool
    aviso_duplicado: str | None = None
    desviacion: str
    desviacion_negativa: bool
    acciones: list[AccionFacturaOut]
    lineas: list[LineaFacturaOut]


class KpiOut(BaseModel):
    etiqueta: str
    valor: str
    detalle: str
    color: str


class PartidaControlOut(BaseModel):
    codigo: str
    descripcion: str
    presupuesto: str
    medicion: str
    facturado: str
    medicion_facturada: str
    desviacion: str
    alerta: bool


class FilaControlOut(BaseModel):
    codigo: str
    nombre: str
    facturado: str
    presupuestado: str
    ancho_presupuesto: str
    ancho_contratado: str
    ancho_facturado: str
    desviacion: str
    alerta: bool
    partidas: list[PartidaControlOut]


class AlertaOut(BaseModel):
    id: str
    tipo: str
    tono: str
    importe: str
    titulo: str
    texto: str
    destino: str
    factura_id: str | None = None


class ControlVistaOut(BaseModel):
    kpis: list[KpiOut]
    filas: list[FilaControlOut]
    alertas: list[AlertaOut]


class ProyectoVistaOut(BaseModel):
    codigo: str
    nombre: str
    subtitulo: str


class VistaObraOut(BaseModel):
    estado: EstadoObraIn
    nav_incidencias: int
    resumen_obras: str
    obras: list[ObraFilaOut]
    proyecto: ProyectoVistaOut
    pasos: list[PasoOut]
    presupuesto: PresupuestoVistaOut
    contratos: ContratosVistaOut
    facturas: list[FacturaFilaOut]
    control: ControlVistaOut
