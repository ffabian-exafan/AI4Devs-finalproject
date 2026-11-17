"""Registro inmutable de gestos. Usuarios y obras ficticios."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import RegistroAccion, Usuario


def _email() -> str:
    return f"ana.registro.{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_la_fila_no_se_puede_modificar(db: Session):
    usuario = Usuario(
        nombre="Ana Ejemplo",
        email=_email(),
        rol="direccion",
        password_hash="hash-ficticio",
    )
    db.add(usuario)
    db.commit()
    fila = RegistroAccion(
        usuario_id=usuario.id,
        nombre_en_el_momento=usuario.nombre,
        accion="inicio_sesion",
        ocurrido_en=datetime.now(timezone.utc),
    )
    db.add(fila)
    db.commit()
    fila_id = fila.id
    with pytest.raises(DatabaseError, match="no se puede modificar"):
        db.execute(
            RegistroAccion.__table__.update()
            .where(RegistroAccion.id == fila_id)
            .values(nombre_en_el_momento="Otro Nombre")
        )
        db.commit()
    db.rollback()