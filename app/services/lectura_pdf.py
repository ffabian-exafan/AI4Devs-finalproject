"""Elige si un PDF se lee del texto local o lo tiene que ver Sonnet.

Sonnet queda para el PDF sin texto, la casilla de manuscrito, una anotación
de corrección y el caso en que el vistazo ve bolígrafo o falla.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import pymupdf

from app.config import get_settings
from app.services import llm as llm_svc
from app.services import ocr as ocr_svc

Via = Literal["texto_local", "sonnet"]

# Tipos de anotación que pueden tapar una cifra. La firma (Widget) y el sello
# (Stamp) no entran: un contrato firmado en digital seguiría pagando Sonnet.
_TIPOS_CORRECCION = frozenset(
    {"Ink", "StrikeOut", "Squiggly", "Caret", "Highlight", "Underline", "FreeText"}
)

_PROMPT_VISTA = """\
Miras un PDF de obra solo para detectar bolígrafo.
Respondes solo JSON: {"tiene_manuscrito": true} o {"tiene_manuscrito": false}.
true si un tachón, una cifra escrita a mano o una corrección tapa o cambia un valor impreso.
false si todo es texto impreso, firma digital o sello, sin corrección encima de una cifra.
No transcribas el documento y no inventes importes.
"""


@dataclass(frozen=True)
class DecisionLectura:
    via: Via
    es_escaneado: bool
    texto_local: str
    motivo: str


def decidir_lectura_pdf(
    contenido: bytes,
    *,
    forzar_vision: bool,
    detectar_manuscrito: Callable[[bytes], bool],
) -> DecisionLectura:
    texto = _texto_pdf(contenido)
    escaneado = ocr_svc.pdf_parece_escaneado(texto)
    if escaneado:
        return DecisionLectura("sonnet", True, texto, "sin_texto")
    if forzar_vision:
        return DecisionLectura("sonnet", False, texto, "forzar")
    if _tiene_anotacion_de_correccion(contenido):
        return DecisionLectura("sonnet", False, texto, "anotacion")
    try:
        hay_manuscrito = detectar_manuscrito(contenido)
    except Exception:
        return DecisionLectura("sonnet", False, texto, "detector_fallo")
    if hay_manuscrito:
        return DecisionLectura("sonnet", False, texto, "manuscrito")
    return DecisionLectura("texto_local", False, texto, "limpio")


def detectar_manuscrito_haiku(contenido: bytes) -> bool:
    """True si Haiku ve un tachón. Si la respuesta no es un bool, lanza ValueError."""
    settings = get_settings()
    if not (llm_svc.hay_llm(settings) and llm_svc.es_anthropic(settings)):
        raise ValueError("El vistazo de manuscrito pide la API de Claude")
    texto = llm_svc.completar_texto(
        api_key=settings.llm_api_key or "",
        api_base=settings.llm_api_base,
        anthropic=True,
        model=llm_svc.modelo_extraccion(settings),
        system=_PROMPT_VISTA,
        user="¿Hay una corrección manuscrita sobre un valor impreso?",
        documento_b64=base64.b64encode(contenido).decode("ascii"),
        documento_mime="application/pdf",
        max_tokens=200,
    )
    parsed = llm_svc.parsear_json_llm(texto)
    valor = parsed.get("tiene_manuscrito")
    if not isinstance(valor, bool):
        raise ValueError("el vistazo no devolvió tiene_manuscrito como bool")
    return valor


def _texto_pdf(contenido: bytes) -> str:
    doc = pymupdf.open(stream=contenido, filetype="pdf")
    try:
        texto = "\n".join(pagina.get_text() for pagina in doc)
    finally:
        doc.close()
    if not ocr_svc.pdf_parece_escaneado(texto):
        return texto
    return _texto_pdfplumber(contenido) or texto


def _texto_pdfplumber(contenido: bytes) -> str:
    import io

    import pdfplumber

    partes: list[str] = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            extraido = pagina.extract_text() or ""
            if extraido:
                partes.append(extraido)
    return "\n".join(partes)


def _tiene_anotacion_de_correccion(contenido: bytes) -> bool:
    doc = pymupdf.open(stream=contenido, filetype="pdf")
    try:
        for pagina in doc:
            anotaciones = pagina.annots()
            if anotaciones is None:
                continue
            for anotacion in anotaciones:
                nombre = anotacion.type[1] if anotacion.type else ""
                if nombre in _TIPOS_CORRECCION:
                    return True
        return False
    finally:
        doc.close()
