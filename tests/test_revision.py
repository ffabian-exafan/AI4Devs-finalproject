"""Test de integración: revisión humana (listar, abrir árbol, confirmar)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "presupuesto_nave_destete_anonimizado.md"
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _aplanar(nodos):
    out = []
    for n in nodos:
        out.append(n)
        out.extend(_aplanar(n.get("hijos") or []))
    return out


def test_flujo_revision_presupuesto(client: TestClient):
    with FIXTURE.open("rb") as fh:
        imp = client.post(
            "/proyectos/importar-presupuesto",
            files={"fichero": (FIXTURE.name, fh, "text/markdown")},
        )
    assert imp.status_code == 201, imp.text
    proyecto_id = imp.json()["proyecto_id"]

    pend = client.get("/revisiones/pendientes")
    assert pend.status_code == 200
    items = [p for p in pend.json() if p["proyecto_id"] == proyecto_id and p["tipo"] == "presupuesto"]
    assert items, "El presupuesto importado debe aparecer como pendiente"
    doc_id = items[0]["documento_id"]
    assert items[0]["anotaciones_manuales"] == 2

    doc = client.get(
        "/revisiones/documento",
        params={"tipo": "presupuesto", "documento_id": doc_id},
    )
    assert doc.status_code == 200, doc.text
    body = doc.json()
    filas = _aplanar(body["arbol"])
    assert filas
    assert any(f["tiene_anotacion_manual"] for f in filas)

    # Confirmar sin resolver manuscritos → 422
    mal = client.post(
        "/revisiones/confirmar",
        json={
            "tipo": "presupuesto",
            "documento_id": doc_id,
            "tareas": [
                {
                    "id": f["id"],
                    "codigo": f["codigo"],
                    "descripcion": f["descripcion"],
                    "capitulo": f.get("capitulo"),
                    "unidad": f.get("unidad"),
                    "cantidad": f.get("cantidad"),
                    "precio_unitario": f.get("precio_unitario"),
                    "importe_presupuestado": f["importe_presupuestado"],
                    "estado_revision": "revisada",
                    "anotacion_confirmada": False,
                }
                for f in filas
            ],
        },
    )
    assert mal.status_code == 422

    # Confirmar bien: manuscritos con anotacion_confirmada
    payload = {
        "tipo": "presupuesto",
        "documento_id": doc_id,
        "tareas": [
            {
                "id": f["id"],
                "codigo": f["codigo"],
                "descripcion": f["descripcion"],
                "capitulo": f.get("capitulo"),
                "unidad": f.get("unidad"),
                "cantidad": f.get("cantidad"),
                "precio_unitario": f.get("precio_unitario"),
                "importe_presupuestado": f["importe_presupuestado"],
                "estado_revision": "confirmada" if f["tiene_anotacion_manual"] else "revisada",
                "anotacion_confirmada": bool(f["tiene_anotacion_manual"]),
            }
            for f in filas
        ],
    }
    ok = client.post("/revisiones/confirmar", json=payload)
    assert ok.status_code == 200, ok.text
    assert ok.json()["ok"] is True

    pend2 = client.get("/revisiones/pendientes")
    assert not any(
        p["documento_id"] == doc_id and p["tipo"] == "presupuesto"
        for p in pend2.json()
    )
