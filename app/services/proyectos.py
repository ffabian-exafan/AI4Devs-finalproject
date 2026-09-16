"""Consultas de proyectos para listado y detalle de UI."""

from decimal import Decimal

from sqlalchemy import func
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


def listar_proyectos(db: Session) -> list[ProyectoRead]:
    filas = db.query(Proyecto).order_by(Proyecto.id.desc()).all()
    return [ProyectoRead.model_validate(p) for p in filas]


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

    apartados_db: list[Tarea] = []
    if nave_ids:
        apartados_db = (
            db.query(Tarea)
            .filter(
                Tarea.nave_id.in_(nave_ids),
                Tarea.presupuesto_id.isnot(None),
                Tarea.nivel == "apartado",
                Tarea.tarea_padre_id.is_(None),
            )
            .order_by(Tarea.codigo)
            .all()
        )

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

    apartados_out = [
        ApartadoResumenOut(
            id=ap.id,
            codigo=ap.codigo,
            descripcion=ap.descripcion,
            nivel=ap.nivel,
            importe_presupuestado=ap.importe_presupuestado,
            nave_id=ap.nave_id,
            nave_codigo=nave_por_id[ap.nave_id].codigo
            if ap.nave_id in nave_por_id
            else "",
            estado_revision=ap.estado_revision,
            contrato_enlazado_id=(
                contratos_por_apartado[ap.id][0].id
                if contratos_por_apartado.get(ap.id)
                else None
            ),
            contratos=contratos_por_apartado.get(ap.id, []),
        )
        for ap in apartados_db
    ]

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
        naves=[NaveResumenOut.model_validate(n) for n in naves],
        apartados=apartados_out,
        contratos=contratos_out,
    )
