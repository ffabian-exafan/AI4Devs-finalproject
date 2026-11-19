"""¿Las cifras sin euro suman el total de la oferta? Solo un sí o un no."""

import re
from decimal import Decimal

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
con = []
sin = []
for page in doc:
    for bloque in page.get_text("dict")["blocks"]:
        if bloque.get("type") != 0:
            continue
        for line in bloque.get("lines", []):
            texto = "".join(span.get("text", "") for span in line.get("spans", []))
            hallado = patron.search(texto)
            if not hallado:
                continue
            cifra = Decimal(hallado.group().replace(".", "").replace(",", "."))
            (con if "€" in texto else sin).append(cifra)
doc.close()
total = max(con) if con else Decimal(0)
print("sin_euro_suman_el_total", sum(sin) == total)
print("sin_euro_suman_el_doble", sum(sin) == total * 2)
print("sin_euro_suman_el_triple", sum(sin) == total * 3)
print("cuantos_sin", len(sin), "cuantos_con", len(con))
