"""Línea del PDF marcada como solo gestión: apartado sin Excel para contratistas."""

import uuid
from datetime import date
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
    RegistroAccion,
    Tarea,
    Usuario,
)
from app.services.proyectos import borrar_proyecto
from tests.sesion import entrar


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


def _usuario_limpieza(db: Session) -> Usuario:
    usuario = Usuario(
        nombre="Ana Ejemplo",
        email=f"ana.{uuid.uuid4().hex}@example.com",
        rol="direccion",
        password_hash="hash-ficticio",
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _contratista(db: Session, nif: str, nombre: str) -> Contratista:
    fila = db.query(Contratista).filter(Contratista.nif == nif).first()
    if fila is None:
        fila = Contratista(nif=nif, nombre=nombre, tipo="externo")
        db.add(fila)
        db.flush()
    return fila


def _obra(db: Session) -> dict:
    proyecto = Proyecto(nombre="Obra ficticia solo gestión", tipo="llave_en_mano", estado="borrador")
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
    return {"proyecto": proyecto, "nave": nave, "pdf": pdf, "excel": excel}


def _linea(db: Session, pdf_id: int, **datos) -> LineaPdfCliente:
    fila = LineaPdfCliente(
        presupuesto_id=pdf_id,
        orden=datos.pop("orden", 0),
        tipo=datos.pop("tipo", "importe"),
        codigo=datos.pop("codigo", "5"),
        descripcion=datos.pop("descripcion", "Obra civil ficticia"),
        importe=datos.pop("importe", Decimal("1000.00")),
        es_manuscrito=datos.pop("es_manuscrito", False),
    )
    db.add(fila)
    db.flush()
    return fila


def _contrato(db: Session, proyecto_id: int, nave_id: int, nif: str, precio: str) -> Contrato:
    contratista = _contratista(db, nif, "CONTRATISTA FICTICIO " + nif)
    fila = Contrato(
        proyecto_id=proyecto_id,
        nave_id=nave_id,
        contratista_id=contratista.id,
        precio_total=Decimal(precio),
        fecha_firma=date(2026, 1, 1),
        fichero_origen="contrato-ficticio.md",
        estado_extraccion="confirmada",
        condiciones_facturacion="Obra civil ficticia",
    )
    db.add(fila)
    db.flush()
    return fila


def test_marcar_linea_crea_apartado_y_sale_de_sin_bloque(client: TestClient, db: Session):
    obra = _obra(db)
    linea = _linea(db, obra["pdf"].id)
    bloque = Tarea(
        nave_id=obra["nave"].id,
        presupuesto_id=obra["excel"].id,
        codigo="01",
        nivel="apartado",
        descripcion="Ventilacion ficticia",
        importe_presupuestado=Decimal("10.00"),
        tiene_anotacion_manual=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(bloque)
    db.flush()
    db.add(
        LineaPdfClienteTarea(linea_id=linea.id, tarea_id=bloque.id, es_sugerencia=True)
    )
    db.commit()
    try:
        respuesta = client.post(
            f"/proyectos/{obra['proyecto'].id}/lineas-pdf/{linea.id}/solo-gestion"
        )
        assert respuesta.status_code == 201, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["linea_id"] == linea.id
        assert cuerpo["codigo"] == "5"
        assert cuerpo["descripcion"] == "Obra civil ficticia"
        assert cuerpo["importe"] == 1000.0
        assert cuerpo["estado_revision"] == "confirmada"
        assert cuerpo["tiene_anotacion_manual"] is False
        assert cuerpo["solo_gestion"] is True

        db.expire_all()
        apartado = db.get(Tarea, cuerpo["tarea_id"])
        assert apartado is not None
        assert apartado.solo_gestion is True
        assert apartado.nivel == "apartado"
        assert apartado.presupuesto_id == obra["pdf"].id
        assert apartado.nave_id == obra["nave"].id
        assert apartado.importe_presupuestado == Decimal("1000.00")
        assert apartado.importe_contrato_cliente == Decimal("1000.00")
        assert apartado.es_montaje is False
        assert apartado.tarea_padre_id is None
        assert apartado.estado == "no_iniciada"
        assert apartado.avance_fisico_pct == Decimal("0")
        db.refresh(linea)
        assert linea.apartado_gestion_id == apartado.id
        assert (
            db.query(LineaPdfClienteTarea)
            .filter(LineaPdfClienteTarea.linea_id == linea.id)
            .count()
            == 0
        )

        contraste = client.get(f"/proyectos/{obra['proyecto'].id}/contraste-cliente")
        assert contraste.status_code == 200
        fila = contraste.json()["sugerencias"][0]
        assert fila["solo_gestion"] is True
        assert fila["apartado_gestion_id"] == apartado.id
        assert fila["confirmada"] is False
        assert fila["tarea_ids"] == []
    finally:
        borrar_proyecto(db, obra["proyecto"].id, _usuario_limpieza(db))


def test_codigo_vacio_o_repetido_usa_el_id_de_la_linea(client: TestClient, db: Session):
    obra = _obra(db)
    db.add(
        Tarea(
            nave_id=obra["nave"].id,
            presupuesto_id=obra["excel"].id,
            codigo="8",
            nivel="apartado",
            descripcion="Ya existe",
            importe_presupuestado=Decimal("1.00"),
            tiene_anotacion_manual=False,
            estado_revision="pendiente",
            estado="no_iniciada",
            avance_fisico_pct=Decimal("0"),
        )
    )
    vacia = _linea(db, obra["pdf"].id, orden=0, codigo="", descripcion="Sin codigo")
    repetida = _linea(db, obra["pdf"].id, orden=1, codigo="8", descripcion="Codigo usado")
    db.commit()
    try:
        sin_codigo = client.post(
            f"/proyectos/{obra['proyecto'].id}/lineas-pdf/{vacia.id}/solo-gestion"
        )
        assert sin_codigo.status_code == 201, sin_codigo.text
        assert sin_codigo.json()["codigo"] == f"pdf.{vacia.id}"

        choca = client.post(
            f"/proyectos/{obra['proyecto'].id}/lineas-pdf/{repetida.id}/solo-gestion"
        )
        assert choca.status_code == 201, choca.text
        assert choca.json()["codigo"] == f"pdf.{repetida.id}"
    finally:
        borrar_proyecto(db, obra["proyecto"].id, _usuario_limpieza(db))


def test_rechaza_descuento_excel_confirmado_y_segunda_marca(client: TestClient, db: Session):
    obra = _obra(db)
    descuento = _linea(
        db, obra["pdf"].id, orden=0, tipo="descuento", descripcion="Descuento ficticio"
    )
    confirmada = _linea(db, obra["pdf"].id, orden=1, codigo="6", descripcion="Electricidad ficticia")
    bloque = Tarea(
        nave_id=obra["nave"].id,
        presupuesto_id=obra["excel"].id,
        codigo="02",
        nivel="subapartado",
        descripcion="Bloque ficticio",
        importe_presupuestado=Decimal("10.00"),
        tiene_anotacion_manual=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(bloque)
    db.flush()
    db.add(LineaPdfClienteTarea(linea_id=confirmada.id, tarea_id=bloque.id, es_sugerencia=False))
    libre = _linea(db, obra["pdf"].id, orden=2, codigo="7", descripcion="Fontaneria ficticia")
    db.commit()
    try:
        pid = obra["proyecto"].id
        assert client.post(f"/proyectos/{pid}/lineas-pdf/{descuento.id}/solo-gestion").status_code == 422
        assert client.post(f"/proyectos/{pid}/lineas-pdf/{confirmada.id}/solo-gestion").status_code == 422
        primera = client.post(f"/proyectos/{pid}/lineas-pdf/{libre.id}/solo-gestion")
        assert primera.status_code == 201
        segunda = client.post(f"/proyectos/{pid}/lineas-pdf/{libre.id}/solo-gestion")
        assert segunda.status_code == 422
        ajena = client.post(f"/proyectos/999999/lineas-pdf/{libre.id}/solo-gestion")
        assert ajena.status_code == 404
        mal = client.post(f"/proyectos/{pid}/lineas-pdf/no-es-numero/solo-gestion")
        assert mal.status_code == 422
    finally:
        borrar_proyecto(db, obra["proyecto"].id, _usuario_limpieza(db))


def test_desmarcar_borra_y_con_contrato_no(client: TestClient, db: Session):
    obra = _obra(db)
    linea = _linea(db, obra["pdf"].id)
    contrato = _contrato(db, obra["proyecto"].id, obra["nave"].id, "B00000991", "400.00")
    db.commit()
    try:
        pid = obra["proyecto"].id
        creada = client.post(f"/proyectos/{pid}/lineas-pdf/{linea.id}/solo-gestion")
        assert creada.status_code == 201
        tarea_id = creada.json()["tarea_id"]
        enlace = client.post(
            f"/proyectos/{pid}/contratos/{contrato.id}/enlazar-apartado",
            json={"tarea_apartado_id": tarea_id},
        )
        assert enlace.status_code == 200, enlace.text
        ocupada = client.delete(f"/proyectos/{pid}/lineas-pdf/{linea.id}/solo-gestion")
        assert ocupada.status_code == 422

        suelto = client.post(f"/proyectos/{pid}/contratos/{contrato.id}/desenlazar-apartado")
        assert suelto.status_code == 200
        assert suelto.json()["tarea_apartado_id"] is None
        otra = client.post(f"/proyectos/{pid}/contratos/{contrato.id}/desenlazar-apartado")
        assert otra.status_code == 200
        assert otra.json()["tarea_apartado_id"] is None

        borrada = client.delete(f"/proyectos/{pid}/lineas-pdf/{linea.id}/solo-gestion")
        assert borrada.status_code == 204
        db.expire_all()
        assert db.get(Tarea, tarea_id) is None
        db.refresh(linea)
        assert linea.apartado_gestion_id is None
        sin_marca = client.delete(f"/proyectos/{pid}/lineas-pdf/{linea.id}/solo-gestion")
        assert sin_marca.status_code == 422
    finally:
        borrar_proyecto(db, obra["proyecto"].id, _usuario_limpieza(db))


def test_dos_contratos_se_suman_contra_el_importe_del_pdf(client: TestClient, db: Session):
    obra = _obra(db)
    linea = _linea(db, obra["pdf"].id, importe=Decimal("1000.00"))
    uno = _contrato(db, obra["proyecto"].id, obra["nave"].id, "B00000991", "400.00")
    dos = _contrato(db, obra["proyecto"].id, obra["nave"].id, "B00000992", "250.00")
    db.commit()
    try:
        pid = obra["proyecto"].id
        creada = client.post(f"/proyectos/{pid}/lineas-pdf/{linea.id}/solo-gestion")
        assert creada.status_code == 201
        tarea_id = creada.json()["tarea_id"]
        for contrato in (uno, dos):
            enlace = client.post(
                f"/proyectos/{pid}/contratos/{contrato.id}/enlazar-apartado",
                json={"tarea_apartado_id": tarea_id},
            )
            assert enlace.status_code == 200, enlace.text
        control = client.get(f"/proyectos/{pid}/control-economico")
        assert control.status_code == 200
        fila = next(item for item in control.json()["por_apartado"] if item["tarea_id"] == tarea_id)
        assert fila["solo_gestion"] is True
        assert Decimal(str(fila["contratado"])) == Decimal("650.00")
        assert Decimal(str(fila["montaje"])) == Decimal("0")
        assert Decimal(str(fila["presupuestado"])) == Decimal("1000.00")
        assert Decimal(str(fila["contrato_cliente"])) == Decimal("1000.00")
    finally:
        borrar_proyecto(db, obra["proyecto"].id, _usuario_limpieza(db))


def _filas_gestion(db: Session, tarea_id: int) -> int:
    filas = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "confirmar_solo_gestion",
            RegistroAccion.documento_id == tarea_id,
        )
        .all()
    )
    assert all(fila.tipo_documento == "tarea" for fila in filas)
    return len(filas)


def test_manuscrito_queda_pendiente_hasta_confirmar(client: TestClient, db: Session):
    obra = _obra(db)
    linea = _linea(
        db,
        obra["pdf"].id,
        codigo="",
        descripcion="Gestión de obra civil ficticia",
        es_manuscrito=True,
        importe=Decimal("800.00"),
    )
    contrato = _contrato(db, obra["proyecto"].id, obra["nave"].id, "B00000993", "800.00")
    contrato.condiciones_facturacion = "Gestión de obra civil ficticia"
    excel_gestion = Tarea(
        nave_id=obra["nave"].id,
        presupuesto_id=obra["excel"].id,
        codigo="G",
        nivel="apartado",
        descripcion="Gestión EXAFAN ficticia",
        importe_presupuestado=Decimal("10.00"),
        tiene_anotacion_manual=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(excel_gestion)
    db.commit()
    try:
        pid = obra["proyecto"].id
        creada = client.post(f"/proyectos/{pid}/lineas-pdf/{linea.id}/solo-gestion")
        assert creada.status_code == 201, creada.text
        cuerpo = creada.json()
        assert cuerpo["estado_revision"] == "pendiente"
        assert cuerpo["tiene_anotacion_manual"] is True
        tarea_id = cuerpo["tarea_id"]

        enlace = client.post(
            f"/proyectos/{pid}/contratos/{contrato.id}/enlazar-apartado",
            json={"tarea_apartado_id": tarea_id},
        )
        assert enlace.status_code == 422

        control = client.get(f"/proyectos/{pid}/control-economico")
        ids = [item["tarea_id"] for item in control.json()["por_apartado"]]
        assert tarea_id not in ids

        detalle = client.get(f"/proyectos/{pid}")
        assert detalle.status_code == 200
        sugeridas = []
        for fila in detalle.json()["contratos"]:
            if fila["id"] == contrato.id:
                sugeridas = [s["tarea_id"] for s in fila["sugerencias"]]
        assert tarea_id not in sugeridas
        assert excel_gestion.id not in sugeridas

        entrar(client, db, rol="direccion")
        no_es = client.post(f"/proyectos/{pid}/apartados/{excel_gestion.id}/confirmar-gestion")
        assert no_es.status_code == 422
        assert (
            db.query(RegistroAccion)
            .filter(
                RegistroAccion.accion == "confirmar_solo_gestion",
                RegistroAccion.documento_id == excel_gestion.id,
            )
            .count()
            == 0
        )
        assert _filas_gestion(db, tarea_id) == 0

        confirmada = client.post(f"/proyectos/{pid}/apartados/{tarea_id}/confirmar-gestion")
        assert confirmada.status_code == 200, confirmada.text
        assert confirmada.json()["estado_revision"] == "confirmada"
        assert confirmada.json()["importe"] == 800.0
        assert _filas_gestion(db, tarea_id) == 1
        otra = client.post(f"/proyectos/{pid}/apartados/{tarea_id}/confirmar-gestion")
        assert otra.status_code == 200
        assert otra.json()["estado_revision"] == "confirmada"
        assert _filas_gestion(db, tarea_id) == 2

        detalle = client.get(f"/proyectos/{pid}")
        sugeridas = []
        for fila in detalle.json()["contratos"]:
            if fila["id"] == contrato.id:
                sugeridas = [s["tarea_id"] for s in fila["sugerencias"]]
        assert tarea_id in sugeridas
        assert excel_gestion.id not in sugeridas

        enlace = client.post(
            f"/proyectos/{pid}/contratos/{contrato.id}/enlazar-apartado",
            json={"tarea_apartado_id": tarea_id},
        )
        assert enlace.status_code == 200, enlace.text
        detalle = client.get(f"/proyectos/{pid}")
        apartados = detalle.json()["apartados"]
        marcado = next(ap for ap in apartados if ap["id"] == tarea_id)
        assert marcado["solo_gestion"] is True
        assert marcado["estado_revision"] == "confirmada"
    finally:
        borrar_proyecto(db, obra["proyecto"].id, _usuario_limpieza(db))
