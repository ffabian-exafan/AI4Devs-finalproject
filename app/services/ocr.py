"""OCR de escaneados sin instalar nada en el sistema.

Orden de motores (el primero disponible gana):
1. OCR cloud dedicado (`OCR_API_KEY` + `OCR_API_BASE`)
2. Visión vía Claude o LLM compatible (`LLM_API_KEY`; `LLM_API_BASE` si no es Claude)
3. Tesseract local — solo si está instalado; no es obligatorio

Los documentos de obra son [SENSIBLE]: el cloud exige autorización de Seguridad
y cláusula [NO-ENTRENAR].
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass
from urllib import error, request

from app.config import get_settings
from app.services import llm as llm_svc

# Umbral: por debajo, un PDF se trata como escaneado
MIN_CHARS_TEXTO_NATIVO = 40

_PROMPT_OCR = (
    "Transcribe TODO el texto visible del documento escaneado, "
    "en el idioma original (español). Conserva números, importes, "
    "códigos de apartado y saltos de línea razonables. "
    "No inventes contenido que no se lea. Devuelve solo el texto."
)


@dataclass(frozen=True)
class ResultadoOcr:
    texto: str
    motor: str


def es_extension_imagen(nombre_fichero: str) -> bool:
    nombre = nombre_fichero.lower()
    return nombre.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"))


def pdf_parece_escaneado(texto_extraido: str) -> bool:
    """True si el PDF no aporta texto útil (solo imagen)."""
    return len((texto_extraido or "").strip()) < MIN_CHARS_TEXTO_NATIVO


def ocr_imagen(contenido: bytes, *, lang: str = "spa") -> ResultadoOcr:
    """OCR de bytes de imagen (JPG/PNG/TIFF/…). Sin dependencias de sistema."""
    png, mime = _a_png(contenido)
    return _ocr_bytes(png, mime=mime, lang=lang)


def ocr_paginas_pdf(contenido: bytes, *, lang: str = "spa", dpi: int = 200) -> ResultadoOcr:
    """Rasteriza páginas del PDF con PyMuPDF (pip) y pasa OCR a cada una."""
    import pymupdf

    doc = pymupdf.open(stream=contenido, filetype="pdf")
    try:
        partes: list[str] = []
        motores: list[str] = []
        for pagina in doc:
            pix = pagina.get_pixmap(dpi=dpi)
            png = pix.tobytes("png")
            r = _ocr_bytes(png, mime="image/png", lang=lang)
            if r.texto.strip():
                partes.append(r.texto.strip())
                motores.append(r.motor)
        texto = "\n\n".join(partes)
        if not texto.strip():
            raise ValueError(
                "OCR no obtuvo texto del PDF escaneado. "
                "Revisa la calidad del escaneo o confirma en revisión manual."
            )
        motor = motores[0] if motores else "desconocido"
        return ResultadoOcr(texto=texto, motor=f"{motor}+pymupdf")
    finally:
        doc.close()


def _ocr_bytes(contenido: bytes, *, mime: str, lang: str) -> ResultadoOcr:
    settings = get_settings()
    errores: list[str] = []

    if settings.ocr_api_key and settings.ocr_api_base:
        try:
            return _ocr_api_dedicada(
                contenido,
                mime=mime,
                lang=lang,
                api_key=settings.ocr_api_key,
                api_base=settings.ocr_api_base,
            )
        except ValueError as exc:
            errores.append(f"OCR cloud: {exc}")

    if llm_svc.hay_llm(settings):
        try:
            return _ocr_llm_vision(
                contenido,
                mime=mime,
                api_key=settings.llm_api_key,
                api_base=settings.llm_api_base,
                model=llm_svc.modelo_vision(settings),
                anthropic=llm_svc.es_anthropic(settings),
            )
        except ValueError as exc:
            errores.append(f"LLM visión: {exc}")

    # Opcional: Tesseract si el entorno lo tiene (no requerido)
    try:
        return _ocr_tesseract_opcional(contenido, lang=lang)
    except ValueError as exc:
        errores.append(str(exc))

    detalle = " | ".join(errores) if errores else "sin motores configurados"
    raise ValueError(
        "No hay OCR usable sin instalar nada en el sistema. "
        "Configura OCR_API_KEY + OCR_API_BASE, o LLM_API_KEY + LLM_API_BASE "
        "(visión), con autorización de Seguridad. "
        f"Detalle: {detalle}"
    )


def _ocr_api_dedicada(
    contenido: bytes,
    *,
    mime: str,
    lang: str,
    api_key: str,
    api_base: str,
) -> ResultadoOcr:
    """
    Contrato simple (OCR_API_BASE = URL completa del endpoint):

    POST {OCR_API_BASE}
    Authorization: Bearer …
    {"image_base64": "…", "mime_type": "image/png", "language": "spa"}
    → {"text": "…"}
    """
    url = api_base.rstrip("/")
    payload = {
        "image_base64": base64.b64encode(contenido).decode("ascii"),
        "mime_type": mime,
        "language": lang,
    }
    data = _post_json(url, payload, api_key)
    texto = _extraer_texto_respuesta(data)
    if not texto.strip():
        raise ValueError("la API OCR devolvió texto vacío")
    return ResultadoOcr(texto=texto, motor="ocr_cloud")


def _ocr_llm_vision(
    contenido: bytes,
    *,
    mime: str,
    api_key: str,
    api_base: str | None,
    model: str,
    anthropic: bool = False,
) -> ResultadoOcr:
    """Visión: API de Claude o chat/completions multimodal. Sin binarios locales."""
    b64 = base64.b64encode(contenido).decode("ascii")
    try:
        texto = llm_svc.completar_texto(
            api_key=api_key,
            api_base=api_base,
            anthropic=anthropic,
            model=model,
            system="Transcribes documentos de obra. No inventas texto.",
            user=_PROMPT_OCR,
            imagen_b64=b64,
            mime=mime,
            max_tokens=8000,
        )
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc
    return ResultadoOcr(texto=texto, motor="claude_vision" if anthropic else "llm_vision")


def _ocr_tesseract_opcional(contenido: bytes, *, lang: str) -> ResultadoOcr:
    """Fallback local si alguien tiene Tesseract; nunca es requisito."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Tesseract/pytesseract no disponible (opcional)") from exc

    imagen = Image.open(io.BytesIO(contenido))
    try:
        texto = pytesseract.image_to_string(imagen, lang=f"{lang}+eng") or ""
    except Exception:
        try:
            texto = pytesseract.image_to_string(imagen, lang="eng") or ""
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Tesseract falló: {exc}") from exc

    if not texto.strip():
        raise ValueError("Tesseract no obtuvo texto")
    return ResultadoOcr(texto=texto, motor="tesseract")


