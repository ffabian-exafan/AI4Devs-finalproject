"""Tests de GET /proyectos y GET /proyectos/{id}."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Contratista, Factura, Nave, Presupuesto, Proyecto, Tarea


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


def test_listar_proyectos_suma_raices_y_facturas_confirmadas(
    client: TestClient, db: Session
):
    proyecto = Proyecto(
        nombre="Proyecto test totales listado",
        tipo="llave_en_mano",
        estado="pendiente_revision",
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
    db.flush()
    presupuesto = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="presupuesto_test_listado.md",
        fecha=date(2026, 1, 1),
        estado_extraccion="pendiente_revision",
        es_escaneado=False,
    )
    db.add(presupuesto)
    db.flush()
    padre = Tarea(
        nave_id=nave.id,
        presupuesto_id=presupuesto.id,
        codigo="1.1",
        nivel="apartado",
        descripcion="Apartado de prueba",
        importe_presupuestado=Decimal("1000.00"),
        tiene_anotacion_manual=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(padre)
    db.flush()
    db.add(
        Tarea(
            nave_id=nave.id,
            presupuesto_id=presupuesto.id,
            tarea_padre_id=padre.id,
            codigo="1.1.1",
            nivel="subapartado",
            descripcion="Subapartado sin sumar otra vez",
            importe_presupuestado=Decimal("400.00"),
            tiene_anotacion_manual=False,
            estado_revision="pendiente",
            estado="no_iniciada",
            avance_fisico_pct=Decimal("0"),
        )
    )
    db.add(
        Tarea(
            nave_id=nave.id,
            presupuesto_id=presupuesto.id,
            codigo="descuento.1",
            nivel="apartado",
            capitulo="Precio final",
            descripcion="Descuento de prueba",
            importe_presupuestado=Decimal("-100.00"),
            tiene_anotacion_manual=False,
            estado_revision="pendiente",
            estado="no_iniciada",
            avance_fisico_pct=Decimal("0"),
        )
    )
    contratista = (
        db.query(Contratista).filter(Contratista.nif == "B00000999").first()
    )
    if contratista is None:
        contratista = Contratista(
            nif="B00000999",
            nombre="Subcontrata de prueba",
            tipo="externo",
        )
        db.add(contratista)
        db.flush()
    db.add(
        Factura(
            proyecto_id=proyecto.id,
            contratista_id=contratista.id,
            numero="F-TEST-1",
            base_imponible=Decimal("200.00"),
            iva=Decimal("0"),
            total=Decimal("200.00"),
            tipo="ordinaria",
            fichero_origen="factura_test.md",
            estado_revision="confirmada",
        )
    )
    db.add(
        Factura(
            proyecto_id=proyecto.id,
            contratista_id=contratista.id,
            numero="F-TEST-2",
            base_imponible=Decimal("50.00"),
            iva=Decimal("0"),
            total=Decimal("50.00"),
            tipo="ordinaria",
            fichero_origen="factura_pendiente.md",
            estado_revision="pendiente",
        )
    )
    db.commit()

    response = client.get("/proyectos")
    assert response.status_code == 200, response.text
    fila = next(p for p in response.json() if p["id"] == proyecto.id)
    assert fila["presupuestado"] == 900.0
    assert fila["facturado"] == 200.0

    detalle = client.get(f"/proyectos/{proyecto.id}")
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["presupuestado"] == 900.0
    assert detalle.json()["facturado"] == 200.0


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


def test_borrar_proyecto_quita_la_obra_y_sus_filas(client: TestClient, db: Session):
    proyecto = Proyecto(
        nombre="Proyecto test borrar obra",
        tipo="reforma",
        estado="en_curso",
    )
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave de prueba",
        importe_presupuestado=Decimal("100.00"),
    )
    db.add(nave)
    db.flush()
    presupuesto = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="presupuesto_borrar.md",
        fecha=date(2026, 1, 2),
        estado_extraccion="pendiente_revision",
        es_escaneado=False,
    )
    db.add(presupuesto)
    db.flush()
    db.add(
        Tarea(
            nave_id=nave.id,
            presupuesto_id=presupuesto.id,
            codigo="1.1",
            nivel="apartado",
            descripcion="Apartado a borrar",
            importe_presupuestado=Decimal("100.00"),
            tiene_anotacion_manual=False,
            estado_revision="pendiente",
            estado="no_iniciada",
            avance_fisico_pct=Decimal("0"),
        )
    )
    db.commit()
    proyecto_id = proyecto.id
    nave_id = nave.id
    presupuesto_id = presupuesto.id

    response = client.delete(f"/proyectos/{proyecto_id}")
    assert response.status_code == 204, response.text
    assert response.content == b""

    detalle = client.get(f"/proyectos/{proyecto_id}")
    assert detalle.status_code == 404
    ids = {p["id"] for p in client.get("/proyectos").json()}
    assert proyecto_id not in ids
    db.expire_all()
    assert db.get(Nave, nave_id) is None
    assert db.get(Presupuesto, presupuesto_id) is None


def test_borrar_proyecto_inexistente(client: TestClient):
    response = client.delete("/proyectos/999999999")
    assert response.status_code == 404


def test_obtener_proyecto_inexistente(client: TestClient):
    response = client.get("/proyectos/999999999")
    assert response.status_code == 404
