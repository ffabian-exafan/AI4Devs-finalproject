"""Consultas de proyectos para listado y detalle de UI."""

from decimal import Decimal

from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from app.models import Contrato, Factura, Nave, Proyecto, Tarea
from app.schemas.proyecto import (
    ApartadoResumenOut,
    ContratoApartadoOut,
    ContratoResumenOut,
    NaveResumenOut,
    ProyectoDetalleOut,
    ProyectoRead,
)
from app.services import casado as casado_svc
from app.services.jerarquia import asegurar_apartados_padre, mapa_padres


def listar_proyectos(db: Session) -> list[ProyectoRead]:
    filas = db.query(Proyecto).order_by(Proyecto.id.desc()).all()
    if not filas:
        return []
    ids = [p.id for p in filas]
    presupuestado = _presupuestado_raices(db, ids)
    facturado = _facturado_confirmado(db, ids)
    return [
        ProyectoRead(
            id=p.id,
            nombre=p.nombre,
            tipo=p.tipo,
            fecha_inicio=p.fecha_inicio,
            estado=p.estado,
            created_at=p.created_at,
            presupuestado=presupuestado.get(p.id, Decimal("0")),
            facturado=facturado.get(p.id, Decimal("0")),
        )
        for p in filas
    ]


def _presupuestado_raices(db: Session, proyecto_ids: list[int]) -> dict[int, Decimal]:
    """Suma solo apartados raíz. Un subapartado no se vuelve a sumar."""
    tareas = (
        db.query(Tarea, Nave.proyecto_id)
        .join(Nave, Tarea.nave_id == Nave.id)
        .filter(
            Nave.proyecto_id.in_(proyecto_ids),
            Tarea.presupuesto_id.isnot(None),
        )
        .all()
    )
    por_proyecto: dict[int, list[Tarea]] = {}
    for tarea, proyecto_id in tareas:
        por_proyecto.setdefault(proyecto_id, []).append(tarea)

    totales: dict[int, Decimal] = {}
    for proyecto_id, grupo in por_proyecto.items():
        padres = mapa_padres(grupo)
        totales[proyecto_id] = sum(
            (t.importe_presupuestado for t in grupo if padres.get(t.id) is None),
            Decimal("0"),
        )
    return totales


def _facturado_confirmado(db: Session, proyecto_ids: list[int]) -> dict[int, Decimal]:
    filas = (
        db.query(Factura.proyecto_id, func.coalesce(func.sum(Factura.total), 0))
        .filter(
            Factura.proyecto_id.in_(proyecto_ids),
            Factura.estado_revision == "confirmada",
        )
        .group_by(Factura.proyecto_id)
        .all()
    )
    return {
        proyecto_id: Decimal(total)
        for proyecto_id, total in filas
        if proyecto_id is not None
    }


