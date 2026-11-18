# Inversión del sujeto pasivo — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Marcar una obra con la carta del promotor para que sus importes se lean sin IVA y ninguna factura de esa obra se confirme si el IVA no es cero.

**Architecture:** La marca y la ruta de la carta viven en `proyecto`. Un servicio nuevo guarda el PDF, devuelve a pendiente las facturas confirmadas con IVA y rechaza la confirmación posterior. El control no cambia de fórmula. Las pantallas solo añaden el texto y el bloqueo.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, HTML + Alpine.js, pytest.

**Spec:** `docs/superpowers/specs/2026-11-18-inversion-sujeto-pasivo-design.md`

La carta real no se usa. Los tests llevan un PDF mínimo que empieza por `%PDF` y obras ficticias.

## Ficheros

- Crear: `migrations/versions/0016_inversion_sujeto_pasivo.py` — columnas y check del registro.
- Modificar: `app/models/proyecto.py` — las tres columnas.
- Modificar: `app/models/registro_accion.py`, `app/services/registro.py`, `app/static/js/registro.js` — `marcar_isp` y `quitar_isp`.
- Modificar: `app/services/almacen.py` — tipo `carta_isp`.
- Crear: `app/services/sujeto_pasivo.py` — marcar, quitar, aviso.
- Modificar: `app/schemas/proyecto.py`, `app/schemas/factura.py`, `app/schemas/control_economico.py` — campos de salida.
- Modificar: `app/services/proyectos.py` — rellenar el detalle.
- Modificar: `app/services/facturas.py` — aviso y rechazo al confirmar.
- Modificar: `app/services/economico.py` — indicador, mismas cifras.
- Modificar: `app/routers/proyectos.py` — tres endpoints.
- Modificar: `app/static/index.html`, `app/static/js/obras.js` — ficha.
- Modificar: `app/static/facturas.html`, `app/static/js/facturas.js`, `app/static/control.html`, `app/static/proyecto.html`, `app/static/js/proyecto.js`.
- Modificar: `docs/readme.md`.
- Crear: `tests/test_sujeto_pasivo.py`.

---

### Task 1: Columnas y catálogo del registro

**Files:**
- Create: `migrations/versions/0016_inversion_sujeto_pasivo.py`
- Modify: `app/models/proyecto.py`
- Modify: `app/models/registro_accion.py`
- Modify: `app/services/registro.py`
- Modify: `app/static/js/registro.js`
- Test: `tests/test_sujeto_pasivo.py`

- [ ] **Step 1: Write the failing test**

Crear `tests/test_sujeto_pasivo.py`:

```python
"""Inversión del sujeto pasivo. Obras y PDF ficticios, sin datos reales."""

from pathlib import Path

from app.models.registro_accion import ACCIONES
from app.services.registro import ETIQUETAS


def test_el_catalogo_conoce_la_marca():
    assert "marcar_isp" in ACCIONES
    assert "quitar_isp" in ACCIONES
    assert ETIQUETAS["marcar_isp"] == "Marcó la inversión del sujeto pasivo"
    assert ETIQUETAS["quitar_isp"] == "Quitó la inversión del sujeto pasivo"


def test_la_pantalla_de_registro_lista_la_marca():
    texto = Path("app/static/js/registro.js").read_text(encoding="utf-8")
    assert '["marcar_isp", "Marcó la inversión del sujeto pasivo"]' in texto
    assert '["quitar_isp", "Quitó la inversión del sujeto pasivo"]' in texto
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_el_catalogo_conoce_la_marca tests/test_sujeto_pasivo.py::test_la_pantalla_de_registro_lista_la_marca -v`

Expected: FAIL. `marcar_isp` no está en `ACCIONES` o no está en `registro.js`.

- [ ] **Step 3: Write minimal implementation**

En `app/models/registro_accion.py`, añade al final de `ACCIONES`, antes del cierre:

```python
    "marcar_isp",
    "quitar_isp",
```

En `app/services/registro.py`, añade a `ETIQUETAS`:

