"""Registro inmutable de gestos. Usuarios y obras ficticios."""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import RegistroAccion, Usuario
from app.services.registro import registrar


def _email() -> str:
    return f"ana.registro.{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_la_fila_no_se_puede_modificar(db: Session):
    usuario = Usuario(
        nombre="Ana Ejemplo",
        email=_email(),
        rol="direccion",
        password_hash="hash-ficticio",
    )
    db.add(usuario)
    db.commit()
    fila = RegistroAccion(
        usuario_id=usuario.id,
        nombre_en_el_momento=usuario.nombre,
        accion="inicio_sesion",
        ocurrido_en=datetime.now(timezone.utc),
    )
    db.add(fila)
    db.commit()
    fila_id = fila.id
    with pytest.raises(DatabaseError, match="no se puede modificar"):
        db.execute(
            RegistroAccion.__table__.update()
            .where(RegistroAccion.id == fila_id)
            .values(nombre_en_el_momento="Otro Nombre")
        )
        db.commit()
    db.rollback()


def _filas_del_usuario(db: Session, usuario_id: int) -> int:
    return (
        db.query(RegistroAccion)
        .filter(RegistroAccion.usuario_id == usuario_id)
        .count()
    )


def test_registrar_copia_el_nombre_y_no_hace_commit(db: Session):
    usuario = Usuario(
        nombre="Ana Ejemplo",
        email=_email(),
        rol="direccion",
        password_hash="hash-ficticio",
    )
    db.add(usuario)
    db.commit()
    antes = _filas_del_usuario(db, usuario.id)
    registrar(db, usuario, "inicio_sesion")
    db.rollback()
    despues = _filas_del_usuario(db, usuario.id)
    assert antes == 0
    assert despues == antes

    registrar(db, usuario, "inicio_sesion")
    db.commit()
    usuario.nombre = "Nombre Nuevo"
    db.commit()
    fila = (
        db.query(RegistroAccion)
        .filter(RegistroAccion.usuario_id == usuario.id)
        .one()
    )
    assert fila.nombre_en_el_momento == "Ana Ejemplo"
    assert fila.usuario_id == usuario.id
    assert fila.tipo_documento is None


def test_registrar_rechaza_accion_desconocida(db: Session):
    usuario = Usuario(
        nombre="Ana Ejemplo",
        email=_email(),
        rol="direccion",
        password_hash="hash-ficticio",
    )
    db.add(usuario)
    db.commit()
    with pytest.raises(ValueError, match="desconocida"):
        registrar(db, usuario, "mirar_pantalla")


def test_la_consulta_solo_la_ven_direccion_y_superadministrador(client, db):
    from tests.sesion import entrar

    entrar(client, db, rol="jefe_obra")
    denegado = client.get("/registro")
    assert denegado.status_code == 403
    assert denegado.json()["detail"] == (
        "La consulta es para dirección y el superadministrador."
    )


def test_administracion_no_lista_el_registro(client, db):
    from tests.sesion import entrar

    entrar(client, db, rol="administracion")
    denegado = client.get("/registro")
    assert denegado.status_code == 403
    assert denegado.json()["detail"] == (
        "La consulta es para dirección y el superadministrador."
    )


def test_direccion_lista_el_registro(client, db):
    from tests.sesion import entrar

    persona = entrar(client, db, rol="direccion")
    res = client.get("/registro")
    assert res.status_code == 200, res.text
    cuerpo = res.json()
    assert cuerpo["page"] == 1
    assert cuerpo["page_size"] == 50
    assert any(item["nombre"] == "Persona Ejemplo" for item in cuerpo["items"])
    assert all("importe" not in item for item in cuerpo["items"])
    assert persona.id


def test_superadministrador_lista_el_registro(client, db):
    from tests.sesion import entrar

    entrar(client, db, rol="superadministrador")
    res = client.get("/registro")
    assert res.status_code == 200, res.text
    cuerpo = res.json()
    assert cuerpo["page"] == 1
    assert cuerpo["page_size"] == 50


def test_importar_presupuesto_no_escribe_fila(client, db):
    from pathlib import Path

    antes = db.query(RegistroAccion).count()
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "presupuesto_nave_destete_anonimizado.md"
    )
    with fixture.open("rb") as fh:
        res = client.post(
            "/proyectos/importar-presupuesto",
            files={"fichero": (fixture.name, fh, "text/markdown")},
        )
    assert res.status_code == 201, res.text
    assert db.query(RegistroAccion).count() == antes
