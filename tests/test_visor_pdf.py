"""El PDF se puede ver en línea. La descarga sigue forzando el fichero."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Contratista, Factura, Presupuesto, Proyecto
from app.services import almacen as almacen_svc


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


def _disposicion(respuesta) -> str:
    return respuesta.headers["content-disposition"].split(";", 1)[0].strip().lower()


def test_el_pdf_se_ve_en_linea_y_el_excel_se_descarga(
    client: TestClient, db: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        proyecto = Proyecto(
            nombre="Obra ficticia visor",
            tipo="llave_en_mano",
            estado="en_curso",
        )
        db.add(proyecto)
        db.flush()
        pdf = Presupuesto(
            proyecto_id=proyecto.id,
            version=1,
            fichero_origen="presupuesto-ficticio.pdf",
            estado_extraccion="confirmada",
            es_escaneado=False,
            formato="pdf_cliente",
        )
        excel = Presupuesto(
            proyecto_id=proyecto.id,
            version=2,
            fichero_origen="presupuesto-ficticio.xlsx",
            estado_extraccion="confirmada",
            es_escaneado=False,
            formato="excel_expertis",
        )
        db.add(pdf)
        db.add(excel)
        db.flush()
        pdf.ruta_almacen = almacen_svc.guardar(
            proyecto.id, "presupuesto", pdf.id, pdf.fichero_origen, b"%PDF-1.4 ficticio"
        )
        excel.ruta_almacen = almacen_svc.guardar(
            proyecto.id, "presupuesto", excel.id, excel.fichero_origen, b"excel-ficticio"
        )
        db.commit()

        base = f"/proyectos/{proyecto.id}/presupuestos"
        descarga = client.get(f"{base}/{pdf.id}/fichero")
        assert descarga.status_code == 200, descarga.text
        assert _disposicion(descarga) == "attachment"
        assert descarga.content == b"%PDF-1.4 ficticio"

        visto = client.get(f"{base}/{pdf.id}/fichero", params={"ver": "1"})
        assert visto.status_code == 200, visto.text
        assert _disposicion(visto) == "inline"
        assert visto.headers["content-type"].startswith("application/pdf")
        assert "presupuesto-ficticio.pdf" in visto.headers["content-disposition"]
        assert visto.content == b"%PDF-1.4 ficticio"

        excel_visto = client.get(f"{base}/{excel.id}/fichero", params={"ver": "1"})
        assert excel_visto.status_code == 200, excel_visto.text
        assert _disposicion(excel_visto) == "attachment"
        assert excel_visto.headers["content-type"].startswith("application/octet-stream")
    finally:
        get_settings.cache_clear()


def test_el_sello_se_ve_en_linea(client: TestClient, db: Session, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        proyecto = Proyecto(
            nombre="Obra ficticia sello",
            tipo="llave_en_mano",
            estado="en_curso",
        )
        contratista = Contratista(
            nif="B99999019",
            nombre="Proveedor ficticio",
            tipo="externo",
        )
        db.add(proyecto)
        db.flush()
        contratista.nif = f"B{proyecto.id:08d}"[:20]
        db.add(contratista)
        db.flush()
        factura = Factura(
            proyecto_id=proyecto.id,
            contratista_id=contratista.id,
            numero="F-FICT-19",
            base_imponible=Decimal("10.00"),
            iva=Decimal("0.00"),
            irpf=Decimal("0.00"),
            retencion_garantia=Decimal("0.00"),
            total=Decimal("10.00"),
            tipo="ordinaria",
            fichero_origen="factura-ficticia.pdf",
            estado_revision="confirmada",
            es_escaneada=False,
        )
        db.add(factura)
        db.flush()
        factura.ruta_sello = almacen_svc.guardar(
            proyecto.id,
            "factura",
            factura.id,
            "sello-confirmacion.pdf",
            b"%PDF-1.4 sello",
        )
        db.commit()

        descarga = client.get(f"/facturas/{factura.id}/sello")
        assert descarga.status_code == 200, descarga.text
        assert _disposicion(descarga) == "attachment"

        visto = client.get(f"/facturas/{factura.id}/sello", params={"ver": "1"})
        assert visto.status_code == 200, visto.text
        assert _disposicion(visto) == "inline"
        assert visto.headers["content-type"].startswith("application/pdf")
        assert "sello-factura.pdf" in visto.headers["content-disposition"]
        assert visto.content == b"%PDF-1.4 sello"
    finally:
        get_settings.cache_clear()
