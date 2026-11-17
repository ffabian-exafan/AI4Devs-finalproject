# Registro inmutable de acciones — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guardar una fila inmutable por cada gesto de obra ya cerrado y por cada inicio de sesión correcto, y dejar que dirección y el superadministrador la consulten.

**Architecture:** Una tabla `registro_accion` sin claves ajenas. Un solo `registrar` inserta en la misma sesión, antes del `commit` que el servicio ya hace. Un disparador rechaza `UPDATE` y `DELETE`. `GET /registro` exige rol `direccion` o `superadministrador`. El día visible se calcula en `Europe/Madrid`.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, HTML + Alpine.js, pytest.

**Spec:** `docs/designs/registro_inmutable_de_acciones.md`

**Corte que el diseño no nombra:** `confirmar_importe_cliente` llama a `confirmar_importes_cliente`. La fila se escribe solo en `confirmar_importes_cliente`, con un flag. Si hay una tarea, el código es `confirmar_importe_cliente` y el documento es la tarea. Si hay varias, el código es `confirmar_importes_cliente` y el documento es el proyecto. Así una petición deja una fila.

---

### Task 1: Tabla y modelo

**Files:**
- Create: `migrations/versions/0015_registro_accion.py`
- Create: `app/models/registro_accion.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_registro.py`

- [ ] **Step 1: Write the failing test**

Crear `tests/test_registro.py`:

```python
"""Registro inmutable de gestos. Usuarios y obras ficticios."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.models import RegistroAccion, Usuario
from app.db import SessionLocal


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_la_fila_no_se_puede_modificar(db: Session):
    usuario = Usuario(
        nombre="Ana Ejemplo",
        email="ana.registro.ejemplo@example.com",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registro.py::test_la_fila_no_se_puede_modificar -v`

Expected: FAIL. `RegistroAccion` no existe, o la tabla no existe.

- [ ] **Step 3: Write minimal implementation**

`app/models/registro_accion.py`:

```python
"""Fila inmutable de un gesto de persona."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ACCIONES = (
    "confirmar_revision",
    "confirmar_factura",
    "confirmar_importe_cliente",
    "confirmar_importes_cliente",
    "confirmar_solo_gestion",
    "borrar_proyecto",
    "borrar_contrato",
    "borrar_factura",
    "borrar_linea",
    "inicio_sesion",
)


class RegistroAccion(Base):
    __tablename__ = "registro_accion"
    __table_args__ = (
        CheckConstraint(
            "accion IN (" + ", ".join(f"'{codigo}'" for codigo in ACCIONES) + ")",
            name="registro_accion_codigo",
        ),
        CheckConstraint(
            "("
            "accion = 'inicio_sesion' "
            "AND tipo_documento IS NULL "
            "AND documento_id IS NULL "
            "AND etiqueta IS NULL"
            ") OR ("
            "accion <> 'inicio_sesion' "
            "AND tipo_documento IS NOT NULL "
            "AND documento_id IS NOT NULL "
            "AND etiqueta IS NOT NULL"
            ")",
            name="registro_accion_documento",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nombre_en_el_momento: Mapped[str] = mapped_column(String(255), nullable=False)
    accion: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    tipo_documento: Mapped[str | None] = mapped_column(String(32), nullable=True)
    documento_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etiqueta: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

En `app/models/__init__.py`, importar `RegistroAccion` y añadirlo a `__all__`.

`migrations/versions/0015_registro_accion.py`:

```python
"""Tabla inmutable del registro de acciones.

Revision ID: 0015_registro_accion
Revises: 0014_linea_pdf_manual
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_registro_accion"
down_revision: Union[str, Sequence[str], None] = "0014_linea_pdf_manual"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registro_accion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ocurrido_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("nombre_en_el_momento", sa.String(length=255), nullable=False),
        sa.Column("accion", sa.String(length=40), nullable=False),
        sa.Column("tipo_documento", sa.String(length=32), nullable=True),
        sa.Column("documento_id", sa.Integer(), nullable=True),
        sa.Column("etiqueta", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "accion IN ("
            "'confirmar_revision', 'confirmar_factura', "
            "'confirmar_importe_cliente', 'confirmar_importes_cliente', "
            "'confirmar_solo_gestion', 'borrar_proyecto', 'borrar_contrato', "
            "'borrar_factura', 'borrar_linea', 'inicio_sesion'"
            ")",
            name="registro_accion_codigo",
        ),
        sa.CheckConstraint(
            "("
            "accion = 'inicio_sesion' AND tipo_documento IS NULL "
            "AND documento_id IS NULL AND etiqueta IS NULL"
            ") OR ("
            "accion <> 'inicio_sesion' AND tipo_documento IS NOT NULL "
            "AND documento_id IS NOT NULL AND etiqueta IS NOT NULL"
            ")",
            name="registro_accion_documento",
        ),
    )
    op.create_index("ix_registro_accion_ocurrido_en", "registro_accion", ["ocurrido_en"])
    op.create_index("ix_registro_accion_usuario_id", "registro_accion", ["usuario_id"])
    op.create_index("ix_registro_accion_accion", "registro_accion", ["accion"])
    op.create_index(
        "ix_registro_accion_documento",
        "registro_accion",
        ["tipo_documento", "documento_id"],
    )
    op.execute(
        """
        CREATE FUNCTION registro_accion_rechazar_cambio()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'La fila del registro no se puede modificar';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER registro_accion_bloquear
        BEFORE UPDATE OR DELETE ON registro_accion
        FOR EACH ROW
        EXECUTE FUNCTION registro_accion_rechazar_cambio();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS registro_accion_bloquear ON registro_accion")
    op.execute("DROP FUNCTION IF EXISTS registro_accion_rechazar_cambio()")
    op.drop_table("registro_accion")
