"""PDF de pedido ficticio. No lleva datos reales."""

import pymupdf


def pdf_pedido(lineas, numero="1-10001", rotulo="NAVE 1", cabecera=True) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=900, height=842)
    page.insert_text((40, 40), numero, fontsize=11)
    if rotulo:
        page.insert_text((40, 58), rotulo, fontsize=11)
    if cabecera:
        for x, texto in (
            (40, "Código"),
            (120, "Descripción"),
            (460, "Unds"),
            (505, "Precio"),
            (545, "%.Dto"),
            (575, "Importe"),
        ):
            page.insert_text((x, 90), texto, fontsize=9)
    y = 120
    for codigo, desc, unds, precio, dto, importe in lineas:
        page.insert_text((40, y), codigo, fontsize=9)
        page.insert_text((120, y), desc, fontsize=8)
        page.insert_text((460, y), unds, fontsize=9)
        page.insert_text((505, y), precio, fontsize=9)
        page.insert_text((545, y), dto, fontsize=9)
        page.insert_text((575, y), importe, fontsize=9)
        y += 18
    page.insert_text((40, y + 12), "Importe Neto", fontsize=9)
    datos = doc.tobytes()
    doc.close()
    return datos
