"""Quitar un contrato de proveedor deja las facturas y el presupuesto."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import (
    Asignacion,
    Contratista,
    Contrato,
    ContratoApartado,
    Factura,
    LineaFactura,
    Nave,
    Presupuesto,
    Proyecto,
    RegistroAccion,
    Tarea,
)
from tests.sesion import entrar
from app.services import almacen as almacen_svc

NIF_FICTICIO = "B00000999"


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


def _alta(db: Session) -> dict:
    proyecto = Proyecto(
        nombre="Obra ficticia para quitar contrato",
        tipo="reforma",
        estado="en_curso",
    )
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="NQ",
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
        descripcion="Apartado del presupuesto",
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
            nombre="PROVEEDOR_FICTICIO",
            tipo="externo",
        )
        db.add(contratista)
        db.flush()
    contrato = Contrato(
        proyecto_id=proyecto.id,
        nave_id=nave.id,
        contratista_id=contratista.id,
        tarea_apartado_id=apartado.id,
        precio_total=Decimal("1000"),
        fichero_origen="contrato_ficticio.md",
        estado_extraccion="confirmada",
    )
    db.add(contrato)
    db.flush()
    db.add(ContratoApartado(contrato_id=contrato.id, tarea_id=apartado.id))
    padre = Tarea(
        nave_id=nave.id,
        contrato_id=contrato.id,
        codigo="C1",
        nivel="apartado",
        descripcion="Partida nacida del contrato",
        importe_presupuestado=Decimal("1000"),
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(padre)
    db.flush()
    hija = Tarea(
        nave_id=nave.id,
        contrato_id=contrato.id,
        tarea_padre_id=padre.id,
        codigo="C1.1",
        nivel="partida",
        descripcion="Detalle nacido del contrato",
        importe_presupuestado=Decimal("400"),
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(hija)
    db.flush()
    factura = Factura(
        proyecto_id=proyecto.id,
        contratista_id=contratista.id,
        contrato_id=contrato.id,
        numero="F-0001",
        fecha_emision=date(2026, 10, 1),
        base_imponible=Decimal("100"),
        iva=Decimal("21"),
        total=Decimal("121"),
        tipo="ordinaria",
        fichero_origen="factura_ficticia.md",
        es_escaneada=False,
        estado_revision="confirmada",
    )
    db.add(factura)
    db.flush()
    linea = LineaFactura(
        factura_id=factura.id,
        descripcion="Línea ficticia",
        importe=Decimal("100"),
        tarea_id=padre.id,
    )
    db.add(linea)
    db.add(
        Asignacion(
            factura_id=factura.id,
            tarea_id=padre.id,
            nave_id=nave.id,
            importe_asignado=Decimal("100"),
            metodo="manual",
            es_estimacion=False,
        )
    )
    db.add(
        Asignacion(
            factura_id=factura.id,
            tarea_id=apartado.id,
            nave_id=nave.id,
            importe_asignado=Decimal("50"),
            metodo="manual",
            es_estimacion=False,
        )
    )
    contrato.ruta_almacen = almacen_svc.guardar(
        proyecto.id,
        "contrato",
        contrato.id,
        "contrato_ficticio.md",
        b"contrato ficticio",
    )
    db.commit()
    return {
        "proyecto_id": proyecto.id,
        "apartado_id": apartado.id,
        "contrato_id": contrato.id,
        "padre_id": padre.id,
        "hija_id": hija.id,
        "factura_id": factura.id,
        "linea_id": linea.id,
        "ruta": contrato.ruta_almacen,
        "contratista_id": contratista.id,
    }


def test_quitar_contrato_deja_factura_y_presupuesto(
    client: TestClient,
    db: Session,
):
    datos = _alta(db)
    pid = datos["proyecto_id"]
    cid = datos["contrato_id"]
    contrato = db.get(Contrato, cid)
    assert contrato is not None
    contrato.referencia_presupuesto = "P-FICT-01"
    db.commit()
    nombre = db.get(Proyecto, pid).nombre

    entrar(client, db, rol="direccion")
    respuesta = client.delete(f"/proyectos/{pid}/contratos/{cid}")
    assert respuesta.status_code == 204, respuesta.text

    db.expire_all()
    assert db.get(Contrato, cid) is None
    borrados = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "borrar_contrato",
            RegistroAccion.documento_id == cid,
        )
        .all()
    )
    assert len(borrados) == 1
    assert nombre in borrados[0].etiqueta
    assert "P-FICT-01" in borrados[0].etiqueta
    assert db.get(Tarea, datos["apartado_id"]) is not None
    assert db.get(Tarea, datos["padre_id"]) is None
    assert db.get(Tarea, datos["hija_id"]) is None
    assert (
        db.query(ContratoApartado).filter(ContratoApartado.contrato_id == cid).count()
        == 0
    )
    factura = db.get(Factura, datos["factura_id"])
    assert factura is not None
    assert factura.contrato_id is None
    linea = db.get(LineaFactura, datos["linea_id"])
    assert linea is not None
    assert linea.tarea_id is None
    assert (
        db.query(Asignacion).filter(Asignacion.tarea_id == datos["padre_id"]).count()
        == 0
    )
    assert (
        db.query(Asignacion)
        .filter(Asignacion.tarea_id == datos["apartado_id"])
        .count()
        == 1
    )
    assert db.get(Contratista, datos["contratista_id"]) is not None
    assert almacen_svc.abrir_si_existe(datos["ruta"]) is None

    entrar(client, db, rol="direccion")
    otra = client.delete(f"/proyectos/{pid}/contratos/{cid}")
    assert otra.status_code == 404
    db.expire_all()
    siguen = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "borrar_contrato",
            RegistroAccion.documento_id == cid,
        )
        .all()
    )
    assert len(siguen) == 1


def test_quitar_contrato_de_otra_obra_no_lo_borra(client: TestClient, db: Session):
    datos = _alta(db)
    ajena = Proyecto(nombre="Otra obra ficticia", tipo="reforma", estado="en_curso")
    db.add(ajena)
    db.commit()

    entrar(client, db, rol="direccion")
    respuesta = client.delete(
        f"/proyectos/{ajena.id}/contratos/{datos['contrato_id']}"
    )
    assert respuesta.status_code == 404
    db.expire_all()
    assert db.get(Contrato, datos["contrato_id"]) is not None
    borrados = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "borrar_contrato",
            RegistroAccion.documento_id == datos["contrato_id"],
        )
        .all()
    )
    assert len(borrados) == 0
