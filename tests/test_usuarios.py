"""Login y gestión de usuarios. Datos ficticios, sin personas reales."""

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import RegistroAccion, Usuario

CLAVE = "clave-ficticia"


def _email() -> str:
    return f"ana.ejemplo.{uuid.uuid4().hex[:8]}@example.com"


def _alta(
    db: Session,
    *,
    email: str,
    rol: str = "direccion",
    nombre: str = "Ana Ejemplo",
    password: str = CLAVE,
) -> Usuario:
    usuario = Usuario(
        nombre=nombre,
        email=email,
        rol=rol,
        password_hash=PasswordHasher().hash(password),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def test_la_app_y_la_pantalla_exigen_login(client: TestClient):
    portada = client.get("/", follow_redirects=False)
    assert portada.status_code == 303
    assert portada.headers["location"].startswith("/login.html")

    pantalla = client.get("/usuarios.html", follow_redirects=False)
    assert pantalla.status_code == 303
    assert "login.html" in pantalla.headers["location"]

    assert client.get("/usuarios").status_code == 401
    assert client.get("/login.html").status_code == 200
    assert client.get("/css/exafan.css").status_code == 200


def test_login_rechaza_clave_incorrecta(client: TestClient, db: Session):
    email = _email()
    _alta(db, email=email)
    antes = (
        db.query(RegistroAccion)
        .filter(RegistroAccion.accion == "inicio_sesion")
        .count()
    )

    res = client.post(
        "/auth/login",
        json={"email": email, "password": "otra-clave-mala"},
    )

    despues = (
        db.query(RegistroAccion)
        .filter(RegistroAccion.accion == "inicio_sesion")
        .count()
    )
    assert res.status_code == 401
    assert "password_hash" not in res.text
    assert despues == antes


def test_login_deja_entrar_y_no_devuelve_la_clave(client: TestClient, db: Session):
    email = _email()
    _alta(db, email=email, rol="jefe_obra", nombre="Jefe Ejemplo")

    res = client.post("/auth/login", json={"email": email, "password": CLAVE})

    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["email"] == email
    assert cuerpo["rol"] == "jefe_obra"
    assert cuerpo["nombre"] == "Jefe Ejemplo"
    assert "password" not in cuerpo
    yo = client.get("/auth/yo")
    assert yo.status_code == 200
    entradas = (
        db.query(RegistroAccion)
        .filter(RegistroAccion.accion == "inicio_sesion")
        .all()
    )
    assert any(fila.usuario_id == cuerpo["id"] for fila in entradas)
    assert yo.json()["id"] == cuerpo["id"]
    assert client.get("/", follow_redirects=False).status_code == 200


def test_logout_cierra_la_sesion(client: TestClient, db: Session):
    email = _email()
    usuario = _alta(db, email=email)
    client.post("/auth/login", json={"email": email, "password": CLAVE})
    tras_login = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "inicio_sesion",
            RegistroAccion.usuario_id == usuario.id,
        )
        .count()
    )

    out = client.post("/auth/logout")
    tras_logout = (
        db.query(RegistroAccion)
        .filter(
            RegistroAccion.accion == "inicio_sesion",
            RegistroAccion.usuario_id == usuario.id,
        )
        .count()
    )

    assert out.status_code == 204
    assert client.get("/auth/yo").status_code == 401
    assert client.get("/usuarios").status_code == 401
    assert tras_logout == tras_login


def test_alta_edicion_y_borrado(client: TestClient, db: Session):
    email = _email()
    propio = _alta(db, email=email)
    client.post("/auth/login", json={"email": email, "password": CLAVE})

    nuevo_email = _email()
    alta = client.post(
        "/usuarios",
        json={
            "nombre": "Admin Ejemplo",
            "email": nuevo_email,
            "rol": "administracion",
            "password": "clave-ficticia-2",
        },
    )
    assert alta.status_code == 201
    creado = alta.json()
    assert creado["rol"] == "administracion"
    assert "password" not in creado

    lista = client.get("/usuarios")
    assert lista.status_code == 200
    assert any(fila["email"] == nuevo_email for fila in lista.json())

    edit = client.patch(
        f"/usuarios/{creado['id']}",
        json={"nombre": "Admin Corregido", "rol": "direccion", "password": "clave-nueva-ok"},
    )
    assert edit.status_code == 200
    assert edit.json()["nombre"] == "Admin Corregido"
    assert edit.json()["rol"] == "direccion"

    client.post("/auth/logout")
    assert (
        client.post(
            "/auth/login",
            json={"email": nuevo_email, "password": "clave-ficticia-2"},
        ).status_code
        == 401
    )
    bien = client.post(
        "/auth/login",
        json={"email": nuevo_email, "password": "clave-nueva-ok"},
    )
    assert bien.status_code == 200

    no = client.delete(f"/usuarios/{bien.json()['id']}")
    assert no.status_code == 409

    borrar = client.delete(f"/usuarios/{propio.id}")
    assert borrar.status_code == 204
    assert client.get("/auth/yo").status_code == 200


def test_rol_invalido_y_email_duplicado(client: TestClient, db: Session):
    email = _email()
    _alta(db, email=email)
    client.post("/auth/login", json={"email": email, "password": CLAVE})

    rol = client.post(
        "/usuarios",
        json={
            "nombre": "X Ejemplo",
            "email": _email(),
            "rol": "admin",
            "password": CLAVE,
        },
    )
    assert rol.status_code == 422

    alta = client.post(
        "/usuarios",
        json={
            "nombre": "Super Ejemplo",
            "email": _email(),
            "rol": "superadministrador",
            "password": CLAVE,
        },
    )
    assert alta.status_code == 201
    assert alta.json()["rol"] == "superadministrador"

    pagina = client.get("/registro.html")
    assert pagina.status_code == 200

    dup = client.post(
        "/usuarios",
        json={
            "nombre": "Otro Ejemplo",
            "email": email,
            "rol": "jefe_obra",
            "password": CLAVE,
        },
    )
    assert dup.status_code == 409


def test_semilla_crea_el_usuario_de_ejemplo(db: Session):
    from app.seed import asegurar_usuario_inicial

    primero = asegurar_usuario_inicial(db)
    segundo = asegurar_usuario_inicial(db)

    assert primero.id == segundo.id
    assert primero.email == "ana.ejemplo@example.com"
    assert primero.rol == "direccion"
    assert primero.password_hash != "clave-ficticia"


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
