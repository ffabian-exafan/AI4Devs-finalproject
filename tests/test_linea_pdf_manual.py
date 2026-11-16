"""Línea de importe añadida a mano en el PDF del cliente."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import (
    Contratista,
    Contrato,
    LineaPdfCliente,
    LineaPdfClienteTarea,
    Nave,
    Presupuesto,
    Proyecto,
    Tarea,
)
from app.schemas.extraccion import ApartadoExtraido, NaveExtraida, PresupuestoExtraido
from app.services.proyectos import borrar_proyecto


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


def _obra(db: Session) -> dict:
    proyecto = Proyecto(nombre="Obra ficticia linea manual", tipo="llave_en_mano", estado="borrador")
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave ficticia",
        importe_presupuestado=Decimal("40.00"),
    )
    db.add(nave)
    db.flush()
    pdf = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="contrato-cliente-ficticio.md",
        estado_extraccion="extraido",
        es_escaneado=False,
        formato="pdf_cliente",
    )
    excel = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="ventilacion-ficticia.xlsx",
        estado_extraccion="pendiente",
        es_escaneado=False,
        formato="excel_expertis",
    )
    db.add_all([pdf, excel])
    db.flush()
    uno = Tarea(
        nave_id=nave.id,
        presupuesto_id=excel.id,
        codigo="01",
        nivel="subapartado",
        descripcion="Bloque uno ficticio",
        importe_presupuestado=Decimal("10.00"),
        tiene_anotacion_manual=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    dos = Tarea(
        nave_id=nave.id,
        presupuesto_id=excel.id,
        codigo="02",
        nivel="subapartado",
        descripcion="Bloque dos ficticio",
        importe_presupuestado=Decimal("30.00"),
        tiene_anotacion_manual=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add_all([uno, dos])
    db.flush()
    return {"proyecto": proyecto, "nave": nave, "pdf": pdf, "excel": excel, "uno": uno, "dos": dos}


def _linea(db: Session, pdf_id: int, **datos) -> LineaPdfCliente:
    fila = LineaPdfCliente(
        presupuesto_id=pdf_id,
        orden=datos.pop("orden", 0),
        tipo=datos.pop("tipo", "importe"),
        codigo=datos.pop("codigo", "S1"),
        descripcion=datos.pop("descripcion", "Salida leida"),
        importe=datos.pop("importe", Decimal("1000.00")),
        es_manuscrito=datos.pop("es_manuscrito", False),
        es_manual=datos.pop("es_manual", False),
    )
    db.add(fila)
    db.flush()
    return fila


def test_alta_manual_queda_al_final_y_rechaza_datos_malos(client: TestClient, db: Session):
    obra = _obra(db)
    leida = _linea(db, obra["pdf"].id, orden=0, codigo="S1", descripcion="Salida leida")
    db.commit()
    pid = obra["proyecto"].id
    try:
        alta = client.post(
            f"/proyectos/{pid}/lineas-pdf",
            json={"codigo": " 12 ", "descripcion": " Fontanería ficticia ", "importe": 0},
        )
        assert alta.status_code == 201, alta.text
        filas = alta.json()["sugerencias"]
        assert [fila["codigo_pdf"] for fila in filas] == ["S1", "12"]
        manual = filas[-1]
        assert manual["descripcion_pdf"] == "Fontanería ficticia"
        assert manual["importe_pdf"] == 0
        assert manual["es_manual"] is True
        assert filas[0]["es_manual"] is False
        assert manual["id"] != leida.id

        db.expire_all()
        guardada = db.get(LineaPdfCliente, manual["id"])
        assert guardada is not None
        assert guardada.es_manual is True
        assert guardada.es_manuscrito is False

        vacio = client.post(
            f"/proyectos/{pid}/lineas-pdf",
            json={"codigo": "   ", "descripcion": "Fontanería", "importe": 1},
        )
        assert vacio.status_code == 422
        corta = client.post(
            f"/proyectos/{pid}/lineas-pdf",
            json={"codigo": "9", "descripcion": " A ", "importe": 1},
        )
        assert corta.status_code == 422
        negativo = client.post(
            f"/proyectos/{pid}/lineas-pdf",
            json={"codigo": "9", "descripcion": "Fontanería", "importe": -1},
        )
        assert negativo.status_code == 422

        sin_pdf = Proyecto(nombre="Obra sin pdf", tipo="llave_en_mano", estado="borrador")
        db.add(sin_pdf)
        db.commit()
        try:
            falta = client.post(
                f"/proyectos/{sin_pdf.id}/lineas-pdf",
                json={"codigo": "1", "descripcion": "Fontanería", "importe": 1},
            )
            assert falta.status_code == 404
        finally:
            borrar_proyecto(db, sin_pdf.id)
    finally:
        borrar_proyecto(db, pid)


def test_editar_manual_confirmada_reparte_y_la_leida_no_se_toca(client: TestClient, db: Session):
    obra = _obra(db)
    leida = _linea(db, obra["pdf"].id, orden=0)
    db.commit()
    pid = obra["proyecto"].id
    try:
        alta = client.post(
            f"/proyectos/{pid}/lineas-pdf",
            json={"codigo": "12", "descripcion": "Fontanería ficticia", "importe": 100},
        )
        assert alta.status_code == 201, alta.text
        manual_id = alta.json()["sugerencias"][-1]["id"]
        confirmado = client.post(
            f"/proyectos/{pid}/importe-cliente",
            json={
                "tarea_ids": [obra["uno"].id, obra["dos"].id],
                "importe": 100,
                "linea_id": manual_id,
            },
        )
        assert confirmado.status_code == 200, confirmado.text

        editada = client.patch(
            f"/proyectos/{pid}/lineas-pdf/{manual_id}",
            json={"codigo": "12b", "descripcion": "Fontanería revisada", "importe": 40},
        )
        assert editada.status_code == 200, editada.text
        fila = next(item for item in editada.json()["sugerencias"] if item["id"] == manual_id)
        assert fila["codigo_pdf"] == "12b"
        assert fila["descripcion_pdf"] == "Fontanería revisada"
        assert fila["importe_pdf"] == 40
        assert fila["confirmada"] is True
        assert set(fila["tarea_ids"]) == {obra["uno"].id, obra["dos"].id}

        db.expire_all()
        assert db.get(Tarea, obra["uno"].id).importe_contrato_cliente == Decimal("10.00")
        assert db.get(Tarea, obra["dos"].id).importe_contrato_cliente == Decimal("30.00")

        rechazada = client.patch(
            f"/proyectos/{pid}/lineas-pdf/{leida.id}",
            json={"codigo": "Z", "descripcion": "No se toca", "importe": 1},
        )
        assert rechazada.status_code == 422
    finally:
        borrar_proyecto(db, pid)


def test_editar_solo_gestion_no_cambia_el_codigo_del_apartado(client: TestClient, db: Session):
    obra = _obra(db)
    db.commit()
    pid = obra["proyecto"].id
    try:
        alta = client.post(
            f"/proyectos/{pid}/lineas-pdf",
            json={"codigo": "8", "descripcion": "Obra civil ficticia", "importe": 1000},
        )
        manual_id = alta.json()["sugerencias"][-1]["id"]
        marca = client.post(f"/proyectos/{pid}/lineas-pdf/{manual_id}/solo-gestion")
        assert marca.status_code == 201, marca.text
        codigo_apartado = marca.json()["codigo"]

        editada = client.patch(
            f"/proyectos/{pid}/lineas-pdf/{manual_id}",
            json={"codigo": "8b", "descripcion": "Obra civil revisada", "importe": 80},
        )
        assert editada.status_code == 200, editada.text
        db.expire_all()
        apartado = db.get(Tarea, marca.json()["tarea_id"])
        assert apartado is not None
        assert apartado.codigo == codigo_apartado
        assert apartado.descripcion == "Obra civil revisada"
        assert apartado.importe_presupuestado == Decimal("80.00")
        assert apartado.importe_contrato_cliente == Decimal("80.00")
    finally:
        borrar_proyecto(db, pid)


def test_borrar_manual_suelta_el_excel_y_respeta_el_contrato(client: TestClient, db: Session):
    obra = _obra(db)
    leida = _linea(db, obra["pdf"].id, orden=0)
    db.commit()
    pid = obra["proyecto"].id
    try:
        alta = client.post(
            f"/proyectos/{pid}/lineas-pdf",
            json={"codigo": "12", "descripcion": "Fontanería ficticia", "importe": 40},
        )
        manual_id = alta.json()["sugerencias"][-1]["id"]
        client.post(
            f"/proyectos/{pid}/importe-cliente",
            json={"tarea_ids": [obra["uno"].id], "importe": 40, "linea_id": manual_id},
        )
        borrada = client.delete(f"/proyectos/{pid}/lineas-pdf/{manual_id}")
        assert borrada.status_code == 204, borrada.text
        db.expire_all()
        assert db.get(LineaPdfCliente, manual_id) is None
        assert (
            db.query(LineaPdfClienteTarea)
            .filter(LineaPdfClienteTarea.linea_id == manual_id)
            .count()
            == 0
        )
        assert db.get(Tarea, obra["uno"].id).importe_contrato_cliente is None

        leida_no = client.delete(f"/proyectos/{pid}/lineas-pdf/{leida.id}")
        assert leida_no.status_code == 422

        otra = client.post(
            f"/proyectos/{pid}/lineas-pdf",
            json={"codigo": "9", "descripcion": "Gestión ficticia", "importe": 50},
        )
        gestion_id = otra.json()["sugerencias"][-1]["id"]
        marca = client.post(f"/proyectos/{pid}/lineas-pdf/{gestion_id}/solo-gestion")
        assert marca.status_code == 201, marca.text
        contratista = db.query(Contratista).filter(Contratista.nif == "B00000992").first()
        if contratista is None:
            contratista = Contratista(
                nif="B00000992", nombre="Contratista ficticio", tipo="externo"
            )
            db.add(contratista)
            db.flush()
        contrato = Contrato(
            proyecto_id=pid,
            nave_id=obra["nave"].id,
            contratista_id=contratista.id,
            tarea_apartado_id=marca.json()["tarea_id"],
            precio_total=Decimal("50.00"),
            fichero_origen="contrato-ficticio.md",
            estado_extraccion="confirmada",
        )
        db.add(contrato)
        db.commit()
        bloqueada = client.delete(f"/proyectos/{pid}/lineas-pdf/{gestion_id}")
        assert bloqueada.status_code == 422

        contrato.tarea_apartado_id = None
        db.commit()
        libre = client.delete(f"/proyectos/{pid}/lineas-pdf/{gestion_id}")
        assert libre.status_code == 204, libre.text
        db.expire_all()
        assert db.get(Tarea, marca.json()["tarea_id"]) is None
        assert db.get(LineaPdfCliente, gestion_id) is None
    finally:
        db.rollback()
        borrar_proyecto(db, pid)


def test_un_pdf_nuevo_conserva_las_lineas_manuales(
    client: TestClient, db: Session, monkeypatch, tmp_path
):
    from app.config import get_settings

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    obra = _obra(db)
    manual = _linea(
        db,
        obra["pdf"].id,
        orden=3,
        codigo="12",
        descripcion="Fontanería ficticia",
        importe=Decimal("40.00"),
        es_manual=True,
    )
    db.add(
        LineaPdfClienteTarea(
            linea_id=manual.id,
            tarea_id=obra["uno"].id,
            es_sugerencia=False,
        )
    )
    obra["uno"].importe_contrato_cliente = Decimal("40.00")
    db.commit()
    pid = obra["proyecto"].id

    def extraer(_texto):
        return PresupuestoExtraido(
            nombre_proyecto="Obra ficticia",
            naves=[
                NaveExtraida(
                    codigo="N1",
                    descripcion="Nave",
                    apartados=[
                        ApartadoExtraido(
                            codigo="S1",
                            descripcion="Salida leida nueva",
                            importe=Decimal("15.00"),
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr(
        "app.services.presupuesto_excel.extraccion_svc.extraer_presupuesto",
        extraer,
    )
    monkeypatch.setattr(
        "app.services.presupuesto_excel._relacionar_pdf_llm",
        lambda *_args, **_kwargs: None,
    )
    try:
        contraste = client.post(
            f"/proyectos/{pid}/contrastar-presupuesto-cliente",
            files={"fichero": ("contrato-nuevo.md", b"Texto de contrato ficticio nuevo", "text/markdown")},
        )
        assert contraste.status_code == 201, contraste.text
        filas = contraste.json()["sugerencias"]
        assert [fila["codigo_pdf"] for fila in filas] == ["S1", "12"]
        assert filas[0]["es_manual"] is False
        assert filas[0]["descripcion_pdf"] == "Salida leida nueva"
        copiada = filas[1]
        assert copiada["es_manual"] is True
        assert copiada["importe_pdf"] == 40
        assert copiada["confirmada"] is True
        assert copiada["tarea_ids"] == [obra["uno"].id]
        assert copiada["id"] != manual.id
        db.expire_all()
        assert db.get(Tarea, obra["uno"].id).importe_contrato_cliente == Decimal("40.00")
    finally:
        get_settings.cache_clear()
        borrar_proyecto(db, pid)
