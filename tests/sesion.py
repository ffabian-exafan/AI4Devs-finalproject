"""Entra en la app de test con un usuario ficticio. No es un fixture global."""

import uuid

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Usuario

CLAVE = "clave-ficticia"


def entrar(client: TestClient, db: Session, rol: str = "direccion") -> Usuario:
    email = f"persona.{uuid.uuid4().hex[:8]}@example.com"
    usuario = Usuario(
        nombre="Persona Ejemplo",
        email=email,
        rol=rol,
        password_hash=PasswordHasher().hash(CLAVE),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    res = client.post("/auth/login", json={"email": email, "password": CLAVE})
    assert res.status_code == 200, res.text
    return usuario
