"""Recuento del último PDF de cliente. Sin nombres ni importes."""

from sqlalchemy import text

from app.db import SessionLocal

db = SessionLocal()
try:
    fila = db.execute(
        text(
            """
            SELECT p.id, p.proyecto_id, length(p.fichero_origen),
                   right(p.fichero_origen, 4),
                   p.ver_pagina, p.es_escaneado,
                   (SELECT count(*) FROM linea_pdf_cliente l WHERE l.presupuesto_id = p.id) AS lineas,
                   (SELECT count(*) FROM linea_pdf_cliente l WHERE l.presupuesto_id = p.id AND l.tipo = 'importe') AS importes,
                   (SELECT count(*) FROM linea_pdf_cliente l WHERE l.presupuesto_id = p.id AND l.tipo = 'descuento') AS descuentos,
                   (SELECT count(*) FROM linea_pdf_cliente l WHERE l.presupuesto_id = p.id AND l.importe = 0) AS ceros
            FROM presupuesto p
            WHERE p.formato = 'pdf_cliente'
            ORDER BY p.id DESC
            LIMIT 3
            """
        )
    ).fetchall()
    for item in fila:
        print("pres", tuple(item))
    if fila:
        pid = fila[0][0]
        formas = db.execute(
            text(
                """
                SELECT length(descripcion), length(codigo),
                       CASE WHEN descripcion ILIKE '%[VERIFICAR]%' THEN 1 ELSE 0 END
                FROM linea_pdf_cliente
                WHERE presupuesto_id = :pid
                ORDER BY orden
                LIMIT 40
                """
            ),
            {"pid": pid},
        ).fetchall()
        print("formas", len(formas))
        for forma in formas:
            print(tuple(forma))
finally:
    db.close()
