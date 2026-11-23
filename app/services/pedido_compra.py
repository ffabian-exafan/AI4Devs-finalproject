"""Pedido de compra de serie 1. Plantilla de Exafan, sin LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

import pymupdf

_ENTRA = ("MONTAJE", "COLOCACIÓN", "COLOCACION", "INSTALACIÓN", "INSTALACION")
_NUMERO = re.compile(r"(?<![A-Z0-9])1-\d{5}(?!\d)")
_ROTULO = re.compile(r"NAVE\s+\d+", re.IGNORECASE)
_CODIGO_ART = re.compile(r"^[A-Z]{3,}\d+$")
AVISO_PLANTILLA = "El pedido no trae la plantilla de Exafan"
AVISO_VARIOS = "El pedido trae varios números"


@dataclass(frozen=True)
class LineaPedido:
    codigo: str
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_pct: Decimal
    importe: Decimal
    sugerida: bool


@dataclass(frozen=True)
class LecturaPedido:
    cuadra: bool
    numero: str | None
    rotulo: str | None
    lineas: list[LineaPedido]
    aviso: str | None


def leer_pedido(contenido: bytes) -> LecturaPedido:
    try:
        documento = pymupdf.open(stream=contenido, filetype="pdf")
    except Exception:
        return LecturaPedido(False, None, None, [], AVISO_PLANTILLA)
    try:
        palabras: list[tuple[float, float, str]] = []
        for pagina in documento:
            for palabra in pagina.get_text("words"):
                texto = str(palabra[4]).strip()
                if texto:
                    palabras.append((float(palabra[1]), (float(palabra[0]) + float(palabra[2])) / 2, texto))
    finally:
        documento.close()
    return _leer_palabras(palabras)


def _leer_palabras(palabras: list[tuple[float, float, str]]) -> LecturaPedido:
    filas = _filas(palabras)
    numeros = _numeros(filas)
    rotulo = _rotulo(filas)
    cabecera = _cabecera(filas)
    if len(set(numeros)) != 1 or cabecera is None:
        aviso = AVISO_VARIOS if len(set(numeros)) > 1 else AVISO_PLANTILLA
        return LecturaPedido(False, None, rotulo, [], aviso)
    return LecturaPedido(True, numeros[0], rotulo, _lineas(filas, cabecera), None)


def _filas(palabras: list[tuple[float, float, str]]) -> list[list[tuple[float, float, str]]]:
    orden = sorted(palabras, key=lambda item: (round(item[0], 1), item[1]))
    filas: list[list[tuple[float, float, str]]] = []
    for palabra in orden:
        if filas and abs(palabra[0] - filas[-1][0][0]) <= 3:
            filas[-1].append(palabra)
        else:
            filas.append([palabra])
    for fila in filas:
        fila.sort(key=lambda item: item[1])
    return filas


def _numeros(filas: list[list[tuple[float, float, str]]]) -> list[str]:
    hallados: list[str] = []
    for fila in filas:
        pegado = ""
        previo = ""
        for _, _, texto in fila:
            if previo == "1-" and re.fullmatch(r"\d{5}", texto):
                pegado += texto
            else:
                pegado += f" {texto}"
            previo = texto
        hallados.extend(_NUMERO.findall(pegado.upper()))
    return hallados


def _rotulo(filas: list[list[tuple[float, float, str]]]) -> str | None:
    texto = " ".join(palabra for fila in filas for _, _, palabra in fila)
    hallazgo = _ROTULO.search(texto)
    if hallazgo is None:
        return None
    return re.sub(r"\s+", " ", hallazgo.group()).upper()


def _clave(texto: str) -> str | None:
    normal = texto.lower().replace("ó", "o").replace("á", "a").replace("%", "").replace(".", "")
    if normal.startswith("cod"):
        return "codigo"
    if normal.startswith("descrip"):
        return "descripcion"
    if normal in {"unds", "und", "uds"}:
        return "cantidad"
    if normal == "precio":
        return "precio"
    if "dto" in normal:
        return "descuento"
    if normal == "importe":
        return "importe"
    return None


def _cabecera(filas: list[list[tuple[float, float, str]]]) -> dict[str, float] | None:
    for fila in filas:
        columnas: dict[str, float] = {}
        for _, x, texto in fila:
            clave = _clave(texto)
            if clave is not None:
                columnas[clave] = x
        if "descripcion" in columnas and "importe" in columnas:
            return columnas
    return None


def _lineas(
    filas: list[list[tuple[float, float, str]]],
    columnas: dict[str, float],
) -> list[LineaPedido]:
    y_cabecera = None
    for fila in filas:
        claves = {_clave(texto) for _, _, texto in fila}
        if "descripcion" in claves and "importe" in claves:
            y_cabecera = fila[0][0]
            break
    if y_cabecera is None:
        return []
    lineas: list[LineaPedido] = []
    for fila in filas:
        if fila[0][0] <= y_cabecera + 3:
            continue
        texto_fila = " ".join(texto for _, _, texto in fila).lower()
        if "importe neto" in texto_fila or "observaciones" in texto_fila:
            break
        celdas: dict[str, list[str]] = {clave: [] for clave in columnas}
        for _, x, texto in fila:
            clave = min(columnas, key=lambda nombre: abs(columnas[nombre] - x))
            celdas[clave].append(texto)
        descripcion = re.sub(r"\s+", " ", " ".join(celdas.get("descripcion", []))).strip()
        if not descripcion:
            continue
        importe = _decimal(" ".join(celdas.get("importe", [])))
        if importe is None:
            continue
        codigo = "".join(celdas.get("codigo", []))
        if not _CODIGO_ART.fullmatch(codigo):
            codigo = f"ped.{len(lineas) + 1}"
        lineas.append(
            LineaPedido(
                codigo=codigo[:50],
                descripcion=descripcion,
                cantidad=_decimal(" ".join(celdas.get("cantidad", []))) or Decimal("0.00"),
                precio_unitario=_decimal(" ".join(celdas.get("precio", []))) or Decimal("0.00"),
                descuento_pct=_decimal(" ".join(celdas.get("descuento", []))) or Decimal("0.00"),
                importe=importe,
                sugerida=descripcion.upper().startswith(_ENTRA),
            )
        )
    return lineas


def _decimal(texto: str) -> Decimal | None:
    limpio = texto.strip().replace(" ", "")
    if not limpio or not re.fullmatch(r"\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?", limpio):
        return None
    return Decimal(limpio.replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))
