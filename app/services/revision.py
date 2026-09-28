"""Servicio de revisión humana de presupuestos y contratos extraídos."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Contrato, Contratista, Presupuesto, Proyecto, Tarea
from app.services.jerarquia import asegurar_apartados_padre, mapa_padres
from app.schemas.revision import (
    ConfirmarRevisionIn,
    ConfirmarRevisionOut,
    DocumentoRevisionOut,
    RevisionPendienteOut,
    TareaRevisionNodo,
    TareaRevisionUpdate,
)


def listar_pendientes(db: Session) -> list[RevisionPendienteOut]:
    resultado: list[RevisionPendienteOut] = []

    for presup in (
        db.query(Presupuesto)
        .filter(Presupuesto.estado_extraccion == "pendiente_revision")
        .order_by(Presupuesto.id.desc())
        .all()
    ):
        proyecto = db.get(Proyecto, presup.proyecto_id)
        if proyecto is None:
            continue
        tareas = (
            db.query(Tarea).filter(Tarea.presupuesto_id == presup.id).all()
        )
        resultado.append(
            RevisionPendienteOut(
                proyecto_id=proyecto.id,
                proyecto_nombre=proyecto.nombre,
                tipo="presupuesto",
                documento_id=presup.id,
                fichero_origen=presup.fichero_origen,
                pendientes=sum(1 for t in tareas if t.estado_revision == "pendiente"),
                anotaciones_manuales=sum(1 for t in tareas if t.tiene_anotacion_manual),
            )
        )

    for contrato in (
        db.query(Contrato)
        .filter(Contrato.estado_extraccion == "pendiente_revision")
        .order_by(Contrato.id.desc())
        .all()
    ):
        proyecto = db.get(Proyecto, contrato.proyecto_id)
        if proyecto is None:
            continue
        tareas = db.query(Tarea).filter(Tarea.contrato_id == contrato.id).all()
        resultado.append(
            RevisionPendienteOut(
                proyecto_id=proyecto.id,
                proyecto_nombre=proyecto.nombre,
                tipo="contrato",
                documento_id=contrato.id,
                fichero_origen=contrato.fichero_origen,
                pendientes=sum(1 for t in tareas if t.estado_revision == "pendiente"),
                anotaciones_manuales=sum(1 for t in tareas if t.tiene_anotacion_manual),
            )
        )

    return resultado


def obtener_documento(
    db: Session,
    tipo: str,
    documento_id: int,
) -> DocumentoRevisionOut:
    if tipo == "presupuesto":
        doc = db.get(Presupuesto, documento_id)
        if doc is None:
            raise ValueError(f"Presupuesto {documento_id} no encontrado")
        proyecto = db.get(Proyecto, doc.proyecto_id)
        if proyecto is None:
            raise ValueError(f"Proyecto {doc.proyecto_id} no encontrado")
        tareas = db.query(Tarea).filter(Tarea.presupuesto_id == doc.id).all()
        asegurar_apartados_padre(db, tareas)
        return DocumentoRevisionOut(
            proyecto_id=proyecto.id,
            proyecto_nombre=proyecto.nombre,
            tipo="presupuesto",
            documento_id=doc.id,
            fichero_origen=doc.fichero_origen,
            contratista_nif=None,
            arbol=_construir_arbol(tareas),
        )

    if tipo == "contrato":
        doc = db.get(Contrato, documento_id)
        if doc is None:
            raise ValueError(f"Contrato {documento_id} no encontrado")
        proyecto = db.get(Proyecto, doc.proyecto_id)
        if proyecto is None:
            raise ValueError(f"Proyecto {doc.proyecto_id} no encontrado")
        contratista = db.get(Contratista, doc.contratista_id)
        tareas = db.query(Tarea).filter(Tarea.contrato_id == doc.id).all()
        return DocumentoRevisionOut(
            proyecto_id=proyecto.id,
            proyecto_nombre=proyecto.nombre,
            tipo="contrato",
            documento_id=doc.id,
            fichero_origen=doc.fichero_origen,
            contratista_nif=contratista.nif if contratista else None,
            arbol=_construir_arbol(tareas),
        )

    raise ValueError(f"Tipo de documento no válido: {tipo}")


def confirmar_revision(db: Session, payload: ConfirmarRevisionIn) -> ConfirmarRevisionOut:
    """
    Persiste la revisión. La validación de forma ya viene en ConfirmarRevisionIn (Pydantic).
    Aquí se aplica la regla de negocio: manuscrito exige confirmación explícita.
    """
    if payload.tipo == "presupuesto":
        doc = db.get(Presupuesto, payload.documento_id)
        if doc is None:
            raise ValueError(f"Presupuesto {payload.documento_id} no encontrado")
        tareas_db = {
            t.id: t
            for t in db.query(Tarea).filter(Tarea.presupuesto_id == doc.id).all()
        }
    else:
        doc = db.get(Contrato, payload.documento_id)
        if doc is None:
            raise ValueError(f"Contrato {payload.documento_id} no encontrado")
        tareas_db = {
            t.id: t
            for t in db.query(Tarea).filter(Tarea.contrato_id == doc.id).all()
        }

    if set(tareas_db.keys()) != {t.id for t in payload.tareas}:
        raise ValueError(
            "El conjunto de tareas enviadas no coincide con las del documento"
        )

    for upd in payload.tareas:
        tarea = tareas_db[upd.id]
        _validar_negocio_fila(tarea, upd)
        tarea.codigo = upd.codigo
        tarea.descripcion = upd.descripcion
        tarea.capitulo = upd.capitulo
        tarea.unidad = upd.unidad
        tarea.cantidad = upd.cantidad
        tarea.precio_unitario = upd.precio_unitario
        tarea.importe_presupuestado = upd.importe_presupuestado
        tarea.estado_revision = (
            "confirmada" if tarea.tiene_anotacion_manual else upd.estado_revision
        )

    doc.estado_extraccion = "confirmada"
    proyecto = db.get(Proyecto, doc.proyecto_id)
    if proyecto is not None and proyecto.estado == "pendiente_revision":
        # doc ya está en confirmada en la sesión: no cuenta como pendiente
        otros_p = (
            db.query(Presupuesto)
            .filter(
                Presupuesto.proyecto_id == proyecto.id,
                Presupuesto.estado_extraccion == "pendiente_revision",
            )
            .count()
        )
        otros_c = (
            db.query(Contrato)
            .filter(
                Contrato.proyecto_id == proyecto.id,
                Contrato.estado_extraccion == "pendiente_revision",
            )
            .count()
        )
        if otros_p == 0 and otros_c == 0:
            proyecto.estado = "en_curso"

    db.commit()

    return ConfirmarRevisionOut(
        ok=True,
        proyecto_id=doc.proyecto_id,
        tipo=payload.tipo,
        documento_id=payload.documento_id,
        tareas_confirmadas=len(payload.tareas),
        mensaje="Revisión confirmada y persistida",
    )


def _validar_negocio_fila(tarea: Tarea, upd: TareaRevisionUpdate) -> None:
    if not upd.descripcion.strip():
        raise ValueError(f"La tarea {upd.id} tiene descripción vacía")
    if not upd.codigo.strip():
        raise ValueError(f"La tarea {upd.id} tiene código vacío")
    if tarea.tiene_anotacion_manual and not upd.anotacion_confirmada:
        raise ValueError(
            f"La tarea {upd.id} ({upd.codigo}) tiene anotación manuscrita "
            "y debe confirmarse explícitamente"
        )


def _construir_arbol(tareas: list[Tarea]) -> list[TareaRevisionNodo]:
    padres = mapa_padres(tareas)
    por_padre: dict[int | None, list[Tarea]] = defaultdict(list)
    for t in tareas:
        por_padre[padres.get(t.id)].append(t)

    def _nodo(t: Tarea) -> TareaRevisionNodo:
        padre_id = padres.get(t.id)
        hijos = sorted(por_padre.get(t.id, []), key=lambda x: (x.codigo, x.id))
        nivel = t.nivel
        if padre_id is not None and nivel == "apartado":
            nivel = "subapartado"
        return TareaRevisionNodo(
            id=t.id,
            tarea_padre_id=padre_id,
            codigo=t.codigo,
            nivel=nivel,
            capitulo=t.capitulo,
            descripcion=t.descripcion,
            unidad=t.unidad,
            cantidad=t.cantidad,
            precio_unitario=t.precio_unitario,
            importe_presupuestado=t.importe_presupuestado,
            tiene_anotacion_manual=t.tiene_anotacion_manual,
            estado_revision=t.estado_revision,
            hijos=[_nodo(h) for h in hijos],
        )

    raices = sorted(por_padre.get(None, []), key=lambda x: (x.codigo, x.id))
    return [_nodo(r) for r in raices]
