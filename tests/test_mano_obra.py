"""Mano de obra propia. Horas y precios ficticios, sin datos reales."""

from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Nave, Proyecto, RegistroAccion, Tarea
from app.models.registro_accion import ACCIONES
from app.services.extraccion_parte import CamposParte
from app.services.registro import ETIQUETAS
from tests.sesion import entrar


def test_el_catalogo_conoce_la_mano_de_obra():
    assert "guardar_precio_hora" in ACCIONES
    assert "borrar_linea_mano_obra" in ACCIONES
    assert "confirmar_parte" in ACCIONES
    assert "borrar_parte" in ACCIONES
    assert ETIQUETAS["guardar_precio_hora"] == "Guardó el precio por hora"
    assert ETIQUETAS["borrar_linea_mano_obra"] == "Borró la línea de mano de obra"
    assert ETIQUETAS["confirmar_parte"] == "Confirmó el parte"
    assert ETIQUETAS["borrar_parte"] == "Borró el parte"


def test_la_pantalla_de_registro_lista_la_mano_de_obra():
    texto = Path("app/static/js/registro.js").read_text(encoding="utf-8")
    assert '["guardar_precio_hora", "Guardó el precio por hora"]' in texto
    assert '["borrar_linea_mano_obra", "Borró la línea de mano de obra"]' in texto
    assert '["confirmar_parte", "Confirmó el parte"]' in texto
    assert '["borrar_parte", "Borró el parte"]' in texto


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


@pytest.fixture
def lectura(monkeypatch):
    def _poner(horas="8.00", fecha=None, manuscrito=False):
        def falso(_texto: str) -> CamposParte:
            cifra = None if horas is None else Decimal(horas)
            return CamposParte(cifra, fecha, manuscrito)

        monkeypatch.setattr("app.services.extraccion_parte.extraer_campos", falso)

    _poner()
    return _poner


def _pdf(texto: str) -> bytes:
    documento = pymupdf.open()
    pagina = documento.new_page()
    pagina.insert_text((72, 72), texto)
    datos = documento.tobytes()
    documento.close()
    return datos


def _obra(db: Session) -> Proyecto:
    obra = Proyecto(nombre="Obra ficticia mano de obra", tipo="reforma", estado="en_curso")
    db.add(obra)
    db.commit()
    db.refresh(obra)
    return obra


def _linea(client: TestClient, obra_id: int, nombre: str = "Montaje de comederos"):
    return client.post(
        f"/proyectos/{obra_id}/lineas-mano-obra",
        json={"nombre": nombre},
    )


def _precio(client: TestClient, obra_id: int, precio: str = "18.50"):
    return client.patch(
        f"/proyectos/{obra_id}/precio-hora",
        json={"precio_hora": precio},
    )


def _subir(client: TestClient, obra_id: int, linea_id: int, texto: str = "Parte ficticio"):
    return client.post(
        f"/proyectos/{obra_id}/lineas-mano-obra/{linea_id}/partes",
        files={"fichero": (f"{texto}.pdf", _pdf(texto), "application/pdf")},
    )


def _parte(cuerpo: dict) -> dict:
    return cuerpo["lineas"][0]["partes"][0]


def test_el_nombre_vacio_no_crea_linea(client: TestClient, db: Session):
    obra = _obra(db)
    entrar(client, db)
    vacio = _linea(client, obra.id, "   ")
    assert vacio.status_code == 422
    creado = _linea(client, obra.id, "  Montaje de comederos  ")
    assert creado.status_code == 201, creado.text
    assert creado.json()["lineas"][0]["nombre"] == "Montaje de comederos"
    assert creado.json()["lineas"][0]["acumulado"] == "0,00 €"


def test_subir_un_parte_lo_deja_pendiente(client: TestClient, db: Session, uploads, lectura):
    obra = _obra(db)
    entrar(client, db)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    respuesta = _subir(client, obra.id, linea_id)
    assert respuesta.status_code == 201, respuesta.text
    parte = _parte(respuesta.json())
    assert parte["estado_revision"] == "pendiente"
    assert parte["horas"] == "8.00"
    assert parte["precio_hora_aplicado"] is None
    assert respuesta.json()["lineas"][0]["acumulado"] == "0,00 €"
    assert respuesta.json()["acumulado"] == "0,00 €"
    assert "ruta_almacen" not in parte


