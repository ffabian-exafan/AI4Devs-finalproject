"""Cifras solo por tamaño del entero, nunca el importe."""

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
for numero, page in enumerate(doc, start=1):
    filas = []
    for bloque in page.get_text("dict")["blocks"]:
        if bloque.get("type") != 0:
            continue
        for line in bloque.get("lines", []):
            texto = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if texto:
                filas.append((line["bbox"][1], line["bbox"][0], line["bbox"][2], texto))
    for y, x, _, texto in filas:
        hallado = patron.search(texto)
        if not hallado:
            continue
        entero = hallado.group().split(",")[0].replace(".", "")
        letras = len(re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", "", " ".join(
            fila[3]
            for fila in filas
            if abs(fila[0] - y) < 8 and fila[2] < x - 10 and not patron.search(fila[3])
        )))
        print(f"p{numero:02d} digitos={len(entero)} letras_etiq={letras}")
doc.close()
