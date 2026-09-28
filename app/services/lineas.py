"""Alta, edición y borrado de líneas de presupuesto.

[VERIFICAR] docs/readme.md no define el alta manual ni el borrado de una TAREA.
Una línea añadida o corregida queda pendiente de revisión humana.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.models import Asignacion, Contrato, LineaFactura, Nave, Presupuesto, Proyecto, Tarea
from app.schemas.tarea import LineaPresupuestoIn, LineaPresupuestoOut


class LineaNoEncontrada(Exception):
    """La obra o la línea no existe en este proyecto."""


class LineaEnlazada(Exception):
    """Hay un contrato que apunta a la línea o a una hija."""


def crear_linea(
    db: Session, proyecto_id: int, payload: LineaPresupuestoIn
) -> LineaPresupuestoOut:
    proyecto = _proyecto(db, proyecto_id)
    presupuesto = _presupuesto(db, proyecto.id)
    nave = _nave(db, proyecto.id)
    codigo, descripcion = _texto(payload)
    tarea = Tarea(
        nave_id=nave.id,
        presupuesto_id=presupuesto.id,
        tarea_padre_id=None,
        codigo=codigo,
        nivel="apartado",
        descripcion=descripcion,
        importe_presupuestado=_importe(payload.importe_presupuestado),
        tiene_anotacion_manual=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(tarea)
    _reabrir(db, presupuesto)
    db.commit()
    db.refresh(tarea)
    return _out(tarea)


def editar_linea(
    db: Session, proyecto_id: int, tarea_id: int, payload: LineaPresupuestoIn
) -> LineaPresupuestoOut:
    tarea = _tarea_presupuesto(db, proyecto_id, tarea_id)
    codigo, descripcion = _texto(payload)
    tarea.codigo = codigo
    tarea.descripcion = descripcion
    tarea.importe_presupuestado = _importe(payload.importe_presupuestado)
    # El valor detectado ha cambiado: vuelve a revisión. La marca manuscrita se conserva.
    tarea.estado_revision = "pendiente"
    presupuesto = db.get(Presupuesto, tarea.presupuesto_id)
    if presupuesto is not None:
        _reabrir(db, presupuesto)
    db.commit()
    db.refresh(tarea)
    return _out(tarea)


def borrar_linea(db: Session, proyecto_id: int, tarea_id: int) -> None:
    tarea = _tarea_presupuesto(db, proyecto_id, tarea_id)
    presupuesto_id = tarea.presupuesto_id
    ids = _ids_subarbol(db, tarea.id)
    enlace = (
        db.query(Contrato.id)
        .filter(Contrato.tarea_apartado_id.in_(ids))
        .first()
    )
    if enlace is not None:
        raise LineaEnlazada(
            "Hay un contrato enlazado a esta línea. Quita el enlace antes de borrarla."
        )
    db.execute(
        update(LineaFactura)
        .where(LineaFactura.tarea_id.in_(ids))
        .values(tarea_id=None)
    )
    db.execute(delete(Asignacion).where(Asignacion.tarea_id.in_(ids)))
    db.execute(
        update(Tarea)
        .where(Tarea.id.in_(ids))
        .values(tarea_padre_id=None, contrato_id=None)
    )
    db.execute(delete(Tarea).where(Tarea.id.in_(ids)))
    presupuesto = db.get(Presupuesto, presupuesto_id)
    if presupuesto is not None:
        _reabrir(db, presupuesto)
    db.commit()


def _proyecto(db: Session, proyecto_id: int) -> Proyecto:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise LineaNoEncontrada(f"Proyecto {proyecto_id} no encontrado")
    return proyecto


def _presupuesto(db: Session, proyecto_id: int) -> Presupuesto:
    presupuesto = (
        db.query(Presupuesto)
        .filter(Presupuesto.proyecto_id == proyecto_id)
        .order_by(Presupuesto.version.desc(), Presupuesto.id.desc())
        .first()
    )
    if presupuesto is None:
        raise ValueError("La obra no tiene presupuesto")
    return presupuesto


def _nave(db: Session, proyecto_id: int) -> Nave:
    nave = (
        db.query(Nave)
        .filter(Nave.proyecto_id == proyecto_id)
        .order_by(Nave.id)
        .first()
    )
    if nave is None:
        raise ValueError("La obra no tiene nave")
    return nave


def _tarea_presupuesto(db: Session, proyecto_id: int, tarea_id: int) -> Tarea:
    _proyecto(db, proyecto_id)
    tarea = db.get(Tarea, tarea_id)
    if tarea is None or tarea.presupuesto_id is None:
        raise LineaNoEncontrada("Línea no encontrada")
    nave = db.get(Nave, tarea.nave_id)
    presupuesto = db.get(Presupuesto, tarea.presupuesto_id)
    if (
        nave is None
        or nave.proyecto_id != proyecto_id
        or presupuesto is None
        or presupuesto.proyecto_id != proyecto_id
    ):
        raise LineaNoEncontrada("Línea no encontrada")
    return tarea


def _texto(payload: LineaPresupuestoIn) -> tuple[str, str]:
    codigo = payload.codigo.strip()
    descripcion = payload.descripcion.strip()
    if not codigo or not descripcion:
        raise ValueError("Código y descripción son obligatorios")
    if len(codigo) > 50:
        raise ValueError("El código admite como máximo 50 caracteres")
    return codigo, descripcion


def _importe(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(Decimal("0.01"))


def _reabrir(db: Session, presupuesto: Presupuesto) -> None:
    presupuesto.estado_extraccion = "pendiente_revision"
    proyecto = db.get(Proyecto, presupuesto.proyecto_id)
    if proyecto is not None and proyecto.estado != "pendiente_revision":
        proyecto.estado = "pendiente_revision"


def _ids_subarbol(db: Session, raiz_id: int) -> list[int]:
    ids = [raiz_id]
    frontera = [raiz_id]
    while frontera:
        hijos = [
            fila[0]
            for fila in db.query(Tarea.id)
            .filter(Tarea.tarea_padre_id.in_(frontera))
            .all()
        ]
        frontera = [hijo for hijo in hijos if hijo not in ids]
        ids.extend(frontera)
    return ids


def _out(tarea: Tarea) -> LineaPresupuestoOut:
    return LineaPresupuestoOut(
        id=tarea.id,
        codigo=tarea.codigo,
        descripcion=tarea.descripcion,
        nivel=tarea.nivel,
        importe_presupuestado=tarea.importe_presupuestado,
        estado_revision=tarea.estado_revision,
    )
