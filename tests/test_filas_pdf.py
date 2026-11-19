"""El cuadro en euros de una oferta no se lee como una sola línea ni se suma dos veces."""

from decimal import Decimal

import pymupdf

from app.services.filas_pdf import filas_oferta


def _texto(page, punto, texto: str) -> None:
    # La fuente base no lleva el euro y lo cambia por otro carácter.
    page.insert_text(punto, texto, fontname="arial", fontfile=r"C:\Windows\Fonts\arial.ttf")


def _pdf() -> bytes:
    doc = pymupdf.open()
    portada = doc.new_page()
    _texto(portada, (72, 700), "Total")
    _texto(portada, (400, 700), "35.000,00 €")
    oferta = doc.new_page()
    filas = [
        (160, "Nave uno ficticia", "10.000,00 €"),
        (190, "Nave dos ficticia", "20.000,00 €"),
        (220, "Anexo ficticio", "5.000,00 €"),
        (260, "Importe total", "35.000,00 €"),
    ]
    for y, concepto, cifra in filas:
        _texto(oferta, (72, y), concepto)
        _texto(oferta, (400, y), cifra)
    contenido = doc.tobytes()
    doc.close()
    return contenido


def test_la_oferta_deja_los_conceptos_y_no_el_total():
    filas = filas_oferta(_pdf())
    assert [(fila.descripcion, fila.importe) for fila in filas] == [
        ("Nave uno ficticia", Decimal("10000.00")),
        ("Nave dos ficticia", Decimal("20000.00")),
        ("Anexo ficticio", Decimal("5000.00")),
    ]
