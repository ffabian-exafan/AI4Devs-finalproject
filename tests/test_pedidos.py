"""Alta de obra desde pedidos ficticios."""

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Contrato, ContratoApartado, Contratista, Nave, Pedido, Proyecto, RegistroAccion, Tarea, Usuario
from app.services.casado import enlazar_contrato_apartado
from app.models.registro_accion import ACCIONES
from app.services.pedidos import anadir_pedido, confirmar_pedido, importar_pedidos
from app.services.proyectos import asignar_codigo_contrato, borrar_proyecto, obtener_proyecto
from app.services.registro import ETIQUETAS
from tests.pdf_pedido import pdf_pedido


def test_el_modelo_tiene_numero_unico_y_nave():
    assert Pedido.__tablename__ == "pedido"
    columnas = {col.name for col in Pedido.__table__.columns}
    assert {"proyecto_id", "nave_id", "numero", "rotulo", "estado_revision", "ruta_almacen"} <= columnas


def test_el_almacen_acepta_el_tipo_pedido():
    texto = Path("app/services/almacen.py").read_text(encoding="utf-8")
    assert '"pedido"' in texto


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _usuario(db: Session) -> Usuario:
    usuario = Usuario(
        nombre="Ana Ejemplo",
        email=f"ana.{uuid.uuid4().hex}@example.com",
        rol="direccion",
        password_hash="hash-ficticio",
    )
    db.add(usuario)
    db.commit()
    return usuario


def test_dos_pedidos_son_dos_naves_de_una_obra(db: Session):
    usuario = _usuario(db)
    primero = pdf_pedido(
        [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "150,00", "0", "100,00")],
        numero="1-10001",
        rotulo="NAVE 1",
    )
    segundo = pdf_pedido(
        [("SUST01000001", "INSTALACION DE EJEMPLO", "1,00", "80,00", "0", "80,00")],
        numero="1-10002",
        rotulo="NAVE 2",
    )
    alta = importar_pedidos(db, "Obra ficticia serie 1", [("nave-1.pdf", primero)])
    anadir_pedido(db, alta.proyecto_id, "nave-2.pdf", segundo)
    proyecto = db.get(Proyecto, alta.proyecto_id)
    assert proyecto.estado == "pendiente_revision"
    pedidos = db.query(Pedido).filter(Pedido.proyecto_id == proyecto.id).order_by(Pedido.numero).all()
    assert [p.numero for p in pedidos] == ["1-10001", "1-10002"]
    assert pedidos[0].nave.codigo == "1-10001"
    assert pedidos[0].nave.descripcion == "NAVE 1"
    linea = db.query(Tarea).filter(Tarea.pedido_id == pedidos[0].id).one()
    assert linea.nivel == "apartado"
    assert linea.es_montaje is True
    assert linea.estado_revision == "pendiente"
    assert linea.importe_presupuestado == Decimal("100.00")
    assert linea.presupuesto_id is None
    borrar_proyecto(db, proyecto.id, usuario)


def test_la_plantilla_rota_no_crea_la_obra(db: Session):
    with pytest.raises(ValueError, match="plantilla"):
        importar_pedidos(
            db,
            "Obra que no debe quedar",
            [("roto.pdf", pdf_pedido(
                [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "10,00", "0", "10,00")],
                cabecera=False,
            ))],
        )
    assert db.query(Proyecto).filter(Proyecto.nombre == "Obra que no debe quedar").count() == 0


def test_confirmar_deja_la_linea_lista_para_el_contrato(db: Session):
    usuario = _usuario(db)
    alta = importar_pedidos(
        db,
        "Obra a confirmar",
        [("nave.pdf", pdf_pedido(
            [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "10,00", "0", "10,00")],
        ))],
    )
    pedido = db.query(Pedido).filter(Pedido.proyecto_id == alta.proyecto_id).one()
    confirmar_pedido(db, alta.proyecto_id, pedido.id, usuario)
    db.refresh(pedido)
    assert pedido.estado_revision == "confirmada"
    assert db.get(Proyecto, alta.proyecto_id).estado == "en_curso"
    linea = db.query(Tarea).filter(Tarea.pedido_id == pedido.id).one()
    assert linea.estado_revision == "confirmada"
    assert "confirmar_pedido" in ACCIONES
    assert ETIQUETAS["confirmar_pedido"] == "Confirmó el pedido"
    fila = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "confirmar_pedido",
            RegistroAccion.documento_id == pedido.id,
        )
        .one()
    )
    assert fila.documento_id == pedido.id
    borrar_proyecto(db, alta.proyecto_id, usuario)