def test_sin_precio_no_se_confirma(client: TestClient, db: Session, uploads, lectura):
    obra = _obra(db)
    entrar(client, db)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    parte_id = _parte(_subir(client, obra.id, linea_id).json())["id"]
    respuesta = client.post(f"/proyectos/{obra.id}/partes/{parte_id}/confirmar")
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == "Falta el precio por hora de la obra."
    detalle = client.get(f"/proyectos/{obra.id}").json()["mano_obra"]
    assert _parte(detalle)["estado_revision"] == "pendiente"


def test_las_horas_a_cero_no_confirman(client: TestClient, db: Session, uploads, lectura):
    obra = _obra(db)
    entrar(client, db)
    _precio(client, obra.id)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    parte_id = _parte(_subir(client, obra.id, linea_id).json())["id"]
    vacias = client.patch(
        f"/proyectos/{obra.id}/partes/{parte_id}",
        json={"horas": None},
    )
    assert vacias.status_code == 200, vacias.text
    assert _parte(vacias.json())["aviso"] == "No se han leído las horas. Escríbelas."
    cero = client.patch(
        f"/proyectos/{obra.id}/partes/{parte_id}",
        json={"horas": "0"},
    )
    assert cero.status_code == 422
    confirmar = client.post(f"/proyectos/{obra.id}/partes/{parte_id}/confirmar")
    assert confirmar.status_code == 422
    assert confirmar.json()["detail"] == "Las horas tienen que ser mayores que cero."


def test_confirmar_copia_el_precio_y_suma_el_acumulado(
    client: TestClient, db: Session, uploads, lectura
):
    obra = _obra(db)
    entrar(client, db)
    _precio(client, obra.id, "18.50")
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    parte_id = _parte(_subir(client, obra.id, linea_id).json())["id"]
    respuesta = client.post(f"/proyectos/{obra.id}/partes/{parte_id}/confirmar")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    parte = _parte(cuerpo)
    assert parte["estado_revision"] == "confirmada"
    assert parte["precio_hora_aplicado"] == "18.5000"
    assert parte["importe"] == "148,00 €"
    assert cuerpo["lineas"][0]["horas"] == "8.00"
    assert cuerpo["lineas"][0]["acumulado"] == "148,00 €"
    assert cuerpo["acumulado"] == "148,00 €"
    fila = (
        db.query(RegistroAccion)
        .filter(RegistroAccion.accion == "confirmar_parte", RegistroAccion.documento_id == parte_id)
        .one()
    )
    assert fila.tipo_documento == "parte_trabajo"
    assert fila.etiqueta.endswith(".pdf")


def test_el_importe_redondea_half_up(client: TestClient, db: Session, uploads, lectura):
    lectura(horas="1.25")
    obra = _obra(db)
    entrar(client, db)
    _precio(client, obra.id, "1.0040")
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    parte_id = _parte(_subir(client, obra.id, linea_id, "Parte redondeo").json())["id"]
    respuesta = client.post(f"/proyectos/{obra.id}/partes/{parte_id}/confirmar")
    assert _parte(respuesta.json())["importe"] == "1,26 €"


def test_cambiar_el_precio_no_toca_lo_confirmado(
    client: TestClient, db: Session, uploads, lectura
):
    obra = _obra(db)
    entrar(client, db)
    _precio(client, obra.id, "18.50")
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    primero = _parte(_subir(client, obra.id, linea_id, "Parte uno").json())["id"]
    client.post(f"/proyectos/{obra.id}/partes/{primero}/confirmar")
    cambio = _precio(client, obra.id, "20")
    assert cambio.status_code == 200, cambio.text
    assert cambio.json()["precio_hora"] == "20.0000"
    guardado = next(
        parte for parte in cambio.json()["lineas"][0]["partes"] if parte["id"] == primero
    )
    assert guardado["precio_hora_aplicado"] == "18.5000"
    assert guardado["importe"] == "148,00 €"
    segundo = next(
        parte
        for parte in _subir(client, obra.id, linea_id, "Parte dos").json()["lineas"][0]["partes"]
        if parte["archivo"] == "Parte dos.pdf"
    )
    assert segundo["estado_revision"] == "pendiente"
    nuevo = client.post(f"/proyectos/{obra.id}/partes/{segundo['id']}/confirmar")
    partes = {parte["id"]: parte for parte in nuevo.json()["lineas"][0]["partes"]}
    assert partes[primero]["precio_hora_aplicado"] == "18.5000"
    assert partes[segundo["id"]]["precio_hora_aplicado"] == "20.0000"
    assert partes[segundo["id"]]["importe"] == "160,00 €"


