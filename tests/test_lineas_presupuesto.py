"""Alta, edición y borrado de líneas de presupuesto."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Contratista, Contrato, Nave, Presupuesto, Proyecto, Tarea


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


def _obra(db: Session) -> tuple[int, int, int]:
    proyecto = Proyecto(
        nombre="Proyecto test lineas manuales",
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
        fichero_origen="presupuesto_lineas_test.md",
        fecha=date(2026, 3, 1),
        estado_extraccion="confirmada",
        es_escaneado=False,
    )
    db.add(presupuesto)
    db.flush()
    padre = Tarea(
        nave_id=nave.id,
        presupuesto_id=presupuesto.id,
        codigo="A1",
        nivel="apartado",
        descripcion="Apartado detectado",
        importe_presupuestado=Decimal("100.00"),
        tiene_anotacion_manual=False,
        estado_revision="revisada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(padre)
    db.flush()
    hijo = Tarea(
        nave_id=nave.id,
        presupuesto_id=presupuesto.id,
        tarea_padre_id=padre.id,
        codigo="A1.1",
        nivel="subapartado",
        descripcion="Subapartado detectado",
        importe_presupuestado=Decimal("40.00"),
        tiene_anotacion_manual=False,
        estado_revision="revisada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(hijo)
    db.commit()
    return proyecto.id, padre.id, hijo.id


def test_crear_editar_y_borrar_linea(client: TestClient, db: Session):
    proyecto_id, padre_id, hijo_id = _obra(db)
    try:
        alta = client.post(
            f"/proyectos/{proyecto_id}/lineas",
            json={
                "codigo": "Z9",
                "descripcion": "Linea anadida a mano",
                "importe_presupuestado": 125.5,
            },
        )
        assert alta.status_code == 201, alta.text
        creada = alta.json()
        assert creada["codigo"] == "Z9"
        assert creada["nivel"] == "apartado"
        assert creada["estado_revision"] == "pendiente"
        assert creada["importe_presupuestado"] == 125.5

        editada = client.patch(
            f"/proyectos/{proyecto_id}/lineas/{padre_id}",
            json={
                "codigo": "A1",
                "descripcion": "Apartado corregido",
                "importe_presupuestado": 80,
            },
        )
        assert editada.status_code == 200, editada.text
        assert editada.json()["descripcion"] == "Apartado corregido"
        assert editada.json()["importe_presupuestado"] == 80
        assert editada.json()["estado_revision"] == "pendiente"

        detalle = client.get(f"/proyectos/{proyecto_id}")
        assert detalle.status_code == 200
        cuerpo = detalle.json()
        assert cuerpo["estado"] == "pendiente_revision"
        codigos = {ap["codigo"] for ap in cuerpo["apartados"]}
        assert {"A1", "Z9"} <= codigos

        borrada = client.delete(f"/proyectos/{proyecto_id}/lineas/{padre_id}")
        assert borrada.status_code == 204, borrada.text
        detalle = client.get(f"/proyectos/{proyecto_id}")
        ids: list[int] = []

        def walk(nodos: list[dict]) -> None:
            for nodo in nodos:
                ids.append(nodo["id"])
                walk(nodo.get("subapartados") or [])

        walk(detalle.json()["apartados"])
        assert padre_id not in ids
        assert hijo_id not in ids
        assert creada["id"] in ids
    finally:
        client.delete(f"/proyectos/{proyecto_id}")


def test_borrar_linea_enlazada_a_contrato(client: TestClient, db: Session):
    proyecto_id, padre_id, _hijo_id = _obra(db)
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
        Contrato(
            proyecto_id=proyecto_id,
            contratista_id=contratista.id,
            tarea_apartado_id=padre_id,
            precio_total=Decimal("10.00"),
            fichero_origen="contrato_linea_test.md",
            estado_extraccion="pendiente_revision",
        )
    )
    db.commit()
    try:
        response = client.delete(f"/proyectos/{proyecto_id}/lineas/{padre_id}")
        assert response.status_code == 422, response.text
        detalle = client.get(f"/proyectos/{proyecto_id}")
        ids = {ap["id"] for ap in detalle.json()["apartados"]}
        assert padre_id in ids
    finally:
        client.delete(f"/proyectos/{proyecto_id}")


def test_linea_vacia_y_ajena(client: TestClient, db: Session):
    proyecto_id, padre_id, _hijo_id = _obra(db)
    try:
        vacia = client.post(
            f"/proyectos/{proyecto_id}/lineas",
            json={
                "codigo": "   ",
                "descripcion": "Sin codigo",
                "importe_presupuestado": 1,
            },
        )
        assert vacia.status_code == 422, vacia.text

        ajena = client.patch(
            f"/proyectos/999999999/lineas/{padre_id}",
            json={
                "codigo": "A1",
                "descripcion": "No es de esta obra",
                "importe_presupuestado": 1,
            },
        )
        assert ajena.status_code == 404, ajena.text
    finally:
        client.delete(f"/proyectos/{proyecto_id}")
