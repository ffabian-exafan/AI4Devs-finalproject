"""La transcripción parte el PDF para no resumirlo y perder los importes."""

import pymupdf

from app.services.transcripcion import PAGINAS_POR_LLAMADA, _trozos_pdf


def _pdf(paginas: int) -> bytes:
    doc = pymupdf.open()
    for _ in range(paginas):
        doc.new_page()
    contenido = doc.tobytes()
    doc.close()
    return contenido


def test_un_pdf_largo_se_parte_en_tramos_cortos():
    trozos = _trozos_pdf(_pdf(PAGINAS_POR_LLAMADA + 1))
    assert len(trozos) == 2
    assert PAGINAS_POR_LLAMADA <= 6
    for trozo in trozos:
        doc = pymupdf.open(stream=trozo, filetype="pdf")
        try:
            assert doc.page_count <= PAGINAS_POR_LLAMADA
        finally:
            doc.close()
