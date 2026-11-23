"""Código impreso en el contrato y en la factura para relacionarlos.

Obra: PYCON o PYEQU, 3 dígitos de proyecto, 2 de trabajo y 1 de contrato.
Serie 1, sin PY: el pedido es 1- y cinco dígitos; el contrato impreso añade un dígito del 0 al 9. Por administración, el mismo código termina en ADM.
El tramo del trabajo no se enlaza con ningún apartado de este sistema.
"""

from __future__ import annotations

import re

_FORMATO = re.compile(r"^(?:PYCON\d{6}|PYEQU\d{6}|1-\d{6})(?:ADM)?$")
_PEDIDO_DE_CODIGO = re.compile(r"^1-(\d{5})\d(?:ADM)?$")
_EN_TEXTO = re.compile(
    r"(?<![A-Z0-9])((?:PYCON|PYEQU)\d{6}|1-\d{6})(ADM)?(?![A-Z0-9])",
    re.IGNORECASE,
)


def pedido_de_codigo(valor: str) -> str | None:
    """1-256580 y 1-256580ADM son el pedido 1-25658. Un PYCON no lo es."""
    hallazgo = _PEDIDO_DE_CODIGO.fullmatch(re.sub(r"\s+", "", valor or "").upper())
    if hallazgo is None:
        return None
    return f"1-{hallazgo.group(1)}"

MENSAJE_FORMATO = (
    "El código no cumple el formato. "
    "Obra: PYCON o PYEQU, 3 dígitos de proyecto, 2 de trabajo y 1 de contrato. "
    "Serie 1, sin PY: 1-, cinco dígitos del pedido y un dígito de contrato (0-9). "
    "Por administración, termina en ADM."
)
AVISO_SIN_CODIGO = "El PDF no trae código de contrato. Indícalo."
AVISO_VARIOS = "El PDF trae varios códigos de contrato. Indica cuál corresponde."
AVISO_REPETIDO = "Ese código ya está en otro contrato. Indica el que corresponde."
AVISO_SIN_CODIGO_FACTURA = "La factura no trae código de contrato. Indícalo."


def normalizar_codigo(valor: str) -> str:
    codigo = re.sub(r"\s+", "", valor or "").upper()
    if not _FORMATO.fullmatch(codigo):
        raise ValueError(MENSAJE_FORMATO)
    return codigo


def validar_codigo(valor: str) -> str:
    """Igual que normalizar, con un error que la API muestra tal cual."""
    try:
        return normalizar_codigo(valor)
    except ValueError as exc:
        from pydantic_core import PydanticCustomError

        raise PydanticCustomError("codigo_contrato", str(exc)) from None


def codigos_en_texto(texto: str) -> list[str]:
    vistos: list[str] = []
    for hallazgo in _EN_TEXTO.finditer(texto or ""):
        codigo = (hallazgo.group(1) + (hallazgo.group(2) or "")).upper()
        if codigo not in vistos:
            vistos.append(codigo)
    return vistos


def aviso_sin_contrato(codigo: str) -> str:
    return f"No hay un contrato con el código {codigo}."


def aviso_otra_obra(codigo: str) -> str:
    return f"El código {codigo} pertenece a otra obra."

