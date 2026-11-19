"""Texto y color del sello, sin base de datos."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pymupdf

from app.services.sello_factura import DatosSello, lineas_sello, linea_codigo, pdf_con_sello


def _plano(texto: str) -> str:
    """La extracción de Arial devuelve espacio duro y guion blando."""
    return texto.replace("\xa0", " ").replace("\xad", "-")


def test_el_codigo_se_parte_en_proyecto_y_trabajo():
    assert linea_codigo("PYCON123456") == "PYCON/123 - TRABAJO/45"
    assert linea_codigo("pyequ123456adm") == "PYEQU/123 - TRABAJO/45"
    assert linea_codigo("1-123456") == "1-/123 - TRABAJO/45"
    assert linea_codigo(None) == "PYCON/— - TRABAJO/—"
    assert linea_codigo("no-es-codigo") == "PYCON/— - TRABAJO/—"


def _y_sello(documento: pymupdf.Document) -> tuple[int, float]:
    for indice, pagina in enumerate(documento):
        for bloque in pagina.get_text("dict")["blocks"]:
            for linea in bloque.get("lines", []):
                for span in linea.get("spans", []):
                    if span["text"].replace("\xa0", " ").startswith("Ref."):
                        return indice, span["bbox"][1]
    raise AssertionError("el sello no está en el PDF")


def test_el_sello_baja_si_la_cabecera_esta_ocupada(tmp_path: Path):
    origen = tmp_path / "factura.pdf"
    documento = pymupdf.open()
    pagina = documento.new_page()
    pagina.draw_rect(pymupdf.Rect(0, 0, 595, 500), color=None, fill=(0.8, 0.8, 0.8))
    pagina.insert_text((40, 80), "CABECERA FICTICIA")
    documento.save(origen)
    documento.close()

    pdf = pdf_con_sello(origen, lineas_sello(_datos()))
    abierto = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        _indice, y = _y_sello(abierto)
        assert y > 500
        assert "CABECERA FICTICIA" in abierto[0].get_text()
    finally:
        abierto.close()


def test_el_sello_sube_si_el_pie_esta_ocupado(tmp_path: Path):
    origen = tmp_path / "factura.pdf"
    documento = pymupdf.open()
    pagina = documento.new_page()
    pagina.draw_rect(pymupdf.Rect(0, 280, 595, 842), color=None, fill=(0.8, 0.8, 0.8))
    documento.save(origen)
    documento.close()

    pdf = pdf_con_sello(origen, lineas_sello(_datos()))
    abierto = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        _indice, y = _y_sello(abierto)
        assert y < 280
    finally:
        abierto.close()


def test_el_sello_pasa_a_la_pagina_en_blanco(tmp_path: Path):
    origen = tmp_path / "factura.pdf"
    documento = pymupdf.open()
    llena = documento.new_page()
    llena.draw_rect(llena.rect, color=None, fill=(0.8, 0.8, 0.8))
    documento.new_page()
    documento.save(origen)
    documento.close()

    pdf = pdf_con_sello(origen, lineas_sello(_datos()))
    abierto = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        indice, _y = _y_sello(abierto)
        assert indice == 1
    finally:
        abierto.close()


def _datos() -> DatosSello:
    return DatosSello(
        obra="Obra ficticia",
        codigo="PYCON123456",
        referencia_alc="00001",
        nombre="Persona Ejemplo",
        fecha=date(2026, 11, 19),
        presupuestado=Decimal("5000"),
        ordinal=1,
        importe_factura=Decimal("1210"),
        pendiente=Decimal("3790"),
    )


def test_el_sello_queda_en_azul_sobre_el_pdf(tmp_path: Path):
    origen = tmp_path / "factura.pdf"
    documento = pymupdf.open()
    pagina = documento.new_page()
    pagina.insert_text((40, 500), "TEXTO ORIGINAL FICTICIO")
    documento.save(origen)
    documento.close()

    datos = DatosSello(
        obra="Obra ficticia",
        codigo="PYCON123456",
        referencia_alc="00001",
        nombre="Persona Ejemplo",
        fecha=date(2026, 11, 19),
        presupuestado=Decimal("5000"),
        ordinal=1,
        importe_factura=Decimal("1210"),
        pendiente=Decimal("3790"),
    )
    pdf = pdf_con_sello(origen, lineas_sello(datos))
    abierto = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        texto = _plano(abierto[0].get_text())
        assert "TEXTO ORIGINAL FICTICIO" in texto
        assert "Ref. Obra ficticia" in texto
        assert "PYCON/123 - TRABAJO/45" in texto
        assert "ALC/00001" in texto
        assert "Persona Ejemplo - 19/11/2026" in texto
        assert "Presupuestado: 5.000,00 €" in texto
        assert "1ª factura: 1.210,00 €" in texto
        assert "Pendiente: 3.790,00 €" in texto
    finally:
        abierto.close()
