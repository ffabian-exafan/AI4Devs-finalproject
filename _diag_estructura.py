"""Estructura del último PDF y del Excel de esa obra. Sin textos ni cifras."""

import re

import pymupdf
from sqlalchemy import text

from app.db import SessionLocal
from app.services import almacen as almacen_svc

db = SessionLocal()
try:
    pres = db.execute(
        text(
            """
            SELECT id, proyecto_id, ruta_almacen
            FROM presupuesto
            WHERE formato = 'pdf_cliente'
            ORDER BY id DESC
            LIMIT 1
            """
        )
    ).one()
    excel = db.execute(
        text(
            """
            SELECT count(*)
            FROM tarea
            WHERE nave_id IN (SELECT id FROM nave WHERE proyecto_id = :pid)
              AND nivel = 'subapartado'
            """
        ),
        {"pid": pres.proyecto_id},
    ).scalar()
    apartados = db.execute(
        text(
            """
            SELECT count(*)
            FROM tarea
            WHERE nave_id IN (SELECT id FROM nave WHERE proyecto_id = :pid)
              AND nivel = 'apartado'
              AND presupuesto_id IN (
                SELECT id FROM presupuesto
                WHERE proyecto_id = :pid AND formato = 'excel_expertis'
              )
            """
        ),
        {"pid": pres.proyecto_id},
    ).scalar()
finally:
    db.close()

print("excel_apartados", apartados, "excel_subapartados", excel)

ruta = almacen_svc.abrir_si_existe(pres.ruta_almacen)
doc = pymupdf.open(stream=ruta.read_bytes(), filetype="pdf")
patron = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}")
print("paginas", doc.page_count)
for i, page in enumerate(doc):
    filas = []
    for bloque in page.get_text("dict")["blocks"]:
        if bloque.get("type") != 0:
            continue
        for line in bloque.get("lines", []):
            texto = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if texto:
                filas.append((line["bbox"][1], line["bbox"][0], line["bbox"][2], texto))
    importes = [fila for fila in filas if patron.search(fila[3])]
    if not importes:
        continue
    mismos = 0
    for y, x, _, _ in importes:
        cerca = [
            fila
            for fila in filas
            if abs(fila[0] - y) < 8 and fila[2] < x - 10 and not patron.search(fila[3])
        ]
        if cerca:
            mismos += 1
    print(f"p{i+1:02d} importes={len(importes)} con_texto_a_la_izquierda={mismos}")
doc.close()
