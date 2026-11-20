"""Flujo de carga, revisión y seguimiento de facturas."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import (
    Contratista,
    Contrato,
    Factura,
    Nave,
    Presupuesto,
    Proyecto,
    RegistroAccion,
    Tarea,
)
from app.services.facturas import _contratista_por_nif, _parsear_factura
from app.services.ocr import ResultadoOcr
from tests.sesion import certificar_montaje, entrar

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


def test_contratista_casa_aunque_el_nif_guarde_guiones(db: Session):
    nif_plano = "B12000001"
    for previo in db.query(Contratista).all():
        if "".join(ch for ch in previo.nif.upper() if ch.isalnum()) == nif_plano:
            db.delete(previo)
    db.flush()
    contratista = Contratista(
        nif="B-12.000.001",
        nombre="SUBCONTRATA_FICTICIA",
        tipo="externo",
    )
    db.add(contratista)
    db.commit()

    encontrado = _contratista_por_nif(db, nif_plano)
    assert encontrado is not None
    assert encontrado.id == contratista.id


def test_borrar_factura_y_permite_volver_a_subirla(
    client: TestClient,
    db: Session,
    escenario_factura: dict,
):
    proyecto_id = escenario_factura["proyecto_id"]
    fichero = (FIXTURE.name, FIXTURE.read_bytes(), "text/markdown")
    alta = client.post(
        "/facturas",
        data={"proyecto_id": str(proyecto_id)},
        files={"fichero": fichero},
    )
    assert alta.status_code == 201, alta.text
    factura_id = alta.json()["factura_id"]
    numero = client.get(f"/facturas/{factura_id}").json()["numero"]

    entrar(client, db, rol="administracion")
    borrada = client.delete(f"/facturas/{factura_id}")
    assert borrada.status_code == 204, borrada.text
    assert client.get(f"/facturas/{factura_id}").status_code == 404
    borradas = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "borrar_factura",
            RegistroAccion.documento_id == factura_id,
        )
        .all()
    )
    assert len(borradas) == 1
    assert numero in borradas[0].etiqueta

    otra = client.post(
        "/facturas",
        data={"proyecto_id": str(proyecto_id)},
        files={"fichero": (FIXTURE.name, FIXTURE.read_bytes(), "text/markdown")},
    )
    assert otra.status_code == 201, otra.text


def test_factura_enlaza_el_contrato_del_proveedor_aunque_siga_pendiente(
    client: TestClient,
    db: Session,
    escenario_factura: dict,
):
    contrato = db.get(Contrato, escenario_factura["contrato_id"])
    assert contrato is not None
    contrato.estado_extraccion = "pendiente_revision"
    db.commit()

    alta = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": (FIXTURE.name, FIXTURE.read_bytes(), "text/markdown")},
    )
    assert alta.status_code == 201, alta.text
    cuerpo = alta.json()
    assert cuerpo["contrato_id"] == escenario_factura["contrato_id"]
    assert cuerpo["codigo_contrato"] is None
    assert "Indícalo" in cuerpo["aviso_codigo"]

    factura = db.get(Factura, cuerpo["factura_id"])
    assert factura is not None
    factura.contrato_id = None
    db.commit()

    listado = client.get(
        "/facturas",
        params={"proyecto_id": escenario_factura["proyecto_id"]},
    )
    assert listado.status_code == 200, listado.text
    fila = next(item for item in listado.json() if item["id"] == cuerpo["factura_id"])
    assert fila["contrato_id"] == escenario_factura["contrato_id"]
    assert fila["contrato_etiqueta"] == "SUBCONTRATISTA_1"

    detalle = client.get(f"/facturas/{cuerpo['factura_id']}").json()
    certificar_montaje(client, db, cuerpo["factura_id"])
    entrar(client, db, rol="administracion")
    confirmar = client.post(
        f"/facturas/{cuerpo['factura_id']}/confirmar",
        json={
            "numero": detalle["numero"],
            "fecha_emision": detalle["fecha_emision"],
            "base_imponible": detalle["base_imponible"],
            "iva": detalle["iva"],
            "irpf": detalle["irpf"],
            "retencion_garantia": detalle["retencion_garantia"],
            "total": detalle["total"],
            "tipo": detalle["tipo"],
            "referencia_alc": "00001",
            "contrato_id": escenario_factura["contrato_id"],
            "lineas": [],
        },
    )
    assert confirmar.status_code == 200, confirmar.text
    assert confirmar.json()["contrato_id"] == escenario_factura["contrato_id"]


def test_la_factura_con_codigo_elige_ese_contrato(
    client: TestClient,
    db: Session,
    escenario_factura: dict,
):
    for codigo in ("PYCON901070", "PYCON901071"):
        previo = db.query(Contrato).filter(Contrato.codigo == codigo).one_or_none()
        if previo is not None:
            previo.codigo = None
    primero = db.get(Contrato, escenario_factura["contrato_id"])
    assert primero is not None
    primero.codigo = "PYCON901070"
    segundo = Contrato(
        proyecto_id=escenario_factura["proyecto_id"],
        nave_id=primero.nave_id,
        contratista_id=primero.contratista_id,
        precio_total=Decimal("800"),
        fichero_origen="otro_contrato_ficticio.md",
        estado_extraccion="confirmada",
        codigo="PYCON901071",
    )
    db.add(segundo)
    db.commit()
    texto = FIXTURE.read_text(encoding="utf-8") + "\nCódigo: PYCON901071\n"
    alta = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": ("factura_codigo.md", texto.encode(), "text/markdown")},
    )
    assert alta.status_code == 201, alta.text
    cuerpo = alta.json()
    assert cuerpo["codigo_contrato"] == "PYCON901071"
    assert cuerpo["contrato_id"] == segundo.id
    assert cuerpo["aviso_codigo"] is None


def test_el_codigo_enlaza_aunque_el_contrato_se_leyera_con_otro_nif(
    client: TestClient,
    db: Session,
    escenario_factura: dict,
):
    codigo = "PYCON901080"
    previo = db.query(Contrato).filter(Contrato.codigo == codigo).one_or_none()
    if previo is not None:
        previo.codigo = None
    contrato = db.get(Contrato, escenario_factura["contrato_id"])
    assert contrato is not None
    proveedor_id = contrato.contratista_id
    quien_encarga = (
        db.query(Contratista).filter(Contratista.nif == "B00000099").one_or_none()
    )
    if quien_encarga is None:
        quien_encarga = Contratista(
            nif="B00000099",
            nombre="EMPRESA_QUE_ENCARGA",
            tipo="externo",
        )
        db.add(quien_encarga)
        db.flush()
    contrato.codigo = codigo
    contrato.contratista_id = quien_encarga.id
    db.commit()

    texto = FIXTURE.read_text(encoding="utf-8") + f"\nCódigo: {codigo}\n"
    alta = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": ("factura_mismo_proveedor.md", texto.encode(), "text/markdown")},
    )
    assert alta.status_code == 201, alta.text
    cuerpo = alta.json()
    assert cuerpo["contrato_id"] == contrato.id
    assert cuerpo["aviso_codigo"] is None
    db.refresh(contrato)
    assert contrato.contratista_id == proveedor_id


def test_numero_de_factura_cuando_el_valor_va_en_la_linea_siguiente():
    texto = """
