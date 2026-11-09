"""Marca una línea del PDF del cliente como apartado de solo gestión."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Contrato, LineaPdfCliente, LineaPdfClienteTarea, Nave, Presupuesto, Proyecto, Tarea
from app.schemas.casado import DesenlazarApartadoOut
from app.schemas.presupuesto import SoloGestionOut


def marcar(db: Session, proyecto_id: int, linea_id: int) -> SoloGestionOut:
    linea, presupuesto = _linea_del_proyecto(db, proyecto_id, linea_id)
    if linea.tipo != "importe":
        raise ValueError("Solo se puede marcar una línea de importe")
    if linea.apartado_gestion_id is not None:
        raise ValueError("La línea ya está marcada como solo gestión")
    confirmada = (
        db.query(LineaPdfClienteTarea)
        .filter(
            LineaPdfClienteTarea.linea_id == linea.id,
            LineaPdfClienteTarea.es_sugerencia.is_(False),
        )
        .count()
    )
    if confirmada:
        raise ValueError("La línea ya está confirmada contra un bloque de Excel")

    db.execute(delete(LineaPdfClienteTarea).where(LineaPdfClienteTarea.linea_id == linea.id))
    nave = _nave_de_la_obra(db, proyecto_id)
    codigo = _codigo_apartado(db, nave.id, linea)
    manuscrito = bool(linea.es_manuscrito)
    apartado = Tarea(
        nave_id=nave.id,
        presupuesto_id=presupuesto.id,
        codigo=codigo,
        nivel="apartado",
        descripcion=linea.descripcion,
        importe_presupuestado=linea.importe,
        importe_contrato_cliente=linea.importe,
        es_montaje=False,
        solo_gestion=True,
        tiene_anotacion_manual=manuscrito,
        estado_revision="pendiente" if manuscrito else "confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(apartado)
    db.flush()
    linea.apartado_gestion_id = apartado.id
    db.commit()
    db.refresh(apartado)
    return _salida(apartado, linea)


def desmarcar(db: Session, proyecto_id: int, linea_id: int) -> None:
    linea, _presupuesto = _linea_del_proyecto(db, proyecto_id, linea_id)
    if linea.apartado_gestion_id is None:
        raise ValueError("La línea no está marcada como solo gestión")
    tarea_id = linea.apartado_gestion_id
    enlazados = (
        db.query(Contrato).filter(Contrato.tarea_apartado_id == tarea_id).count()
    )
    if enlazados:
        raise ValueError("Hay un contrato enlazado a este apartado")
    linea.apartado_gestion_id = None
    db.flush()
    apartado = db.get(Tarea, tarea_id)
    if apartado is not None:
        db.delete(apartado)
    db.commit()


def confirmar(db: Session, proyecto_id: int, tarea_id: int) -> SoloGestionOut:
    apartado = _apartado_de_la_obra(db, proyecto_id, tarea_id)
    if not apartado.solo_gestion:
        raise ValueError("El apartado no es de solo gestión")
    linea = (
        db.query(LineaPdfCliente)
        .filter(LineaPdfCliente.apartado_gestion_id == apartado.id)
        .first()
    )
    if linea is None:
        raise ValueError(f"Línea del apartado {tarea_id} no encontrada")
    if apartado.estado_revision != "confirmada":
        apartado.estado_revision = "confirmada"
        db.commit()
        db.refresh(apartado)
    return _salida(apartado, linea)


def desenlazar(db: Session, proyecto_id: int, contrato_id: int) -> DesenlazarApartadoOut:
    contrato = (
        db.query(Contrato)
        .filter(Contrato.id == contrato_id, Contrato.proyecto_id == proyecto_id)
        .first()
    )
    if contrato is None:
        raise ValueError(f"Contrato {contrato_id} no encontrado en proyecto {proyecto_id}")
    if contrato.tarea_apartado_id is not None:
        contrato.tarea_apartado_id = None
        db.commit()
        db.refresh(contrato)
    return DesenlazarApartadoOut(contrato_id=contrato.id, tarea_apartado_id=None)


def _linea_del_proyecto(
    db: Session, proyecto_id: int, linea_id: int
) -> tuple[LineaPdfCliente, Presupuesto]:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    linea = db.get(LineaPdfCliente, linea_id)
    if linea is None:
        raise ValueError(f"Línea {linea_id} no encontrada")
    presupuesto = db.get(Presupuesto, linea.presupuesto_id)
    if (
        presupuesto is None
        or presupuesto.proyecto_id != proyecto_id
        or presupuesto.formato != "pdf_cliente"
    ):
        raise ValueError(f"Línea {linea_id} no encontrada")
    return linea, presupuesto


def _nave_de_la_obra(db: Session, proyecto_id: int) -> Nave:
    nave = (
        db.query(Nave)
        .filter(Nave.proyecto_id == proyecto_id)
        .order_by(Nave.id)
        .first()
    )
    if nave is None:
        raise ValueError("La obra no tiene nave")
    return nave


def _codigo_apartado(db: Session, nave_id: int, linea: LineaPdfCliente) -> str:
    codigo = (linea.codigo or "").strip()
    if codigo and len(codigo) <= 50:
        usado = (
            db.query(Tarea)
            .filter(Tarea.nave_id == nave_id, Tarea.codigo == codigo)
            .first()
        )
        if usado is None:
            return codigo
    return f"pdf.{linea.id}"


def _apartado_de_la_obra(db: Session, proyecto_id: int, tarea_id: int) -> Tarea:
    apartado = db.get(Tarea, tarea_id)
    if apartado is None:
        raise ValueError(f"Apartado {tarea_id} no encontrado")
    nave = db.get(Nave, apartado.nave_id)
    if nave is None or nave.proyecto_id != proyecto_id:
        raise ValueError(f"Apartado {tarea_id} no encontrado")
    return apartado


def _salida(apartado: Tarea, linea: LineaPdfCliente) -> SoloGestionOut:
    return SoloGestionOut(
        tarea_id=apartado.id,
        linea_id=linea.id,
        codigo=apartado.codigo,
        descripcion=apartado.descripcion,
        importe=apartado.importe_presupuestado,
        estado_revision=apartado.estado_revision,
        tiene_anotacion_manual=bool(apartado.tiene_anotacion_manual),
        solo_gestion=True,
    )