```

Run: `alembic upgrade head`

El correo del test puede chocar si se repite. Usar `uuid` en el email, igual que `tests/test_usuarios.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_registro.py::test_la_fila_no_se_puede_modificar -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/0015_registro_accion.py app/models/registro_accion.py app/models/__init__.py tests/test_registro.py
git commit -m "Añade la tabla inmutable del registro de acciones"
```

---

### Task 2: Escritor

**Files:**
- Create: `app/services/registro.py`
- Test: `tests/test_registro.py`

- [ ] **Step 1: Write the failing test**

Añadir a `tests/test_registro.py`:

```python
from app.services.registro import registrar


def test_registrar_copia_el_nombre_y_no_hace_commit(db: Session):
    usuario = Usuario(
        nombre="Ana Ejemplo",
        email="ana.copia.ejemplo@example.com",
        rol="direccion",
        password_hash="hash-ficticio",
    )
    db.add(usuario)
    db.commit()
    registrar(db, usuario, "inicio_sesion")
    db.rollback()
    assert db.query(RegistroAccion).count() == 0

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
        email="ana.codigo.ejemplo@example.com",
        rol="direccion",
        password_hash="hash-ficticio",
    )
    db.add(usuario)
    db.commit()
    with pytest.raises(ValueError, match="desconocida"):
        registrar(db, usuario, "mirar_pantalla")
```

Usar emails con `uuid` para no chocar con la fila de la tarea 1.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registro.py::test_registrar_copia_el_nombre_y_no_hace_commit tests/test_registro.py::test_registrar_rechaza_accion_desconocida -v`

Expected: FAIL con `ImportError` de `app.services.registro`.

- [ ] **Step 3: Write minimal implementation**

`app/services/registro.py`:

