"""PDF → Markdown con Sonnet.

Haiku no ve el PDF: solo el markdown, para no repetir los tokens del documento.
Presupuesto y contrato usan el mismo modelo de transcripción y un prompt distinto.
"""

from __future__ import annotations

import base64
import re

import pymupdf

from app.config import get_settings
from app.services import llm as llm_svc

# La API de Claude admite 100 páginas por documento. Dejamos margen.
PAGINAS_POR_LLAMADA = 80

_PROMPT = """\
Transcribes presupuestos de obra a Markdown fiel.
Devuelves solo Markdown, sin explicación ni bloque de código.
Conserva códigos, descripciones, unidades, cantidades, precios e importes tal como aparecen.
Usa tablas markdown para las partidas.
Si una anotación manuscrita corrige un valor impreso, deja el valor manuscrito y escribe al lado «(manuscrito)».
No inventes cifras ni apartados que no se lean.
"""

_PEDIDO = (
    "Transforma este PDF de presupuesto a Markdown. "
    "No resumas. No calcules importes que el documento no muestre."
)


_PROMPT_CONTRATO = """\
Transcribes contratos de subcontrata de obra a Markdown fiel.
Devuelves solo Markdown, sin explicación ni bloque de código.
Conserva contratista, NIF, objeto, precio total, fechas, condiciones de facturación
y el desglose (códigos, descripciones, unidades, cantidades, precios e importes).
Usa tablas markdown para las partidas.
Si una anotación manuscrita corrige un valor impreso, deja el valor manuscrito y escribe al lado «(manuscrito)».
No inventes cifras, partidas ni datos del contratista que no se lean.
"""

_PEDIDO_CONTRATO = (
    "Transforma este PDF de contrato de subcontrata a Markdown. "
    "No resumas. No calcules importes que el documento no muestre."
)


def transcribir_pdf_a_markdown(contenido: bytes) -> str:
    """Una llamada a Sonnet por tramo de páginas. Devuelve el markdown unido."""
    return _transcribir(contenido, _PROMPT, _PEDIDO, "presupuesto")


def transcribir_contrato_a_markdown(contenido: bytes) -> str:
    """Igual que el presupuesto: Sonnet ve el PDF y devuelve markdown."""
    return _transcribir(contenido, _PROMPT_CONTRATO, _PEDIDO_CONTRATO, "contrato")


def _transcribir(contenido: bytes, system: str, pedido: str, documento: str) -> str:
    settings = get_settings()
    if not (llm_svc.hay_llm(settings) and llm_svc.es_anthropic(settings)):
        raise ValueError("La transcripción a markdown pide la API de Claude")

    partes: list[str] = []
    try:
        for trozo in _trozos_pdf(contenido):
            texto = llm_svc.completar_texto(
                api_key=settings.llm_api_key or "",
                api_base=settings.llm_api_base,
                anthropic=True,
                model=llm_svc.modelo_transcripcion(settings),
                system=system,
                user=pedido,
                documento_b64=base64.b64encode(trozo).decode("ascii"),
                documento_mime="application/pdf",
                max_tokens=16000,
            )
            limpio = _markdown_limpio(texto)
            if limpio:
                partes.append(limpio)
    except RuntimeError as exc:
        raise ValueError(f"No se pudo transcribir el PDF con Sonnet: {exc}") from exc

    if not partes:
        raise ValueError(f"Sonnet no devolvió markdown del {documento}")
    return "\n\n".join(partes)


def _trozos_pdf(contenido: bytes) -> list[bytes]:
    doc = pymupdf.open(stream=contenido, filetype="pdf")
    try:
        if doc.page_count <= PAGINAS_POR_LLAMADA:
            return [contenido]
        trozos: list[bytes] = []
        for inicio in range(0, doc.page_count, PAGINAS_POR_LLAMADA):
            fin = min(inicio + PAGINAS_POR_LLAMADA, doc.page_count) - 1
            parte = pymupdf.open()
            try:
                parte.insert_pdf(doc, from_page=inicio, to_page=fin)
                trozos.append(parte.tobytes())
            finally:
                parte.close()
        return trozos
    finally:
        doc.close()


def _markdown_limpio(texto: str) -> str:
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```(?:markdown|md)?\s*", "", limpio)
        limpio = re.sub(r"\s*```$", "", limpio)
    return limpio.strip()
