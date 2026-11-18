"""Cálculo de desvíos: presupuestado / contratado / facturado."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Asignacion, Contratista, Contrato, Factura, Nave, Proyecto, Tarea
from app.services import casado as casado_svc
from app.schemas.control_economico import (
    ControlEconomicoOut,
    DesvioApartadoOut,
    DesvioContratistaOut,
    DesvioContratoOut,
    DesvioNaveOut,
)
from app.services.jerarquia import mapa_padres


def control_economico(db: Session, proyecto_id: int) -> ControlEconomicoOut:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")

    return ControlEconomicoOut(
        inversion_sujeto_pasivo=bool(proyecto.inversion_sujeto_pasivo),
        por_contratista=_por_contratista(db, proyecto_id),
        por_contrato=_por_contrato(db, proyecto_id),
        por_nave=_por_nave(db, proyecto_id),
        por_apartado=_por_apartado(db, proyecto_id),
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


def _por_apartado(db: Session, proyecto_id: int) -> list[DesvioApartadoOut]:
    """Presupuestado Excel, montaje, contrato cliente, contratado y facturado."""
    nave_ids = [
        nave_id
        for (nave_id,) in db.query(Nave.id).filter(Nave.proyecto_id == proyecto_id).all()
    ]
    if not nave_ids:
        return []
    tareas = (
        db.query(Tarea)
        .filter(Tarea.nave_id.in_(nave_ids), Tarea.presupuesto_id.isnot(None))
        .all()
    )
    padres = mapa_padres(tareas)
    hijos: dict[int, list[Tarea]] = {}
    for tarea in tareas:
        padre_id = padres.get(tarea.id)
        if padre_id is not None:
            hijos.setdefault(padre_id, []).append(tarea)

    contratos = (
        db.query(Contrato)
        .options(joinedload(Contrato.enlaces_apartado))
        .filter(Contrato.proyecto_id == proyecto_id)
        .all()
    )
    unicos: dict[int, Contrato] = {}
    for contrato in contratos:
        unicos[contrato.id] = contrato
    contratos = list(unicos.values())
    facturado_por_contrato = {
        contrato_id: Decimal(total)
        for contrato_id, total in (
            db.query(Factura.contrato_id, func.coalesce(func.sum(Factura.total), 0))
            .filter(
                Factura.proyecto_id == proyecto_id,
                Factura.contrato_id.isnot(None),
                Factura.estado_revision == "confirmada",
            )
            .group_by(Factura.contrato_id)
            .all()
        )
    }

    def montaje_de(tarea_id: int) -> Decimal:
        total = Decimal("0")
        pila = list(hijos.get(tarea_id, []))
        while pila:
            nodo = pila.pop()
            if nodo.es_montaje:
                total += Decimal(nodo.importe_presupuestado)
            pila.extend(hijos.get(nodo.id, []))
        return total

    def cliente_de(tarea: Tarea) -> Decimal | None:
        if tarea.importe_contrato_cliente is not None:
            return Decimal(tarea.importe_contrato_cliente)
        total = Decimal("0")
        hay = False
        pila = list(hijos.get(tarea.id, []))
        while pila:
            nodo = pila.pop()
            if nodo.importe_contrato_cliente is not None:
                total += Decimal(nodo.importe_contrato_cliente)
                hay = True
                continue
            pila.extend(hijos.get(nodo.id, []))
        return total if hay else None

    def peso(tarea: Tarea) -> Decimal:
        if tarea.solo_gestion:
            return Decimal(tarea.importe_presupuestado or 0)
        propio = Decimal(tarea.importe_presupuestado) if tarea.es_montaje else Decimal("0")
        return propio + montaje_de(tarea.id)

    por_id = {tarea.id: tarea for tarea in tareas}
    partes: dict[int, list[tuple[Decimal, Decimal]]] = {}
    for contrato in contratos:
        ids = casado_svc.ids_apartados_enlazados(contrato)
        extra = {
            tarea.id: tarea
            for tarea in db.query(Tarea).filter(Tarea.id.in_(ids)).all()
        } if ids else {}
        ligados = [extra[tarea_id] for tarea_id in ids if tarea_id in extra]
        ligados.sort(key=lambda tarea: (tarea.presupuesto_id is None, tarea.codigo, tarea.id))
        if not ligados:
            continue
        pesos = [
            Decimal(tarea.importe_presupuestado or 0)
            if tarea.presupuesto_id is None
            else peso(tarea)
            for tarea in ligados
        ]
        precios = casado_svc.repartir_importe(Decimal(contrato.precio_total), pesos)
        facts = casado_svc.repartir_importe(
            facturado_por_contrato.get(contrato.id, Decimal("0")),
            pesos,
        )
        for tarea, precio, fact in zip(ligados, precios, facts):
            if tarea.presupuesto_id is None or tarea.id not in por_id:
                continue
            partes.setdefault(tarea.id, []).append((precio, fact))

    salida: list[DesvioApartadoOut] = []
    for tarea in tareas:
        if padres.get(tarea.id) is not None or tarea.codigo.startswith("descuento."):
            continue
        if tarea.solo_gestion and tarea.estado_revision != "confirmada":
            continue
        trozos = partes.get(tarea.id, [])
        contratado = sum((precio for precio, _fact in trozos), Decimal("0"))
        facturado = sum((fact for _precio, fact in trozos), Decimal("0"))
        salida.append(
            DesvioApartadoOut(
                tarea_id=tarea.id,
                codigo=tarea.codigo,
                descripcion=tarea.descripcion,
                presupuestado=Decimal(tarea.importe_presupuestado),
                montaje=montaje_de(tarea.id),
                contrato_cliente=cliente_de(tarea),
                contratado=contratado,
                facturado=facturado,
                solo_gestion=bool(tarea.solo_gestion),
            )
        )
    salida.sort(key=lambda fila: fila.codigo)
    return salida


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
