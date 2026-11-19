"""Lee horas, fecha y anotación manuscrita de un parte. Las pruebas sustituyen extraer_campos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pymupdf

from app.config import get_settings
from app.services import llm as llm_svc
from app.services import ocr

AVISO_SIN_HORAS = "No se han leído las horas. Escríbelas."

_SISTEMA = (
    "Lees un parte de trabajo. Responde solo un objeto JSON con las claves "
    "horas (número o null), fecha (YYYY-MM-DD o null) y tiene_anotacion_manual "
    "(true si una cifra escrita a mano corrige un valor impreso). "
    "No inventes horas que no estén en el documento. No añadas texto fuera del JSON."
)


@dataclass(frozen=True)
class CamposParte:
    horas: Decimal | None
    fecha: date | None
    tiene_anotacion_manual: bool


def texto_de_parte(contenido: bytes, nombre: str) -> tuple[str, bool]:
    """Devuelve el texto y si la lectura es de un escaneo."""
    extension = Path(nombre).suffix.lower()
    if extension in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        return ocr.ocr_imagen(contenido).texto, True
    if extension != ".pdf":
        raise ValueError("El parte tiene que ser un PDF o una imagen.")
    documento = pymupdf.open(stream=contenido, filetype="pdf")
    try:
        texto = "\n".join(pagina.get_text() for pagina in documento)
    finally:
        documento.close()
    if ocr.pdf_parece_escaneado(texto):
        return ocr.ocr_paginas_pdf(contenido).texto, True
    return texto, False


def extraer_campos(texto: str) -> CamposParte:
    settings = get_settings()
    if not llm_svc.hay_llm(settings):
        raise RuntimeError("No hay modelo para leer el parte")
    crudo = llm_svc.completar_texto(
        api_key=settings.llm_api_key or "",
        api_base=settings.llm_api_base,
        anthropic=llm_svc.es_anthropic(settings),
        model=llm_svc.modelo_extraccion(settings),
        system=_SISTEMA,
        user=texto or "(sin texto)",
        max_tokens=400,
    )
    datos = llm_svc.parsear_json_llm(crudo)
    return CamposParte(
        horas=_horas(datos.get("horas")),
        fecha=_fecha(datos.get("fecha")),
        tiene_anotacion_manual=bool(datos.get("tiene_anotacion_manual")),
    )


def leer_campos(contenido: bytes, nombre: str) -> tuple[bool, CamposParte]:
    """Si la lectura falla, devuelve horas vacías para dejar el parte pendiente."""
    try:
        texto, escaneado = texto_de_parte(contenido, nombre)
    except Exception:
        return True, CamposParte(None, None, False)
    try:
        return escaneado, extraer_campos(texto)
    except Exception:
        return escaneado, CamposParte(None, None, False)


def _horas(valor: object) -> Decimal | None:
    if valor is None or valor == "":
        return None
    try:
        cifra = Decimal(str(valor))
    except Exception:
        return None
    if cifra <= 0:
        return None
    return cifra.quantize(Decimal("0.01"))


def _fecha(valor: object) -> date | None:
    if not valor or not isinstance(valor, str):
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None
