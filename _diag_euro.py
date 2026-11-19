"""Cuenta importes con símbolo de euro y sin él. No imprime cifras."""

import re

import pymupdf
from sqlalchemy import text

from app.db import SessionLocal
from app.services import almacen as almacen_svc

db = SessionLocal()
try:
    ruta_almacen = db.execute(
        text(
            """
            SELECT ruta_almacen FROM presupuesto
            WHERE formato = 'pdf_cliente'
            ORDER BY id DESC LIMIT 1
            """
        )
    ).scalar_one()
finally:
    db.close()

doc = pymupdf.open(stream=almacen_svc.abrir_si_existe(ruta_almacen).read_bytes(), filetype="pdf")
patron = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}")
con_euro = 0
sin_euro = 0
for numero, page in enumerate(doc, start=1):
    for bloque in page.get_text("dict")["blocks"]:
        if bloque.get("type") != 0:
            continue
        for line in bloque.get("lines", []):
            texto = "".join(span.get("text", "") for span in line.get("spans", []))
            if not patron.search(texto):
                continue
            if "€" in texto:
                con_euro += 1
                print(f"p{numero:02d} euro")
            else:
                sin_euro += 1
print("con_euro", con_euro, "sin_euro", sin_euro)
doc.close()
