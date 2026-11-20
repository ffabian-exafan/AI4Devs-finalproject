"""Entra en la app de test con un usuario ficticio. No es un fixture global."""

import uuid

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Usuario

CLAVE = "clave-ficticia"


def certificar_montaje(client: TestClient, db: Session, factura_id: int) -> Usuario:
    """Primera persona: sello verde. Deja la sesión en esa persona."""
    from app.models import Contrato, Factura

    factura = db.get(Factura, factura_id)
    assert factura is not None
    db.refresh(factura)
    if not factura.codigo_contrato and factura.contrato_id:
        contrato = db.get(Contrato, factura.contrato_id)
        if contrato is not None and contrato.codigo:
            factura.codigo_contrato = contrato.codigo
            db.commit()
    if not factura.codigo_contrato:
        factura.codigo_contrato = "PYCON000000"
        db.commit()
    return _poner_certificacion(client, db, factura_id)


def _poner_certificacion(client: TestClient, db: Session, factura_id: int) -> Usuario:
    usuario = entrar(client, db, rol="jefe_obra")
    respuesta = client.post(f"/facturas/{factura_id}/certificar-montaje")
    assert respuesta.status_code == 200, respuesta.text
    return usuario


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
