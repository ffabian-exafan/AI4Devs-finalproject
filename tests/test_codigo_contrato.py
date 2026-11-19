"""Formato del código de contrato que viene escrito en el PDF."""

import pytest

from app.services.codigo_contrato import codigos_en_texto, normalizar_codigo


def test_acepta_obra_de_construccion_y_de_equipamiento():
    assert normalizar_codigo("pycon244070") == "PYCON244070"
    assert normalizar_codigo("PYEQU244071") == "PYEQU244071"


def test_acepta_pedido_de_serie_1():
    assert normalizar_codigo("1-256580") == "1-256580"
    assert normalizar_codigo("1-256581") == "1-256581"


def test_acepta_el_sufijo_de_administracion():
    assert normalizar_codigo("PYCON244070ADM") == "PYCON244070ADM"
    assert normalizar_codigo("1-256580adm") == "1-256580ADM"


@pytest.mark.parametrize(
    "valor",
    [
        "PYCON24407",
        "PYCON2440700",
        "PYMAN244070",
        "1-25658",
        "1-2565800",
        "2-256580",
        "PYCON244070ADM1",
        "",
        "   ",
    ],
)
def test_rechaza_longitudes_o_prefijos_distintos(valor: str):
    with pytest.raises(ValueError):
        normalizar_codigo(valor)


def test_encuentra_un_codigo_dentro_del_texto():
    texto = "Contrato de montaje\nReferencia: PYCON244070\nPrecio cerrado."
    assert codigos_en_texto(texto) == ["PYCON244070"]


def test_no_recorta_un_codigo_mas_largo():
    assert codigos_en_texto("PYCON2440700 y 1-2565801") == []


def test_si_hay_varios_distintos_los_devuelve_sin_repetir():
    texto = "PYCON244070\nPYCON244070\nPYCON244071"
    assert codigos_en_texto(texto) == ["PYCON244070", "PYCON244071"]