def test_confirmar_dos_veces_no_cambia_ni_registra(
    client: TestClient, db: Session, uploads, lectura
):
    obra = _obra(db)
    entrar(client, db)
    _precio(client, obra.id)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    parte_id = _parte(_subir(client, obra.id, linea_id).json())["id"]
    client.post(f"/proyectos/{obra.id}/partes/{parte_id}/confirmar")
    otra = client.post(f"/proyectos/{obra.id}/partes/{parte_id}/confirmar")
    assert otra.status_code == 200
    assert _parte(otra.json())["importe"] == "148,00 €"
    filas = (
        db.query(RegistroAccion)
        .filter(RegistroAccion.accion == "confirmar_parte", RegistroAccion.documento_id == parte_id)
        .count()
    )
    assert filas == 1
    editar = client.patch(
        f"/proyectos/{obra.id}/partes/{parte_id}",
        json={"horas": "4"},
    )
    assert editar.status_code == 409
    assert editar.json()["detail"] == "El parte ya está confirmado."


def test_quitar_un_parte_confirmado_lo_saca_del_acumulado(
    client: TestClient, db: Session, uploads, lectura
):
    obra = _obra(db)
    entrar(client, db)
    _precio(client, obra.id)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    primero = _parte(_subir(client, obra.id, linea_id, "Parte uno").json())["id"]
    segundo = next(
        parte["id"]
        for parte in _subir(client, obra.id, linea_id, "Parte dos").json()["lineas"][0]["partes"]
        if parte["archivo"] == "Parte dos.pdf"
    )
    client.post(f"/proyectos/{obra.id}/partes/{primero}/confirmar")
    client.post(f"/proyectos/{obra.id}/partes/{segundo}/confirmar")
    quitado = client.delete(f"/proyectos/{obra.id}/partes/{primero}")
    assert quitado.status_code == 204
    detalle = client.get(f"/proyectos/{obra.id}").json()["mano_obra"]
    assert detalle["acumulado"] == "148,00 €"
    assert len(detalle["lineas"][0]["partes"]) == 1
    assert detalle["lineas"][0]["partes"][0]["precio_hora_aplicado"] == "18.5000"


def test_no_se_borra_una_linea_con_partes_confirmados(
    client: TestClient, db: Session, uploads, lectura
):
    obra = _obra(db)
    entrar(client, db)
    _precio(client, obra.id)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    parte_id = _parte(_subir(client, obra.id, linea_id).json())["id"]
    client.post(f"/proyectos/{obra.id}/partes/{parte_id}/confirmar")
    respuesta = client.delete(f"/proyectos/{obra.id}/lineas-mano-obra/{linea_id}")
    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Quita antes los partes confirmados."
    assert len(client.get(f"/proyectos/{obra.id}").json()["mano_obra"]["lineas"]) == 1


def test_borrar_una_linea_pendiente_borra_el_fichero(
    client: TestClient, db: Session, uploads, lectura
):
    obra = _obra(db)
    entrar(client, db)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    _subir(client, obra.id, linea_id)
    carpeta = uploads / str(obra.id) / "parte"
    assert any(carpeta.iterdir())
    respuesta = client.delete(f"/proyectos/{obra.id}/lineas-mano-obra/{linea_id}")
    assert respuesta.status_code == 204
    assert client.get(f"/proyectos/{obra.id}").json()["mano_obra"]["lineas"] == []
    assert not carpeta.exists() or not any(carpeta.iterdir())
    filas = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "borrar_parte",
            RegistroAccion.etiqueta == "Parte ficticio.pdf",
        )
        .count()
    )
    assert filas == 0
    linea = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "borrar_linea_mano_obra",
            RegistroAccion.documento_id == linea_id,
        )
        .one()
    )
    assert linea.etiqueta == "Montaje de comederos"