def obtener_proyecto(db: Session, proyecto_id: int) -> ProyectoDetalleOut:
    proyecto = (
        db.query(Proyecto)
        .options(joinedload(Proyecto.naves))
        .filter(Proyecto.id == proyecto_id)
        .first()
    )
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")

    naves = sorted(proyecto.naves, key=lambda n: n.id)
    nave_por_id = {n.id: n for n in naves}
    nave_ids = list(nave_por_id.keys())

    tareas_presupuesto: list[Tarea] = []
    if nave_ids:
        tareas_presupuesto = (
            db.query(Tarea)
            .filter(
                Tarea.nave_id.in_(nave_ids),
                Tarea.presupuesto_id.isnot(None),
            )
            .order_by(Tarea.codigo, Tarea.id)
            .all()
        )
        asegurar_apartados_padre(db, tareas_presupuesto)

    contratos_db = (
        db.query(Contrato)
        .options(
            joinedload(Contrato.contratista),
            joinedload(Contrato.tarea_apartado),
        )
        .filter(Contrato.proyecto_id == proyecto_id)
        .order_by(Contrato.id.desc())
        .all()
    )

    facturado_por_contrato = {
        contrato_id: Decimal(total)
        for contrato_id, total in (
            db.query(
                Factura.contrato_id,
                func.coalesce(func.sum(Factura.total), 0),
            )
            .filter(
                Factura.proyecto_id == proyecto_id,
                Factura.contrato_id.isnot(None),
                Factura.estado_revision == "confirmada",
            )
            .group_by(Factura.contrato_id)
            .all()
        )
    }
    contratos_por_apartado: dict[int, list[ContratoApartadoOut]] = {}
    for contrato in contratos_db:
        if contrato.tarea_apartado_id is None:
            continue
        contratado = Decimal(contrato.precio_total)
        facturado = facturado_por_contrato.get(contrato.id, Decimal("0"))
        porcentaje = (
            (facturado / contratado * Decimal("100"))
            if contratado != 0
            else Decimal("0")
        )
        contratos_por_apartado.setdefault(contrato.tarea_apartado_id, []).append(
            ContratoApartadoOut(
                id=contrato.id,
                contratista_nombre=(
                    contrato.contratista.nombre if contrato.contratista else "—"
                ),
                contratista_nif=(
                    contrato.contratista.nif if contrato.contratista else "—"
                ),
                contratado=contratado,
                facturado=facturado,
                pendiente=contratado - facturado,
                porcentaje_facturado=porcentaje.quantize(Decimal("0.01")),
            )
        )

    padres = mapa_padres(tareas_presupuesto)
    hijos_por_id: dict[int, list[Tarea]] = {}
    raices: list[Tarea] = []
    for tarea in tareas_presupuesto:
        padre_id = padres.get(tarea.id)
        if padre_id is None:
            raices.append(tarea)
        else:
            hijos_por_id.setdefault(padre_id, []).append(tarea)

    def resumen_apartado(ap: Tarea, *, con_contratos: bool) -> ApartadoResumenOut:
        nivel = ap.nivel
        if padres.get(ap.id) is not None and nivel == "apartado":
            nivel = "subapartado"
        return ApartadoResumenOut(
            id=ap.id,
            codigo=ap.codigo,
            descripcion=ap.descripcion,
            nivel=nivel,
            importe_presupuestado=ap.importe_presupuestado,
            nave_id=ap.nave_id,
            nave_codigo=nave_por_id[ap.nave_id].codigo
            if ap.nave_id in nave_por_id
            else "",
            estado_revision=ap.estado_revision,
            contrato_enlazado_id=(
                contratos_por_apartado[ap.id][0].id
                if con_contratos and contratos_por_apartado.get(ap.id)
                else None
            ),
            contratos=contratos_por_apartado.get(ap.id, []) if con_contratos else [],
            subapartados=[
                resumen_apartado(hijo, con_contratos=False)
                for hijo in hijos_por_id.get(ap.id, [])
            ],
        )

    apartados_out = [resumen_apartado(ap, con_contratos=True) for ap in raices]

    contratos_out: list[ContratoResumenOut] = []
    for c in contratos_db:
        sugerencias = []
        apartado_codigo = None
        apartado_descripcion = None
        if c.tarea_apartado_id and c.tarea_apartado is not None:
            apartado_codigo = c.tarea_apartado.codigo
            apartado_descripcion = c.tarea_apartado.descripcion
        else:
            sugerencias = casado_svc.sugerir_apartados_para_contrato(db, c)

        contratos_out.append(
            ContratoResumenOut(
                id=c.id,
                contratista_nombre=c.contratista.nombre if c.contratista else "—",
                contratista_nif=c.contratista.nif if c.contratista else "—",
                precio_total=c.precio_total,
                estado_extraccion=c.estado_extraccion,
                nave_id=c.nave_id,
                tarea_apartado_id=c.tarea_apartado_id,
                apartado_codigo=apartado_codigo,
                apartado_descripcion=apartado_descripcion,
                sugerencias=sugerencias,
            )
        )

    return ProyectoDetalleOut(
        id=proyecto.id,
        nombre=proyecto.nombre,
        tipo=proyecto.tipo,
        fecha_inicio=proyecto.fecha_inicio,
        estado=proyecto.estado,
        created_at=proyecto.created_at,
        presupuestado=_presupuestado_raices(db, [proyecto.id]).get(proyecto.id, Decimal("0")),
        facturado=_facturado_confirmado(db, [proyecto.id]).get(proyecto.id, Decimal("0")),
        naves=[NaveResumenOut.model_validate(n) for n in naves],
        apartados=apartados_out,
        contratos=contratos_out,
    )


def borrar_proyecto(db: Session, proyecto_id: int) -> None:
    """Elimina la obra y lo que cuelga de ella. El contratista se conserva.

    [VERIFICAR] docs/readme.md no define el borrado de un proyecto.
    """
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")

    params = {"id": proyecto_id}
    db.execute(
        text(
            """
            UPDATE factura
            SET duplicado_de_id = NULL
            WHERE proyecto_id = :id
               OR duplicado_de_id IN (SELECT id FROM factura WHERE proyecto_id = :id)
            """
        ),
        params,
    )
    db.execute(
        text(
            """
            DELETE FROM asignacion
            WHERE factura_id IN (SELECT id FROM factura WHERE proyecto_id = :id)
               OR nave_id IN (SELECT id FROM nave WHERE proyecto_id = :id)
               OR tarea_id IN (
                    SELECT tarea.id FROM tarea
                    JOIN nave ON nave.id = tarea.nave_id
                    WHERE nave.proyecto_id = :id
               )
            """
        ),
        params,
    )
    db.execute(
        text(
            """
            DELETE FROM linea_factura
            WHERE factura_id IN (SELECT id FROM factura WHERE proyecto_id = :id)
               OR tarea_id IN (
                    SELECT tarea.id FROM tarea
                    JOIN nave ON nave.id = tarea.nave_id
                    WHERE nave.proyecto_id = :id
               )
            """
        ),
        params,
    )
    db.execute(text("DELETE FROM factura WHERE proyecto_id = :id"), params)
    db.execute(
        text("UPDATE contrato SET tarea_apartado_id = NULL WHERE proyecto_id = :id"),
        params,
    )
    db.execute(
        text(
            """
            UPDATE tarea
            SET tarea_padre_id = NULL, contrato_id = NULL
            WHERE nave_id IN (SELECT id FROM nave WHERE proyecto_id = :id)
            """
        ),
        params,
    )
    db.execute(
        text(
            """
            DELETE FROM tarea
            WHERE nave_id IN (SELECT id FROM nave WHERE proyecto_id = :id)
            """
        ),
        params,
    )
    db.execute(text("DELETE FROM contrato WHERE proyecto_id = :id"), params)
    db.execute(text("DELETE FROM presupuesto WHERE proyecto_id = :id"), params)
    db.execute(text("DELETE FROM nave WHERE proyecto_id = :id"), params)
    db.delete(proyecto)
    db.commit()
