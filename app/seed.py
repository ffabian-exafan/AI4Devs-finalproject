"""Semilla anonimizada para poder entrar la primera vez.

Usuario ficticio. No es una persona de Exafan.
Ejecutar con: python -m app.seed
"""

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Usuario
from app.services.claves import hash_clave
from app.services.usuarios import buscar_por_email

EMAIL_INICIAL = "ana.ejemplo@example.com"
CLAVE_INICIAL = "clave-ficticia"
NOMBRE_INICIAL = "Ana Ejemplo"
ROL_INICIAL = "direccion"


def asegurar_usuario_inicial(db: Session) -> Usuario:
    existente = buscar_por_email(db, EMAIL_INICIAL)
    if existente is not None:
        return existente
    usuario = Usuario(
        nombre=NOMBRE_INICIAL,
        email=EMAIL_INICIAL,
        rol=ROL_INICIAL,
        password_hash=hash_clave(CLAVE_INICIAL),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def main() -> None:
    db = SessionLocal()
    try:
        asegurar_usuario_inicial(db)
    finally:
        db.close()
    print(f"Usuario de ejemplo listo: {EMAIL_INICIAL} / {CLAVE_INICIAL}")


if __name__ == "__main__":
    main()
