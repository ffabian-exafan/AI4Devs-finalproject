"""Estado de los dos últimos PDF, sin rutas ni textos."""

from sqlalchemy import text

from app.db import SessionLocal
from app.services import almacen as almacen_svc
from app.services.filas_pdf import filas_oferta

db = SessionLocal()
try:
    filas = db.execute(
        text(
            """
            SELECT id, proyecto_id, ruta_almacen IS NOT NULL, length(coalesce(ruta_almacen, ''))
            FROM presupuesto
            WHERE formato = 'pdf_cliente'
            ORDER BY id DESC
            LIMIT 2
            """
        )
    ).fetchall()
    rutas = db.execute(
        text(
            """
            SELECT id, ruta_almacen FROM presupuesto
            WHERE formato = 'pdf_cliente'
            ORDER BY id DESC
            LIMIT 2
            """
        )
    ).fetchall()
finally:
    db.close()

for fila in filas:
    print("meta", tuple(fila))

for ident, ruta in rutas:
    archivo = almacen_svc.abrir_si_existe(ruta)
    if archivo is None:
        print("id", ident, "archivo", False)
        continue
    contenido = archivo.read_bytes()
    print("id", ident, "bytes", len(contenido), "oferta", len(filas_oferta(contenido)))
