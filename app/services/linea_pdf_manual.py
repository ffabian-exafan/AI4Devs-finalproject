"""Alta, edición y borrado de un importe del PDF que la lectura no trajo."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from app.models import (
    Contrato,
    ContratoApartado,
    LineaPdfCliente,
    LineaPdfClienteTarea,
    Presupuesto,
    Proyecto,
    Tarea,
)
from app.schemas.presupuesto import ContrastarClienteOut


def crear(
    db: Session,
    proyecto_id: int,
    codigo: str,
    descripcion: str,
    importe: Decimal,
) -> ContrastarClienteOut:
    presupuesto = _presupuesto_pdf(db, proyecto_id)
    max_orden = (
        db.query(func.max(LineaPdfCliente.orden))
        .filter(LineaPdfCliente.presupuesto_id == presupuesto.id)
        .scalar()
    )
    orden = 0 if max_orden is None else int(max_orden) + 1
    db.add(
        LineaPdfCliente(
            presupuesto_id=presupuesto.id,
            orden=orden,
            tipo="importe",
            codigo=codigo[:128],
            descripcion=descripcion[:512],
            importe=_centimos(importe),
            importe_bruto=None,
            es_manuscrito=False,
            es_manual=True,
            relacion_intentada=False,
        )
    )
    db.flush()
    from app.services.presupuesto_excel import _proponer_relaciones, _salida_contraste

    _proponer_relaciones(db, proyecto_id, presupuesto.id)
    db.commit()
    return _salida_contraste(db, presupuesto)


def editar(
    db: Session,
    proyecto_id: int,
    linea_id: int,
    codigo: str,
    descripcion: str,
    importe: Decimal,
) -> ContrastarClienteOut:
    linea, presupuesto = _linea_manual(db, proyecto_id, linea_id)
    linea.codigo = codigo[:128]
    linea.descripcion = descripcion[:512]
    linea.importe = _centimos(importe)
    if linea.apartado_gestion_id is not None:
        apartado = db.get(Tarea, linea.apartado_gestion_id)
        if apartado is not None:
            apartado.descripcion = linea.descripcion
            apartado.importe_presupuestado = linea.importe
            apartado.importe_contrato_cliente = linea.importe
        db.commit()
    else:
        confirmados = _tareas_confirmadas(db, linea.id)
        if confirmados:
            from app.services.presupuesto_excel import confirmar_importes_cliente

            confirmar_importes_cliente(
                db, proyecto_id, confirmados, linea.importe, linea.id
            )
        else:
            db.commit()
    from app.services.presupuesto_excel import _salida_contraste

    return _salida_contraste(db, presupuesto)


def borrar(db: Session, proyecto_id: int, linea_id: int) -> None:
    linea, _presupuesto = _linea_manual(db, proyecto_id, linea_id)
    if linea.apartado_gestion_id is not None:
        tarea_id = linea.apartado_gestion_id
        enlazado = (
            db.query(Contrato.id).filter(Contrato.tarea_apartado_id == tarea_id).first()
            or db.query(ContratoApartado.contrato_id)
            .filter(ContratoApartado.tarea_id == tarea_id)
            .first()
        )
        if enlazado:
            raise ValueError("Hay un contrato enlazado a este apartado")
        linea.apartado_gestion_id = None
        db.flush()
        apartado = db.get(Tarea, tarea_id)
        if apartado is not None:
            db.delete(apartado)
    else:
        for tarea_id in _tareas_confirmadas(db, linea.id):
            tarea = db.get(Tarea, tarea_id)
            if tarea is not None:
                tarea.importe_contrato_cliente = None
    db.execute(delete(LineaPdfClienteTarea).where(LineaPdfClienteTarea.linea_id == linea.id))
    db.delete(linea)
    db.commit()


def copiar_al_presupuesto(db: Session, proyecto_id: int, presupuesto_id: int) -> None:
    """Copia las líneas manuales del PDF anterior, detrás de las recién leídas."""
    anterior = (
        db.query(Presupuesto)
        .filter(
            Presupuesto.proyecto_id == proyecto_id,
            Presupuesto.formato == "pdf_cliente",
            Presupuesto.id != presupuesto_id,
        )
        .order_by(Presupuesto.id.desc())
        .first()
    )
    if anterior is None:
        return
    manuales = (
        db.query(LineaPdfCliente)
        .filter(
            LineaPdfCliente.presupuesto_id == anterior.id,
            LineaPdfCliente.tipo == "importe",
            LineaPdfCliente.es_manual.is_(True),
        )
        .order_by(LineaPdfCliente.orden, LineaPdfCliente.id)
        .all()
    )
    if not manuales:
        return
    max_orden = (
        db.query(func.max(LineaPdfCliente.orden))
        .filter(LineaPdfCliente.presupuesto_id == presupuesto_id)
        .scalar()
    )
    orden = 0 if max_orden is None else int(max_orden) + 1
    for vieja in manuales:
        confirmados = _tareas_confirmadas(db, vieja.id)
        nueva = LineaPdfCliente(
            presupuesto_id=presupuesto_id,
            orden=orden,
            tipo="importe",
            codigo=vieja.codigo,
            descripcion=vieja.descripcion,
            importe=vieja.importe,
            importe_bruto=None,
            es_manuscrito=False,
            es_manual=True,
            relacion_intentada=bool(confirmados) or vieja.apartado_gestion_id is not None,
        )
        db.add(nueva)
        db.flush()
        for tarea_id in confirmados:
            db.add(
                LineaPdfClienteTarea(
                    linea_id=nueva.id,
                    tarea_id=tarea_id,
                    es_sugerencia=False,
                )
            )
        if vieja.apartado_gestion_id is not None:
            tarea_id = vieja.apartado_gestion_id
            vieja.apartado_gestion_id = None
            db.flush()
            nueva.apartado_gestion_id = tarea_id
        orden += 1
    db.flush()


def _presupuesto_pdf(db: Session, proyecto_id: int) -> Presupuesto:
    if db.get(Proyecto, proyecto_id) is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    from app.services.presupuesto_excel import _ultimo_pdf_cliente

    presupuesto = _ultimo_pdf_cliente(db, proyecto_id)
    if presupuesto is None:
        raise ValueError("Esta obra no tiene PDF del cliente")
    return presupuesto


def _linea_manual(db: Session, proyecto_id: int, linea_id: int) -> tuple[LineaPdfCliente, Presupuesto]:
    presupuesto = _presupuesto_pdf(db, proyecto_id)
    linea = db.get(LineaPdfCliente, linea_id)
    if linea is None or linea.presupuesto_id != presupuesto.id:
        raise ValueError("Línea del PDF no encontrada")
    if linea.tipo != "importe" or not linea.es_manual:
        raise ValueError("Solo se puede cambiar una línea añadida a mano")
    return linea, presupuesto


def _tareas_confirmadas(db: Session, linea_id: int) -> list[int]:
    filas = (
        db.query(LineaPdfClienteTarea.tarea_id)
        .filter(
            LineaPdfClienteTarea.linea_id == linea_id,
            LineaPdfClienteTarea.es_sugerencia.is_(False),
        )
        .all()
    )
    return [fila.tarea_id for fila in filas]


def _centimos(importe: Decimal) -> Decimal:
    return Decimal(importe).quantize(Decimal("0.01"))
