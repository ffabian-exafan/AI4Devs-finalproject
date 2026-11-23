"""Sello azul que se estampa en el PDF al confirmar una factura."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pymupdf

# Azul de boli, como el sello de papel. Sin borde.
AZUL = (0.0, 0.2, 0.85)
# Verde de boli para la certificación de montaje. Sin borde.
VERDE = (0.0, 0.45, 0.18)
_TAMANO = 8
_INTERLINEADO = 10
_MARGEN = 18
_RELLENO = 3
# Por debajo de esto el píxel cuenta como tinta. El blanco de la hoja queda libre.
_UMBRAL_TINTA = 245
_CELDA = 4
_IMAGENES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
_CODIGO = re.compile(r"^(PYCON|PYEQU)(\d{6})", re.IGNORECASE)
_SERIE_1 = re.compile(r"^1-\d{6}(?:ADM)?$", re.IGNORECASE)
_FUENTES = (
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


@dataclass(frozen=True)
class DatosSello:
    obra: str
    codigo: str | None
    referencia_alc: str
    nombre: str
    fecha: date
    presupuestado: Decimal
    ordinal: int
    importe_factura: Decimal
    pendiente: Decimal


def lineas_sello(datos: DatosSello) -> list[str]:
    ordinal = datos.ordinal if datos.ordinal >= 1 else 1
    return [
        f"Ref. {datos.obra}",
        linea_codigo(datos.codigo),
        f"ALC/{datos.referencia_alc}",
        f"{datos.nombre} - {datos.fecha.strftime('%d/%m/%Y')}",
        f"Presupuestado: {euros(datos.presupuestado)}",
        f"{ordinal}ª factura: {euros(datos.importe_factura)}",
        f"Pendiente: {euros(datos.pendiente)}",
    ]


def lineas_certificacion(nombre: str, fecha: date, codigo: str | None) -> list[str]:
    """Sello verde: nombre, fecha y PYCON (o PYEQU / serie 1)."""
    return [
        "Certificación de montaje",
        (nombre or "").strip() or "—",
        fecha.strftime("%d/%m/%Y"),
        linea_codigo(codigo),
    ]


def linea_codigo(codigo: str | None) -> str:
    """PYCON/123 - TRABAJO/45 a partir de PYCON123456.

    Los 3 primeros dígitos son el proyecto y el 4º y el 5º el trabajo.
    El 6º no se imprime. En serie 1 el sello lleva el código entero
    (pedido de cinco dígitos más el dígito de contrato).
    """
    texto = re.sub(r"\s+", "", codigo or "").upper()
    if _SERIE_1.fullmatch(texto):
        return texto
    hallazgo = _CODIGO.match(texto)
    if hallazgo is None:
        return "PYCON/— - TRABAJO/—"
    prefijo, digitos = hallazgo.group(1), hallazgo.group(2)
    return f"{prefijo}/{digitos[:3]} - TRABAJO/{digitos[3:5]}"


def euros(valor: Decimal) -> str:
    cuantia = Decimal(valor).quantize(Decimal("0.01"))
    signo = "-" if cuantia < 0 else ""
    entero, decimal = f"{abs(cuantia):.2f}".split(".")
    grupos: list[str] = []
    while entero:
        grupos.append(entero[-3:])
        entero = entero[:-3]
    return f"{signo}{'.'.join(reversed(grupos))},{decimal} €"


def pdf_con_sello(
    origen: Path | None,
    lineas: list[str],
    color: tuple[float, float, float] = AZUL,
) -> bytes:
    """Devuelve el PDF de la factura con el sello en un hueco en blanco.

    Si el origen no es un PDF ni una imagen, el resultado es una hoja en blanco
    con el sello. El color por defecto es el azul; la certificación de montaje
    usa verde.
    """
    try:
        documento = _documento(origen)
    except Exception as exc:
        raise ValueError("No se pudo abrir la factura para estamparla") from exc
    try:
        _estampar(documento, lineas, color)
        return documento.tobytes()
    finally:
        documento.close()


def _documento(origen: Path | None) -> pymupdf.Document:
    if origen is not None and origen.is_file() and origen.suffix.lower() == ".pdf":
        documento = pymupdf.open(origen)
        if documento.page_count == 0:
            documento.new_page(width=595, height=842)
        return documento
    documento = pymupdf.open()
    if origen is not None and origen.is_file() and origen.suffix.lower() in _IMAGENES:
        pagina = documento.new_page(width=595, height=842)
        pagina.insert_image(pagina.rect, filename=str(origen))
        return documento
    documento.new_page(width=595, height=842)
    return documento


def _ruta_fuente() -> str | None:
    for ruta in _FUENTES:
        if ruta.is_file():
            return str(ruta)
    return None


def _estampar(
    documento: pymupdf.Document,
    lineas: list[str],
    color: tuple[float, float, float],
) -> None:
    ruta_fuente = _ruta_fuente()
    fuente = pymupdf.Font(fontfile=ruta_fuente) if ruta_fuente else pymupdf.Font("helv")
    pagina_base = documento[0]
    ancho_util = max(80.0, pagina_base.rect.width - _MARGEN * 2 - _RELLENO * 2)
    filas: list[str] = []
    for linea in lineas:
        filas.extend(_partir(linea, fuente, ancho_util))
    if not filas:
        return
    ancho = min(
        pagina_base.rect.width - _MARGEN * 2,
        max(fuente.text_length(fila, fontsize=_TAMANO) for fila in filas) + _RELLENO * 2,
    )
    alto = _RELLENO * 2 + _TAMANO + _INTERLINEADO * (len(filas) - 1)
    indice, rect = _hueco(documento, ancho, alto)
    pagina = documento[indice]
    pagina.draw_rect(rect, color=None, fill=(1, 1, 1), width=0)
    y = rect.y0 + _RELLENO + _TAMANO
    opciones = {"fontsize": _TAMANO, "color": color}
    if ruta_fuente:
        opciones["fontname"] = "sello"
        opciones["fontfile"] = ruta_fuente
    else:
        opciones["fontname"] = "helv"
    for fila in filas:
        pagina.insert_text(pymupdf.Point(rect.x0 + _RELLENO, y), fila, **opciones)
        y += _INTERLINEADO


def _hueco(documento: pymupdf.Document, ancho: float, alto: float) -> tuple[int, pymupdf.Rect]:
    """Elige la página y el rectángulo con menos tinta que quepa el sello."""
    mejor: tuple[tuple[int, int, int, int], int, pymupdf.Rect] | None = None
    for indice, pagina in enumerate(documento):
        tinta, x0, y0 = _hueco_de_pagina(pagina, ancho, alto)
        # Menos tinta primero. Si hay blanco de sobra, la primera página y la zona baja.
        clave = (tinta, indice, -int(y0), -int(x0))
        rect = pymupdf.Rect(x0, y0, x0 + ancho, y0 + alto)
        if mejor is None or clave < mejor[0]:
            mejor = (clave, indice, rect)
    assert mejor is not None
    return mejor[1], mejor[2]


def _hueco_de_pagina(pagina: pymupdf.Page, ancho: float, alto: float) -> tuple[int, float, float]:
    margen = float(_MARGEN)
    if ancho + margen * 2 > pagina.rect.width or alto + margen * 2 > pagina.rect.height:
        return 0, margen, margen
    ocupado, cols, rows = _tinta(pagina)
    integral = _integral(ocupado, cols, rows)
    ancho_c = max(1, math.ceil(ancho / _CELDA))
    alto_c = max(1, math.ceil(alto / _CELDA))
    margen_c = max(1, math.floor(margen / _CELDA))
    mejor: tuple[int, int, int] | None = None
    origen: tuple[int, int] | None = None
    y_max = rows - alto_c - margen_c
    x_max = cols - ancho_c - margen_c
    for y in range(margen_c, y_max + 1):
        for x in range(margen_c, x_max + 1):
            tinta = _suma(integral, cols, x, y, x + ancho_c, y + alto_c)
            clave = (tinta, -y, -x)
            if mejor is None or clave < mejor:
                mejor = clave
                origen = (x, y)
    if origen is None or mejor is None:
        return 0, margen, margen
    return mejor[0], origen[0] * _CELDA, origen[1] * _CELDA


def _tinta(pagina: pymupdf.Page) -> tuple[bytearray, int, int]:
    pix = pagina.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False, colorspace=pymupdf.csRGB)
    cols = max(1, int(pagina.rect.width // _CELDA))
    rows = max(1, int(pagina.rect.height // _CELDA))
    ocupado = bytearray(cols * rows)
    muestras = pix.samples
    canales = pix.n
    escala_x = pagina.rect.width / pix.width
    escala_y = pagina.rect.height / pix.height
    for y in range(pix.height):
        base = y * pix.stride
        cy = int((y * escala_y) // _CELDA)
        if cy < 0 or cy >= rows:
            continue
        fila = cy * cols
        for x in range(0, pix.width, 2):
            i = base + x * canales
            if (
                muestras[i] < _UMBRAL_TINTA
                or muestras[i + 1] < _UMBRAL_TINTA
                or muestras[i + 2] < _UMBRAL_TINTA
            ):
                cx = int((x * escala_x) // _CELDA)
                if 0 <= cx < cols:
                    ocupado[fila + cx] = 1
    return _dilatar(ocupado, cols, rows), cols, rows


def _dilatar(ocupado: bytearray, cols: int, rows: int) -> bytearray:
    """Separa el sello un paso de la tinta para no rozar una línea."""
    dilatado = bytearray(ocupado)
    for y in range(rows):
        for x in range(cols):
            if not ocupado[y * cols + x]:
                continue
            for dy in (-1, 0, 1):
                ny = y + dy
                if ny < 0 or ny >= rows:
                    continue
                for dx in (-1, 0, 1):
                    nx = x + dx
                    if 0 <= nx < cols:
                        dilatado[ny * cols + nx] = 1
    return dilatado


def _integral(ocupado: bytearray, cols: int, rows: int) -> list[int]:
    ancho = cols + 1
    suma = [0] * (ancho * (rows + 1))
    for y in range(rows):
        corrido = 0
        for x in range(cols):
            corrido += ocupado[y * cols + x]
            suma[(y + 1) * ancho + (x + 1)] = suma[y * ancho + (x + 1)] + corrido
    return suma


def _suma(integral: list[int], cols: int, x0: int, y0: int, x1: int, y1: int) -> int:
    ancho = cols + 1
    return (
        integral[y1 * ancho + x1]
        - integral[y0 * ancho + x1]
        - integral[y1 * ancho + x0]
        + integral[y0 * ancho + x0]
    )


def _partir(texto: str, fuente: pymupdf.Font, ancho: float) -> list[str]:
    if fuente.text_length(texto, fontsize=_TAMANO) <= ancho:
        return [texto]
    filas: list[str] = []
    actual = ""
    for palabra in texto.split(" "):
        candidato = palabra if not actual else f"{actual} {palabra}"
        if fuente.text_length(candidato, fontsize=_TAMANO) <= ancho:
            actual = candidato
            continue
        if actual:
            filas.append(actual)
        actual = palabra
    if actual:
        filas.append(actual)
    return filas or [texto]