def test_el_control_no_incluye_el_acumulado(client: TestClient, db: Session, uploads, lectura):
    obra = _obra(db)
    nave = Nave(
        proyecto_id=obra.id,
        codigo="N1",
        descripcion="Nave ficticia",
        importe_presupuestado=Decimal("1000.00"),
    )
    db.add(nave)
    db.flush()
    db.add(
        Tarea(
            nave_id=nave.id,
            codigo="01",
            nivel="apartado",
            descripcion="Apartado ficticio",
            importe_presupuestado=Decimal("1000.00"),
            estado_revision="confirmada",
            estado="no_iniciada",
            avance_fisico_pct=Decimal("0"),
            tiene_anotacion_manual=False,
        )
    )
    db.commit()
    entrar(client, db)
    antes = client.get(f"/proyectos/{obra.id}/control-economico").json()
    _precio(client, obra.id)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    parte_id = _parte(_subir(client, obra.id, linea_id).json())["id"]
    client.post(f"/proyectos/{obra.id}/partes/{parte_id}/confirmar")
    despues = client.get(f"/proyectos/{obra.id}/control-economico").json()
    assert despues == antes


def test_un_fichero_malo_no_crea_parte(client: TestClient, db: Session, uploads, lectura):
    obra = _obra(db)
    entrar(client, db)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    ruta = f"/proyectos/{obra.id}/lineas-mano-obra/{linea_id}/partes"
    vacio = client.post(ruta, files={"fichero": ("vacio.pdf", b"", "application/pdf")})
    falso = client.post(ruta, files={"fichero": ("falso.pdf", b"no es pdf", "application/pdf")})
    texto = client.post(ruta, files={"fichero": ("nota.txt", b"horas 8", "text/plain")})
    assert vacio.status_code == 422
    assert falso.status_code == 422
    assert texto.status_code == 422
    assert client.get(f"/proyectos/{obra.id}").json()["mano_obra"]["lineas"][0]["partes"] == []


def test_sin_horas_leidas_queda_el_aviso(client: TestClient, db: Session, uploads, lectura):
    lectura(horas=None)
    obra = _obra(db)
    entrar(client, db)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    respuesta = _subir(client, obra.id, linea_id, "Parte sin horas")
    parte = _parte(respuesta.json())
    assert parte["estado_revision"] == "pendiente"
    assert parte["horas"] is None
    assert parte["aviso"] == "No se han leído las horas. Escríbelas."
    assert respuesta.json()["acumulado"] == "0,00 €"


def test_la_anotacion_manuscrita_sigue_pendiente_hasta_confirmar(
    client: TestClient, db: Session, uploads, lectura
):
    lectura(manuscrito=True)
    obra = _obra(db)
    entrar(client, db)
    _precio(client, obra.id)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    subido = _subir(client, obra.id, linea_id, "Parte manuscrito")
    parte = _parte(subido.json())
    assert parte["tiene_anotacion_manual"] is True
    assert parte["estado_revision"] == "pendiente"
    confirmado = client.post(f"/proyectos/{obra.id}/partes/{parte['id']}/confirmar")
    assert _parte(confirmado.json())["estado_revision"] == "confirmada"


def test_un_parte_de_otra_obra_responde_404(client: TestClient, db: Session, uploads, lectura):
    obra = _obra(db)
    ajena = _obra(db)
    entrar(client, db)
    _precio(client, obra.id)
    linea_id = _linea(client, obra.id).json()["lineas"][0]["id"]
    parte_id = _parte(_subir(client, obra.id, linea_id).json())["id"]
    assert client.post(f"/proyectos/{ajena.id}/partes/{parte_id}/confirmar").status_code == 404
    assert (
        client.patch(
            f"/proyectos/{ajena.id}/partes/{parte_id}",
            json={"horas": "3"},
        ).status_code
        == 404
    )
    assert client.get(f"/proyectos/{ajena.id}/partes/{parte_id}/fichero").status_code == 404
    assert client.delete(f"/proyectos/{ajena.id}/partes/{parte_id}").status_code == 404
    assert _parte(client.get(f"/proyectos/{obra.id}").json()["mano_obra"])["id"] == parte_id
