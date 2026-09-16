"""Test de integración: POST /proyectos/{id}/importar-contrato."""

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Contrato, Nave, Proyecto, Tarea

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "contrato_subcontrata_electricidad_anonimizado.md"
)

NIF_ESPERADO = "B00000001"
PRECIO_TOTAL_ESPERADO = Decimal("45000.00")
SALAS_ESPERADAS = 3


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


@pytest.fixture
def proyecto_con_nave(db: Session) -> Proyecto:
    proyecto = Proyecto(
        nombre="Proyecto test contrato electricidad",
        tipo="llave_en_mano",
        estado="en_curso",
    )
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave de destete",
        importe_presupuestado=Decimal("0"),
    )
    db.add(nave)
    db.commit()
    db.refresh(proyecto)
    return proyecto


def test_importar_contrato_fixture_electricidad(
    client: TestClient,
    db: Session,
    proyecto_con_nave: Proyecto,
):
    assert FIXTURE.exists(), f"Falta la fixture: {FIXTURE}"

    with FIXTURE.open("rb") as fh:
        response = client.post(
            f"/proyectos/{proyecto_con_nave.id}/importar-contrato",
            files={"fichero": (FIXTURE.name, fh, "text/markdown")},
        )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["contratista_nif"] == NIF_ESPERADO
    assert Decimal(str(body["precio_total"])) == PRECIO_TOTAL_ESPERADO
    assert body["partidas_detalle_detectadas"] > 0
    assert body["requiere_revision"] is True

    contrato = db.get(Contrato, body["contrato_id"])
    assert contrato is not None
    assert contrato.proyecto_id == proyecto_con_nave.id
    assert contrato.precio_total == PRECIO_TOTAL_ESPERADO
    assert contrato.plazo_ejecucion is not None
    assert contrato.plazo_ejecucion.isoformat() == "2026-07-15"
    assert contrato.condiciones_facturacion
    assert "factura" in contrato.condiciones_facturacion.lower()

    tareas = db.query(Tarea).filter(Tarea.contrato_id == contrato.id).all()
    assert all(t.presupuesto_id is None for t in tareas), (
        "El árbol del contrato no debe enlazarse solo al presupuesto"
    )
    assert all(t.contrato_id == contrato.id for t in tareas)

    salas = [t for t in tareas if t.nivel == "apartado" and t.descripcion.startswith("Sala ")]
    assert len(salas) == SALAS_ESPERADAS
    assert {t.descripcion for t in salas} == {"Sala 1", "Sala 2", "Sala 3"}

    # Cada sala tiene partidas hijas (vía subapartados) con precio unitario
    for sala in salas:
        partidas_sala = _partidas_descendientes(db, sala.id)
        assert partidas_sala, f"{sala.descripcion} debe tener partidas de detalle"
        assert all(p.precio_unitario is not None for p in partidas_sala)
        assert all(p.cantidad is not None for p in partidas_sala)
        assert all(p.unidad is not None for p in partidas_sala)
        # Numeración anidada tipo 4.3.1 bajo Sala 1
        if sala.codigo == "4":
            codigos = {p.codigo for p in partidas_sala}
            assert any(c.startswith("4.3.1") for c in codigos)


def _partidas_descendientes(db: Session, raiz_id: int) -> list[Tarea]:
    """BFS: partidas (nivel=partida) bajo un nodo del árbol."""
    resultado: list[Tarea] = []
    cola = [raiz_id]
    while cola:
        padre_id = cola.pop(0)
        hijos = db.query(Tarea).filter(Tarea.tarea_padre_id == padre_id).all()
        for h in hijos:
            if h.nivel == "partida":
                resultado.append(h)
            else:
                cola.append(h.id)
    return resultado
