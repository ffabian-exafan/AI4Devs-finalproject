"""Tests de GET /proyectos y GET /proyectos/{id}."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Nave, Proyecto


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_listar_proyectos_incluye_creado(client: TestClient, db: Session):
    proyecto = Proyecto(
        nombre="Proyecto test listado UI",
        tipo="llave_en_mano",
        estado="en_curso",
    )
    db.add(proyecto)
    db.commit()
    db.refresh(proyecto)

    response = client.get("/proyectos")
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    ids = {p["id"] for p in body}
    assert proyecto.id in ids
    fila = next(p for p in body if p["id"] == proyecto.id)
    assert fila["nombre"] == "Proyecto test listado UI"
    assert fila["tipo"] == "llave_en_mano"
    assert fila["estado"] == "en_curso"


def test_obtener_proyecto_con_naves(client: TestClient, db: Session):
    proyecto = Proyecto(
        nombre="Proyecto detalle con naves",
        tipo="reforma",
        estado="en_curso",
    )
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave de prueba",
        importe_presupuestado=Decimal("1000.00"),
    )
    db.add(nave)
    db.commit()
    db.refresh(proyecto)
    db.refresh(nave)

    response = client.get(f"/proyectos/{proyecto.id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == proyecto.id
    assert body["nombre"] == "Proyecto detalle con naves"
    assert len(body["naves"]) == 1
    assert body["naves"][0]["id"] == nave.id
    assert body["naves"][0]["codigo"] == "N1"
    assert body["naves"][0]["descripcion"] == "Nave de prueba"
    assert "importe_presupuestado" not in body["naves"][0]
    assert body["apartados"] == []
    assert body["contratos"] == []


def test_obtener_proyecto_inexistente(client: TestClient):
    response = client.get("/proyectos/999999999")
    assert response.status_code == 404
