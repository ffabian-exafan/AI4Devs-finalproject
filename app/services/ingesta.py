"""Ingesta de presupuestos y contratos: lectura, extracción y persistencia."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pdfplumber
import pymupdf
from sqlalchemy.orm import Session

from app.models import Contratista, Contrato, Nave, Presupuesto, Proyecto, Tarea
from app.schemas.contrato import ImportarContratoOut
from app.schemas.extraccion import ContratoExtraido, NodoTareaExtraido, PresupuestoExtraido
from app.schemas.presupuesto import ImportarPresupuestoOut
from app.services import casado as casado_svc
from app.services import extraccion as extraccion_svc
from app.services import extraccion_contrato as extraccion_contrato_svc
from app.services import ocr as ocr_svc


@dataclass(frozen=True)
class DocumentoLeido:
    texto: str
    es_escaneado: bool


def leer_documento(contenido: bytes, nombre_fichero: str) -> DocumentoLeido:
    """
    Devuelve texto + si el origen es escaneado/imagen.

    - .md / texto: lectura directa (fixtures).
    - Imagen (jpg/png/tiff/…): OCR obligatorio.
    - PDF con texto útil: lectura nativa.
    - PDF sin texto útil: OCR (escaneado).
    """
    nombre = nombre_fichero.lower()
    if nombre.endswith(".md") or nombre.endswith(".txt"):
        return DocumentoLeido(texto=contenido.decode("utf-8"), es_escaneado=False)

    if _parece_texto(contenido):
        return DocumentoLeido(texto=contenido.decode("utf-8"), es_escaneado=False)

    if ocr_svc.es_extension_imagen(nombre) or _parece_imagen(contenido):
        resultado = ocr_svc.ocr_imagen(contenido)
        return DocumentoLeido(texto=resultado.texto, es_escaneado=True)

    texto = _leer_pdf_pymupdf(contenido)
    if not ocr_svc.pdf_parece_escaneado(texto):
        return DocumentoLeido(texto=texto, es_escaneado=False)

    texto_plumber = _leer_pdf_pdfplumber(contenido)
    if not ocr_svc.pdf_parece_escaneado(texto_plumber):
        return DocumentoLeido(texto=texto_plumber, es_escaneado=False)

    resultado = ocr_svc.ocr_paginas_pdf(contenido)
    return DocumentoLeido(texto=resultado.texto, es_escaneado=True)


def leer_fichero(ruta: Path | str) -> DocumentoLeido:
    path = Path(ruta)
    return leer_documento(path.read_bytes(), path.name)


def importar_presupuesto(
    db: Session,
    contenido: bytes,
    nombre_fichero: str,
) -> ImportarPresupuestoOut:
    """Lee, extrae, valida forma y persiste proyecto en pendiente de revisión."""
    leido = leer_documento(contenido, nombre_fichero)
    extraido = extraccion_svc.extraer_presupuesto(leido.texto)
    if leido.es_escaneado:
        extraido = extraido.model_copy(update={"requiere_revision": True})
    return persistir_presupuesto(
        db,
        extraido,
        nombre_fichero,
        es_escaneado=leido.es_escaneado,
    )


def persistir_presupuesto(
    db: Session,
    extraido: PresupuestoExtraido,
    nombre_fichero: str,
    *,
    es_escaneado: bool = False,
) -> ImportarPresupuestoOut:
    fecha = _parse_fecha(extraido.fecha)
    requiere = bool(extraido.requiere_revision or es_escaneado)

    proyecto = Proyecto(
        nombre=extraido.nombre_proyecto,
        tipo=extraido.tipo_proyecto,
        fecha_inicio=fecha,
        estado="pendiente_revision",
    )
    db.add(proyecto)
    db.flush()

    presupuesto = Presupuesto(
        proyecto_id=proyecto.id,
        version=extraido.version,
        fichero_origen=nombre_fichero,
        fecha=fecha,
        estado_extraccion="pendiente_revision" if requiere else "extraido",
        es_escaneado=es_escaneado,
    )
    db.add(presupuesto)
    db.flush()

    partidas = 0
    anotaciones = 0

    for nave_x in extraido.naves:
        nave = Nave(
            proyecto_id=proyecto.id,
            codigo=nave_x.codigo,
            descripcion=nave_x.descripcion,
            importe_presupuestado=nave_x.importe_presupuestado,
        )
        db.add(nave)
        db.flush()

        for ap in nave_x.apartados:
            if ap.tiene_anotacion_manual:
                anotaciones += 1
                estado_rev = "pendiente"
            else:
                estado_rev = "pendiente" if requiere else "revisada"

            tarea = Tarea(
                nave_id=nave.id,
                presupuesto_id=presupuesto.id,
                contrato_id=None,
                tarea_padre_id=None,
                contratista_id=None,
                codigo=ap.codigo,
                nivel="apartado",
                capitulo=ap.capitulo,
                descripcion=ap.descripcion,
                unidad=ap.unidad,
                cantidad=ap.cantidad,
                precio_unitario=ap.precio_unitario,
                importe_presupuestado=ap.importe,
                tiene_anotacion_manual=ap.tiene_anotacion_manual,
                estado_revision=estado_rev,
                estado="no_iniciada",
                avance_fisico_pct=Decimal("0"),
            )
            db.add(tarea)
            partidas += 1

    db.commit()
    db.refresh(proyecto)

    return ImportarPresupuestoOut(
        proyecto_id=proyecto.id,
        naves_detectadas=len(extraido.naves),
        partidas_detectadas=partidas,
        requiere_revision=requiere,
        anotaciones_manuscritas_detectadas=anotaciones,
        es_escaneado=es_escaneado,
    )


def importar_contrato(
    db: Session,
    proyecto_id: int,
    contenido: bytes,
    nombre_fichero: str,
    nave_id: int | None = None,
) -> ImportarContratoOut:
    """Lee, extrae y persiste un contrato enlazado al proyecto (árbol propio)."""
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")

    leido = leer_documento(contenido, nombre_fichero)
    extraido = extraccion_contrato_svc.extraer_contrato(leido.texto)
    return persistir_contrato(db, proyecto, extraido, nombre_fichero, nave_id)


def persistir_contrato(
    db: Session,
    proyecto: Proyecto,
    extraido: ContratoExtraido,
    nombre_fichero: str,
    nave_id: int | None = None,
) -> ImportarContratoOut:
    nave = _resolver_nave(db, proyecto, nave_id)
    contratista = _get_or_create_contratista(db, extraido)

    contrato = Contrato(
        proyecto_id=proyecto.id,
        nave_id=nave.id,
        contratista_id=contratista.id,
        referencia_presupuesto=extraido.referencia_presupuesto,
        precio_total=extraido.precio_total,
        fecha_firma=_parse_fecha(extraido.fecha_firma),
        plazo_ejecucion=_parse_fecha(extraido.plazo_ejecucion),
        condiciones_facturacion=extraido.condiciones_facturacion,
        fichero_origen=nombre_fichero,
        estado_extraccion="pendiente_revision"
        if extraido.requiere_revision
        else "extraido",
    )
    db.add(contrato)
    db.flush()

    for nodo in extraido.arbol_tareas:
        _persistir_nodo_tarea(
            db,
            nodo=nodo,
            nave_id=nave.id,
            contrato_id=contrato.id,
            contratista_id=contratista.id,
            tarea_padre_id=None,
            requiere_revision=extraido.requiere_revision,
        )

    db.commit()
    db.refresh(contrato)

    sugerencias = casado_svc.sugerir_apartados_para_contrato(db, contrato)

    return ImportarContratoOut(
        contrato_id=contrato.id,
        contratista_nif=contratista.nif,
        precio_total=contrato.precio_total,
        partidas_detalle_detectadas=extraido.partidas_detalle,
        requiere_revision=extraido.requiere_revision,
        sugerencias_apartado=sugerencias,
    )


def _resolver_nave(
    db: Session,
    proyecto: Proyecto,
    nave_id: int | None,
) -> Nave:
    if nave_id is not None:
        nave = db.get(Nave, nave_id)
        if nave is None or nave.proyecto_id != proyecto.id:
            raise ValueError(f"Nave {nave_id} no pertenece al proyecto {proyecto.id}")
        return nave

    existente = db.query(Nave).filter(Nave.proyecto_id == proyecto.id).order_by(Nave.id).first()
    if existente is not None:
        return existente

    # Contrato sin nave previa: crea una genérica para colgar el árbol
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave del proyecto",
        importe_presupuestado=Decimal("0"),
    )
    db.add(nave)
    db.flush()
    return nave


def _get_or_create_contratista(db: Session, extraido: ContratoExtraido) -> Contratista:
    existente = (
        db.query(Contratista).filter(Contratista.nif == extraido.contratista_nif).first()
    )
    if existente is not None:
        return existente
    contratista = Contratista(
        nif=extraido.contratista_nif,
        nombre=extraido.contratista_nombre,
        tipo=extraido.contratista_tipo,
        email=None,
    )
    db.add(contratista)
    db.flush()
    return contratista


def _persistir_nodo_tarea(
    db: Session,
    *,
    nodo: NodoTareaExtraido,
    nave_id: int,
    contrato_id: int,
    contratista_id: int,
    tarea_padre_id: int | None,
    requiere_revision: bool,
) -> Tarea:
    """Persiste el árbol del contrato sin enlazar a partidas de presupuesto."""
    tarea = Tarea(
        nave_id=nave_id,
        presupuesto_id=None,
        contrato_id=contrato_id,
        tarea_padre_id=tarea_padre_id,
        contratista_id=contratista_id,
        codigo=nodo.codigo,
        nivel=nodo.nivel,
        capitulo=nodo.capitulo,
        descripcion=nodo.descripcion,
        unidad=nodo.unidad,
        cantidad=nodo.cantidad,
        precio_unitario=nodo.precio_unitario,
        importe_presupuestado=nodo.importe,
        tiene_anotacion_manual=False,
        estado_revision="pendiente" if requiere_revision else "revisada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(tarea)
    db.flush()

    for hijo in nodo.hijos:
        _persistir_nodo_tarea(
            db,
            nodo=hijo,
            nave_id=nave_id,
            contrato_id=contrato_id,
            contratista_id=contratista_id,
            tarea_padre_id=tarea.id,
            requiere_revision=requiere_revision,
        )
    return tarea


def _parece_texto(contenido: bytes) -> bool:
    muestra = contenido[:200].lstrip()
    if muestra.startswith(b"%PDF"):
        return False
    if _parece_imagen(contenido):
        return False
    try:
        muestra.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _parece_imagen(contenido: bytes) -> bool:
    """Magic bytes habituales de imagen (por si la extensión falta o miente)."""
    if contenido.startswith(b"\xff\xd8\xff"):
        return True  # JPEG
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return True  # PNG
    if contenido.startswith(b"II*\x00") or contenido.startswith(b"MM\x00*"):
        return True  # TIFF
    if contenido.startswith(b"BM"):
        return True  # BMP
    if len(contenido) >= 12 and contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return True
    return False


def _leer_pdf_pymupdf(contenido: bytes) -> str:
    doc = pymupdf.open(stream=contenido, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _leer_pdf_pdfplumber(contenido: bytes) -> str:
    import io

    partes: list[str] = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t:
                partes.append(t)
    return "\n".join(partes)


def _parse_fecha(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        try:
            return datetime.strptime(valor, "%d/%m/%Y").date()
        except ValueError:
            return None
