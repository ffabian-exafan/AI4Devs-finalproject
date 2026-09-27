"""Cliente LLM para extraer presupuestos y transcribir escaneos.

Proveedor por defecto: API de Claude (Messages).
Si `LLM_API_BASE` apunta a otro host, se usa chat/completions compatible.
"""

from __future__ import annotations

import json
import re
from urllib import error, request

from app.config import Settings

ANTHROPIC_HOST = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
MODELO_CLAUDE = "claude-sonnet-5"
MODELO_HAIKU = "claude-haiku-4-5"
MODELO_COMPATIBLE = "gpt-4o-mini"


def es_anthropic(settings: Settings) -> bool:
    """True si la clave debe ir a la API de Claude."""
    proveedor = (settings.llm_proveedor or "").strip().lower()
    if proveedor in {"anthropic", "claude"}:
        return True
    if proveedor in {"openai", "compatible"}:
        return False
    base = (settings.llm_api_base or "").strip().lower()
    if not base:
        return True
    return "anthropic.com" in base


def hay_llm(settings: Settings) -> bool:
    if not settings.llm_api_key:
        return False
    if es_anthropic(settings):
        return True
    return bool(settings.llm_api_base)


def modelo_texto(settings: Settings) -> str:
    if (settings.llm_model or "").strip():
        return settings.llm_model.strip()
    if es_anthropic(settings):
        return MODELO_CLAUDE
    return MODELO_COMPATIBLE


def modelo_transcripcion(settings: Settings) -> str:
    """Sonnet: pasa el PDF a markdown."""
    explicito = (settings.llm_modelo_transcripcion or "").strip()
    if explicito:
        return explicito
    if es_anthropic(settings):
        return MODELO_CLAUDE
    return modelo_texto(settings)


def modelo_extraccion(settings: Settings) -> str:
    """Haiku: lee el markdown ya transcrito. Más barato que repetir Sonnet."""
    explicito = (settings.llm_modelo_extraccion or "").strip()
    if explicito:
        return explicito
    if es_anthropic(settings):
        return MODELO_HAIKU
    return modelo_texto(settings)


def modelo_vision(settings: Settings) -> str:
    explicito = (settings.llm_vision_model or "").strip()
    # El valor por defecto histórico no existe en la API de Claude.
    if es_anthropic(settings):
        if explicito and explicito != MODELO_COMPATIBLE:
            return explicito
        return modelo_texto(settings)
    return explicito or MODELO_COMPATIBLE


def completar_texto(
    *,
    api_key: str,
    api_base: str | None,
    anthropic: bool,
    model: str,
    system: str,
    user: str,
    imagen_b64: str | None = None,
    mime: str | None = None,
    documento_b64: str | None = None,
    documento_mime: str | None = None,
    max_tokens: int = 16000,
) -> str:
    """Devuelve el texto del modelo. En Claude ignora bloques de pensamiento."""
    if anthropic:
        data = _post_anthropic(
            api_key=api_key,
            api_base=api_base,
            model=model,
            system=system,
            user=user,
            imagen_b64=imagen_b64,
            mime=mime,
            documento_b64=documento_b64,
            documento_mime=documento_mime,
            max_tokens=max_tokens,
        )
        return _texto_anthropic(data)
    data = _post_compatible(
        api_key=api_key,
        api_base=api_base or "",
        model=model,
        system=system,
        user=user,
        imagen_b64=imagen_b64,
        mime=mime,
    )
    return _texto_compatible(data)


def parsear_json_llm(contenido: str) -> dict:
    texto = contenido.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto)
    parsed = json.loads(texto)
    if not isinstance(parsed, dict):
        raise ValueError("el modelo no devolvió un objeto JSON")
    return parsed


def _url_messages(api_base: str | None) -> str:
    base = (api_base or ANTHROPIC_HOST).rstrip("/")
    if base.endswith("/messages"):
        return base
    if base.endswith("/v1"):
        return base + "/messages"
    return base + "/v1/messages"


def _post_anthropic(
    *,
    api_key: str,
    api_base: str | None,
    model: str,
    system: str,
    user: str,
    imagen_b64: str | None,
    mime: str | None,
    documento_b64: str | None,
    documento_mime: str | None,
    max_tokens: int,
) -> dict:
    bloques: list[dict] = []
    if documento_b64:
        bloques.append(
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": documento_mime or "application/pdf",
                    "data": documento_b64,
                },
            }
        )
    if imagen_b64:
        bloques.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime or "image/png",
                    "data": imagen_b64,
                },
            }
        )
    if bloques:
        bloques.append({"type": "text", "text": user})
        contenido: str | list[dict] = bloques
    else:
        contenido = user
    payload: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": contenido}],
    }
    # Sonnet 5 piensa por defecto y eso se come el tope de salida.
    if _conviene_apagar_pensamiento(model):
        payload["thinking"] = {"type": "disabled"}
    return _post(
        _url_messages(api_base),
        payload,
        {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
    )


def _post_compatible(
    *,
    api_key: str,
    api_base: str,
    model: str,
    system: str,
    user: str,
    imagen_b64: str | None,
    mime: str | None,
) -> dict:
    if imagen_b64:
        user_content: str | list[dict] = [
            {"type": "text", "text": user},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime or 'image/png'};base64,{imagen_b64}"},
            },
        ]
    else:
        user_content = user
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    }
    if imagen_b64 is None:
        payload["response_format"] = {"type": "json_object"}
    url = api_base.rstrip("/") + "/chat/completions"
    return _post(
        url,
        payload,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )


def _post(url: str, payload: dict, headers: dict[str, str]) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"LLM HTTP {exc.code}: {detalle}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"No se pudo contactar el LLM: {exc}") from exc


def _conviene_apagar_pensamiento(model: str) -> bool:
    nombre = model.lower()
    return "sonnet-5" in nombre or "opus-5" in nombre or "fable" in nombre


def _texto_anthropic(data: dict) -> str:
    partes: list[str] = []
    for bloque in data.get("content") or []:
        if isinstance(bloque, dict) and bloque.get("type") == "text":
            partes.append(str(bloque.get("text") or ""))
    texto = "\n".join(partes).strip()
    if not texto:
        raise RuntimeError("Claude no devolvió texto")
    return texto


def _texto_compatible(data: dict) -> str:
    try:
        texto = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("respuesta LLM inesperada") from exc
    if not str(texto).strip():
        raise RuntimeError("el LLM devolvió texto vacío")
    return str(texto)
