"""Test de integración: POST /proyectos/importar-presupuesto con la fixture anonimizada."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Nave, Proyecto, Tarea

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "presupuesto_nave_destete_anonimizado.md"
)

# Valores esperados según la fixture y el extractor determinista
NAVES_ESPERADAS = 1
# 8 EXAFAN + opción calefacción + 7 proveedores + fila descuento manuscrito
APARTADOS_ESPERADOS = 17
ANOTACIONES_ESPERADAS = 2


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


def test_importar_presupuesto_fixture_destete(client: TestClient, db: Session):
    assert FIXTURE.exists(), f"Falta la fixture: {FIXTURE}"

    with FIXTURE.open("rb") as fh:
        response = client.post(
            "/proyectos/importar-presupuesto",
            files={"fichero": (FIXTURE.name, fh, "text/markdown")},
        )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["naves_detectadas"] == NAVES_ESPERADAS
    assert body["partidas_detectadas"] == APARTADOS_ESPERADOS
    assert body["anotaciones_manuscritas_detectadas"] == ANOTACIONES_ESPERADAS
    # Hay manuscrito → revisión humana obligatoria aunque las sumas cuadren
    assert body["requiere_revision"] is True

    proyecto_id = body["proyecto_id"]
    assert isinstance(body["presupuesto_id"], int)
    proyecto = db.get(Proyecto, proyecto_id)
    assert proyecto is not None
    assert proyecto.estado == "pendiente_revision"

    naves = db.query(Nave).filter(Nave.proyecto_id == proyecto_id).all()
    assert len(naves) == NAVES_ESPERADAS

    tareas = (
        db.query(Tarea)
        .join(Nave, Tarea.nave_id == Nave.id)
        .filter(Nave.proyecto_id == proyecto_id)
        .all()
    )
    assert len(tareas) == APARTADOS_ESPERADOS
    assert all(t.nivel == "apartado" for t in tareas)
    # El documento cierra por apartado: sin unidad/cantidad/precio unitario
    assert all(t.unidad is None for t in tareas)
    assert all(t.cantidad is None for t in tareas)
    assert all(t.precio_unitario is None for t in tareas)

    manuscritas = [t for t in tareas if t.tiene_anotacion_manual]
    assert len(manuscritas) == ANOTACIONES_ESPERADAS
    assert all(t.estado_revision == "pendiente" for t in manuscritas)

    por_codigo = {t.codigo: t for t in manuscritas}
    assert "1.1" in por_codigo, "Debe marcarse la cubierta (color manuscrito)"
    assert "11.descuento" in por_codigo, "Debe marcarse el descuento/importe final manuscrito"
    assert "Verde" in por_codigo["1.1"].descripcion
