"""Inversión del sujeto pasivo. Obras y PDF ficticios, sin datos reales."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Contratista, Factura, Proyecto, RegistroAccion
from app.models.registro_accion import ACCIONES
from app.services.registro import ETIQUETAS
from tests.sesion import entrar

PDF = b"%PDF-1.4\n%carta ficticia\n%%EOF\n"
NIF_FICTICIO = "B00000001"


def test_el_catalogo_conoce_la_marca():
    assert "marcar_isp" in ACCIONES
    assert "quitar_isp" in ACCIONES
    assert ETIQUETAS["marcar_isp"] == "Marcó la inversión del sujeto pasivo"
    assert ETIQUETAS["quitar_isp"] == "Quitó la inversión del sujeto pasivo"


def test_la_pantalla_de_registro_lista_la_marca():
    texto = Path("app/static/js/registro.js").read_text(encoding="utf-8")
    assert '["marcar_isp", "Marcó la inversión del sujeto pasivo"]' in texto
    assert '["quitar_isp", "Quitó la inversión del sujeto pasivo"]' in texto


def test_el_almacen_guarda_la_carta(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.services import almacen

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        ruta = almacen.guardar(7, "carta_isp", 7, "carta-ficticia.pdf", b"%PDF-1.4 ficticio")
    finally:
        get_settings.cache_clear()

    assert ruta == "7/carta_isp/7_carta-ficticia.pdf"
    assert (tmp_path / ruta).read_bytes().startswith(b"%PDF")


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
def uploads(monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _obra(db: Session) -> Proyecto:
    obra = Proyecto(nombre="Obra ficticia ISP", tipo="reforma", estado="en_curso")
    db.add(obra)
    db.commit()
    db.refresh(obra)
    return obra


def _factura(db: Session, obra: Proyecto, iva: str, estado: str) -> Factura:
    contratista = db.query(Contratista).filter(Contratista.nif == NIF_FICTICIO).first()
    if contratista is None:
        contratista = Contratista(nif=NIF_FICTICIO, nombre="SUBCONTRATISTA_1", tipo="externo")
        db.add(contratista)
        db.flush()
    factura = Factura(
        proyecto_id=obra.id,
        contratista_id=contratista.id,
        numero="F-ISP-1" if iva != "0" else "F-ISP-0",
        fecha_emision=date(2026, 11, 1),
        base_imponible=Decimal("100.00"),
        iva=Decimal(iva),
        irpf=Decimal("0"),
        retencion_garantia=Decimal("0"),
        total=Decimal("100.00"),
        tipo="ordinaria",
        fichero_origen="factura-ficticia.md",
        es_escaneada=False,
        estado_revision=estado,
    )
    db.add(factura)
    db.commit()
    db.refresh(factura)
    return factura


def test_marcar_guarda_la_carta_y_el_registro(client: TestClient, db: Session, uploads):
    obra = _obra(db)
    entrar(client, db)
    respuesta = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta-ficticia.pdf", PDF, "application/pdf")},
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["inversion_sujeto_pasivo"] is True
    assert cuerpo["tiene_carta_isp"] is True
    assert cuerpo["fichero_carta_isp"] == "carta-ficticia.pdf"
    assert "ruta_carta_isp" not in cuerpo
    db.refresh(obra)
    assert obra.inversion_sujeto_pasivo is True
    assert obra.ruta_carta_isp.startswith(f"{obra.id}/carta_isp/")
    assert (uploads / obra.ruta_carta_isp).read_bytes().startswith(b"%PDF")
    fila = (
        db.query(RegistroAccion)
        .filter(RegistroAccion.accion == "marcar_isp", RegistroAccion.documento_id == obra.id)
        .one()
    )
    assert fila.tipo_documento == "proyecto"
    assert fila.etiqueta == "Obra ficticia ISP"


def test_un_fichero_que_no_es_pdf_no_marca(client: TestClient, db: Session, uploads):
    obra = _obra(db)
    entrar(client, db)
    vacio = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta.pdf", b"", "application/pdf")},
    )
    texto = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta.pdf", b"hola", "application/pdf")},
    )
    assert vacio.status_code == 422
    assert texto.status_code == 422
    db.refresh(obra)
    assert obra.inversion_sujeto_pasivo is False
    assert list(uploads.rglob("*")) == []


def test_la_obra_inexistente_responde_404(client: TestClient, db: Session, uploads):
    entrar(client, db)
    respuesta = client.post(
        "/proyectos/999999/inversion-sujeto-pasivo",
        files={"fichero": ("carta-ficticia.pdf", PDF, "application/pdf")},
    )
    assert respuesta.status_code == 404


def test_sustituir_la_carta_deja_un_solo_fichero(client: TestClient, db: Session, uploads):
    obra = _obra(db)
    entrar(client, db)
    primero = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("una.pdf", PDF, "application/pdf")},
    )
    assert primero.status_code == 200
    segundo = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("otra.pdf", PDF + b"2", "application/pdf")},
    )
    assert segundo.status_code == 200
    assert segundo.json()["fichero_carta_isp"] == "otra.pdf"
    db.refresh(obra)
    assert obra.inversion_sujeto_pasivo is True
    guardados = list((uploads / str(obra.id) / "carta_isp").iterdir())
    assert len(guardados) == 1
    assert guardados[0].read_bytes().endswith(b"2")


def test_marcar_devuelve_a_pendiente_solo_el_iva_distinto_de_cero(
    client: TestClient, db: Session, uploads
):
    obra = _obra(db)
    con_iva = _factura(db, obra, "21.00", "confirmada")
    sin_iva = _factura(db, obra, "0.00", "confirmada")
    sin_iva.numero = "F-ISP-CERO"
    ya_pendiente = _factura(db, obra, "21.00", "pendiente")
    ya_pendiente.numero = "F-ISP-PEND"
    db.commit()
    entrar(client, db)
    respuesta = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta-ficticia.pdf", PDF, "application/pdf")},
    )
    assert respuesta.status_code == 200, respuesta.text
    db.refresh(con_iva)
    db.refresh(sin_iva)
    db.refresh(ya_pendiente)
    assert con_iva.estado_revision == "pendiente"
    assert con_iva.iva == Decimal("21.00")
    assert con_iva.total == Decimal("100.00")
    assert sin_iva.estado_revision == "confirmada"
    assert ya_pendiente.estado_revision == "pendiente"


def test_quitar_borra_la_carta_y_no_toca_las_facturas(client: TestClient, db: Session, uploads):
    obra = _obra(db)
    factura = _factura(db, obra, "21.00", "pendiente")
    entrar(client, db)
    alta = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta-ficticia.pdf", PDF, "application/pdf")},
    )
    assert alta.status_code == 200
    db.refresh(obra)
    ruta = uploads / obra.ruta_carta_isp
    assert ruta.is_file()
    baja = client.delete(f"/proyectos/{obra.id}/inversion-sujeto-pasivo")
    assert baja.status_code == 204
    db.refresh(obra)
    db.refresh(factura)
    assert obra.inversion_sujeto_pasivo is False
    assert obra.ruta_carta_isp is None
    assert obra.fichero_carta_isp is None
    assert not ruta.exists()
    assert factura.estado_revision == "pendiente"
    assert (
        db.query(RegistroAccion)
        .filter(RegistroAccion.accion == "quitar_isp", RegistroAccion.documento_id == obra.id)
        .count()
        == 1
    )


def test_quitar_una_obra_sin_marca_responde_204(client: TestClient, db: Session, uploads):
    obra = _obra(db)
    entrar(client, db)
    respuesta = client.delete(f"/proyectos/{obra.id}/inversion-sujeto-pasivo")
    assert respuesta.status_code == 204
    assert (
        db.query(RegistroAccion)
        .filter(RegistroAccion.accion == "quitar_isp", RegistroAccion.documento_id == obra.id)
        .count()
        == 0
    )


def test_descargar_la_carta(client: TestClient, db: Session, uploads):
    obra = _obra(db)
    entrar(client, db)
    sin_carta = client.get(f"/proyectos/{obra.id}/carta-isp")
    assert sin_carta.status_code == 404
    alta = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta-ficticia.pdf", PDF, "application/pdf")},
    )
    assert alta.status_code == 200
    bajada = client.get(f"/proyectos/{obra.id}/carta-isp")
    assert bajada.status_code == 200
    assert bajada.content.startswith(b"%PDF")


def test_borrar_la_obra_borra_la_carta(client: TestClient, db: Session, uploads):
    obra = _obra(db)
    entrar(client, db)
    alta = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta-ficticia.pdf", PDF, "application/pdf")},
    )
    assert alta.status_code == 200
    carpeta = uploads / str(obra.id)
    assert carpeta.is_dir()
    borrado = client.delete(f"/proyectos/{obra.id}")
    assert borrado.status_code == 204
    assert not carpeta.exists()


def _payload(factura: Factura, iva: str) -> dict:
    return {
        "numero": factura.numero,
        "fecha_emision": factura.fecha_emision.isoformat(),
        "base_imponible": "100.00",
        "iva": iva,
        "irpf": "0",
        "retencion_garantia": "0",
        "total": "100.00",
        "tipo": "ordinaria",
        "contrato_id": None,
        "referencia_alc": "00001",
        "lineas": [],
    }


def test_confirmar_en_obra_marcada_exige_iva_cero(client: TestClient, db: Session, uploads):
    obra = _obra(db)
    factura = _factura(db, obra, "21.00", "pendiente")
    entrar(client, db)
    alta = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta-ficticia.pdf", PDF, "application/pdf")},
    )
    assert alta.status_code == 200
    mal = client.post(f"/facturas/{factura.id}/confirmar", json=_payload(factura, "21.00"))
    assert mal.status_code == 422
    assert mal.json()["detail"] == (
        "La obra está en inversión del sujeto pasivo. El IVA tiene que ser 0."
    )
    db.refresh(factura)
    assert factura.estado_revision == "pendiente"
    assert factura.iva == Decimal("21.00")
    negativo = client.post(f"/facturas/{factura.id}/confirmar", json=_payload(factura, "-1"))
    assert negativo.status_code == 422
    db.refresh(factura)
    assert factura.estado_revision == "pendiente"
    assert factura.iva == Decimal("21.00")
    bien = client.post(f"/facturas/{factura.id}/confirmar", json=_payload(factura, "0"))
    assert bien.status_code == 200, bien.text
    db.refresh(factura)
    assert factura.estado_revision == "confirmada"
    assert factura.iva == Decimal("0.00") or factura.iva == Decimal("0")


def test_sin_marca_se_puede_confirmar_con_iva(client: TestClient, db: Session):
    obra = _obra(db)
    factura = _factura(db, obra, "21.00", "pendiente")
    entrar(client, db)
    respuesta = client.post(
        f"/facturas/{factura.id}/confirmar",
        json=_payload(factura, "21.00"),
    )
    assert respuesta.status_code == 200, respuesta.text
    db.refresh(factura)
    assert factura.estado_revision == "confirmada"
    assert factura.iva == Decimal("21.00")


def test_el_listado_avisa_solo_si_hay_iva(client: TestClient, db: Session, uploads):
    obra = _obra(db)
    con_iva = _factura(db, obra, "21.00", "pendiente")
    sin_iva = _factura(db, obra, "0", "pendiente")
    sin_iva.numero = "F-ISP-LISTA-0"
    db.commit()
    otra = _obra(db)
    otra.nombre = "Obra ficticia sin carta"
    suelta = _factura(db, otra, "21.00", "pendiente")
    suelta.numero = "F-ISP-LIBRE"
    db.commit()
    entrar(client, db)
    alta = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta-ficticia.pdf", PDF, "application/pdf")},
    )
    assert alta.status_code == 200
    texto = "La obra está en inversión del sujeto pasivo. El IVA tiene que ser 0."
    listado = client.get("/facturas", params={"proyecto_id": obra.id}).json()
    por_id = {fila["id"]: fila for fila in listado}
    assert por_id[con_iva.id]["aviso_isp"] == texto
    assert por_id[sin_iva.id]["aviso_isp"] is None
    detalle = client.get(f"/facturas/{sin_iva.id}").json()
    assert detalle["inversion_sujeto_pasivo"] is True
    assert detalle["aviso_isp"] is None
    libre = client.get("/facturas", params={"proyecto_id": otra.id}).json()
    assert next(fila for fila in libre if fila["id"] == suelta.id)["aviso_isp"] is None


def test_el_control_marca_la_obra_sin_cambiar_el_facturado(
    client: TestClient, db: Session, uploads
):
    from app.models import Contrato

    obra = _obra(db)
    factura = _factura(db, obra, "0", "confirmada")
    contrato = Contrato(
        proyecto_id=obra.id,
        contratista_id=factura.contratista_id,
        precio_total=Decimal("100.00"),
        fichero_origen="contrato-ficticio.md",
        estado_extraccion="confirmada",
    )
    db.add(contrato)
    db.flush()
    factura.contrato_id = contrato.id
    factura.total = Decimal("40.00")
    db.commit()
    entrar(client, db)
    antes = client.get(f"/proyectos/{obra.id}/control-economico").json()
    alta = client.post(
        f"/proyectos/{obra.id}/inversion-sujeto-pasivo",
        files={"fichero": ("carta-ficticia.pdf", PDF, "application/pdf")},
    )
    assert alta.status_code == 200
    despues = client.get(f"/proyectos/{obra.id}/control-economico").json()
    assert despues["inversion_sujeto_pasivo"] is True
    assert antes["por_contrato"] == despues["por_contrato"]
    assert despues["por_contrato"][0]["contratado"] == 100.0
    assert despues["por_contrato"][0]["facturado"] == 40.0


def test_la_ficha_nombra_la_inversion():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    js = Path("app/static/js/obras.js").read_text(encoding="utf-8")
    assert "Marcar inversión del sujeto pasivo" in html
    assert "Facturación al promotor: sin IVA" in html
    assert "Ver carta" in html
    assert "Quitar la marca" in html
    assert "Contrato cliente" in html and "sin IVA" in html
    assert "Importes sin IVA" in html
    assert "marcarIsp" in js
    assert "quitarIsp" in js
    assert "aviso_isp" in js


def test_las_otras_pantallas_nombran_la_inversion():
    facturas = Path("app/static/facturas.html").read_text(encoding="utf-8")
    facturas_js = Path("app/static/js/facturas.js").read_text(encoding="utf-8")
    control = Path("app/static/control.html").read_text(encoding="utf-8")
    proyecto = Path("app/static/proyecto.html").read_text(encoding="utf-8")
    proyecto_js = Path("app/static/js/proyecto.js").read_text(encoding="utf-8")
    assert "inversion_sujeto_pasivo" in facturas
    assert "La obra está en inversión del sujeto pasivo" in facturas_js
    assert "Importes sin IVA" in control
    assert "Facturación al promotor: sin IVA" in proyecto
    assert "sin IVA" in proyecto
    assert "marcarIsp" in proyecto_js


def test_el_readme_documenta_la_marca():
    texto = Path("docs/readme.md").read_text(encoding="utf-8")
    assert "inversion_sujeto_pasivo" in texto
    assert "/proyectos/{id}/inversion-sujeto-pasivo" in texto
    assert "/proyectos/{id}/carta-isp" in texto
    assert "El IVA tiene que ser 0" in texto
