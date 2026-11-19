"""Completa el último PDF de cliente con el cuadro en euros. No imprime datos."""

from sqlalchemy import text

from app.db import SessionLocal
from app.services.presupuesto_excel import contraste_guardado

db = SessionLocal()
try:
    proyecto_id = 542
    salida = contraste_guardado(db, proyecto_id)
    print("lineas", 0 if salida is None else len(salida.sugerencias))
finally:
    db.close()
