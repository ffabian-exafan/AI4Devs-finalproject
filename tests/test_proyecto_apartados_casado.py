"""Tests: detalle de proyecto con apartados y enlace contrato↔apartado."""

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Contrato, Nave, Proyecto, Tarea

FIXTURE_PRESUPUESTO = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "presupuesto_nave_destete_anonimizado.md"
)
FIXTURE_CONTRATO = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "contrato_subcontrata_electricidad_anonimizado.md"
)


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


def test_detalle_incluye_apartados_tras_importar_presupuesto(
    client: TestClient,
    db: Session,
):
    assert FIXTURE_PRESUPUESTO.exists()
    with FIXTURE_PRESUPUESTO.open("rb") as fh:
        response = client.post(
            "/proyectos/importar-presupuesto",
            files={"fichero": (FIXTURE_PRESUPUESTO.name, fh, "text/markdown")},
        )
    assert response.status_code == 201, response.text
    proyecto_id = response.json()["proyecto_id"]

    detalle = client.get(f"/proyectos/{proyecto_id}")
    assert detalle.status_code == 200, detalle.text
    body = detalle.json()
    assert body["id"] == proyecto_id
    assert len(body["apartados"]) >= 1
    codigos = {a["codigo"] for a in body["apartados"]}
    assert "8.2" in codigos
    electricidad = next(a for a in body["apartados"] if a["codigo"] == "8.2")
    assert "lectric" in electricidad["descripcion"].lower()
    assert body["contratos"] == []


def test_sugerencia_y_enlace_contrato_electricidad(
    client: TestClient,
    db: Session,
):
    with FIXTURE_PRESUPUESTO.open("rb") as fh:
        r_p = client.post(
            "/proyectos/importar-presupuesto",
            files={"fichero": (FIXTURE_PRESUPUESTO.name, fh, "text/markdown")},
        )
    assert r_p.status_code == 201, r_p.text
    proyecto_id = r_p.json()["proyecto_id"]

    with FIXTURE_CONTRATO.open("rb") as fh:
        r_c = client.post(
            f"/proyectos/{proyecto_id}/importar-contrato",
            files={"fichero": (FIXTURE_CONTRATO.name, fh, "text/markdown")},
        )
    assert r_c.status_code == 201, r_c.text
    body_c = r_c.json()
    assert body_c["requiere_revision"] is True
    sugerencias = body_c["sugerencias_apartado"]
    assert len(sugerencias) >= 1
    top = sugerencias[0]
    assert top["codigo"] == "8.2"
    assert Decimal(str(top["confianza"])) >= Decimal("0.5")

    contrato_id = body_c["contrato_id"]
    enlace = client.post(
        f"/proyectos/{proyecto_id}/contratos/{contrato_id}/enlazar-apartado",
        json={"tarea_apartado_id": top["tarea_id"]},
    )
    assert enlace.status_code == 200, enlace.text
    out = enlace.json()
    assert out["contrato_id"] == contrato_id
    assert out["codigo_apartado"] == "8.2"

    db.expire_all()
    contrato = db.get(Contrato, contrato_id)
    assert contrato is not None
    assert contrato.tarea_apartado_id == top["tarea_id"]

    detalle = client.get(f"/proyectos/{proyecto_id}").json()
    ap = next(a for a in detalle["apartados"] if a["codigo"] == "8.2")
    assert ap["contrato_enlazado_id"] == contrato_id
    c_ui = next(c for c in detalle["contratos"] if c["id"] == contrato_id)
    assert c_ui["tarea_apartado_id"] == top["tarea_id"]
    assert c_ui["sugerencias"] == []


def test_enlazar_apartado_rechaza_tarea_de_contrato(client: TestClient, db: Session):
    proyecto = Proyecto(
        nombre="Proyecto enlace inválido",
        tipo="llave_en_mano",
        estado="en_curso",
    )
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave test",
        importe_presupuestado=Decimal("0"),
    )
    db.add(nave)
    db.flush()
    from app.models import Contratista
    import uuid

    nif = "B" + uuid.uuid4().hex[:8].upper()
    contratista = Contratista(
        nif=nif,
        nombre="SUBCONTRATISTA_TEST",
        tipo="externo",
    )
    db.add(contratista)
    db.flush()
    contrato = Contrato(
        proyecto_id=proyecto.id,
        nave_id=nave.id,
        contratista_id=contratista.id,
        precio_total=Decimal("100.00"),
        fichero_origen="test.md",
        estado_extraccion="pendiente_revision",
    )
    db.add(contrato)
    db.flush()
    tarea_contrato = Tarea(
        nave_id=nave.id,
        contrato_id=contrato.id,
        codigo="1",
        nivel="apartado",
        descripcion="Solo del contrato",
        importe_presupuestado=Decimal("100.00"),
        tiene_anotacion_manual=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(tarea_contrato)
    db.commit()

    response = client.post(
        f"/proyectos/{proyecto.id}/contratos/{contrato.id}/enlazar-apartado",
        json={"tarea_apartado_id": tarea_contrato.id},
    )
    assert response.status_code == 422
    assert "presupuesto" in response.json()["detail"].lower()
