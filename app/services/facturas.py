"""Ingesta, casado y revisión humana de facturas."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf
from sqlalchemy.orm import Session, joinedload

from app.models import Contratista, Contrato, Factura, LineaFactura, Proyecto
from app.schemas.factura import (
    ConfirmarFacturaIn,
    ConfirmarFacturaOut,
    ContratoCandidatoFacturaOut,
    FacturaImportacionOut,
    FacturaRevisionOut,
    FacturaResumenOut,
    LineaFacturaCreate,
)
from app.services import ocr

_NIF_RE = re.compile(r"\b(?:[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z])\b", re.IGNORECASE)


def importar_factura(
    db: Session,
    proyecto_id: int,
    contenido: bytes,
    nombre_fichero: str,
) -> FacturaImportacionOut:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")

    texto, es_escaneada = _extraer_texto(contenido, nombre_fichero)
    datos = _parsear_factura(texto)

    contratista = (
        db.query(Contratista)
        .filter(Contratista.nif == datos["contratista_nif"])
        .first()
    )
    if contratista is None:
        raise ValueError(
            f"No existe un contratista con NIF {datos['contratista_nif']}"
        )

    contratos = _contratos_candidatos(db, proyecto_id, contratista.id)
    contrato_sugerido = contratos[0] if len(contratos) == 1 else None

    factura = Factura(
        proyecto_id=proyecto_id,
        contratista_id=contratista.id,
        contrato_id=contrato_sugerido.id if contrato_sugerido else None,
        numero=datos["numero"],
        fecha_emision=datos["fecha_emision"],
        base_imponible=datos["base_imponible"],
        iva=datos["iva"],
        irpf=datos["irpf"],
        retencion_garantia=datos["retencion_garantia"],
        total=datos["total"],
        tipo=datos["tipo"],
        fichero_origen=Path(nombre_fichero).name,
        es_escaneada=es_escaneada,
        estado_revision="pendiente",
    )
    db.add(factura)
    db.flush()
    for linea in datos["lineas"]:
        db.add(
            LineaFactura(
                factura_id=factura.id,
                descripcion=linea.descripcion,
                importe=linea.importe,
            )
        )
    db.commit()

    return FacturaImportacionOut(
        factura_id=factura.id,
        contratista_nif=contratista.nif,
        contrato_id=factura.contrato_id,
        estado_revision=factura.estado_revision,
        requiere_revision=True,
    )


def listar_facturas(db: Session, proyecto_id: int) -> list[FacturaResumenOut]:
    if db.get(Proyecto, proyecto_id) is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    facturas = (
        db.query(Factura)
        .options(joinedload(Factura.contratista))
        .filter(Factura.proyecto_id == proyecto_id)
        .order_by(Factura.id.desc())
        .all()
    )
    return [_a_resumen(f) for f in facturas]


def obtener_factura(db: Session, factura_id: int) -> FacturaRevisionOut:
    factura = (
        db.query(Factura)
        .options(joinedload(Factura.contratista), joinedload(Factura.lineas))
        .filter(Factura.id == factura_id)
        .first()
    )
    if factura is None:
        raise ValueError(f"Factura {factura_id} no encontrada")
    if factura.proyecto_id is None:
        raise ValueError(f"La factura {factura_id} no tiene proyecto")

    candidatos = _contratos_candidatos(
        db, factura.proyecto_id, factura.contratista_id
    )
    resumen = _a_resumen(factura)
    return FacturaRevisionOut(
        **resumen.model_dump(),
        base_imponible=factura.base_imponible,
        iva=factura.iva,
        irpf=factura.irpf,
        retencion_garantia=factura.retencion_garantia,
        fichero_origen=factura.fichero_origen,
        lineas=sorted(factura.lineas, key=lambda linea: linea.id),
        contratos_candidatos=[
            ContratoCandidatoFacturaOut(
                id=contrato.id,
                contratista_nombre=(
                    contrato.contratista.nombre if contrato.contratista else "—"
                ),
                precio_total=contrato.precio_total,
            )
            for contrato in candidatos
        ],
    )


def confirmar_factura(
    db: Session,
    factura_id: int,
    payload: ConfirmarFacturaIn,
) -> ConfirmarFacturaOut:
    factura = db.get(Factura, factura_id)
    if factura is None:
        raise ValueError(f"Factura {factura_id} no encontrada")
    if factura.proyecto_id is None:
        raise ValueError(f"La factura {factura_id} no tiene proyecto")

    if payload.contrato_id is not None:
        contrato = db.get(Contrato, payload.contrato_id)
        if contrato is None:
            raise ValueError(f"Contrato {payload.contrato_id} no encontrado")
        if contrato.proyecto_id != factura.proyecto_id:
            raise ValueError("El contrato no pertenece al proyecto de la factura")
        if contrato.contratista_id != factura.contratista_id:
            raise ValueError("El contrato no pertenece al contratista de la factura")
        if contrato.estado_extraccion != "confirmada":
            raise ValueError("El contrato debe estar confirmado antes de enlazar la factura")

    factura.numero = payload.numero
    factura.fecha_emision = payload.fecha_emision
    factura.base_imponible = payload.base_imponible
    factura.iva = payload.iva
    factura.irpf = payload.irpf
    factura.retencion_garantia = payload.retencion_garantia
    factura.total = payload.total
    factura.tipo = payload.tipo
    factura.contrato_id = payload.contrato_id
    factura.estado_revision = "confirmada"

    db.query(LineaFactura).filter(
        LineaFactura.factura_id == factura.id
    ).delete(synchronize_session=False)
    for linea in payload.lineas:
        db.add(
            LineaFactura(
                factura_id=factura.id,
                descripcion=linea.descripcion.strip(),
                importe=linea.importe,
            )
        )
    db.commit()

    return ConfirmarFacturaOut(
        ok=True,
        factura_id=factura.id,
        proyecto_id=factura.proyecto_id,
        contrato_id=factura.contrato_id,
        estado_revision=factura.estado_revision,
    )


def _contratos_candidatos(
    db: Session,
    proyecto_id: int,
    contratista_id: int,
) -> list[Contrato]:
    return (
        db.query(Contrato)
        .options(joinedload(Contrato.contratista))
        .filter(
            Contrato.proyecto_id == proyecto_id,
            Contrato.contratista_id == contratista_id,
            Contrato.estado_extraccion == "confirmada",
        )
        .order_by(Contrato.id.desc())
        .all()
    )


def _a_resumen(factura: Factura) -> FacturaResumenOut:
    return FacturaResumenOut(
        id=factura.id,
        proyecto_id=factura.proyecto_id,
        numero=factura.numero,
        fecha_emision=factura.fecha_emision,
        contratista_nombre=(
            factura.contratista.nombre if factura.contratista else "—"
        ),
        contratista_nif=factura.contratista.nif if factura.contratista else "—",
        contrato_id=factura.contrato_id,
        total=factura.total,
        tipo=factura.tipo,
        es_escaneada=factura.es_escaneada,
        estado_revision=factura.estado_revision,
    )


def _extraer_texto(contenido: bytes, nombre_fichero: str) -> tuple[str, bool]:
    extension = Path(nombre_fichero).suffix.lower()
    if extension in {".md", ".txt"}:
        try:
            return contenido.decode("utf-8"), False
        except UnicodeDecodeError as exc:
            raise ValueError("La factura de texto no está codificada en UTF-8") from exc

    if ocr.es_extension_imagen(nombre_fichero):
        return ocr.ocr_imagen(contenido).texto, True

    if extension == ".pdf":
        try:
            documento = pymupdf.open(stream=contenido, filetype="pdf")
            try:
                texto = "\n".join(pagina.get_text() for pagina in documento)
            finally:
                documento.close()
        except Exception as exc:
            raise ValueError("No se pudo leer el PDF de la factura") from exc
        if ocr.pdf_parece_escaneado(texto):
            return ocr.ocr_paginas_pdf(contenido).texto, True
        return texto, False

    raise ValueError("Formato no admitido. Usa PDF, JPG, PNG, TIFF, WEBP o MD")


def _parsear_factura(texto: str) -> dict:
    nif_match = _NIF_RE.search(texto.upper())
    if nif_match is None:
        raise ValueError("No se ha detectado el NIF del contratista")

    numero = _campo_texto(texto, ("número", "numero", "factura"))
    if not numero:
        raise ValueError("No se ha detectado el número de factura")

    fecha_texto = _campo_texto(texto, ("fecha de emisión", "fecha emision", "fecha"))
    fecha_emision = _parsear_fecha(fecha_texto) if fecha_texto else None
    base = _campo_importe(texto, ("base imponible",))
    total = _campo_importe(texto, ("total factura", "total"))
    if base is None:
        raise ValueError("No se ha detectado la base imponible")
    if total is None:
        raise ValueError("No se ha detectado el total de la factura")

    tipo = (_campo_texto(texto, ("tipo",)) or "ordinaria").lower()
    if tipo not in {"ordinaria", "anticipo", "certificacion"}:
        tipo = "ordinaria"

    return {
        "contratista_nif": nif_match.group(0).upper(),
        "numero": numero,
        "fecha_emision": fecha_emision,
        "base_imponible": base,
        "iva": _campo_importe(texto, ("iva",)) or Decimal("0"),
        "irpf": _campo_importe(texto, ("irpf",)) or Decimal("0"),
        "retencion_garantia": (
            _campo_importe(texto, ("retención de garantía", "retencion de garantia"))
            or Decimal("0")
        ),
        "total": total,
        "tipo": tipo,
        "lineas": _parsear_lineas(texto),
    }


def _campo_texto(texto: str, etiquetas: tuple[str, ...]) -> str | None:
    for linea in texto.splitlines():
        limpia = linea.strip()
        for etiqueta in etiquetas:
            match = re.match(
                rf"^{re.escape(etiqueta)}\s*(?:n[.º°o]\s*)?[:#-]\s*(.+)$",
                limpia,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).strip()
    return None


def _campo_importe(texto: str, etiquetas: tuple[str, ...]) -> Decimal | None:
    for linea in texto.splitlines():
        limpia = linea.strip()
        for etiqueta in etiquetas:
            match = re.match(
                rf"^{re.escape(etiqueta)}(?:\s+\d+(?:[.,]\d+)?\s*%)?\s*[:#-]\s*(.+)$",
                limpia,
                flags=re.IGNORECASE,
            )
            if match:
                return _parsear_decimal(match.group(1))
    return None


def _parsear_decimal(valor: str) -> Decimal:
    limpio = re.sub(r"[^\d,.\-]", "", valor)
    if not limpio:
        raise ValueError(f"Importe no válido: {valor}")
    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif limpio.count(".") > 1:
        partes = limpio.split(".")
        limpio = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return Decimal(limpio).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Importe no válido: {valor}") from exc


def _parsear_fecha(valor: str) -> date:
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor.strip(), formato).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha de emisión no válida: {valor}")


def _parsear_lineas(texto: str) -> list[LineaFacturaCreate]:
    resultado: list[LineaFacturaCreate] = []
    en_lineas = False
    for linea in texto.splitlines():
        limpia = linea.strip()
        if limpia.lower() in {"líneas", "lineas", "detalle"}:
            en_lineas = True
            continue
        if not en_lineas or "|" not in limpia:
            continue
        descripcion, importe = limpia.rsplit("|", 1)
        if descripcion.strip():
            resultado.append(
                LineaFacturaCreate(
                    descripcion=descripcion.strip(),
                    importe=_parsear_decimal(importe),
                )
            )
    return resultado