NIF: B00000001
Fecha: 01/02/26
Número de factura:
77
Base imponible IVA 0,00 %
1.000,00€
Cuota IVA 0,00 %
0,00€
Total (Euro)
1.000,00€
"""
    datos = _parsear_factura(texto)
    assert datos["numero"] == "77"
    assert datos["fecha_emision"] == date(2026, 2, 1)
    assert datos["base_imponible"] == Decimal("1000.00")
    assert datos["iva"] == Decimal("0.00")
    assert datos["total"] == Decimal("1000.00")


def test_factura_pendiente_no_suma_y_confirmada_actualiza_seguimiento(
    client: TestClient,
    db: Session,
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

    certificar_montaje(client, db, factura_id)
    entrar(client, db, rol="administracion")
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
            "referencia_alc": "00001",
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
    confirmadas = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "confirmar_factura",
            RegistroAccion.documento_id == factura_id,
        )
        .all()
    )
    assert len(confirmadas) == 1
    assert "·" in confirmadas[0].etiqueta

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
    entrar(client, db, rol="administracion")
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
            "referencia_alc": "00001",
            "contrato_id": contrato_ajeno.id,
            "lineas": [],
        },
    )
    assert respuesta.status_code == 422
    assert "no pertenece al proyecto" in respuesta.text
    assert (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "confirmar_factura",
            RegistroAccion.documento_id == importada["factura_id"],
        )
        .count()
        == 0
    )

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

    entrar(client, db, rol="administracion")
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
            "referencia_alc": "00001",
            "contrato_id": contrato_otro_contratista.id,
            "lineas": [],
        },
    )
    assert respuesta.status_code == 422
    assert "no pertenece al contratista" in respuesta.text
    assert (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "confirmar_factura",
            RegistroAccion.documento_id == importada["factura_id"],
        )
        .count()
        == 0
    )


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


def test_confirmar_genera_el_pdf_con_sello(
    client: TestClient,
    db: Session,
    escenario_factura: dict,
):
    import pymupdf

    codigo = "PYCON901070"
    previo = db.query(Contrato).filter(Contrato.codigo == codigo).one_or_none()
    contrato = db.get(Contrato, escenario_factura["contrato_id"])
    assert contrato is not None
    if previo is not None and previo.id != contrato.id:
        previo.codigo = None
    contrato.codigo = codigo
    db.commit()

    alta = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": (FIXTURE.name, FIXTURE.read_bytes(), "text/markdown")},
    )
    assert alta.status_code == 201, alta.text
    factura_id = alta.json()["factura_id"]
    datos = client.get(f"/facturas/{factura_id}").json()
    certificar_montaje(client, db, factura_id)
    entrar(client, db, rol="administracion")
    base = {
        "numero": datos["numero"],
        "fecha_emision": datos["fecha_emision"],
        "base_imponible": datos["base_imponible"],
        "iva": datos["iva"],
        "irpf": datos["irpf"],
        "retencion_garantia": datos["retencion_garantia"],
        "total": datos["total"],
        "tipo": datos["tipo"],
        "codigo_contrato": codigo,
        "contrato_id": contrato.id,
        "lineas": [],
    }
    sin_alc = client.post(f"/facturas/{factura_id}/confirmar", json=base)
    assert sin_alc.status_code == 422

    confirmar = client.post(
        f"/facturas/{factura_id}/confirmar",
        json={**base, "referencia_alc": "ALC/00001"},
    )
    assert confirmar.status_code == 200, confirmar.text
    assert confirmar.json()["tiene_sello"] is True

    factura = db.get(Factura, factura_id)
    assert factura is not None
    db.refresh(factura)
    assert factura.referencia_alc == "00001"
    assert factura.confirmada_por == "Persona Ejemplo"
    assert factura.ruta_sello

    pdf = client.get(f"/facturas/{factura_id}/sello")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    documento = pymupdf.open(stream=pdf.content, filetype="pdf")
    try:
        texto = documento[0].get_text().replace("\xa0", " ").replace("\xad", "-")
        assert "Ref. Proyecto ficticio para facturas" in texto
        assert "PYCON/901 - TRABAJO/07" in texto
        assert "ALC/00001" in texto
        assert "Persona Ejemplo - " in texto
        assert "Presupuestado: 5.000,00 €" in texto
        assert "1ª factura: 1.210,00 €" in texto
        assert "Pendiente: 3.790,00 €" in texto
        azul = False
        for bloque in documento[0].get_text("dict")["blocks"]:
            for linea in bloque.get("lines", []):
                for span in linea.get("spans", []):
                    if "ALC/00001" not in span["text"]:
                        continue
                    color = span["color"]
                    azul = (color & 0xFF) > 180 and ((color >> 16) & 0xFF) < 40
        assert azul
    finally:
        documento.close()

    segunda = FIXTURE.read_text(encoding="utf-8").replace("F-FICT-001", "F-FICT-002")
    alta2 = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": ("factura_ficticia_2.md", segunda.encode(), "text/markdown")},
    )
    assert alta2.status_code == 201, alta2.text
    id2 = alta2.json()["factura_id"]
    datos2 = client.get(f"/facturas/{id2}").json()
    certificar_montaje(client, db, id2)
    entrar(client, db, rol="administracion")
    confirmar2 = client.post(
        f"/facturas/{id2}/confirmar",
        json={
            "numero": datos2["numero"],
            "fecha_emision": datos2["fecha_emision"],
            "base_imponible": datos2["base_imponible"],
            "iva": datos2["iva"],
            "irpf": datos2["irpf"],
            "retencion_garantia": datos2["retencion_garantia"],
            "total": datos2["total"],
            "tipo": datos2["tipo"],
            "codigo_contrato": codigo,
            "contrato_id": contrato.id,
            "referencia_alc": "00002",
            "lineas": [],
        },
    )
    assert confirmar2.status_code == 200, confirmar2.text
    pdf2 = client.get(f"/facturas/{id2}/sello")
    assert pdf2.status_code == 200
    documento2 = pymupdf.open(stream=pdf2.content, filetype="pdf")
    try:
        texto2 = documento2[0].get_text().replace("\xa0", " ").replace("\xad", "-")
    finally:
        documento2.close()
    assert "ALC/00002" in texto2
    assert "2ª factura: 1.210,00 €" in texto2
    assert "Pendiente: 2.580,00 €" in texto2


def test_el_sello_verde_va_antes_y_lo_pone_otra_persona(
    client: TestClient,
    db: Session,
    escenario_factura: dict,
):
    import pymupdf

    codigo = "PYCON246810"
    previo = db.query(Contrato).filter(Contrato.codigo == codigo).one_or_none()
    contrato = db.get(Contrato, escenario_factura["contrato_id"])
    assert contrato is not None
    if previo is not None and previo.id != contrato.id:
        previo.codigo = None
    contrato.codigo = codigo
    db.commit()

    alta = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": (FIXTURE.name, FIXTURE.read_bytes(), "text/markdown")},
    )
    assert alta.status_code == 201, alta.text
    factura_id = alta.json()["factura_id"]
    factura_alta = db.get(Factura, factura_id)
    assert factura_alta is not None
    factura_alta.codigo_contrato = codigo
    factura_alta.contrato_id = contrato.id
    db.commit()
    datos = client.get(f"/facturas/{factura_id}").json()
    cuerpo = {
        "numero": datos["numero"],
        "fecha_emision": datos["fecha_emision"],
        "base_imponible": datos["base_imponible"],
        "iva": datos["iva"],
        "irpf": datos["irpf"],
        "retencion_garantia": datos["retencion_garantia"],
        "total": datos["total"],
        "tipo": datos["tipo"],
        "codigo_contrato": codigo,
        "contrato_id": contrato.id,
        "referencia_alc": "00011",
        "lineas": [],
    }
    entrar(client, db, rol="administracion")
    sin_verde = client.post(f"/facturas/{factura_id}/confirmar", json=cuerpo)
    assert sin_verde.status_code == 422
    assert "certificación de montaje" in sin_verde.text

    primera = entrar(client, db, rol="jefe_obra")
    primera.nombre = "Persona Montaje"
    db.commit()
    client.post("/auth/logout")
    client.post(
        "/auth/login",
        json={"email": primera.email, "password": "clave-ficticia"},
    )
    certificada = client.post(f"/facturas/{factura_id}/certificar-montaje")
    assert certificada.status_code == 200, certificada.text
    factura = db.get(Factura, factura_id)
    assert factura is not None
    db.refresh(factura)
    assert factura.estado_revision == "pendiente"
    assert factura.certificacion_montaje_por == "Persona Montaje"
    assert factura.certificacion_montaje_usuario_id == primera.id

    verde = client.get(f"/facturas/{factura_id}/certificacion")
    assert verde.status_code == 200
    documento = pymupdf.open(stream=verde.content, filetype="pdf")
    try:
        texto = documento[0].get_text().replace("\xa0", " ").replace("\xad", "-")
        assert "Certificación de montaje" in texto
        assert "Persona Montaje" in texto
        assert "PYCON/246 - TRABAJO/81" in texto
        assert "ALC/" not in texto
        color_verde = False
        for bloque in documento[0].get_text("dict")["blocks"]:
            for linea in bloque.get("lines", []):
                for span in linea.get("spans", []):
                    if "Certificación de montaje" not in span["text"].replace("\xa0", " "):
                        continue
                    color = span["color"]
                    color_verde = ((color >> 8) & 0xFF) > 80 and ((color >> 16) & 0xFF) < 40
        assert color_verde
    finally:
        documento.close()

    misma = client.post(f"/facturas/{factura_id}/confirmar", json=cuerpo)
    assert misma.status_code == 422
    assert "otra persona" in misma.text
    db.refresh(factura)
    assert factura.estado_revision == "pendiente"

    entrar(client, db, rol="administracion")
    confirmar = client.post(f"/facturas/{factura_id}/confirmar", json=cuerpo)
    assert confirmar.status_code == 200, confirmar.text
    pdf = client.get(f"/facturas/{factura_id}/sello")
    assert pdf.status_code == 200
    final = pymupdf.open(stream=pdf.content, filetype="pdf")
    try:
        texto_final = final[0].get_text().replace("\xa0", " ").replace("\xad", "-")
        assert "Certificación de montaje" in texto_final
        assert "Persona Montaje" in texto_final
        assert "PYCON/246 - TRABAJO/81" in texto_final
        assert "ALC/00011" in texto_final
    finally:
        final.close()


def test_se_puede_saltar_el_sello_verde(
    client: TestClient,
    db: Session,
    escenario_factura: dict,
):
    import pymupdf

    alta = client.post(
        "/facturas",
        data={"proyecto_id": str(escenario_factura["proyecto_id"])},
        files={"fichero": (FIXTURE.name, FIXTURE.read_bytes(), "text/markdown")},
    )
    assert alta.status_code == 201, alta.text
    factura_id = alta.json()["factura_id"]
    datos = client.get(f"/facturas/{factura_id}").json()
    cuerpo = {
        "numero": datos["numero"],
        "fecha_emision": datos["fecha_emision"],
        "base_imponible": datos["base_imponible"],
        "iva": datos["iva"],
        "irpf": datos["irpf"],
        "retencion_garantia": datos["retencion_garantia"],
        "total": datos["total"],
        "tipo": datos["tipo"],
        "contrato_id": escenario_factura["contrato_id"],
        "referencia_alc": "00021",
        "lineas": [],
    }
    usuario = entrar(client, db, rol="administracion")
    omitir = client.post(f"/facturas/{factura_id}/omitir-certificacion-montaje")
    assert omitir.status_code == 200, omitir.text
    assert omitir.json()["certificacion_montaje_omitida"] is True
    factura = db.get(Factura, factura_id)
    assert factura is not None
    db.refresh(factura)
    assert factura.estado_revision == "pendiente"
    assert factura.ruta_certificacion is None

    verde = client.post(f"/facturas/{factura_id}/certificar-montaje")
    assert verde.status_code == 422
    assert "no es necesaria" in verde.text

    confirmar = client.post(f"/facturas/{factura_id}/confirmar", json=cuerpo)
    assert confirmar.status_code == 200, confirmar.text
    db.refresh(factura)
    assert factura.confirmada_por == usuario.nombre
    pdf = client.get(f"/facturas/{factura_id}/sello")
    assert pdf.status_code == 200
    documento = pymupdf.open(stream=pdf.content, filetype="pdf")
    try:
        texto = documento[0].get_text().replace("\xa0", " ").replace("\xad", "-")
    finally:
        documento.close()
    assert "ALC/00021" in texto
    assert "Certificación de montaje" not in texto