```python
    "marcar_isp": "Marcó la inversión del sujeto pasivo",
    "quitar_isp": "Quitó la inversión del sujeto pasivo",
```

En `app/static/js/registro.js`, añade antes de `["inicio_sesion", "Entró"]`:

```javascript
    ["marcar_isp", "Marcó la inversión del sujeto pasivo"],
    ["quitar_isp", "Quitó la inversión del sujeto pasivo"],
```

En `app/models/proyecto.py`, cambia el import de SQLAlchemy a:

```python
from sqlalchemy import Boolean, Date, DateTime, String, func
```

Después de `created_at`, añade:

```python
    # La carta del promotor la adjunta una persona. No la lee el modelo.
    inversion_sujeto_pasivo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    ruta_carta_isp: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    fichero_carta_isp: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

Crea `migrations/versions/0016_inversion_sujeto_pasivo.py`:

```python
"""Marca de inversión del sujeto pasivo en la obra.

Revision ID: 0016_inversion_sujeto_pasivo
Revises: 0015_registro_accion
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_inversion_sujeto_pasivo"
down_revision: Union[str, Sequence[str], None] = "0015_registro_accion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CODIGOS = (
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
    "marcar_isp",
    "quitar_isp",
)

_CODIGOS_ANTERIORES = _CODIGOS[:-2]


def upgrade() -> None:
    op.add_column(
        "proyecto",
        sa.Column(
            "inversion_sujeto_pasivo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("proyecto", sa.Column("ruta_carta_isp", sa.String(1024), nullable=True))
    op.add_column("proyecto", sa.Column("fichero_carta_isp", sa.String(512), nullable=True))
    op.drop_constraint("registro_accion_codigo", "registro_accion", type_="check")
    op.create_check_constraint(
        "registro_accion_codigo",
        "registro_accion",
        "accion IN (" + ", ".join(f"'{codigo}'" for codigo in _CODIGOS) + ")",
    )


def downgrade() -> None:
    op.drop_constraint("registro_accion_codigo", "registro_accion", type_="check")
    op.create_check_constraint(
        "registro_accion_codigo",
        "registro_accion",
        "accion IN (" + ", ".join(f"'{codigo}'" for codigo in _CODIGOS_ANTERIORES) + ")",
    )
    op.drop_column("proyecto", "fichero_carta_isp")
    op.drop_column("proyecto", "ruta_carta_isp")
    op.drop_column("proyecto", "inversion_sujeto_pasivo")
```

El downgrade del check falla si ya hay filas `marcar_isp` o `quitar_isp`: el disparador impide borrarlas. No intentes borrarlas.

- [ ] **Step 4: Apply the migration and run the tests**

Run: `python -m alembic upgrade head`

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_el_catalogo_conoce_la_marca tests/test_sujeto_pasivo.py::test_la_pantalla_de_registro_lista_la_marca -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/0016_inversion_sujeto_pasivo.py app/models/proyecto.py app/models/registro_accion.py app/services/registro.py app/static/js/registro.js tests/test_sujeto_pasivo.py
git commit -m "Añade la marca de inversión del sujeto pasivo en la obra."
```

---

### Task 2: El almacén acepta la carta

**Files:**
- Modify: `app/services/almacen.py`
- Test: `tests/test_sujeto_pasivo.py`

- [ ] **Step 1: Write the failing test**

Añade a `tests/test_sujeto_pasivo.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_el_almacen_guarda_la_carta -v`

Expected: FAIL. `ValueError` con `Tipo de documento no válido: carta_isp`.

- [ ] **Step 3: Write minimal implementation**

En `app/services/almacen.py`, cambia:

```python
_TIPOS = frozenset({"presupuesto", "contrato", "factura", "carta_isp"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_el_almacen_guarda_la_carta -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/almacen.py tests/test_sujeto_pasivo.py
git commit -m "Deja guardar la carta de inversión del sujeto pasivo junto a la obra."
```

---

### Task 3: Marcar, sustituir, quitar y descargar

**Files:**
- Create: `app/services/sujeto_pasivo.py`
- Modify: `app/schemas/proyecto.py`
- Modify: `app/services/proyectos.py`
- Modify: `app/routers/proyectos.py`
- Test: `tests/test_sujeto_pasivo.py`

- [ ] **Step 1: Write the failing test**

Añade a `tests/test_sujeto_pasivo.py` estos helpers y el primer test. El resto de tests de esta tarea van en el step 6, cuando marcar ya responde.

```python
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Contratista, Factura, Proyecto, RegistroAccion
from tests.sesion import entrar

PDF = b"%PDF-1.4\n%carta ficticia\n%%EOF\n"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_marcar_guarda_la_carta_y_el_registro -v`

Expected: FAIL. 404 o 405: la ruta no existe.

- [ ] **Step 3: Write minimal implementation**

Crea `app/services/sujeto_pasivo.py`:

```python
"""Carta del promotor y regla de IVA cero. No lee el PDF."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Factura, Proyecto, Usuario
from app.schemas.proyecto import ProyectoDetalleOut
from app.services import almacen as almacen_svc
from app.services import proyectos as proyectos_svc
from app.services.registro import registrar

