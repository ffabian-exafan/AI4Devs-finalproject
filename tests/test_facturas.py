"""Flujo de carga, revisión y seguimiento de facturas."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Contratista, Contrato, Nave, Presupuesto, Proyecto, Tarea
from app.services.ocr import ResultadoOcr

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "factura_subcontrata_anonimizada.md"
)
NIF_FICTICIO = "B00000001"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def escenario_factura(db: Session) -> dict:
    proyecto = Proyecto(
        nombre="Proyecto ficticio para facturas",
        tipo="reforma",
        estado="en_curso",
    )
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="NF",
        descripcion="Nave ficticia",
        importe_presupuestado=Decimal("8000"),
    )
    db.add(nave)
    db.flush()
    presupuesto = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="presupuesto_ficticio.md",
        fecha=date(2026, 9, 1),
        estado_extraccion="confirmada",
        es_escaneado=False,
    )
    db.add(presupuesto)
    db.flush()
    apartado = Tarea(
        nave_id=nave.id,
        presupuesto_id=presupuesto.id,
        codigo="1",
        nivel="apartado",
        capitulo="Capítulo ficticio",
        descripcion="Instalación ficticia",
        importe_presupuestado=Decimal("8000"),
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(apartado)
    db.flush()
    contratista = (
        db.query(Contratista).filter(Contratista.nif == NIF_FICTICIO).first()
    )
    if contratista is None:
        contratista = Contratista(
            nif=NIF_FICTICIO,
            nombre="SUBCONTRATISTA_1",
            tipo="externo",
        )
        db.add(contratista)
        db.flush()
    contrato = Contrato(
        proyecto_id=proyecto.id,
        nave_id=nave.id,
        contratista_id=contratista.id,
        tarea_apartado_id=apartado.id,
        referencia_presupuesto="[REF_FICTICIA]",
        precio_total=Decimal("5000"),
        fecha_firma=date(2026, 9, 1),
        plazo_ejecucion=date(2026, 12, 1),
        condiciones_facturacion="Condición ficticia",
        fichero_origen="contrato_ficticio.md",
        estado_extraccion="confirmada",
    )
    db.add(contrato)
    db.commit()
    return {
        "proyecto_id": proyecto.id,
        "apartado_id": apartado.id,
        "contrato_id": contrato.id,
    }


def test_factura_pendiente_no_suma_y_confirmada_actualiza_seguimiento(
    client: TestClient,
    escenario_factura: dict,
):
    proyecto_id = escenario_factura["proyecto_id"]
    respuesta = client.post(
        "/facturas",
        data={"proyecto_id": str(proyecto_id)},
        files={"fichero": (FIXTURE.name, FIXTURE.read_bytes(), "text/markdown")},
    )
    assert respuesta.status_code == 201, respuesta.text
    importada = respuesta.json()
    assert importada["estado_revision"] == "pendiente"
    assert importada["contrato_id"] == escenario_factura["contrato_id"]

    control_pendiente = client.get(
        f"/proyectos/{proyecto_id}/control-economico"
    ).json()
    assert control_pendiente["por_contrato"][0]["facturado"] == 0

    factura_id = importada["factura_id"]
    revision = client.get(f"/facturas/{factura_id}")
    assert revision.status_code == 200
    datos = revision.json()
    assert datos["es_escaneada"] is False
    assert len(datos["contratos_candidatos"]) == 1

    confirmar = client.post(
        f"/facturas/{factura_id}/confirmar",
        json={
            "numero": datos["numero"],
            "fecha_emision": datos["fecha_emision"],
            "base_imponible": datos["base_imponible"],
            "iva": datos["iva"],
            "irpf": datos["irpf"],
            "retencion_garantia": datos["retencion_garantia"],
            "total": datos["total"],
            "tipo": datos["tipo"],
            "contrato_id": escenario_factura["contrato_id"],
            "lineas": [
                {
                    "id": linea["id"],
                    "descripcion": linea["descripcion"],
                    "importe": linea["importe"],
                }
                for linea in datos["lineas"]
            ],
        },
    )
    assert confirmar.status_code == 200, confirmar.text

    control = client.get(f"/proyectos/{proyecto_id}/control-economico").json()
    assert Decimal(str(control["por_contrato"][0]["facturado"])) == Decimal(
        "1210.00"
    )
    detalle = client.get(f"/proyectos/{proyecto_id}").json()
    contrato = detalle["apartados"][0]["contratos"][0]
    assert Decimal(str(contrato["facturado"])) == Decimal("1210.00")
    assert Decimal(str(contrato["pendiente"])) == Decimal("3790.00")


def test_factura_rechaza_nif_desconocido(
    client: TestClient,
    db: Session,
    escenario_factura: dict,
):
    nif_desconocido = f"Z{escenario_factura['proyecto_id']:08d}"
    assert (
        db.query(Contratista).filter(Contratista.nif == nif_desconocido).first()
        is None
    )
    contenido = FIXTURE.read_text(encoding="utf-8").replace(
        NIF_FICTICIO, nif_desconocido
    )
    respuesta = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": ("factura_ficticia.md", contenido, "text/markdown")},
    )
    assert respuesta.status_code == 422
    assert "No existe un contratista" in respuesta.text


def test_confirmacion_rechaza_contrato_ajeno(
    client: TestClient,
    db: Session,
    escenario_factura: dict,
):
    otro_proyecto = Proyecto(
        nombre="Otro proyecto ficticio",
        tipo="reforma",
        estado="en_curso",
    )
    db.add(otro_proyecto)
    db.flush()
    contratista = (
        db.query(Contratista).filter(Contratista.nif == NIF_FICTICIO).one()
    )
    contrato_ajeno = Contrato(
        proyecto_id=otro_proyecto.id,
        contratista_id=contratista.id,
        precio_total=Decimal("2000"),
        fichero_origen="contrato_ajeno_ficticio.md",
        estado_extraccion="confirmada",
    )
    db.add(contrato_ajeno)
    db.commit()

    importada = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": (FIXTURE.name, FIXTURE.read_bytes(), "text/markdown")},
    ).json()
    datos = client.get(f"/facturas/{importada['factura_id']}").json()
    respuesta = client.post(
        f"/facturas/{importada['factura_id']}/confirmar",
        json={
            "numero": datos["numero"],
            "fecha_emision": datos["fecha_emision"],
            "base_imponible": datos["base_imponible"],
            "iva": datos["iva"],
            "irpf": datos["irpf"],
            "retencion_garantia": datos["retencion_garantia"],
            "total": datos["total"],
            "tipo": datos["tipo"],
            "contrato_id": contrato_ajeno.id,
            "lineas": [],
        },
    )
    assert respuesta.status_code == 422
    assert "no pertenece al proyecto" in respuesta.text

    otro_contratista = Contratista(
        nif=f"Q{escenario_factura['proyecto_id']:08d}",
        nombre="SUBCONTRATISTA_FICTICIO_AJENO",
        tipo="externo",
    )
    db.add(otro_contratista)
    db.flush()
    contrato_otro_contratista = Contrato(
        proyecto_id=escenario_factura["proyecto_id"],
        contratista_id=otro_contratista.id,
        precio_total=Decimal("3000"),
        fichero_origen="contrato_otro_contratista_ficticio.md",
        estado_extraccion="confirmada",
    )
    db.add(contrato_otro_contratista)
    db.commit()

    respuesta = client.post(
        f"/facturas/{importada['factura_id']}/confirmar",
        json={
            "numero": datos["numero"],
            "fecha_emision": datos["fecha_emision"],
            "base_imponible": datos["base_imponible"],
            "iva": datos["iva"],
            "irpf": datos["irpf"],
            "retencion_garantia": datos["retencion_garantia"],
            "total": datos["total"],
            "tipo": datos["tipo"],
            "contrato_id": contrato_otro_contratista.id,
            "lineas": [],
        },
    )
    assert respuesta.status_code == 422
    assert "no pertenece al contratista" in respuesta.text


def test_factura_escaneada_siempre_queda_pendiente(
    client: TestClient,
    escenario_factura: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    texto = FIXTURE.read_text(encoding="utf-8")
    monkeypatch.setattr(
        "app.services.facturas.ocr.ocr_imagen",
        lambda contenido: ResultadoOcr(texto=texto, motor="test"),
    )
    respuesta = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": ("factura_ficticia.png", b"imagen-ficticia", "image/png")},
    )
    assert respuesta.status_code == 201, respuesta.text
    factura = client.get(f"/facturas/{respuesta.json()['factura_id']}").json()
    assert factura["es_escaneada"] is True
    assert factura["estado_revision"] == "pendiente"