def test_el_detalle_enseña_el_apartado_del_pedido(db: Session):
    usuario = _usuario(db)
    alta = importar_pedidos(
        db,
        "Obra con detalle",
        [("nave.pdf", pdf_pedido(
            [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "10,00", "0", "40,00")],
            rotulo="NAVE 1",
        ))],
    )
    detalle = obtener_proyecto(db, alta.proyecto_id)
    assert detalle.apartados[0].descripcion == "MONTAJE DE EJEMPLO"
    assert detalle.apartados[0].importe_presupuestado == Decimal("40.00")
    assert detalle.pedidos[0].numero == "1-10001"
    assert detalle.pedidos[0].estado_revision == "pendiente"
    assert detalle.naves[0].codigo == "1-10001"
    assert detalle.naves[0].descripcion == "NAVE 1"
    borrar_proyecto(db, alta.proyecto_id, usuario)


def _contrato_minimo(
    db: Session,
    proyecto_id: int,
    codigo: str | None = None,
    nif: str = "B00000000",
):
    contratista = db.query(Contratista).filter(Contratista.nif == nif).first()
    if contratista is None:
        contratista = Contratista(nif=nif, nombre="Proveedor Ejemplo", tipo="externo")
        db.add(contratista)
        db.flush()
    nave = db.query(Nave).filter(Nave.proyecto_id == proyecto_id).order_by(Nave.id).first()
    contrato = Contrato(
        proyecto_id=proyecto_id,
        nave_id=nave.id,
        contratista_id=contratista.id,
        precio_total=Decimal("10.00"),
        fichero_origen="contrato-ficticio.pdf",
        estado_extraccion="pendiente_revision",
        codigo=codigo,
    )
    db.add(contrato)
    db.commit()
    db.refresh(contrato)
    return contrato


def test_rechaza_el_contrato_de_otro_pedido(db: Session):
    usuario = _usuario(db)
    alta = importar_pedidos(
        db,
        "Obra de un pedido",
        [("nave.pdf", pdf_pedido(
            [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "10,00", "0", "10,00")],
        ))],
    )
    contrato = _contrato_minimo(db, alta.proyecto_id)
    with pytest.raises(ValueError, match="1-10099"):
        asignar_codigo_contrato(db, alta.proyecto_id, contrato.id, "1-100990")
    db.refresh(contrato)
    assert contrato.codigo is None
    asignar_codigo_contrato(db, alta.proyecto_id, contrato.id, "1-100010")
    db.refresh(contrato)
    assert contrato.codigo == "1-100010"
    assert contrato.nave_id == db.query(Pedido).filter(Pedido.numero == "1-10001").one().nave_id
    borrar_proyecto(db, alta.proyecto_id, usuario)


def test_dos_proveedores_comparten_la_linea_confirmada(db: Session):
    usuario = _usuario(db)
    alta = importar_pedidos(
        db,
        "Obra de dos proveedores",
        [("nave.pdf", pdf_pedido(
            [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "10,00", "0", "10,00")],
        ))],
    )
    pedido = db.query(Pedido).filter(Pedido.proyecto_id == alta.proyecto_id).one()
    linea = db.query(Tarea).filter(Tarea.pedido_id == pedido.id).one()
    uno = _contrato_minimo(db, alta.proyecto_id, codigo="1-100010", nif="B00000000")
    with pytest.raises(ValueError, match="pendiente"):
        enlazar_contrato_apartado(db, alta.proyecto_id, uno.id, [linea.id])
    confirmar_pedido(db, alta.proyecto_id, pedido.id, usuario)
    dos = _contrato_minimo(db, alta.proyecto_id, codigo="1-100011", nif="B00000001")
    enlazar_contrato_apartado(db, alta.proyecto_id, uno.id, [linea.id])
    enlazar_contrato_apartado(db, alta.proyecto_id, dos.id, [linea.id])
    assert (
        db.query(ContratoApartado).filter(ContratoApartado.tarea_id == linea.id).count()
        == 2
    )
    borrar_proyecto(db, alta.proyecto_id, usuario)


def test_el_alta_ofrece_el_pedido_de_compra():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    js = Path("app/static/js/obras.js").read_text(encoding="utf-8")
    assert "Pedido de compra" in html
    assert "/proyectos/importar-pedidos" in js
    assert "/confirmar" in js


def test_el_flujo_ya_no_dice_que_falta_la_pantalla():
    texto = Path("docs/flujo_ui_proyecto.md").read_text(encoding="utf-8")
    assert "La pantalla de alta desde el pedido no está construida." not in texto
    assert "POST /proyectos/importar-pedidos" in texto