```python
"""Único escritor del registro. No hace commit."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models import Usuario
from app.models.registro_accion import ACCIONES, RegistroAccion

ZONA = ZoneInfo("Europe/Madrid")
PAGE_SIZE = 50

ETIQUETAS = {
    "confirmar_revision": "Confirmó la revisión",
    "confirmar_factura": "Confirmó la factura",
    "confirmar_importe_cliente": "Confirmó el importe de cliente",
    "confirmar_importes_cliente": "Confirmó los importes de cliente",
    "confirmar_solo_gestion": "Confirmó el apartado de solo gestión",
    "borrar_proyecto": "Borró el proyecto",
    "borrar_contrato": "Borró el contrato",
    "borrar_factura": "Borró la factura",
    "borrar_linea": "Borró la línea",
    "inicio_sesion": "Entró",
}


def registrar(
    db: Session,
    usuario: Usuario,
    accion: str,
    tipo_documento: str | None = None,
    documento_id: int | None = None,
    etiqueta: str | None = None,
) -> RegistroAccion:
    if accion not in ACCIONES:
        raise ValueError(f"Acción desconocida: {accion}")
    if accion == "inicio_sesion":
        if tipo_documento is not None or documento_id is not None or etiqueta is not None:
            raise ValueError("El inicio de sesión no lleva documento")
    else:
        if not tipo_documento or documento_id is None or not etiqueta or not etiqueta.strip():
            raise ValueError("La acción de obra exige documento y etiqueta")
        etiqueta = etiqueta.strip()[:255]
    fila = RegistroAccion(
        usuario_id=usuario.id,
        nombre_en_el_momento=usuario.nombre,
        accion=accion,
        tipo_documento=tipo_documento,
        documento_id=documento_id,
        etiqueta=etiqueta,
    )
    db.add(fila)
    return fila


def dia_hora(instante: datetime) -> str:
    return instante.astimezone(ZONA).strftime("%d/%m/%Y %H:%M")


def consultar(
    db: Session,
    *,
    page: int,
    usuario_id: int | None = None,
    accion: str | None = None,
    tipo_documento: str | None = None,
    dia: date | None = None,
) -> tuple[list[RegistroAccion], int]:
    consulta = db.query(RegistroAccion)
    if usuario_id is not None:
        consulta = consulta.filter(RegistroAccion.usuario_id == usuario_id)
    if accion:
        consulta = consulta.filter(RegistroAccion.accion == accion)
    if tipo_documento:
        consulta = consulta.filter(RegistroAccion.tipo_documento == tipo_documento)
    if dia is not None:
        inicio = datetime.combine(dia, time.min, tzinfo=ZONA)
        fin = inicio + timedelta(days=1)
        consulta = consulta.filter(
            RegistroAccion.ocurrido_en >= inicio,
            RegistroAccion.ocurrido_en < fin,
        )
    total = consulta.count()
    filas = (
        consulta.order_by(RegistroAccion.ocurrido_en.desc(), RegistroAccion.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )
    return filas, total
```

`ETIQUETAS` debe tener exactamente las claves de `ACCIONES`. Si falta una, el módulo no arranca:

```python
if set(ETIQUETAS) != set(ACCIONES):
    raise RuntimeError("El catálogo de etiquetas no coincide con las acciones")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_registro.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/registro.py tests/test_registro.py
git commit -m "Añade el escritor del registro sin commit propio"
```

---

### Task 3: Inicio de sesión

**Files:**
- Modify: `app/routers/auth.py`
- Modify: `tests/test_usuarios.py`
- Test: `tests/test_registro.py`

- [ ] **Step 1: Write the failing test**

En `tests/test_usuarios.py`, dentro de `test_login_deja_entrar_y_no_devuelve_la_clave`, después del `assert yo.status_code == 200` que ya existe, añadir:

```python
from app.models import RegistroAccion

filas = db.query(RegistroAccion).filter(RegistroAccion.accion == "inicio_sesion").all()
assert any(f.usuario_id == cuerpo["id"] for f in filas)
```

En `test_login_rechaza_clave_incorrecta`, después del 401:

```python
from app.models import RegistroAccion

assert (
    db.query(RegistroAccion)
    .filter(RegistroAccion.accion == "inicio_sesion")
    .count()
    == 0
)
```

El conteo a cero solo vale si la base del test no tiene filas previas de otras pruebas. Contar antes y después:

```python
antes = db.query(RegistroAccion).filter(RegistroAccion.accion == "inicio_sesion").count()
# ... post con clave mala ...
despues = db.query(RegistroAccion).filter(RegistroAccion.accion == "inicio_sesion").count()
assert despues == antes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_usuarios.py::test_login_deja_entrar_y_no_devuelve_la_clave tests/test_usuarios.py::test_login_rechaza_clave_incorrecta -v`

Expected: FAIL. El login correcto no deja fila.

- [ ] **Step 3: Write minimal implementation**

En `app/routers/auth.py`, tras un `autenticar` válido y antes de escribir la cookie:

```python
from app.services.registro import registrar

usuario = usuarios_svc.autenticar(db, str(datos.email), datos.password)
if usuario is None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="El correo o la clave no son válidos.",
    )
registrar(db, usuario, "inicio_sesion")
db.commit()
request.session["usuario_id"] = usuario.id
return usuario
```

