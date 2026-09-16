"""Cálculo de desvíos: presupuestado / contratado / facturado."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Asignacion, Contratista, Contrato, Factura, Nave, Proyecto, Tarea
from app.schemas.control_economico import (
    ControlEconomicoOut,
    DesvioContratistaOut,
    DesvioContratoOut,
    DesvioNaveOut,
)


def control_economico(db: Session, proyecto_id: int) -> ControlEconomicoOut:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")

    return ControlEconomicoOut(
        por_contratista=_por_contratista(db, proyecto_id),
        por_contrato=_por_contrato(db, proyecto_id),
        por_nave=_por_nave(db, proyecto_id),
    )


def _por_contratista(db: Session, proyecto_id: int) -> list[DesvioContratistaOut]:
    """Presupuestado (tareas de presupuesto) vs facturado, por NIF."""
    # Contratistas que aparecen en contratos, facturas o tareas del proyecto
    ids: set[int] = set()

    for (cid,) in (
        db.query(Contrato.contratista_id).filter(Contrato.proyecto_id == proyecto_id).all()
    ):
        ids.add(cid)

    for (cid,) in (
        db.query(Factura.contratista_id)
        .filter(
            Factura.proyecto_id == proyecto_id,
            Factura.estado_revision == "confirmada",
        )
        .all()
    ):
        ids.add(cid)

    for (cid,) in (
        db.query(Tarea.contratista_id)
        .join(Nave, Tarea.nave_id == Nave.id)
        .filter(Nave.proyecto_id == proyecto_id, Tarea.contratista_id.isnot(None))
        .all()
    ):
        if cid is not None:
            ids.add(cid)

    resultado: list[DesvioContratistaOut] = []
    for contratista_id in sorted(ids):
        contratista = db.get(Contratista, contratista_id)
        if contratista is None:
            continue

        presupuestado = (
            db.query(func.coalesce(func.sum(Tarea.importe_presupuestado), 0))
            .join(Nave, Tarea.nave_id == Nave.id)
            .filter(
                Nave.proyecto_id == proyecto_id,
                Tarea.contratista_id == contratista_id,
                Tarea.presupuesto_id.isnot(None),
            )
            .scalar()
        )
        presupuestado = Decimal(presupuestado)

        facturado = (
            db.query(func.coalesce(func.sum(Factura.total), 0))
            .filter(
                Factura.proyecto_id == proyecto_id,
                Factura.contratista_id == contratista_id,
                Factura.estado_revision == "confirmada",
            )
            .scalar()
        )
        facturado = Decimal(facturado)

        resultado.append(
            DesvioContratistaOut(
                nif=contratista.nif,
                presupuestado=presupuestado,
                facturado=facturado,
                desvio=facturado - presupuestado,
            )
        )

    return resultado


def _por_contrato(db: Session, proyecto_id: int) -> list[DesvioContratoOut]:
    """
    Dato medido más preciso: CONTRATO.precio_total vs suma de FACTURA.total
    con factura.contrato_id = contrato.id.
    """
    filas = (
        db.query(Contrato, Contratista)
        .join(Contratista, Contrato.contratista_id == Contratista.id)
        .filter(Contrato.proyecto_id == proyecto_id)
        .order_by(Contrato.id)
        .all()
    )

    resultado: list[DesvioContratoOut] = []
    for contrato, contratista in filas:
        facturado = (
            db.query(func.coalesce(func.sum(Factura.total), 0))
            .filter(
                Factura.contrato_id == contrato.id,
                Factura.estado_revision == "confirmada",
            )
            .scalar()
        )
        facturado = Decimal(facturado)
        contratado = Decimal(contrato.precio_total)
        resultado.append(
            DesvioContratoOut(
                contrato_id=contrato.id,
                contratista_nif=contratista.nif,
                contratado=contratado,
                facturado=facturado,
                desvio=facturado - contratado,
            )
        )
    return resultado


def _por_nave(db: Session, proyecto_id: int) -> list[DesvioNaveOut]:
    """
    Presupuestado vs gasto estimado por nave.
    Mientras no haya certificación medida por nave, es_estimacion = true.
    """
    naves = (
        db.query(Nave).filter(Nave.proyecto_id == proyecto_id).order_by(Nave.id).all()
    )
    resultado: list[DesvioNaveOut] = []
    for nave in naves:
        gasto = (
            db.query(func.coalesce(func.sum(Asignacion.importe_asignado), 0))
            .filter(Asignacion.nave_id == nave.id)
            .scalar()
        )
        gasto = Decimal(gasto)

        # Si hay alguna asignación no estimada, aún no hay certificación medida por nave
        # en el modelo de negocio actual → seguimos marcando estimación [VERIFICAR]
        es_estimacion = True

        resultado.append(
            DesvioNaveOut(
                nave=nave.descripcion or nave.codigo,
                presupuestado=Decimal(nave.importe_presupuestado),
                gasto_estimado=gasto,
                es_estimacion=es_estimacion,
            )
        )
    return resultado
