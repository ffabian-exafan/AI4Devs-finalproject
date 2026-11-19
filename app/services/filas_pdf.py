"""Filas de una oferta cuyo importe va en euros, al lado del concepto.

El cierre que suma al resto, y la misma cifra repetida en la portada, no son
otra partida: si se guardan, el contraste cuenta el total dos veces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

import pymupdf

_IMPORTE = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}")
_LETRAS = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")


@dataclass(frozen=True)
class FilaOferta:
    descripcion: str
    importe: Decimal


def filas_oferta(contenido: bytes) -> list[FilaOferta]:
    """Conceptos con cifra en euros. Vacío si el PDF no trae ese cuadro."""
    try:
        doc = pymupdf.open(stream=contenido, filetype="pdf")
    except Exception:
        return []
    try:
        encontradas: list[FilaOferta] = []
        for page in doc:
            lineas = _lineas(page)
            for y, x, _derecha, texto in lineas:
                if "€" not in texto:
                    continue
                hallado = _IMPORTE.search(texto)
                if hallado is None:
                    continue
                etiqueta = _etiqueta(lineas, y, x)
                letras = len(_LETRAS.findall(etiqueta))
                if letras < 8 or letras > 120:
                    continue
                encontradas.append(
                    FilaOferta(descripcion=etiqueta, importe=_decimal(hallado.group()))
                )
    finally:
        doc.close()
    return _sin_cierre(encontradas)


def _lineas(page) -> list[tuple[float, float, float, str]]:
    lineas: list[tuple[float, float, float, str]] = []
    for bloque in page.get_text("dict")["blocks"]:
        if bloque.get("type") != 0:
            continue
        for line in bloque.get("lines", []):
            texto = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if texto:
                caja = line["bbox"]
                lineas.append((caja[1], caja[0], caja[2], texto))
    return lineas


def _etiqueta(lineas: list[tuple[float, float, float, str]], y: float, x: float) -> str:
    trozos = [
        texto
        for ly, _lx, derecha, texto in lineas
        if abs(ly - y) <= 8 and derecha < x - 8 and "€" not in texto
    ]
    return re.sub(r"\s+", " ", " ".join(trozos)).strip()


def _decimal(texto: str) -> Decimal:
    return Decimal(texto.replace(".", "").replace(",", "."))


def _sin_cierre(filas: list[FilaOferta]) -> list[FilaOferta]:
    """Quita la cifra que es la suma de las demás, también si la portada la repite."""
    cifras = {fila.importe for fila in filas}
    cierre = {
        cifra
        for cifra in cifras
        if cifra > 0 and cifra == sum(otra for otra in cifras if otra != cifra)
    }
    if len(cifras - cierre) < 2:
        return filas
    return [fila for fila in filas if fila.importe not in cierre]