AVISO_ISP = "La obra está en inversión del sujeto pasivo. El IVA tiene que ser 0."


def aviso_de(marcada: bool, iva) -> str | None:
    if marcada and iva != 0:
        return AVISO_ISP
    return None


def _exigir_pdf(nombre: str, contenido: bytes) -> None:
    if not contenido or not nombre.lower().endswith(".pdf") or not contenido.startswith(b"%PDF"):
        raise ValueError("La carta tiene que ser un PDF")


def marcar(
    db: Session,
    proyecto_id: int,
    usuario: Usuario,
    nombre: str,
    contenido: bytes,
) -> ProyectoDetalleOut:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    _exigir_pdf(nombre, contenido)
    if proyecto.ruta_carta_isp:
        almacen_svc.borrar_fichero(proyecto.ruta_carta_isp)
    proyecto.ruta_carta_isp = almacen_svc.guardar(
        proyecto_id, "carta_isp", proyecto_id, nombre, contenido
    )
    proyecto.fichero_carta_isp = Path(nombre).name[:512]
    proyecto.inversion_sujeto_pasivo = True
    db.query(Factura).filter(
        Factura.proyecto_id == proyecto_id,
        Factura.estado_revision == "confirmada",
        Factura.iva != 0,
    ).update({Factura.estado_revision: "pendiente"}, synchronize_session="fetch")
    registrar(
        db,
        usuario,
        "marcar_isp",
        tipo_documento="proyecto",
        documento_id=proyecto_id,
        etiqueta=proyecto.nombre,
    )
    db.commit()
    return proyectos_svc.obtener_proyecto(db, proyecto_id)


def quitar(db: Session, proyecto_id: int, usuario: Usuario) -> None:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    if proyecto.inversion_sujeto_pasivo or proyecto.ruta_carta_isp:
        almacen_svc.borrar_fichero(proyecto.ruta_carta_isp)
        proyecto.inversion_sujeto_pasivo = False
        proyecto.ruta_carta_isp = None
        proyecto.fichero_carta_isp = None
        registrar(
            db,
            usuario,
            "quitar_isp",
            tipo_documento="proyecto",
            documento_id=proyecto_id,
            etiqueta=proyecto.nombre,
        )
    db.commit()


def carta(db: Session, proyecto_id: int) -> tuple[str, str]:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None or not proyecto.ruta_carta_isp:
        raise ValueError(f"Carta {proyecto_id} no encontrado")
    return proyecto.ruta_carta_isp, proyecto.fichero_carta_isp or "carta.pdf"