def _a_png(contenido: bytes) -> tuple[bytes, str]:
    """Normaliza a PNG en memoria (Pillow vía pip; sin binarios del SO)."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError(
            "Falta Pillow (pip install pillow) para leer imágenes"
        ) from exc

    try:
        imagen = Image.open(io.BytesIO(contenido))
        if imagen.mode not in ("RGB", "L"):
            imagen = imagen.convert("RGB")
        buf = io.BytesIO()
        imagen.save(buf, format="PNG")
        return buf.getvalue(), "image/png"
    except Exception as exc:  # noqa: BLE001
        raise ValueError("No se pudo abrir la imagen del presupuesto") from exc


def _post_json(url: str, payload: dict, api_key: str) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace")[:300]
        raise ValueError(f"HTTP {exc.code}: {detalle}") from exc
    except error.URLError as exc:
        raise ValueError(f"no se pudo contactar {url}: {exc}") from exc


def _extraer_texto_respuesta(data: dict) -> str:
    if isinstance(data.get("text"), str):
        return data["text"]
    if isinstance(data.get("texto"), str):
        return data["texto"]
    # Algunos proveedores anidan el resultado
    if isinstance(data.get("result"), dict) and isinstance(data["result"].get("text"), str):
        return data["result"]["text"]
    raise ValueError(f"respuesta OCR sin campo text: claves={list(data.keys())}")
