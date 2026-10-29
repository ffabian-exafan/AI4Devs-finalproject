"""Schemas de presupuesto e ingesta de PDF."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tipos import Money


class PresupuestoCreate(BaseModel):
    proyecto_id: int
    version: int = Field(ge=1)
    fichero_origen: str = Field(min_length=1, max_length=512)
    fecha: date | None = None
    estado_extraccion: str = Field(min_length=1, max_length=50)
    es_escaneado: bool = False


class PresupuestoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proyecto_id: int
    version: int
    fichero_origen: str
    fecha: date | None
    estado_extraccion: str
    es_escaneado: bool = False


class AvisoCuadreOut(BaseModel):
    bloque: str
    suma_lineas: Money
    total_documento: Money


class ApartadoExcelOut(BaseModel):
    tarea_id: int
    presupuesto_id: int
    codigo: str
    descripcion: str
    importe: Money
    partidas: int
    lineas_montaje: int


class ImportarExcelOut(BaseModel):
    """Respuesta de la alta o el añadido de presupuestos Excel."""

    proyecto_id: int
    presupuesto_ids: list[int]
    apartados: list[ApartadoExcelOut]
    partidas_detectadas: int
    lineas_montaje: int
    requiere_revision: bool
    sumas_cuadran: bool
    avisos: list[AvisoCuadreOut]


class SugerenciaContrasteOut(BaseModel):
    descripcion_pdf: str
    codigo_pdf: str
    importe_pdf: Money
    tarea_id: int | None = None
    codigo_apartado: str | None = None
    descripcion_apartado: str | None = None
    confianza: Decimal = Decimal("0")
    motivo: str = ""
    # Cifra de la línea antes de repartir el descuento de cierre. Null si no hay descuento.
    importe_bruto: Money | None = None
    # Id guardado. Null solo en el reparto, antes de persistir la línea.
    id: int | None = None
    tarea_ids: list[int] = Field(default_factory=list)
    confirmada: bool = False
    # True si los bloques los marcó el modelo y una persona aún no ha confirmado.
    sugerida: bool = False


class DescuentoContrasteOut(BaseModel):
    """Descuento del cierre del PDF del cliente. El importe es positivo: se resta."""

    descripcion: str
    importe: Money
    es_manuscrito: bool = False


class ContrastarClienteOut(BaseModel):
    presupuesto_id: int
    sugerencias: list[SugerenciaContrasteOut]
    descuentos: list[DescuentoContrasteOut] = Field(default_factory=list)


class ImporteClienteIn(BaseModel):
    importe: Money


class ImporteClienteOut(BaseModel):
    tarea_id: int
    importe_contrato_cliente: Money


class ImportesClienteIn(BaseModel):
    tarea_ids: list[int] = Field(min_length=1)
    importe: Money
    # Línea del PDF que se está confirmando. Sin ella el importe se guarda igual.
    linea_id: int | None = None


class ImportesClienteOut(BaseModel):
    asignaciones: list[ImporteClienteOut]


class ImportarPresupuestoOut(BaseModel):
    """Respuesta de POST /proyectos/importar-presupuesto."""

    proyecto_id: int
    presupuesto_id: int
    naves_detectadas: int
    partidas_detectadas: int
    requiere_revision: bool
    anotaciones_manuscritas_detectadas: int
    es_escaneado: bool = False
    sumas_cuadran: bool = False
    total_leido: Money | None = None
