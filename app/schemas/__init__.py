"""Esquemas Pydantic (validación de forma y tipos)."""

from app.schemas.asignacion import AsignacionCreate, AsignacionRead
from app.schemas.casado import EnlazarApartadoIn, EnlazarApartadoOut, SugerenciaApartadoOut
from app.schemas.contratista import ContratistaCreate, ContratistaRead
from app.schemas.contrato import ContratoCreate, ContratoRead, ImportarContratoOut
from app.schemas.control_economico import (
    ControlEconomicoOut,
    DesvioContratistaOut,
    DesvioContratoOut,
    DesvioNaveOut,
)
from app.schemas.extraccion import (
    AnotacionManuscrita,
    ApartadoExtraido,
    ContratoExtraido,
    NaveExtraida,
    NodoTareaExtraido,
    PresupuestoExtraido,
)
from app.schemas.factura import (
    FacturaCreate,
    FacturaImportacionOut,
    FacturaRead,
    LineaFacturaCreate,
    LineaFacturaRead,
)
from app.schemas.nave import NaveCreate, NaveRead
from app.schemas.presupuesto import ImportarPresupuestoOut, PresupuestoCreate, PresupuestoRead
from app.schemas.proyecto import (
    ApartadoResumenOut,
    ContratoResumenOut,
    NaveResumenOut,
    ProyectoCreate,
    ProyectoDetalleOut,
    ProyectoRead,
)
from app.schemas.revision import (
    ConfirmarRevisionIn,
    ConfirmarRevisionOut,
    DocumentoRevisionOut,
    RevisionPendienteOut,
    TareaRevisionNodo,
    TareaRevisionUpdate,
)
from app.schemas.tarea import TareaCreate, TareaRead
from app.schemas.usuario import UsuarioCreate, UsuarioRead

__all__ = [
    "AnotacionManuscrita",
    "ApartadoExtraido",
    "ApartadoResumenOut",
    "AsignacionCreate",
    "AsignacionRead",
    "ConfirmarRevisionIn",
    "ConfirmarRevisionOut",
    "ContratistaCreate",
    "ContratistaRead",
    "ContratoCreate",
    "ContratoExtraido",
    "ContratoRead",
    "ContratoResumenOut",
    "ControlEconomicoOut",
    "DesvioContratistaOut",
    "DesvioContratoOut",
    "DesvioNaveOut",
    "DocumentoRevisionOut",
    "EnlazarApartadoIn",
    "EnlazarApartadoOut",
    "FacturaCreate",
    "FacturaImportacionOut",
    "FacturaRead",
    "ImportarContratoOut",
    "ImportarPresupuestoOut",
    "LineaFacturaCreate",
    "LineaFacturaRead",
    "NaveCreate",
    "NaveExtraida",
    "NaveRead",
    "NaveResumenOut",
    "NodoTareaExtraido",
    "PresupuestoCreate",
    "PresupuestoExtraido",
    "PresupuestoRead",
    "ProyectoCreate",
    "ProyectoDetalleOut",
    "ProyectoRead",
    "RevisionPendienteOut",
    "SugerenciaApartadoOut",
    "TareaCreate",
    "TareaRead",
    "TareaRevisionNodo",
    "TareaRevisionUpdate",
    "UsuarioCreate",
    "UsuarioRead",
]
