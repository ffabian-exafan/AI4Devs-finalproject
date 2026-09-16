"""
Test de control económico: caso real electricidad presupuestada ≠ contratada
(docs/contexto_proyecto_obra.md) y desvío contratado vs facturado en por_contrato.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Contratista, Contrato, Factura, Nave, Presupuesto, Proyecto, Tarea

# Importes ficticios alineados con las fixtures de extracción (no son datos reales).
# Caso documentado: presupuestado electricidad ≠ contratado subcontrata.
ELECTRICIDAD_PRESUPUESTADA = Decimal("70000.00")
PRECIO_CONTRATO_ELECTRICIDAD = Decimal("45000.00")
assert ELECTRICIDAD_PRESUPUESTADA != PRECIO_CONTRATO_ELECTRICIDAD

NIF_SUBCONTRATA = "B00000001"
FACTURADO_PARCIAL = Decimal("30000.00")


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
def escenario_electricidad(db: Session) -> dict:
    """
    Reproduce el caso real: electricidad presupuestada al cliente ≠ precio
    del contrato con la subcontrata eléctrica. Añade una factura parcial
    certificando el contrato para poblar por_contrato (contratado vs facturado).
    """
    proyecto = Proyecto(
        nombre="Proyecto test desvío electricidad",
        tipo="llave_en_mano",
        estado="en_curso",
    )
    db.add(proyecto)
    db.flush()

    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="N1",
        descripcion="Nave de destete",
        importe_presupuestado=ELECTRICIDAD_PRESUPUESTADA,
    )
    db.add(nave)
    db.flush()

    presupuesto = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="presupuesto_test.md",
        fecha=date(2025, 6, 27),
        estado_extraccion="confirmada",
    )
    db.add(presupuesto)
    db.flush()

    contratista = (
        db.query(Contratista).filter(Contratista.nif == NIF_SUBCONTRATA).first()
    )
    if contratista is None:
        contratista = Contratista(
            nif=NIF_SUBCONTRATA,
            nombre="SUBCONTRATISTA_1",
            tipo="externo",
        )
        db.add(contratista)
        db.flush()

    # Apartado de electricidad del presupuesto (importe al cliente)
    tarea_elec = Tarea(
        nave_id=nave.id,
        presupuesto_id=presupuesto.id,
        contrato_id=None,
        tarea_padre_id=None,
        contratista_id=contratista.id,
        codigo="8.2",
        nivel="apartado",
        capitulo="Instalaciones",
        descripcion="Electricidad",
        unidad=None,
        cantidad=None,
        precio_unitario=None,
        importe_presupuestado=ELECTRICIDAD_PRESUPUESTADA,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(tarea_elec)

    # Contrato real con la subcontrata (precio distinto)
    contrato = Contrato(
        proyecto_id=proyecto.id,
        nave_id=nave.id,
        contratista_id=contratista.id,
        referencia_presupuesto="[REF_PRESUPUESTO_1]",
        precio_total=PRECIO_CONTRATO_ELECTRICIDAD,
        fecha_firma=date(2026, 6, 1),
        plazo_ejecucion=date(2026, 7, 15),
        condiciones_facturacion="Facturación mensual a origen",
        fichero_origen="contrato_test.md",
        estado_extraccion="confirmada",
    )
    db.add(contrato)
    db.flush()

    # Certificación parcial sobre el contrato (dato medido en por_contrato)
    factura = Factura(
        proyecto_id=proyecto.id,
        contratista_id=contratista.id,
        contrato_id=contrato.id,
        numero="F-TEST-001",
        fecha_emision=date(2026, 7, 1),
        base_imponible=FACTURADO_PARCIAL,
        iva=Decimal("0"),
        irpf=Decimal("0"),
        retencion_garantia=Decimal("0"),
        total=FACTURADO_PARCIAL,
        tipo="certificacion",
        fichero_origen="factura_test.md",
        es_escaneada=False,
        estado_revision="confirmada",
    )
    db.add(factura)
    db.commit()

    return {
        "proyecto_id": proyecto.id,
        "contrato_id": contrato.id,
        "presupuestado_electricidad": ELECTRICIDAD_PRESUPUESTADA,
        "contratado": PRECIO_CONTRATO_ELECTRICIDAD,
        "facturado": FACTURADO_PARCIAL,
    }


def test_control_economico_desvio_electricidad(
    client: TestClient,
    escenario_electricidad: dict,
):
    proyecto_id = escenario_electricidad["proyecto_id"]
    presupuestado = escenario_electricidad["presupuestado_electricidad"]
    contratado = escenario_electricidad["contratado"]
    facturado = escenario_electricidad["facturado"]

    # Premisa del caso real documentado
    assert presupuestado != contratado

    response = client.get(f"/proyectos/{proyecto_id}/control-economico")
    assert response.status_code == 200, response.text
    body = response.json()

    # --- por_contrato: contratado vs facturado (dato medido) ---
    assert len(body["por_contrato"]) == 1
    fila = body["por_contrato"][0]
    assert fila["contrato_id"] == escenario_electricidad["contrato_id"]
    assert fila["contratista_nif"] == NIF_SUBCONTRATA
    assert Decimal(str(fila["contratado"])) == contratado
    assert Decimal(str(fila["facturado"])) == facturado
    assert Decimal(str(fila["desvio"])) == facturado - contratado

    # El precio contratado (visible en por_contrato) no cuadra con lo presupuestado
    assert Decimal(str(fila["contratado"])) != presupuestado

    # --- por_contratista ---
    assert len(body["por_contratista"]) == 1
    c = body["por_contratista"][0]
    assert c["nif"] == NIF_SUBCONTRATA
    assert Decimal(str(c["presupuestado"])) == presupuestado
    assert Decimal(str(c["facturado"])) == facturado
    assert Decimal(str(c["desvio"])) == facturado - presupuestado

    # --- por_nave (estimación) ---
    assert len(body["por_nave"]) == 1
    n = body["por_nave"][0]
    assert n["nave"] == "Nave de destete"
    assert Decimal(str(n["presupuestado"])) == presupuestado
    assert n["es_estimacion"] is True
