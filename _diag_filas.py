"""Clasifica filas con importe. Solo longitudes y si la etiqueta es un total."""

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
total_re = re.compile(r"total|suma|descuento|dto\b", re.I)

filas_ok = 0
totales = 0
cortas = 0
for page in doc:
    filas = []
    for bloque in page.get_text("dict")["blocks"]:
        if bloque.get("type") != 0:
            continue
        for line in bloque.get("lines", []):
            texto = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if texto:
                filas.append((line["bbox"][1], line["bbox"][0], line["bbox"][2], texto))
    for y, x, _, texto in filas:
        if not patron.search(texto):
            continue
        izquierdas = [
            fila[3]
            for fila in filas
            if abs(fila[0] - y) < 8 and fila[2] < x - 10 and not patron.search(fila[3])
        ]
        etiqueta = " ".join(izquierdas).strip()
        grupos = texto.count(".")
        print(f"grupos={grupos} etiq={len(etiqueta):3d} total={bool(total_re.search(etiqueta))}")
        filas_ok += 1
        if total_re.search(etiqueta):
            totales += 1
        if len(etiqueta) < 8:
            cortas += 1
print("filas", filas_ok, "totales", totales, "etiquetas_cortas", cortas)
doc.close()