```

El mensaje de `carta` lleva «no encontrado» para que el router de ficheros, si se reutiliza el patrón, responda 404. Este endpoint responde 404 él mismo.

En `app/schemas/proyecto.py`, dentro de `ProyectoDetalleOut`, después de `contraste_cliente`:

```python
    inversion_sujeto_pasivo: bool = False
    tiene_carta_isp: bool = False
    fichero_carta_isp: str | None = None
```

En `app/services/proyectos.py`, en el `return ProyectoDetalleOut(` de `obtener_proyecto`, añade:

```python
        inversion_sujeto_pasivo=bool(proyecto.inversion_sujeto_pasivo),
        tiene_carta_isp=bool(proyecto.ruta_carta_isp),
        fichero_carta_isp=proyecto.fichero_carta_isp,
```

En `app/routers/proyectos.py`, importa el servicio:

```python
from app.services import sujeto_pasivo as sujeto_pasivo_svc
```

Añade los endpoints antes de `descargar_presupuesto`:

```python
@router.post(
    "/proyectos/{proyecto_id}/inversion-sujeto-pasivo",
    response_model=ProyectoDetalleOut,
)
async def marcar_inversion_sujeto_pasivo(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ProyectoDetalleOut:
    contenido = await fichero.read()
    try:
        return sujeto_pasivo_svc.marcar(
            db,
            proyecto_id,
            actual,
            fichero.filename or "",
            contenido,
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.delete(
    "/proyectos/{proyecto_id}/inversion-sujeto-pasivo",
    status_code=status.HTTP_204_NO_CONTENT,
)
def quitar_inversion_sujeto_pasivo(
    proyecto_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> Response:
    try:
        sujeto_pasivo_svc.quitar(db, proyecto_id, actual)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/proyectos/{proyecto_id}/carta-isp")
def descargar_carta_isp(
    proyecto_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        ruta, nombre = sujeto_pasivo_svc.carta(db, proyecto_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return _responder_fichero(ruta, nombre)
```

`Response` ya está importado en el router. `FileResponse` también.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_marcar_guarda_la_carta_y_el_registro -v`

Expected: PASS

- [ ] **Step 5: Write the rest of the failing tests**

Añade a `tests/test_sujeto_pasivo.py`:

```python
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
```

`_factura` usa el número `F-ISP-1` para el IVA distinto de cero y `F-ISP-0` para el cero. En el test de democión se reescriben dos números antes del commit para no chocar. Si el contratista ya existe, no se duplica.

- [ ] **Step 6: Run the new tests**

Run: `python -m pytest tests/test_sujeto_pasivo.py -v`

Expected: PASS. Si `test_marcar_devuelve_a_pendiente_solo_el_iva_distinto_de_cero` choca por el número de factura, deja los tres números distintos como ya hace el test (`F-ISP-1` sale del helper solo para `con_iva`; los otros dos se reasignan). No hace falta un número único global: la tabla no exige número único.

- [ ] **Step 7: Commit**

```bash
git add app/services/sujeto_pasivo.py app/schemas/proyecto.py app/services/proyectos.py app/routers/proyectos.py tests/test_sujeto_pasivo.py
git commit -m "Permite marcar una obra con la carta y devolver a revisión las facturas con IVA."
```

---

### Task 4: Confirmar solo con IVA cero y avisar en el listado

**Files:**
- Modify: `app/schemas/factura.py`
- Modify: `app/services/facturas.py`
- Test: `tests/test_sujeto_pasivo.py`

- [ ] **Step 1: Write the failing test**

Añade a `tests/test_sujeto_pasivo.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_confirmar_en_obra_marcada_exige_iva_cero tests/test_sujeto_pasivo.py::test_el_listado_avisa_solo_si_hay_iva -v`

Expected: FAIL. La factura con IVA 21 se confirma, o `aviso_isp` no está en el JSON.

- [ ] **Step 3: Write minimal implementation**

En `app/schemas/factura.py`, en `FacturaResumenOut`, después de `fichero_origen`:

```python
    aviso_isp: str | None = None
```

En `FacturaRevisionOut`, después de `contratos_candidatos`:

```python
    inversion_sujeto_pasivo: bool = False
```

En `app/services/facturas.py`, importa:

```python
from app.services.sujeto_pasivo import AVISO_ISP, aviso_de
```

En `listar_facturas` y en `obtener_factura`, añade `joinedload(Factura.proyecto)` al `options`.

En `_a_resumen`, añade el argumento del aviso. La función queda así en la parte del return (el resto de campos no cambia):

```python
def _a_resumen(factura: Factura) -> FacturaResumenOut:
    marcada = bool(factura.proyecto and factura.proyecto.inversion_sujeto_pasivo)
    return FacturaResumenOut(
        id=factura.id,
        proyecto_id=factura.proyecto_id,
        numero=factura.numero,
        fecha_emision=factura.fecha_emision,
        contratista_nombre=(
            factura.contratista.nombre if factura.contratista else "—"
        ),
        contratista_nif=factura.contratista.nif if factura.contratista else "—",
        contrato_id=factura.contrato_id,
        contrato_etiqueta=_etiqueta_contrato(factura),
        total=factura.total,
        tipo=factura.tipo,
        es_escaneada=factura.es_escaneada,
        estado_revision=factura.estado_revision,
        tiene_fichero=bool(factura.ruta_almacen),
        fichero_origen=factura.fichero_origen,
        aviso_isp=aviso_de(marcada, factura.iva),
    )
```

En `obtener_factura`, al construir `FacturaRevisionOut`, añade:

```python
        inversion_sujeto_pasivo=bool(
            factura.proyecto and factura.proyecto.inversion_sujeto_pasivo
        ),
```

En `confirmar_factura`, justo después de comprobar que la factura tiene proyecto y antes de tocar `factura.numero`:

```python
    proyecto = db.get(Proyecto, factura.proyecto_id)
    if proyecto is not None and proyecto.inversion_sujeto_pasivo and payload.iva != 0:
        raise ValueError(AVISO_ISP)
```

`Proyecto` ya está importado al principio de `app/services/facturas.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sujeto_pasivo.py tests/test_facturas.py -v`

Expected: PASS. `test_facturas.py` sigue confirmando facturas de obras sin marca.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/factura.py app/services/facturas.py tests/test_sujeto_pasivo.py
git commit -m "Impide confirmar con IVA una factura de una obra marcada."
```

---

### Task 5: El control lleva el indicador y las mismas cifras

**Files:**
- Modify: `app/schemas/control_economico.py`
- Modify: `app/services/economico.py`
- Test: `tests/test_sujeto_pasivo.py`

- [ ] **Step 1: Write the failing test**

Añade a `tests/test_sujeto_pasivo.py`:

```python
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
```

`_factura(..., "0", "confirmada")` no vuelve a pendiente al marcar, así que el facturado sigue en 40.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_el_control_marca_la_obra_sin_cambiar_el_facturado -v`

Expected: FAIL. `inversion_sujeto_pasivo` no está en la respuesta.

- [ ] **Step 3: Write minimal implementation**

En `app/schemas/control_economico.py`, dentro de `ControlEconomicoOut`:

```python
    inversion_sujeto_pasivo: bool = False
```

En `app/services/economico.py`, en el `return ControlEconomicoOut(` de `control_economico`:

```python
        inversion_sujeto_pasivo=bool(proyecto.inversion_sujeto_pasivo),
```

No toques `_por_contrato` ni las sumas de `Factura.total`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_el_control_marca_la_obra_sin_cambiar_el_facturado tests/test_control_economico.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/control_economico.py app/services/economico.py tests/test_sujeto_pasivo.py
git commit -m "Muestra en el control que la obra va sin IVA, sin cambiar el desvío."
```

---

### Task 6: Ficha de la obra

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/js/obras.js`
- Test: `tests/test_sujeto_pasivo.py`

- [ ] **Step 1: Write the failing test**

Añade a `tests/test_sujeto_pasivo.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_la_ficha_nombra_la_inversion -v`

Expected: FAIL. Falta el texto en `index.html` o en `obras.js`.

- [ ] **Step 3: Write minimal implementation**

En `app/static/index.html`, en la cabecera de la obra, el botón «Borrar obra» está en un `div.fila-titulo`. Sustituye ese botón por un grupo:

```html
            <div class="stack" style="gap: 8px; align-items: flex-end">
              <p class="sub" x-show="proyecto && proyecto.inversion_sujeto_pasivo">
                Facturación al promotor: sin IVA
              </p>
              <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end">
                <template x-if="proyecto && !proyecto.inversion_sujeto_pasivo">
                  <button type="button" class="btn btn-secondary btn-sm"
                    @click="$refs.cartaIsp.click()">Marcar inversión del sujeto pasivo</button>
                </template>
                <template x-if="proyecto && proyecto.inversion_sujeto_pasivo">
                  <a class="btn btn-secondary btn-sm"
                    :href="'/proyectos/' + proyecto.id + '/carta-isp'">Ver carta</a>
                  <button type="button" class="btn btn-secondary btn-sm"
                    @click="$refs.cartaIsp.click()">Sustituir carta</button>
                  <button type="button" class="btn btn-secondary btn-sm"
                    @click="quitarIsp()">Quitar la marca</button>
                </template>
                <button type="button" class="btn btn-secondary btn-sm" x-show="proyecto"
                  @click="borrarObra(proyecto)">Borrar obra</button>
              </div>
              <input type="file" accept="application/pdf,.pdf" hidden x-ref="cartaIsp"
                @change="marcarIsp($event)">
            </div>
```

En el resumen de contraste, la cabecera «Contrato cliente» pasa a:

```html
                  <span class="der">Contrato cliente<span x-show="proyecto && proyecto.inversion_sujeto_pasivo"> sin IVA</span></span>
```

En la lista de contratos, la línea del importe pasa a:

```html
                <div class="num" style="margin-top: 4px">Contratado <strong x-text="c.importe"></strong><span x-show="proyecto && proyecto.inversion_sujeto_pasivo"> sin IVA</span></div>
```

En la bandeja, dentro del detalle de la factura, junto al aviso de duplicado, añade:

```html
                  <div class="aviso-ambar" style="margin: 16px 20px 0" x-show="seleccion.aviso_isp"
                    x-text="seleccion.aviso_isp"></div>
```

Al abrir la pantalla de control de la ficha (`template x-if="vista && screen === 'control'"`), como primera hija del `div.stack`:

```html
          <p class="sub" x-show="proyecto && proyecto.inversion_sujeto_pasivo">Importes sin IVA.</p>
```

En `app/static/js/obras.js`, dentro del objeto de cada factura en `_armarVista`, cambia `acciones` y añade `aviso_isp`:

```javascript
        aviso_isp: factura.aviso_isp || null,
        acciones:
          factura.estado_revision === "confirmada" || factura.aviso_isp
            ? []
            : [{ etiqueta: "Confirmar factura", variante: "primary", resolucion: "Validada" }],
```

Añade estos métodos junto a `leerFactura`:

```javascript
    async marcarIsp(event) {
      const entrada = event.target;
      const fichero = entrada.files && entrada.files[0];
      entrada.value = "";
      if (!fichero || !this.proyectoId) return;
      this.error = "";
      const fd = new FormData();
      fd.append("fichero", fichero, fichero.name);
      try {
        await GestorApi.postForm(
          "/proyectos/" + this.proyectoId + "/inversion-sujeto-pasivo",
          fd
        );
        await this._cargarVistaProyecto(this.proyectoId);
      } catch (err) {
        this.error = err.message || "No se ha podido marcar la obra";
      }
    },

    async quitarIsp() {
      if (!this.proyectoId) return;
      if (!window.confirm("¿Quitar la inversión del sujeto pasivo de esta obra?")) return;
      this.error = "";
      try {
        await GestorApi.borrar(
          "/proyectos/" + this.proyectoId + "/inversion-sujeto-pasivo"
        );
        await this._cargarVistaProyecto(this.proyectoId);
      } catch (err) {
        this.error = err.message || "No se ha podido quitar la marca";
      }
    },
```

No recalcules `precio_total` ni `importe_contrato_cliente`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_la_ficha_nombra_la_inversion -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html app/static/js/obras.js tests/test_sujeto_pasivo.py
git commit -m "Muestra en la ficha que la obra factura al promotor sin IVA."
```

---

### Task 7: Revisión de facturas, control suelto y ficha antigua

**Files:**
- Modify: `app/static/facturas.html`
- Modify: `app/static/js/facturas.js`
- Modify: `app/static/control.html`
- Modify: `app/static/proyecto.html`
- Modify: `app/static/js/proyecto.js`
- Test: `tests/test_sujeto_pasivo.py`

- [ ] **Step 1: Write the failing test**

Añade a `tests/test_sujeto_pasivo.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_las_otras_pantallas_nombran_la_inversion -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

En `app/static/facturas.html`, debajo del campo IVA:

```html
              <p class="estado-msg err"
                x-show="seleccionada && seleccionada.inversion_sujeto_pasivo && Number(edicion.iva) !== 0">
                La obra está en inversión del sujeto pasivo. El IVA tiene que ser 0.
              </p>
```

En `app/static/js/facturas.js`, al principio de `confirmar`, antes de `this.confirmando = true`:

```javascript
      if (
        this.seleccionada.inversion_sujeto_pasivo &&
        Number(this.edicion.iva) !== 0
      ) {
        this.error = "La obra está en inversión del sujeto pasivo. El IVA tiene que ser 0.";
        return;
      }
```

En `app/static/control.html`, justo después del párrafo `p.aviso` de la cabecera:

```html
      <p class="aviso" x-show="datos && datos.inversion_sujeto_pasivo">Importes sin IVA.</p>
```

En `app/static/proyecto.html`, dentro de la sección Resumen, después del párrafo de id, tipo y estado:

```html
            <p x-show="proyecto.inversion_sujeto_pasivo">Facturación al promotor: sin IVA</p>
            <div class="acciones-mini">
              <template x-if="!proyecto.inversion_sujeto_pasivo">
                <button type="button" class="secundario" @click="$refs.cartaIsp.click()">Marcar inversión del sujeto pasivo</button>
              </template>
              <template x-if="proyecto.inversion_sujeto_pasivo">
                <a :href="'/proyectos/' + proyecto.id + '/carta-isp'">Ver carta</a>
                <button type="button" class="secundario" @click="$refs.cartaIsp.click()">Sustituir carta</button>
                <button type="button" class="secundario" @click="quitarIsp()">Quitar la marca</button>
              </template>
            </div>
            <input type="file" accept="application/pdf,.pdf" hidden x-ref="cartaIsp" @change="marcarIsp($event)">
```

En el precio de cada contrato de `proyecto.html`:

```html
                  · <span x-text="euro(c.precio_total)"></span>
                  <span x-show="proyecto.inversion_sujeto_pasivo"> sin IVA</span>
```

En `app/static/js/proyecto.js`, `init` ya guarda `this.proyectoId` y `cargar()` vuelve a pedir el detalle. Añade estos métodos:

```javascript
    async marcarIsp(event) {
      const entrada = event.target;
      const fichero = entrada.files && entrada.files[0];
      entrada.value = "";
      if (!fichero || !this.proyectoId) return;
      this.error = "";
      const fd = new FormData();
      fd.append("fichero", fichero, fichero.name);
      try {
        this.proyecto = await GestorApi.postForm(
          "/proyectos/" + this.proyectoId + "/inversion-sujeto-pasivo",
          fd
        );
      } catch (err) {
        this.error = err.message || "No se ha podido marcar la obra";
      }
    },

    async quitarIsp() {
      if (!this.proyectoId) return;
      if (!window.confirm("¿Quitar la inversión del sujeto pasivo de esta obra?")) return;
      this.error = "";
      try {
        await GestorApi.borrar(
          "/proyectos/" + this.proyectoId + "/inversion-sujeto-pasivo"
        );
        await this.cargar();
      } catch (err) {
        this.error = err.message || "No se ha podido quitar la marca";
      }
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sujeto_pasivo.py -v`

Expected: PASS

- [ ] **Step 5: Verify in the browser**

Arranca la app, entra y abre una obra ficticia.

- Sin marca se ve «Marcar inversión del sujeto pasivo».
- Sube un PDF mínimo. Pasa a «Facturación al promotor: sin IVA», con «Ver carta», «Sustituir carta» y «Quitar la marca».
- «Ver carta» descarga el PDF.
- En contratos, el precio dice «sin IVA» y la cifra no cambia.
- En el contraste, la columna dice «Contrato cliente sin IVA».
- En el control de la ficha y en `control.html` se lee «Importes sin IVA».
- Una factura con IVA distinto de cero no ofrece «Confirmar factura» en la bandeja. En `facturas.html`, con el IVA distinto de cero, el formulario no se envía y se ve el aviso.
- «Quitar la marca» pide confirmación y el texto desaparece.

- [ ] **Step 6: Commit**

```bash
git add app/static/facturas.html app/static/js/facturas.js app/static/control.html app/static/proyecto.html app/static/js/proyecto.js tests/test_sujeto_pasivo.py
git commit -m "Avisa en facturas y en el control cuando la obra va sin IVA."
```

---

### Task 8: Documentar el modelo y la API

**Files:**
- Modify: `docs/readme.md`
- Test: `tests/test_sujeto_pasivo.py`

- [ ] **Step 1: Write the failing test**

Añade a `tests/test_sujeto_pasivo.py`:

```python
def test_el_readme_documenta_la_marca():
    texto = Path("docs/readme.md").read_text(encoding="utf-8")
    assert "inversion_sujeto_pasivo" in texto
    assert "/proyectos/{id}/inversion-sujeto-pasivo" in texto
    assert "/proyectos/{id}/carta-isp" in texto
    assert "El IVA tiene que ser 0" in texto
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sujeto_pasivo.py::test_el_readme_documenta_la_marca -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

En el bloque `PROYECTO` de `docs/readme.md`, después de `timestamp created_at`, añade:

```
        bool inversion_sujeto_pasivo "false por defecto; lo marca una persona"
        string ruta_carta_isp "nullable, ruta relativa en uploads/"
        string fichero_carta_isp "nullable, nombre original del PDF"
```

En el párrafo de **PROYECTO** que sigue al diagrama, añade esta frase: una persona puede marcar la obra subiendo la carta del promotor (`inversion_sujeto_pasivo`). El precio con el cliente y el de la subcontrata se muestran sin IVA. Una factura de esa obra no se confirma si el IVA no es cero, y las ya confirmadas con IVA vuelven a pendiente. La carta no se lee con OCR ni con el modelo.

En la API resumida, junto a los endpoints de proyecto, añade:

```yaml
  /proyectos/{id}/inversion-sujeto-pasivo:
    post:
      summary: Marca la obra con la carta del promotor. Las facturas confirmadas con IVA vuelven a pendiente
    delete:
      summary: Quita la marca y borra la carta. No cambia las facturas
  /proyectos/{id}/carta-isp:
    get:
      summary: Descarga la carta. 404 si no hay
```

En la descripción de **FACTURA**, añade: si la obra tiene `inversion_sujeto_pasivo`, confirmar con IVA distinto de cero responde 422 y no guarda. El listado trae `aviso_isp` en esas facturas.

No copies nombres, NIF ni importes de una carta real.

- [ ] **Step 4: Run the whole file**

Run: `python -m pytest tests/test_sujeto_pasivo.py tests/test_facturas.py tests/test_control_economico.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/readme.md tests/test_sujeto_pasivo.py
git commit -m "Documenta la marca de inversión del sujeto pasivo y la regla del IVA."
```
