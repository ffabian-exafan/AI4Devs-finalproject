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


def test_importe_montaje_no_incluye_material(client: TestClient, db: Session):
    """La base del contrato es la suma es_montaje, no el total del Excel."""
    from app.models import Presupuesto
    from app.services.proyectos import borrar_proyecto

    proyecto = Proyecto(
        nombre="Obra ficticia montaje vs material",
        tipo="llave_en_mano",
        estado="borrador",
    )
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave ficticia",
        importe_presupuestado=Decimal("1500.00"),
    )
    db.add(nave)
    db.flush()
    excel = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="electricidad-ficticia.xlsx",
        estado_extraccion="pendiente",
        es_escaneado=False,
        formato="excel_expertis",
    )
    db.add(excel)
    db.flush()
    apartado = Tarea(
        nave_id=nave.id,
        presupuesto_id=excel.id,
        codigo="8.2",
        nivel="apartado",
        descripcion="Electricidad ficticia",
        importe_presupuestado=Decimal("1500.00"),
        es_montaje=False,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(apartado)
    db.flush()
    material = Tarea(
        nave_id=nave.id,
        presupuesto_id=excel.id,
        tarea_padre_id=apartado.id,
        codigo="8.2.1",
        nivel="partida",
        descripcion="Cable ficticio",
        importe_presupuestado=Decimal("1000.00"),
        es_montaje=False,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    montaje = Tarea(
        nave_id=nave.id,
        presupuesto_id=excel.id,
        tarea_padre_id=apartado.id,
        codigo="8.2.2",
        nivel="partida",
        descripcion="MONTAJE electricidad ficticia",
        importe_presupuestado=Decimal("500.00"),
        es_montaje=True,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add_all([material, montaje])
    db.commit()
    try:
        detalle = client.get(f"/proyectos/{proyecto.id}")
        assert detalle.status_code == 200, detalle.text
        fila = next(a for a in detalle.json()["apartados"] if a["id"] == apartado.id)
        assert Decimal(str(fila["importe_presupuestado"])) == Decimal("1500.00")
        assert Decimal(str(fila["importe_montaje"])) == Decimal("500.00")
        assert Decimal(str(fila["importe_montaje"])) < Decimal(
            str(fila["importe_presupuestado"])
        )
    finally:
        borrar_proyecto(db, proyecto.id)


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
    assert "explicaci" in response.json()["detail"].lower()


def _apartado(nave_id: int, presupuesto_id: int, codigo: str, montaje: str) -> tuple[Tarea, Tarea]:
    apartado = Tarea(
        nave_id=nave_id,
        presupuesto_id=presupuesto_id,
        codigo=codigo,
        nivel="apartado",
        descripcion=f"Apartado ficticio {codigo}",
        importe_presupuestado=Decimal(montaje) + Decimal("10.00"),
        es_montaje=False,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    return apartado, Tarea(
        nave_id=nave_id,
        presupuesto_id=presupuesto_id,
        codigo=codigo + ".1",
        nivel="partida",
        descripcion=f"MONTAJE ficticio {codigo}",
        importe_presupuestado=Decimal(montaje),
        es_montaje=True,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )


def test_contrato_enlaza_varios_apartados(client: TestClient, db: Session):
    """Un contrato puede cubrir más de un apartado. El precio se prorratea por montaje."""
    from app.models import Contratista, Presupuesto
    from app.services.proyectos import borrar_proyecto
    import uuid

    proyecto = Proyecto(
        nombre="Obra ficticia varios apartados",
        tipo="llave_en_mano",
        estado="borrador",
    )
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave ficticia",
        importe_presupuestado=Decimal("0"),
    )
    db.add(nave)
    db.flush()
    excel = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="varios-ficticio.xlsx",
        estado_extraccion="pendiente",
        es_escaneado=False,
        formato="excel_expertis",
    )
    db.add(excel)
    db.flush()
    apartado_a, linea_a = _apartado(nave.id, excel.id, "8.1", "200.00")
    apartado_b, linea_b = _apartado(nave.id, excel.id, "8.2", "100.00")
    db.add_all([apartado_a, apartado_b])
    db.flush()
    linea_a.tarea_padre_id = apartado_a.id
    linea_b.tarea_padre_id = apartado_b.id
    db.add_all([linea_a, linea_b])
    nif = "B" + uuid.uuid4().hex[:8].upper()
    contratista = Contratista(nif=nif, nombre="SUBCONTRATA_FICTICIA", tipo="externo")
    db.add(contratista)
    db.flush()
    contrato = Contrato(
        proyecto_id=proyecto.id,
        nave_id=nave.id,
        contratista_id=contratista.id,
        precio_total=Decimal("90.00"),
        fichero_origen="contrato-ficticio.md",
        estado_extraccion="pendiente_revision",
    )
    db.add(contrato)
    db.commit()

    try:
        vacio = client.post(
            f"/proyectos/{proyecto.id}/contratos/{contrato.id}/enlazar-apartado",
            json={},
        )
        assert vacio.status_code == 422

        enlace = client.post(
            f"/proyectos/{proyecto.id}/contratos/{contrato.id}/enlazar-apartado",
            json={"tarea_apartado_ids": [apartado_a.id, apartado_b.id, apartado_a.id]},
        )
        assert enlace.status_code == 200, enlace.text
        cuerpo = enlace.json()
        assert len(cuerpo["apartados"]) == 2
        assert {ap["tarea_apartado_id"] for ap in cuerpo["apartados"]} == {
            apartado_a.id,
            apartado_b.id,
        }

        detalle = client.get(f"/proyectos/{proyecto.id}").json()
        fila = next(c for c in detalle["contratos"] if c["id"] == contrato.id)
        assert set(fila["tarea_apartado_ids"]) == {apartado_a.id, apartado_b.id}
        assert fila["sugerencias"] == []
        por_id = {ap["id"]: ap for ap in detalle["apartados"]}
        parte_a = next(
            c for c in por_id[apartado_a.id]["contratos"] if c["id"] == contrato.id
        )
        parte_b = next(
            c for c in por_id[apartado_b.id]["contratos"] if c["id"] == contrato.id
        )
        assert Decimal(str(parte_a["contratado"])) == Decimal("60.00")
        assert Decimal(str(parte_b["contratado"])) == Decimal("30.00")

        uno = client.post(
            f"/proyectos/{proyecto.id}/contratos/{contrato.id}/enlazar-apartado",
            json={"tarea_apartado_id": apartado_a.id},
        )
        assert uno.status_code == 200, uno.text
        assert len(uno.json()["apartados"]) == 1
        detalle_uno = client.get(f"/proyectos/{proyecto.id}").json()
        fila_uno = next(c for c in detalle_uno["contratos"] if c["id"] == contrato.id)
        assert fila_uno["tarea_apartado_ids"] == [apartado_a.id]
        solo_b = next(ap for ap in detalle_uno["apartados"] if ap["id"] == apartado_b.id)
        assert solo_b["contratos"] == []
    finally:
        borrar_proyecto(db, proyecto.id)


def test_apartado_de_contrato_exige_explicacion_y_no_descuadra_el_excel(
    client: TestClient,
    db: Session,
):
    """Un apartado del contrato que no está en el Excel justifica parte del precio."""
    from app.models import Contratista, Presupuesto
    from app.services.proyectos import borrar_proyecto
    import uuid

    proyecto = Proyecto(
        nombre="Obra ficticia apartado de contrato",
        tipo="llave_en_mano",
        estado="borrador",
    )
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave ficticia",
        importe_presupuestado=Decimal("0"),
    )
    db.add(nave)
    db.flush()
    excel = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="contrato-fuera-excel.xlsx",
        estado_extraccion="pendiente",
        es_escaneado=False,
        formato="excel_expertis",
    )
    db.add(excel)
    db.flush()
    apartado = Tarea(
        nave_id=nave.id,
        presupuesto_id=excel.id,
        codigo="01",
        nivel="apartado",
        descripcion="COMEDEROS FICTICIOS",
        importe_presupuestado=Decimal("200.00"),
        es_montaje=False,
        solo_gestion=False,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(apartado)
    db.flush()
    montaje = Tarea(
        nave_id=nave.id,
        presupuesto_id=excel.id,
        tarea_padre_id=apartado.id,
        codigo="01.M",
        nivel="partida",
        descripcion="MONTAJE FICTICIO",
        importe_presupuestado=Decimal("60.00"),
        es_montaje=True,
        solo_gestion=False,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(montaje)
    nif = "B" + uuid.uuid4().hex[:8].upper()
    contratista = Contratista(nif=nif, nombre="SUBCONTRATA_FICTICIA", tipo="externo")
    db.add(contratista)
    db.flush()
    contrato = Contrato(
        proyecto_id=proyecto.id,
        nave_id=nave.id,
        contratista_id=contratista.id,
        precio_total=Decimal("90.00"),
        fichero_origen="contrato-ficticio.md",
        estado_extraccion="pendiente_revision",
    )
    db.add(contrato)
    db.flush()
    del_contrato = Tarea(
        nave_id=nave.id,
        contrato_id=contrato.id,
        contratista_id=contratista.id,
        codigo="C.1",
        nivel="apartado",
        descripcion="Andamiaje ficticio que no sale en el Excel",
        importe_presupuestado=Decimal("30.00"),
        es_montaje=False,
        solo_gestion=False,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(del_contrato)
    db.commit()

    try:
        detalle = client.get(f"/proyectos/{proyecto.id}").json()
        fila = next(c for c in detalle["contratos"] if c["id"] == contrato.id)
        assert [ap["id"] for ap in fila["apartados_fuera_excel"]] == [del_contrato.id]

        sin_texto = client.post(
            f"/proyectos/{proyecto.id}/contratos/{contrato.id}/enlazar-apartado",
            json={"tarea_apartado_ids": [apartado.id, del_contrato.id]},
        )
        assert sin_texto.status_code == 422

        enlace = client.post(
            f"/proyectos/{proyecto.id}/contratos/{contrato.id}/enlazar-apartado",
            json={
                "tarea_apartado_ids": [apartado.id, del_contrato.id],
                "explicaciones": [
                    {
                        "tarea_id": del_contrato.id,
                        "explicacion": "Este trabajo no está en el Excel de la obra.",
                    }
                ],
            },
        )
        assert enlace.status_code == 200, enlace.text

        despues = client.get(f"/proyectos/{proyecto.id}").json()
        por_id = {ap["id"]: ap for ap in despues["apartados"]}
        parte = next(c for c in por_id[apartado.id]["contratos"] if c["id"] == contrato.id)
        assert Decimal(str(parte["contratado"])) == Decimal("60.00")
        fila = next(c for c in despues["contratos"] if c["id"] == contrato.id)
        justificado = next(ap for ap in fila["apartados_enlace"] if ap["es_de_contrato"])
        assert justificado["explicacion"] == "Este trabajo no está en el Excel de la obra."

        manual = client.post(
            f"/proyectos/{proyecto.id}/contratos/{contrato.id}/enlazar-apartado",
            json={
                "apartados_nuevos": [
                    {
                        "descripcion": "Retoque ficticio",
                        "importe": "15.00",
                        "explicacion": "Sale en el contrato y no en el Excel.",
                    }
                ]
            },
        )
        assert manual.status_code == 200, manual.text
        assert manual.json()["apartados"][0]["descripcion_apartado"] == "Retoque ficticio"
        corto = client.post(
            f"/proyectos/{proyecto.id}/contratos/{contrato.id}/enlazar-apartado",
            json={
                "apartados_nuevos": [
                    {"descripcion": "Otro", "importe": "10.00", "explicacion": "no"}
                ]
            },
        )
        assert corto.status_code == 422
    finally:
        borrar_proyecto(db, proyecto.id)