`logout` no llama a `registrar`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_usuarios.py::test_login_deja_entrar_y_no_devuelve_la_clave tests/test_usuarios.py::test_login_rechaza_clave_incorrecta tests/test_usuarios.py::test_logout_cierra_la_sesion -v`

Expected: PASS. El logout no añade otra fila: en `test_logout_cierra_la_sesion` afirmar que el conteo de `inicio_sesion` de ese usuario no crece con el logout.

- [ ] **Step 5: Commit**

```bash
git add app/routers/auth.py tests/test_usuarios.py
git commit -m "Anota el inicio de sesión correcto y no el fallido"
```

---

### Task 4: Consulta

**Files:**
- Create: `app/schemas/registro.py`
- Create: `app/routers/registro.py`
- Modify: `app/main.py`
- Create: `tests/sesion.py`
- Test: `tests/test_registro.py`

- [ ] **Step 1: Write the failing test**

`tests/sesion.py`:

```python
"""Entra en la app de test con un usuario ficticio. No es un fixture global."""

import uuid

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Usuario

CLAVE = "clave-ficticia"


def entrar(client: TestClient, db: Session, rol: str = "direccion") -> Usuario:
    email = f"persona.{uuid.uuid4().hex[:8]}@example.com"
    usuario = Usuario(
        nombre="Persona Ejemplo",
        email=email,
        rol=rol,
        password_hash=PasswordHasher().hash(CLAVE),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    res = client.post("/auth/login", json={"email": email, "password": CLAVE})
    assert res.status_code == 200, res.text
    return usuario
```

En `tests/test_registro.py`, con el `client` fixture igual al de `tests/test_usuarios.py`:

```python
def test_la_consulta_solo_la_ven_direccion_y_superadministrador(client, db):
    from tests.sesion import entrar

    entrar(client, db, rol="jefe_obra")
    denegado = client.get("/registro")
    assert denegado.status_code == 403
    assert denegado.json()["detail"] == (
        "La consulta es para dirección y el superadministrador."
    )
```

Ese test deja la cookie de jefe de obra. El caso de dirección va en otro test con otro `TestClient`, o se hace logout antes:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registro.py::test_la_consulta_solo_la_ven_direccion_y_superadministrador tests/test_registro.py::test_direccion_lista_el_registro -v`

Expected: FAIL con 404. La ruta no existe.

- [ ] **Step 3: Write minimal implementation**

`app/schemas/registro.py`:

```python
"""Consulta del registro."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.registro_accion import ACCIONES


class RegistroItem(BaseModel):
    id: int
    ocurrido_en: datetime
    dia_hora: str
    nombre: str
    accion: str
    accion_etiqueta: str
    tipo_documento: str | None
    documento_id: int | None
    etiqueta: str | None


class RegistroPagina(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[RegistroItem]


class RegistroFiltro(BaseModel):
    page: int = Field(default=1, ge=1)
    usuario_id: int | None = None
    accion: str | None = None
    tipo_documento: str | None = None
    dia: str | None = None

    @field_validator("accion")
    @classmethod
    def accion_conocida(cls, valor: str | None) -> str | None:
        if valor is not None and valor not in ACCIONES:
            raise ValueError("Acción desconocida")
        return valor

    @field_validator("tipo_documento")
    @classmethod
    def tipo_conocido(cls, valor: str | None) -> str | None:
        if valor is not None and valor not in {
            "presupuesto",
            "contrato",
            "factura",
            "proyecto",
            "tarea",
        }:
            raise ValueError("Tipo de documento desconocido")
        return valor
```

`app/routers/registro.py`:

```python
"""Consulta de solo lectura del registro."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_actual
from app.models import Usuario
from app.schemas.registro import RegistroFiltro, RegistroItem, RegistroPagina
from app.services.registro import ETIQUETAS, PAGE_SIZE, consultar, dia_hora

router = APIRouter(tags=["registro"])

ROLES_CONSULTA = {"direccion", "superadministrador"}


@router.get("/registro", response_model=RegistroPagina)
def listar_registro(
    page: int = Query(default=1, ge=1),
    usuario_id: int | None = None,
    accion: str | None = None,
    tipo_documento: str | None = None,
    dia: date | None = None,
    actual: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> RegistroPagina:
    if actual.rol not in ROLES_CONSULTA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La consulta es para dirección y el superadministrador.",
        )
    RegistroFiltro(
        page=page,
        usuario_id=usuario_id,
        accion=accion,
        tipo_documento=tipo_documento,
        dia=dia.isoformat() if dia else None,
    )
    filas, total = consultar(
        db,
        page=page,
        usuario_id=usuario_id,
        accion=accion,
        tipo_documento=tipo_documento,
        dia=dia,
    )
    return RegistroPagina(
        page=page,
        page_size=PAGE_SIZE,
        total=total,
        items=[
            RegistroItem(
                id=fila.id,
                ocurrido_en=fila.ocurrido_en,
                dia_hora=dia_hora(fila.ocurrido_en),
                nombre=fila.nombre_en_el_momento,
                accion=fila.accion,
                accion_etiqueta=ETIQUETAS[fila.accion],
                tipo_documento=fila.tipo_documento,
                documento_id=fila.documento_id,
                etiqueta=fila.etiqueta,
            )
            for fila in filas
        ],
    )
```

En `app/main.py`, `include_router` del registro antes del `mount` de estáticos.

No crear `POST`, `PATCH` ni `DELETE`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_registro.py::test_la_consulta_solo_la_ven_direccion_y_superadministrador tests/test_registro.py::test_direccion_lista_el_registro -v`

Expected: PASS

Añadir en el mismo archivo el caso `rol="administracion"` con 403 y `rol="superadministrador"` con 200. Misma aserción, otro `TestClient` por test para no reutilizar la cookie.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/registro.py app/routers/registro.py app/main.py tests/sesion.py tests/test_registro.py
git commit -m "Expone la consulta del registro solo a dirección y superadministrador"
```

---

### Task 5: Confirmar revisión

**Files:**
- Modify: `app/routers/revisiones.py:38-51`
- Modify: `app/services/revision.py:131-195`
- Modify: `tests/test_revision.py`
- Test: `tests/test_registro.py`

- [ ] **Step 1: Write the failing test**

En `tests/test_revision.py` el `POST /revisiones/confirmar` debe ir con sesión. Añadir fixture `db` como en `tests/test_usuarios.py` y, antes del primer `client.post("/revisiones/confirmar"`:

```python
from tests.sesion import entrar

entrar(client, db, rol="direccion")
```

El 422 también pasa por la ruta protegida. Sin sesión el test recibiría 401 y dejaría de comprobar el 422.

En `tests/test_registro.py`, después de un confirmar correcto de `test_flujo_revision_presupuesto` no hace falta duplicar el flujo. Contar filas en `test_revision.py` al final del caso que ya confirma:

```python
from app.models import RegistroAccion

filas = (
    db.query(RegistroAccion)
    .filter(
        RegistroAccion.accion == "confirmar_revision",
        RegistroAccion.documento_id == doc_id,
    )
    .all()
)
assert len(filas) == 1
assert filas[0].tipo_documento == "presupuesto"
assert "presupuesto" in filas[0].etiqueta
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_revision.py::test_flujo_revision_presupuesto -v`

Expected: FAIL. 401, o 200 sin fila.

- [ ] **Step 3: Write minimal implementation**

`app/routers/revisiones.py`:

```python
from app.deps import usuario_actual
from app.models import Usuario

@router.post("/confirmar", response_model=ConfirmarRevisionOut)
def confirmar_revision(
    payload: ConfirmarRevisionIn,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ConfirmarRevisionOut:
    try:
        return revision_svc.confirmar_revision(db, payload, actual)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
```

En `confirmar_revision`, justo antes de `db.commit()`:

```python
from app.services.registro import registrar

proyecto = db.get(Proyecto, doc.proyecto_id)
# ... el bloque que ya pasa el proyecto a en_curso se queda ...
registrar(
    db,
    usuario,
    "confirmar_revision",
    tipo_documento=payload.tipo,
    documento_id=payload.documento_id,
    etiqueta=f"{proyecto.nombre} · {payload.tipo}",
)
db.commit()
```

La firma pasa a `confirmar_revision(db, payload, usuario)`. Un 422 anterior no llega a `registrar`. Una sola llamada aunque `payload.tareas` tenga muchas filas.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_revision.py::test_flujo_revision_presupuesto -v`

Expected: PASS. Una fila, no una por tarea.

- [ ] **Step 5: Commit**

```bash
git add app/routers/revisiones.py app/services/revision.py tests/test_revision.py
git commit -m "Anota una fila al confirmar la revisión"
```

---

### Task 6: Factura

**Files:**
- Modify: `app/routers/facturas.py:101-128`
- Modify: `app/services/facturas.py:167-211` y `253-270`
- Modify: `tests/test_facturas.py`

- [ ] **Step 1: Write the failing test**

En cada test de `tests/test_facturas.py` que haga `POST /facturas/{id}/confirmar` o `DELETE /facturas/{id}`, antes de esa llamada:

```python
from tests.sesion import entrar

entrar(client, db, rol="administracion")
```

Al final de un test que confirma y de uno que borra, afirmar:

```python
from app.models import RegistroAccion

confirmadas = (
    db.query(RegistroAccion)
    .filter(RegistroAccion.accion == "confirmar_factura", RegistroAccion.documento_id == factura_id)
    .all()
)
assert len(confirmadas) == 1
assert "·" in confirmadas[0].etiqueta
```

Tras el delete, la fila de `borrar_factura` sigue y su `etiqueta` contiene el número que tenía la factura. El `GET` de la factura ya no existe; la fila sí.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_facturas.py -v`

Expected: FAIL con 401 en confirmar o borrar.

- [ ] **Step 3: Write minimal implementation**

Las dos rutas reciben `actual: Usuario = Depends(usuario_actual)` y lo pasan al servicio.

`confirmar_factura(db, factura_id, payload, usuario)`, antes de `db.commit()`:

```python
proyecto = db.get(Proyecto, factura.proyecto_id)
registrar(
    db,
    usuario,
    "confirmar_factura",
    tipo_documento="factura",
    documento_id=factura.id,
    etiqueta=f"{payload.numero} · {proyecto.nombre}",
)
```

`borrar_factura(db, factura_id, usuario)`: leer número y nombre del proyecto antes del `delete`. Llamar a `registrar` con `borrar_factura` y esa etiqueta. Después el `delete` y el `commit` que ya existen. `almacen_svc.borrar_fichero` sigue después del commit y no escribe otra fila.

Importar, leer y enlazar contrato no reciben usuario y no registran.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_facturas.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/facturas.py app/services/facturas.py tests/test_facturas.py
git commit -m "Anota confirmar y borrar una factura"
```

---

### Task 7: Importe de cliente y solo gestión

**Files:**
- Modify: `app/routers/proyectos.py` en `confirmar_importe_cliente`, `confirmar_importes_cliente`, `confirmar_solo_gestion`
- Modify: `app/services/presupuesto_excel.py:265-305`
- Modify: `app/services/solo_gestion.py:89-104`
- Modify: `tests/test_presupuesto_excel.py`, `tests/test_linea_pdf_manual.py`, `tests/test_solo_gestion.py`

- [ ] **Step 1: Write the failing test**

Antes de cada `POST` a `importe-cliente` o `confirmar-gestion` en esos tres archivos:

```python
from tests.sesion import entrar

entrar(client, db, rol="direccion")
```

No entrar antes de un `DELETE` de `lineas-pdf` ni de marcar o desmarcar solo gestión.

Tras un `POST` de un solo apartado, una fila `confirmar_importe_cliente` con `tipo_documento == "tarea"`. Tras un `POST` con varias tareas, una fila `confirmar_importes_cliente` con `tipo_documento == "proyecto"`. Tras confirmar solo gestión, una fila `confirmar_solo_gestion`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_presupuesto_excel.py tests/test_linea_pdf_manual.py tests/test_solo_gestion.py -v`

Expected: FAIL con 401 en las rutas que ahora exigen sesión.

- [ ] **Step 3: Write minimal implementation**

Las tres funciones del router dependen de `usuario_actual` y pasan `actual`.

`confirmar_importes_cliente(..., usuario, registrar_fila: bool = True)`. Justo antes de su `db.commit()`, si `registrar_fila`:

```python
proyecto = db.get(Proyecto, proyecto_id)
if len(tareas) == 1:
    tarea = tareas[0]
    registrar(
        db,
        usuario,
        "confirmar_importe_cliente",
        tipo_documento="tarea",
        documento_id=tarea.id,
        etiqueta=f"{tarea.codigo} · {tarea.descripcion} · {proyecto.nombre}",
    )
else:
    registrar(
        db,
        usuario,
        "confirmar_importes_cliente",
        tipo_documento="proyecto",
        documento_id=proyecto.id,
        etiqueta=proyecto.nombre,
    )
```

`confirmar_importe_cliente` llama así, y no registra por su cuenta:

```python
salida = confirmar_importes_cliente(
    db, proyecto_id, [tarea_id], importe, usuario=usuario, registrar_fila=True
)
```

`solo_gestion.confirmar(db, proyecto_id, tarea_id, usuario)`, antes del `commit` del camino que cambia el estado, y también antes del `return` del camino que ya estaba confirmada (si no hay commit, hacer `registrar` y `db.commit()` para que el gesto de pulsar quede). Una fila por llamada que termina bien.

`marcar` y `desmarcar` no cambian.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_presupuesto_excel.py tests/test_linea_pdf_manual.py tests/test_solo_gestion.py -v`

Expected: PASS. Un gesto, una fila.

- [ ] **Step 5: Commit**

```bash
git add app/routers/proyectos.py app/services/presupuesto_excel.py app/services/solo_gestion.py tests/test_presupuesto_excel.py tests/test_linea_pdf_manual.py tests/test_solo_gestion.py
git commit -m "Anota el importe de cliente y la confirmación de solo gestión"
```

---

### Task 8: Borrados de obra

**Files:**
- Modify: `app/routers/proyectos.py` en `borrar_proyecto`, `borrar_linea`, `borrar_contrato`
- Modify: `app/services/proyectos.py:435` y `516`
- Modify: `app/services/lineas.py:80`
- Modify: `tests/test_listar_proyectos.py`, `tests/test_lineas_presupuesto.py`, `tests/test_borrar_contrato.py`

- [ ] **Step 1: Write the failing test**

Antes de cada `DELETE /proyectos/{id}`, `DELETE .../lineas/{tarea_id}` y `DELETE .../contratos/{contrato_id}`, incluido un delete que solo limpia:

```python
from tests.sesion import entrar

entrar(client, db, rol="direccion")
```

Afirmar, con los datos leídos antes del delete:

```python
fila = (
    db.query(RegistroAccion)
    .filter(RegistroAccion.accion == "borrar_proyecto", RegistroAccion.documento_id == proyecto_id)
    .one()
)
assert proyecto.nombre in fila.etiqueta
assert db.get(Proyecto, proyecto_id) is None
```

El mismo patrón para contrato (`referencia_presupuesto` dentro de la etiqueta si no es nula) y para línea (código de la tarea dentro de la etiqueta).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_listar_proyectos.py tests/test_lineas_presupuesto.py tests/test_borrar_contrato.py -v`

Expected: FAIL con 401.

- [ ] **Step 3: Write minimal implementation**

Cada ruta protegida recibe `usuario_actual`. El servicio copia la etiqueta en variables locales antes del primer `DELETE` o `text("DELETE ...")`.

`borrar_proyecto`: etiqueta `nombre` y, si `codigo` no es nulo, `f"{nombre} · {codigo}"`. `registrar` con tipo `proyecto` antes de `db.commit()`. El fichero de almacén sigue después del commit y no registra.

`borrar_contrato`: etiqueta `proyecto.nombre` y, si hay `referencia_presupuesto`, `f"{proyecto.nombre} · {referencia_presupuesto}"`. Tipo `contrato`. Antes del commit.

`borrar_linea`: etiqueta `f"{tarea.codigo} · {tarea.descripcion} · {proyecto.nombre}"`. Tipo `tarea`. Antes del commit. Si salta `LineaEnlazada`, no hay fila.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_listar_proyectos.py tests/test_lineas_presupuesto.py tests/test_borrar_contrato.py -v`

Expected: PASS. La fila sigue cuando el proyecto, el contrato o la línea ya no están.

- [ ] **Step 5: Commit**

```bash
git add app/routers/proyectos.py app/services/proyectos.py app/services/lineas.py tests/test_listar_proyectos.py tests/test_lineas_presupuesto.py tests/test_borrar_contrato.py
git commit -m "Anota los borrados de proyecto, contrato y línea"
```

---

### Task 9: Rol y pantalla

**Files:**
- Modify: `app/schemas/usuario.py:6-16`
- Modify: `app/static/usuarios.html:103-107` y el `<nav>`
- Modify: `app/static/js/usuarios.js:3-7`
- Modify: `app/static/index.html:34-37`
- Create: `app/static/registro.html`
- Create: `app/static/js/registro.js`
- Modify: `docs/readme.md`
- Test: `tests/test_usuarios.py`

- [ ] **Step 1: Write the failing test**

En `tests/test_usuarios.py::test_rol_invalido_y_email_duplicado` el rol inválido sigue en 422. Añadir:

```python
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
```

Y que `GET /registro.html` con sesión responde 200 (el middleware ya deja pasar cualquier sesión a un HTML).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_usuarios.py::test_rol_invalido_y_email_duplicado -v`

Expected: FAIL. El rol nuevo no está en `ROLES`.

- [ ] **Step 3: Write minimal implementation**

`ROLES = ("jefe_obra", "administracion", "direccion", "superadministrador")`.

Mensaje de `_rol_conocido`: «El rol tiene que ser jefe de obra, administración, dirección o superadministrador.»

En `app/static/js/usuarios.js`:

```javascript
const roles = {
  jefe_obra: "Jefe de obra",
  administracion: "Administración",
  direccion: "Dirección",
  superadministrador: "Superadministrador",
};
```

En el `<select>` de `usuarios.html`, otra opción:

```html
<option value="superadministrador">Superadministrador</option>
```

En el `<nav>` de `index.html` y de `usuarios.html`, después del enlace de Usuarios:

```html
<a class="nav-enlace" href="/registro.html" title="Registro"
  x-show="yo && (yo.rol === 'direccion' || yo.rol === 'superadministrador')">
  <span class="nav-marca" aria-hidden="true">R</span>
  <span class="nav-etiqueta">Registro</span>
</a>
```

`app/static/registro.html` copia la cáscara de `usuarios.html` (css, Alpine, `sesion.js`, menú). El cuerpo no tiene botones de editar ni de borrar. Incluye `registro.js`.

`app/static/js/registro.js` parte de `sesionLateral()`, llama a `cargarYo()` y pide `GET /registro?page=1`. Pinta `dia_hora`, `nombre`, `accion_etiqueta` y `etiqueta`. Si la respuesta es 403, muestra `detail` y no la tabla. Si `items` está vacío, muestra «No hay filas.» Cambiar el filtro de acción, tipo, `usuario_id` o día vuelve a `page=1`. No formatea la hora en el navegador.

En `docs/readme.md`, en la entidad USUARIO, añadir `superadministrador` al texto del rol. Después de esa entidad, un párrafo `REGISTRO_ACCION` con las columnas de la tarea 1, sin importes y sin clave ajena, y la ruta `GET /registro`. No escribir una matriz de permisos para los otros tres roles.

La semilla sigue en `direccion`. No hay comprobación nueva en `PATCH /usuarios/{id}`. Quién puede asignar el rol sigue sin estar en el readme: no lo cierres en código. [VERIFICAR]

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_usuarios.py tests/test_registro.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/usuario.py app/static/usuarios.html app/static/js/usuarios.js app/static/index.html app/static/registro.html app/static/js/registro.js docs/readme.md tests/test_usuarios.py
git commit -m "Añade el rol y la pantalla de consulta del registro"
```

---

### Task 10: Lo que no debe escribir fila

**Files:**
- Test: `tests/test_registro.py`
- Modify: ninguno de ingesta, si el test pasa sin cambios

- [ ] **Step 1: Write the failing test**

```python
def test_importar_presupuesto_no_escribe_fila(client, db):
    from pathlib import Path
    from app.models import RegistroAccion

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
```

Este POST no exige sesión. No llamar a `entrar`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registro.py::test_importar_presupuesto_no_escribe_fila -v`

Expected: PASS si ninguna tarea anterior enganchó la ingesta. Si FAIL, hay un `registrar` de más: quitarlo. No añadir un gancho del ORM para «arreglarlo».

- [ ] **Step 3: Write minimal implementation**

Ninguna, si el test pasa. Confirmar leyendo que `app/services/ingesta.py`, `app/services/extraccion.py` y el prorrateo no importan `registrar`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_registro.py tests/test_importar_presupuesto.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_registro.py
git commit -m "Fija que importar un presupuesto no escribe en el registro"
```

Si no hay cambio de código porque el test ya pasaba en la tarea 9, no hagas un commit vacío. Deja el test dentro del commit de la tarea 9 si aún no se ha hecho, o enmienda solo si el commit de la tarea 9 es tuyo y no se ha empujado. Si ya está empujado, haz este commit con el test.

---

## Self-review

- Cada gesto del diseño tiene tarea: revisión (5), factura (6), importe y solo gestión (7), borrados (8), login (3), consulta (4), rol y pantalla (9).
- La ingesta no registra (10). El estado de obra y el avance físico no tienen tarea: el diseño los deja fuera hasta que exista la pantalla.
- No hay columnas de importe.
- No hay clave ajena.
- El disparador está en la tarea 1. El `downgrade` tira la tabla. No hay purga.
- `Europe/Madrid` está en `consultar` y `dia_hora`.
- Quién asigna el rol no se inventa: sigue pudiendo hacerlo quien ya hace `PATCH /usuarios/{id}`.
