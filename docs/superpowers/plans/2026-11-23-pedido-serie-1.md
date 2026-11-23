# Pedido de serie 1 — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Abrir una obra sin presupuesto ni contrato con el cliente subiendo uno o varios pedidos de compra de serie 1, y enlazar varios contratos de proveedor a cada línea de montaje o instalación de ese pedido.

**Architecture:** Un lector determinista saca el número `1-` y cinco dígitos, el rótulo de nave y las líneas de la plantilla de Exafan. No usa LLM. Cada pedido es una nave y cada línea que entra es un apartado pendiente de confirmación. El código de contrato `1-` + seis dígitos obliga a que los cinco primeros ya sean una nave de esa obra. En serie 1 una línea admite varios contratos; en el Excel no. El sello ya imprime el código entero y no se toca.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, PyMuPDF, HTML + Alpine.js, pytest.

**Regla cerrada:** `docs/readme.md` (PROYECTO, NAVE, CONTRATO), `docs/contexto_proyecto_obra.md` y `docs/flujo_ui_proyecto.md`, sección «Obra de serie 1».

Los PDF reales no se copian al repositorio ni a los tests. Números, descripciones e importes de prueba son ficticios (`1-10001`, «MONTAJE DE EJEMPLO», `100,00`).

## Ficheros

- Modificar: `app/services/codigo_contrato.py` — `pedido_de_codigo`.
- Crear: `app/services/pedido_compra.py` — lectura de la plantilla.
- Crear: `tests/pdf_pedido.py` — PDF ficticio en memoria.
- Crear: `app/models/pedido.py` — documento y su nave.
- Modificar: `app/models/tarea.py` — `pedido_id` nullable.
- Modificar: `app/models/__init__.py` — exportar `Pedido`.
- Crear: `migrations/versions/0023_pedido_compra.py`.
- Crear: `migrations/versions/0024_confirmar_pedido.py` — acción del registro.
- Modificar: `app/services/almacen.py` — tipo `pedido`.
- Crear: `app/schemas/pedido.py`.
- Crear: `app/services/pedidos.py` — alta, añadir, confirmar.
- Modificar: `app/services/proyectos.py` — borrar la obra, detalle, código de contrato.
- Modificar: `app/services/ingesta.py` — el contrato de serie 1 exige la nave.
- Modificar: `app/services/casado.py` — enlace de la línea de pedido.
- Modificar: `app/services/presupuesto_excel.py` — no mezclar Excel y pedido.
- Modificar: `app/routers/proyectos.py` — tres rutas.
- Modificar: `app/models/registro_accion.py`, `app/services/registro.py`, `app/static/js/registro.js`.
- Modificar: `app/schemas/proyecto.py` — `pedidos` en el detalle.
- Modificar: `app/static/index.html`, `app/static/js/obras.js`.
- Modificar: `docs/flujo_ui_proyecto.md` — la pantalla ya existe, al acabar.
- Crear: `tests/test_pedido_compra.py`, `tests/test_pedidos.py`.

---

### Task 1: Pedido dentro del código de contrato

El contrato impreso `1-256580` es el pedido `1-25658` más el dígito `0`. `1-256580ADM` es el mismo pedido.

**Files:**
- Modify: `app/services/codigo_contrato.py`
- Test: `tests/test_codigo_contrato.py`

- [ ] **Step 1: Write the failing test**

Al final de `tests/test_codigo_contrato.py`:

```python
from app.services.codigo_contrato import pedido_de_codigo


def test_el_pedido_son_los_cinco_primeros_digitos():
    assert pedido_de_codigo("1-256580") == "1-25658"
    assert pedido_de_codigo("1-256581") == "1-25658"
    assert pedido_de_codigo("1-256580ADM") == "1-25658"
    assert pedido_de_codigo("pycon244070") is None
    assert pedido_de_codigo("1-25658") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_codigo_contrato.py::test_el_pedido_son_los_cinco_primeros_digitos -v`

Expected: FAIL con `ImportError` porque `pedido_de_codigo` no existe.

- [ ] **Step 3: Write minimal implementation**

En `app/services/codigo_contrato.py`, después de `_FORMATO`:

```python
_PEDIDO_DE_CODIGO = re.compile(r"^1-(\d{5})\d(?:ADM)?$")


def pedido_de_codigo(valor: str) -> str | None:
    """1-256580 y 1-256580ADM son el pedido 1-25658. Un PYCON no lo es."""
    hallazgo = _PEDIDO_DE_CODIGO.fullmatch(re.sub(r"\s+", "", valor or "").upper())
    if hallazgo is None:
        return None
    return f"1-{hallazgo.group(1)}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_codigo_contrato.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/codigo_contrato.py tests/test_codigo_contrato.py
git commit -m "feat: separa el pedido del dígito de contrato en serie 1"
```

---

### Task 2: Lectura de la plantilla

La plantilla tiene las columnas Código, Descripción, Unds, Precio, %.Dto e Importe. Entra la línea cuya descripción empieza por MONTAJE, COLOCACIÓN o INSTALACIÓN. El importe es la columna Importe, ya descontada. Material, transporte y cualquier otra línea se ignoran. Una instalación que cita un presupuesto sigue entrando: la cita no crea un presupuesto ni se guarda. Si no hay un único `1-` de cinco dígitos o faltan las columnas Descripción e Importe, `cuadra` es falso y `lineas` queda vacía.

**Files:**
- Create: `app/services/pedido_compra.py`
- Create: `tests/pdf_pedido.py`
- Create: `tests/test_pedido_compra.py`

- [ ] **Step 1: Write the failing test**

Crear `tests/pdf_pedido.py` con `pdf_pedido` y `tests/test_pedido_compra.py`:

```python
"""PDF de pedido ficticio. No lleva datos reales."""

import pymupdf


def pdf_pedido(lineas, numero="1-10001", rotulo="NAVE 1", cabecera=True) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((40, 40), numero, fontsize=11)
    if rotulo:
        page.insert_text((40, 58), rotulo, fontsize=11)
    if cabecera:
        for x, texto in (
            (40, "Código"),
            (150, "Descripción"),
            (340, "Unds"),
            (400, "Precio"),
            (460, "%.Dto"),
            (520, "Importe"),
        ):
            page.insert_text((x, 90), texto, fontsize=9)
    y = 120
    for codigo, desc, unds, precio, dto, importe in lineas:
        page.insert_text((40, y), codigo, fontsize=9)
        page.insert_text((150, y), desc, fontsize=9)
        page.insert_text((340, y), unds, fontsize=9)
        page.insert_text((400, y), precio, fontsize=9)
        page.insert_text((460, y), dto, fontsize=9)
        page.insert_text((520, y), importe, fontsize=9)
        y += 18
    page.insert_text((40, y + 12), "Importe Neto", fontsize=9)
    datos = doc.tobytes()
    doc.close()
    return datos


```

`tests/test_pedido_compra.py` importa `pdf_pedido` desde `tests.pdf_pedido` y `leer_pedido` desde el servicio.

```python
from decimal import Decimal

from app.services.pedido_compra import leer_pedido
from tests.pdf_pedido import pdf_pedido


def test_entra_montaje_e_instalacion_con_el_importe_neto():
    contenido = pdf_pedido(
        [
            ("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "150,00", "0", "100,00"),
            ("SUST01000001", "INSTALACION SEGUN PRESUPUESTO ZZ000000", "1,00", "80,00", "0", "80,00"),
            ("SER01010001", "TRANSPORTE DE EJEMPLO", "1,00", "20,00", "0", "20,00"),
            ("MAT01010001", "MATERIAL DE EJEMPLO", "1,00", "50,00", "30", "35,00"),
            ("SER02010002", "COLOCACIÓN DE EJEMPLO", "2,00", "10,00", "0", "20,00"),
        ]
    )
    lectura = leer_pedido(contenido)
    assert lectura.cuadra is True
    assert lectura.numero == "1-10001"
    assert lectura.rotulo == "NAVE 1"
    assert lectura.aviso is None
    assert [(linea.descripcion, linea.importe) for linea in lectura.lineas] == [
        ("MONTAJE DE EJEMPLO", Decimal("100.00")),
        ("INSTALACION SEGUN PRESUPUESTO ZZ000000", Decimal("80.00")),
        ("COLOCACIÓN DE EJEMPLO", Decimal("20.00")),
    ]
    assert lectura.lineas[0].cantidad == Decimal("1.00")
    assert lectura.lineas[0].precio_unitario == Decimal("150.00")
    assert lectura.lineas[0].descuento_pct == Decimal("0.00")


def test_sin_cabecera_no_inventa_lineas():
    lectura = leer_pedido(pdf_pedido(
        [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "10,00", "0", "10,00")],
        cabecera=False,
    ))
    assert lectura.cuadra is False
    assert lectura.lineas == []
    assert lectura.aviso == "El pedido no trae la plantilla de Exafan"


def test_sin_numero_de_cinco_digitos_no_cuadra():
    lectura = leer_pedido(pdf_pedido(
        [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "10,00", "0", "10,00")],
        numero="SIN-NUMERO",
    ))
    assert lectura.cuadra is False
    assert lectura.lineas == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedido_compra.py -v`

Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Crear `app/services/pedido_compra.py`:

```python
"""Pedido de compra de serie 1. Plantilla de Exafan, sin LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

import pymupdf

_ENTRA = ("MONTAJE", "COLOCACIÓN", "COLOCACION", "INSTALACIÓN", "INSTALACION")
_NUMERO = re.compile(r"(?<![A-Z0-9])1-\d{5}(?!\d)")
_ROTULO = re.compile(r"NAVE\s+\d+", re.IGNORECASE)
_CODIGO_ART = re.compile(r"^[A-Z]{3,}\d+$")
AVISO_PLANTILLA = "El pedido no trae la plantilla de Exafan"
AVISO_VARIOS = "El pedido trae varios números"


@dataclass(frozen=True)
class LineaPedido:
    codigo: str
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_pct: Decimal
    importe: Decimal


@dataclass(frozen=True)
class LecturaPedido:
    cuadra: bool
    numero: str | None
    rotulo: str | None
    lineas: list[LineaPedido]
    aviso: str | None


def leer_pedido(contenido: bytes) -> LecturaPedido:
    try:
        documento = pymupdf.open(stream=contenido, filetype="pdf")
    except Exception:
        return LecturaPedido(False, None, None, [], AVISO_PLANTILLA)
    try:
        palabras: list[tuple[float, float, str]] = []
        for pagina in documento:
            for palabra in pagina.get_text("words"):
                texto = str(palabra[4]).strip()
                if texto:
                    palabras.append((float(palabra[1]), (float(palabra[0]) + float(palabra[2])) / 2, texto))
    finally:
        documento.close()
    return _leer_palabras(palabras)


def _leer_palabras(palabras: list[tuple[float, float, str]]) -> LecturaPedido:
    filas = _filas(palabras)
    numeros = _numeros(filas)
    rotulo = _rotulo(filas)
    cabecera = _cabecera(filas)
    if len(set(numeros)) != 1 or cabecera is None:
        aviso = AVISO_VARIOS if len(set(numeros)) > 1 else AVISO_PLANTILLA
        return LecturaPedido(False, None, rotulo, [], aviso)
    return LecturaPedido(True, numeros[0], rotulo, _lineas(filas, cabecera), None)


def _filas(palabras: list[tuple[float, float, str]]) -> list[list[tuple[float, float, str]]]:
    orden = sorted(palabras, key=lambda item: (round(item[0], 1), item[1]))
    filas: list[list[tuple[float, float, str]]] = []
    for palabra in orden:
        if filas and abs(palabra[0] - filas[-1][0][0]) <= 3:
            filas[-1].append(palabra)
        else:
            filas.append([palabra])
    for fila in filas:
        fila.sort(key=lambda item: item[1])
    return filas


def _numeros(filas: list[list[tuple[float, float, str]]]) -> list[str]:
    hallados: list[str] = []
    for fila in filas:
        pegado = ""
        previo = ""
        for _, _, texto in fila:
            if previo == "1-" and re.fullmatch(r"\d{5}", texto):
                pegado += texto
            else:
                pegado += f" {texto}"
            previo = texto
        hallados.extend(_NUMERO.findall(pegado.upper()))
    return hallados


def _rotulo(filas: list[list[tuple[float, float, str]]]) -> str | None:
    texto = " ".join(palabra for fila in filas for _, _, palabra in fila)
    hallazgo = _ROTULO.search(texto)
    if hallazgo is None:
        return None
    return re.sub(r"\s+", " ", hallazgo.group()).upper()


def _clave(texto: str) -> str | None:
    normal = texto.lower().replace("ó", "o").replace("á", "a").replace("%", "").replace(".", "")
    if normal.startswith("cod"):
        return "codigo"
    if normal.startswith("descrip"):
        return "descripcion"
    if normal in {"unds", "und", "uds"}:
        return "cantidad"
    if normal == "precio":
        return "precio"
    if "dto" in normal:
        return "descuento"
    if normal == "importe":
        return "importe"
    return None


def _cabecera(filas: list[list[tuple[float, float, str]]]) -> dict[str, float] | None:
    for fila in filas:
        columnas: dict[str, float] = {}
        for _, x, texto in fila:
            clave = _clave(texto)
            if clave is not None:
                columnas[clave] = x
        if "descripcion" in columnas and "importe" in columnas:
            return columnas
    return None


def _lineas(
    filas: list[list[tuple[float, float, str]]],
    columnas: dict[str, float],
) -> list[LineaPedido]:
    y_cabecera = None
    for fila in filas:
        claves = {_clave(texto) for _, _, texto in fila}
        if "descripcion" in claves and "importe" in claves:
            y_cabecera = fila[0][0]
            break
    if y_cabecera is None:
        return []
    lineas: list[LineaPedido] = []
    for fila in filas:
        if fila[0][0] <= y_cabecera + 3:
            continue
        texto_fila = " ".join(texto for _, _, texto in fila).lower()
        if "importe neto" in texto_fila or "observaciones" in texto_fila:
            break
        celdas: dict[str, list[str]] = {clave: [] for clave in columnas}
        for _, x, texto in fila:
            clave = min(columnas, key=lambda nombre: abs(columnas[nombre] - x))
            celdas[clave].append(texto)
        descripcion = re.sub(r"\s+", " ", " ".join(celdas.get("descripcion", []))).strip()
        if not descripcion.upper().startswith(_ENTRA):
            continue
        importe = _decimal(" ".join(celdas.get("importe", [])))
        if importe is None:
            continue
        codigo = "".join(celdas.get("codigo", []))
        if not _CODIGO_ART.fullmatch(codigo):
            codigo = f"ped.{len(lineas) + 1}"
        lineas.append(
            LineaPedido(
                codigo=codigo[:50],
                descripcion=descripcion,
                cantidad=_decimal(" ".join(celdas.get("cantidad", []))) or Decimal("0.00"),
                precio_unitario=_decimal(" ".join(celdas.get("precio", []))) or Decimal("0.00"),
                descuento_pct=_decimal(" ".join(celdas.get("descuento", []))) or Decimal("0.00"),
                importe=importe,
            )
        )
    return lineas


def _decimal(texto: str) -> Decimal | None:
    limpio = texto.strip().replace(" ", "")
    if not limpio or not re.fullmatch(r"\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?", limpio):
        return None
    return Decimal(limpio.replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedido_compra.py -q`

Expected: PASS. Si una fila no agrupa las columnas, ajusta solo la tolerancia de `_filas` (sigue en 3) o el `fontsize` del test, sin cambiar la regla de qué línea entra.

- [ ] **Step 5: Commit**

```bash
git add app/services/pedido_compra.py tests/test_pedido_compra.py
git commit -m "feat: lee montaje e instalación del pedido de serie 1"
```

---

### Task 3: Tabla pedido y fichero en disco

**Files:**
- Create: `app/models/pedido.py`
- Modify: `app/models/tarea.py`
- Modify: `app/models/__init__.py`
- Modify: `app/services/almacen.py`
- Create: `migrations/versions/0023_pedido_compra.py`
- Test: `tests/test_pedidos.py`

- [ ] **Step 1: Write the failing test**

Crear `tests/test_pedidos.py`:

```python
"""Alta de obra desde pedidos ficticios."""

from pathlib import Path

from app.models.pedido import Pedido
from app.services.almacen import guardar


def test_el_modelo_tiene_numero_unico_y_nave():
    assert Pedido.__tablename__ == "pedido"
    columnas = {col.name for col in Pedido.__table__.columns}
    assert {"proyecto_id", "nave_id", "numero", "rotulo", "estado_revision", "ruta_almacen"} <= columnas


def test_el_almacen_acepta_el_tipo_pedido():
    texto = Path("app/services/almacen.py").read_text(encoding="utf-8")
    assert '"pedido"' in texto
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_el_modelo_tiene_numero_unico_y_nave tests/test_pedidos.py::test_el_almacen_acepta_el_tipo_pedido -v`

Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Crear `app/models/pedido.py`:

```python
"""Pedido de compra de serie 1. Una nave por pedido."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.nave import Nave
    from app.models.proyecto import Proyecto
    from app.models.tarea import Tarea


class Pedido(Base):
    __tablename__ = "pedido"

    id: Mapped[int] = mapped_column(primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("proyecto.id"), nullable=False, index=True)
    nave_id: Mapped[int] = mapped_column(ForeignKey("nave.id"), nullable=False, unique=True)
    numero: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    rotulo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fichero_origen: Mapped[str] = mapped_column(String(512), nullable=False)
    ruta_almacen: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    estado_revision: Mapped[str] = mapped_column(String(50), nullable=False)
    aviso: Mapped[str | None] = mapped_column(Text, nullable=True)

    proyecto: Mapped[Proyecto] = relationship()
    nave: Mapped[Nave] = relationship()
    tareas: Mapped[list[Tarea]] = relationship(back_populates="pedido")
```

En `app/models/tarea.py`, después de `presupuesto_id`:

```python
    pedido_id: Mapped[int | None] = mapped_column(
        ForeignKey("pedido.id"),
        nullable=True,
        index=True,
    )
```

Añadir el import de tipo y la relación, junto a `presupuesto`:

```python
    pedido: Mapped[Pedido | None] = relationship(back_populates="tareas")
```

En `app/models/__init__.py`, importar `Pedido` desde `app.models.pedido` y añadirlo a `__all__`.

En `app/services/almacen.py`, cambiar el conjunto:

```python
_TIPOS = frozenset({"presupuesto", "contrato", "factura", "carta_isp", "parte", "pedido"})
```

Crear `migrations/versions/0023_pedido_compra.py`. `down_revision` es `0022_verde_opcional`.

```python
"""Pedido de compra de serie 1 y su nave.

Revision ID: 0023_pedido_compra
Revises: 0022_verde_opcional
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_pedido_compra"
down_revision: Union[str, Sequence[str], None] = "0022_verde_opcional"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pedido",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyecto.id"), nullable=False),
        sa.Column("nave_id", sa.Integer(), sa.ForeignKey("nave.id"), nullable=False),
        sa.Column("numero", sa.String(length=16), nullable=False),
        sa.Column("rotulo", sa.String(length=255), nullable=True),
        sa.Column("fichero_origen", sa.String(length=512), nullable=False),
        sa.Column("ruta_almacen", sa.String(length=1024), nullable=True),
        sa.Column("estado_revision", sa.String(length=50), nullable=False),
        sa.Column("aviso", sa.Text(), nullable=True),
        sa.UniqueConstraint("nave_id", name="uq_pedido_nave"),
        sa.UniqueConstraint("numero", name="uq_pedido_numero"),
    )
    op.create_index("ix_pedido_proyecto_id", "pedido", ["proyecto_id"])
    op.add_column("tarea", sa.Column("pedido_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_tarea_pedido", "tarea", "pedido", ["pedido_id"], ["id"])
    op.create_index("ix_tarea_pedido_id", "tarea", ["pedido_id"])


def downgrade() -> None:
    op.drop_index("ix_tarea_pedido_id", table_name="tarea")
    op.drop_constraint("fk_tarea_pedido", "tarea", type_="foreignkey")
    op.drop_column("tarea", "pedido_id")
    op.drop_index("ix_pedido_proyecto_id", table_name="pedido")
    op.drop_table("pedido")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m alembic upgrade head`

Expected: la revisión `0023_pedido_compra` queda aplicada.

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_el_modelo_tiene_numero_unico_y_nave tests/test_pedidos.py::test_el_almacen_acepta_el_tipo_pedido -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models/pedido.py app/models/tarea.py app/models/__init__.py app/services/almacen.py migrations/versions/0023_pedido_compra.py tests/test_pedidos.py
git commit -m "feat: guarda el pedido de serie 1 como documento de la nave"
```

---

### Task 4: Alta de la obra y otro pedido después

La persona pone el nombre. Cada PDF es una nave: `codigo` es el número `1-XXXXX` y `descripcion` es el rótulo, o el número si no hay rótulo. Las líneas nacen `pendiente`, `nivel="apartado"`, `es_montaje=True` (también la instalación, para que el prorrateo ya existente use su importe). Si la plantilla no cuadra, no se guarda ese fichero y, en el alta, no se crea la obra. Un pedido que cuadra y no trae montaje ni instalación sí se guarda, con aviso y sin líneas. No se mezcla con un Excel. Borrar la obra borra sus pedidos.

**Files:**
- Create: `app/schemas/pedido.py`
- Create: `app/services/pedidos.py`
- Modify: `app/services/proyectos.py` (el `DELETE FROM nave`)
- Modify: `app/services/presupuesto_excel.py`
- Modify: `app/routers/proyectos.py`
- Test: `tests/test_pedidos.py`

- [ ] **Step 1: Write the failing test**

Añadir a `tests/test_pedidos.py`, importando `pdf_pedido` desde `tests.pdf_pedido`:

```python
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Pedido, Proyecto, Tarea, Usuario
from app.services.pedidos import anadir_pedido, importar_pedidos
from app.services.proyectos import borrar_proyecto


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_dos_pedidos_son_dos_naves_de_una_obra tests/test_pedidos.py::test_la_plantilla_rota_no_crea_la_obra -v`

Expected: FAIL con `ImportError` de `importar_pedidos`.

- [ ] **Step 3: Write minimal implementation**

Crear `app/schemas/pedido.py`:

```python
from decimal import Decimal

from pydantic import BaseModel, Field


class LineaPedidoOut(BaseModel):
    tarea_id: int
    codigo: str
    descripcion: str
    importe: Decimal
    estado_revision: str


class NavePedidoOut(BaseModel):
    pedido_id: int
    nave_id: int
    numero: str
    rotulo: str | None
    aviso: str | None
    estado_revision: str
    lineas: list[LineaPedidoOut] = Field(default_factory=list)


class ImportarPedidosOut(BaseModel):
    proyecto_id: int
    naves: list[NavePedidoOut]
```

Crear `app/services/pedidos.py` con `importar_pedidos(db, nombre, ficheros: list[tuple[str, bytes]])` y `anadir_pedido(db, proyecto_id, nombre_fichero, contenido)`. Las dos leen antes de escribir. Si alguna lectura tiene `cuadra is False`, lanzan `ValueError(lectura.aviso)` y no hacen commit. `importar_pedidos` crea `Proyecto(nombre=nombre.strip()[:255], tipo="llave_en_mano", estado="pendiente_revision", fase="Pedido")`. Rechaza el nombre vacío con `ValueError("Falta el nombre de la obra")` y la lista vacía con `ValueError("Falta el fichero")`.

Por cada lectura que cuadra:

```python
nave = Nave(
    proyecto_id=proyecto.id,
    codigo=lectura.numero,
    descripcion=(lectura.rotulo or lectura.numero)[:255],
    importe_presupuestado=sum((linea.importe for linea in lectura.lineas), Decimal("0")),
)
pedido = Pedido(
    proyecto_id=proyecto.id,
    nave_id=nave.id,
    numero=lectura.numero,
    rotulo=lectura.rotulo,
    fichero_origen=nombre_fichero[:512],
    estado_revision="pendiente",
    aviso=None if lectura.lineas else "El pedido no trae líneas de montaje ni de instalación",
)
```

Cada `LineaPedido` es una `Tarea` con `pedido_id`, `presupuesto_id=None`, `contrato_id=None`, `nivel="apartado"`, `es_montaje=True`, `solo_gestion=False`, `tiene_anotacion_manual=False`, `estado_revision="pendiente"`, `estado="no_iniciada"`, `avance_fisico_pct=Decimal("0")`, y cantidad, precio, descuento e `importe_presupuestado` de la lectura. Después de `flush` del pedido, `almacen.guardar(proyecto.id, "pedido", pedido.id, nombre, contenido)` rellena `ruta_almacen`.

`anadir_pedido` exige que el proyecto exista. Si ya tiene un `Presupuesto` con `formato="excel_expertis"`, lanza `ValueError("Esta obra nace del Excel")`. Si el `numero` ya existe, lanza `ValueError(f"El pedido {lectura.numero} ya está en una obra")`. Usa `almacen.exigir_distinto` contra las `ruta_almacen` de los pedidos del proyecto. Al terminar deja `proyecto.estado = "pendiente_revision"`.

En `anadir_presupuesto_excel` e `importar_presupuestos_excel`, antes de crear nada, no aplica al alta nueva. En `anadir_presupuesto_excel`, si el proyecto tiene algún `Pedido`, lanza `ValueError("Esta obra nace de pedidos de compra")`.

En `borrar_proyecto`, después del `DELETE FROM tarea` y antes del `DELETE FROM nave`:

```python
db.execute(text("DELETE FROM pedido WHERE proyecto_id = :id"), params)
```

Rutas en `app/routers/proyectos.py`, con el mismo trato de `ValueError` que el Excel (`422`, y `404` si el detalle contiene «no encontrado»):

- `POST /proyectos/importar-pedidos`, `201`, form `nombre` y `ficheros: list[UploadFile]`, respuesta `ImportarPedidosOut`.
- `POST /proyectos/{proyecto_id}/pedidos`, `201`, un `fichero`.
- `GET /proyectos/{proyecto_id}/pedidos/{pedido_id}/fichero` devuelve el PDF con `FileResponse`, igual que el fichero de presupuesto. `404` si el pedido no es de esa obra o no tiene ruta.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py -q`

Expected: PASS. Los proyectos ficticios quedan borrados por `borrar_proyecto`.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/pedido.py app/services/pedidos.py app/services/proyectos.py app/services/presupuesto_excel.py app/routers/proyectos.py tests/test_pedidos.py
git commit -m "feat: abre la obra desde uno o varios pedidos de serie 1"
```

---

### Task 5: Confirmar las líneas

Confirmar pasa el pedido y sus tareas a `confirmada`. Cuando no queda ningún pedido, presupuesto ni contrato pendiente, la obra pasa a `en_curso`, igual que la revisión del Excel. Queda escrito en el registro.

**Files:**
- Modify: `app/services/pedidos.py`
- Modify: `app/routers/proyectos.py`
- Modify: `app/models/registro_accion.py`
- Modify: `app/services/registro.py`
- Modify: `app/static/js/registro.js`
- Create: `migrations/versions/0024_confirmar_pedido.py`
- Test: `tests/test_pedidos.py`

- [ ] **Step 1: Write the failing test**

```python
from app.models.registro_accion import ACCIONES, RegistroAccion
from app.services.pedidos import confirmar_pedido
from app.services.registro import ETIQUETAS


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
    fila = db.query(RegistroAccion).filter(RegistroAccion.accion == "confirmar_pedido").one()
    assert fila.documento_id == pedido.id
    borrar_proyecto(db, alta.proyecto_id, usuario)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_confirmar_deja_la_linea_lista_para_el_contrato -v`

Expected: FAIL con `ImportError` de `confirmar_pedido`.

- [ ] **Step 3: Write minimal implementation**

En `ACCIONES` y en `ETIQUETAS`, añadir `"confirmar_pedido": "Confirmó el pedido"`. En `app/static/js/registro.js`, junto al resto de pares, añadir `["confirmar_pedido", "Confirmó el pedido"]`.

`migrations/versions/0024_confirmar_pedido.py` repite la lista de `0022_verde_opcional` más `"confirmar_pedido"`. `down_revision` es `0023_pedido_compra`. `upgrade` sustituye el check `registro_accion_codigo` por la lista nueva. `downgrade` vuelve a la lista de `0022`.

```python
def confirmar_pedido(db: Session, proyecto_id: int, pedido_id: int, usuario: Usuario) -> Pedido:
    pedido = db.get(Pedido, pedido_id)
    if pedido is None or pedido.proyecto_id != proyecto_id:
        raise ValueError(f"Pedido {pedido_id} no encontrado")
    pedido.estado_revision = "confirmada"
    for tarea in db.query(Tarea).filter(Tarea.pedido_id == pedido.id).all():
        tarea.estado_revision = "confirmada"
    pendientes = (
        db.query(Pedido)
        .filter(Pedido.proyecto_id == proyecto_id, Pedido.estado_revision == "pendiente")
        .count()
    )
    otros_presupuestos = (
        db.query(Presupuesto)
        .filter(Presupuesto.proyecto_id == proyecto_id, Presupuesto.estado_extraccion == "pendiente_revision")
        .count()
    )
    otros_contratos = (
        db.query(Contrato)
        .filter(Contrato.proyecto_id == proyecto_id, Contrato.estado_extraccion == "pendiente_revision")
        .count()
    )
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is not None and pendientes == 0 and otros_presupuestos == 0 and otros_contratos == 0:
        proyecto.estado = "en_curso"
    registrar(db, usuario, "confirmar_pedido", "pedido", pedido.id, pedido.numero)
    db.commit()
    db.refresh(pedido)
    return pedido
```

`registrar(db, usuario, accion, tipo_documento, documento_id, etiqueta)` no hace commit. El commit es el de `confirmar_pedido`. La llamada de arriba ya usa esa firma: la etiqueta es el número de pedido.

Ruta `POST /proyectos/{proyecto_id}/pedidos/{pedido_id}/confirmar` con `usuario_actual`. `422` si el `ValueError` no dice «no encontrado»; `404` si lo dice.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m alembic upgrade head`

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/pedidos.py app/routers/proyectos.py app/models/registro_accion.py app/services/registro.py app/static/js/registro.js migrations/versions/0024_confirmar_pedido.py tests/test_pedidos.py
git commit -m "feat: confirma las líneas del pedido antes de contratarlas"
```

---

### Task 6: La obra muestra las líneas del pedido

`obtener_proyecto` hoy solo carga tareas con `presupuesto_id`. Las de pedido tienen ese campo vacío y no saldrían.

**Files:**
- Modify: `app/schemas/proyecto.py`
- Modify: `app/services/proyectos.py`
- Test: `tests/test_pedidos.py`

- [ ] **Step 1: Write the failing test**

```python
from app.services.proyectos import obtener_proyecto


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_el_detalle_enseña_el_apartado_del_pedido -v`

Expected: FAIL porque `pedidos` no está en el detalle o el apartado no aparece.

- [ ] **Step 3: Write minimal implementation**

En `ProyectoDetalleOut`, añadir `pedidos: list[NavePedidoOut] = Field(default_factory=list)`.

En `obtener_proyecto`, la consulta de tareas pasa a ser:

```python
tareas_presupuesto = (
    db.query(Tarea)
    .filter(
        Tarea.nave_id.in_(nave_ids),
        or_(Tarea.presupuesto_id.isnot(None), Tarea.pedido_id.isnot(None)),
    )
    .order_by(Tarea.codigo, Tarea.id)
    .all()
)
```

`or_` sale de `sqlalchemy`. Las tareas con `pedido_id` no pasan por `rellenar_origen_montaje` ni por el resto de funciones del Excel: ese bucle sigue filtrado por `formato == "excel_expertis"`.

Rellena `pedidos` con un `NavePedidoOut` por cada `Pedido` del proyecto, ordenado por `numero`, y sus líneas desde las tareas de ese `pedido_id`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_el_detalle_enseña_el_apartado_del_pedido tests/test_presupuesto_excel.py -q`

Expected: PASS. El Excel sigue listando solo sus apartados.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/proyecto.py app/services/proyectos.py tests/test_pedidos.py
git commit -m "feat: muestra las líneas del pedido en la obra"
```

---

### Task 7: El contrato tiene que ser de una nave de la obra

Si el PDF trae `1-100011` y la obra no tiene la nave `1-10001`, no se guarda el contrato. Un PYCON no usa esta regla. Asignar el código a mano tampoco guarda un pedido ajeno. Si el pedido sí es nave, `contrato.nave_id` pasa a ser esa nave.

**Files:**
- Modify: `app/services/ingesta.py`
- Modify: `app/services/proyectos.py` (`asignar_codigo_contrato`)
- Test: `tests/test_pedidos.py`

- [ ] **Step 1: Write the failing test**

El test no llama al LLM. Crea la obra con `importar_pedidos`, inserta un `Contrato` mínimo de esa obra con un contratista ficticio (`nif` `B00000000`, nombre `Proveedor Ejemplo`) y llama a `asignar_codigo_contrato`.

```python
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
```

`_contrato_minimo` crea el `Contratista` si no existe y un `Contrato` con `precio_total=Decimal("10.00")`, `fichero_origen="contrato-ficticio.pdf"`, `estado_extraccion="pendiente_revision"` y la primera nave de la obra. No uses un NIF ni un nombre reales.

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_rechaza_el_contrato_de_otro_pedido -v`

Expected: FAIL porque `1-100990` se guarda.

- [ ] **Step 3: Write minimal implementation**

Función común en `app/services/pedidos.py`:

```python
def exigir_nave_del_codigo(db: Session, proyecto_id: int, codigo: str) -> Nave | None:
    numero = pedido_de_codigo(codigo)
    if numero is None:
        return None
    nave = (
        db.query(Nave)
        .filter(Nave.proyecto_id == proyecto_id, Nave.codigo == numero)
        .first()
    )
    if nave is None:
        raise ValueError(f"El pedido {numero} no es una nave de esta obra")
    return nave
```

En `asignar_codigo_contrato`, después de rechazar el código repetido y antes del commit:

```python
nave = exigir_nave_del_codigo(db, proyecto_id, codigo)
if nave is not None:
    contrato.nave_id = nave.id
```

En `persistir_contrato`, después de `_aplicar_codigo_leido` y antes de `db.commit()`: si `contrato.codigo` no es `None`, llama a `exigir_nave_del_codigo`. Si lanza, el commit no ocurre. Si devuelve nave, `contrato.nave_id = nave.id`. Un código PYCON devuelve `None` y la nave no cambia.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py tests/test_codigo_contrato.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/pedidos.py app/services/ingesta.py app/services/proyectos.py tests/test_pedidos.py
git commit -m "feat: impide guardar un contrato de serie 1 en otra nave"
```

---

### Task 8: Varios contratos en la misma línea

En el Excel la misma línea sigue sin poder ir en dos contratos. En serie 1 sí: la suma de los contratos se compara con el importe de la línea mediante el prorrateo que ya usa `es_montaje`. La línea pendiente no se enlaza. `tarea_apartado_id` del contrato queda en la primera línea de pedido enlazada cuando no hay apartado de Excel.

**Files:**
- Modify: `app/services/casado.py`
- Test: `tests/test_pedidos.py`

- [ ] **Step 1: Write the failing test**

Crea dos contratos mínimos en la obra del pedido `1-10001`, confirma el pedido y enlaza los dos a la misma tarea con `enlazar_contrato_apartado`. No debe lanzar «ya la cubre». Un tercer intento contra la línea antes de confirmar sí lanza «pendiente».

```python
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
    uno = _contrato_minimo(db, alta.proyecto_id, codigo="1-100010")
    with pytest.raises(ValueError, match="pendiente"):
        enlazar_contrato_apartado(db, alta.proyecto_id, uno.id, [linea.id])
    confirmar_pedido(db, alta.proyecto_id, pedido.id, usuario)
    uno.nave_id = pedido.nave_id
    dos = _contrato_minimo(db, alta.proyecto_id, codigo="1-100011")
    dos.nave_id = pedido.nave_id
    enlazar_contrato_apartado(db, alta.proyecto_id, uno.id, [linea.id])
    enlazar_contrato_apartado(db, alta.proyecto_id, dos.id, [linea.id])
    assert {uno.id, dos.id} <= {c.id for c in linea.contratos_como_apartado} or _enlaces(db, linea.id) == 2
    borrar_proyecto(db, alta.proyecto_id, usuario)
```

`_enlaces` cuenta filas de `ContratoApartado` con esa `tarea_id`. `_contrato_minimo` acepta `codigo` opcional. Usa dos NIF ficticios distintos, `B00000000` y `B00000001`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_dos_proveedores_comparten_la_linea_confirmada -v`

Expected: FAIL en el enlace, con «Solo se puede enlazar un apartado raíz de este contrato» o «pendiente» ausente.

- [ ] **Step 3: Write minimal implementation**

En `_validar_enlace`, antes de la rama `presupuesto_id is None` actual, si `apartado.pedido_id is not None`:

- la nave de la tarea pertenece al proyecto;
- `nivel == "apartado"` y `tarea_padre_id is None`;
- `estado_revision == "confirmada"`, si no `ValueError("La línea del pedido sigue pendiente de revisión")`;
- `pedido_de_codigo(contrato.codigo or "")` es el `codigo` de esa nave, si no `ValueError("El contrato no es de esta nave")`.

Esas tareas no entran en `_rechazar_solape` porque `presupuesto_id` es `None`. No las añadas a `de_excel`.

Donde ahora queda `contrato.tarea_apartado_id = de_excel[0].id if de_excel else None`, si no hay Excel usa el primer apartado enlazado:

```python
contrato.tarea_apartado_id = de_excel[0].id if de_excel else apartados[0].id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py tests/test_casado.py -q`

Si `tests/test_casado.py` no existe, corre el test de enlace de apartados que ya cubra «esa línea ya la cubre». Expected: el Excel sigue rechazando el solape y el pedido no.

- [ ] **Step 5: Commit**

```bash
git add app/services/casado.py tests/test_pedidos.py
git commit -m "feat: permite varios contratos sobre una línea de pedido confirmada"
```

---

### Task 9: Pantalla de alta

Antes de tocar HTML o JS, lee `.agents/skills/modern-web-guidance/SKILL.md` y sigue esa guía. No cambies el alta por Excel: es el camino por defecto.

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/js/obras.js`
- Test: `tests/test_pedidos.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_el_alta_ofrece_el_pedido_de_compra():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    js = Path("app/static/js/obras.js").read_text(encoding="utf-8")
    assert "Pedido de compra" in html
    assert "/proyectos/importar-pedidos" in js
    assert "/confirmar" in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_el_alta_ofrece_el_pedido_de_compra -v`

Expected: FAIL. El alta solo habla de Excel.

- [ ] **Step 3: Write minimal implementation**

En el estado de `obras.js`, `origenAlta: "excel"`. En la pantalla `presupuestos` / `up === 'empty'`, encima de la zona de soltar, dos botones con las clases que ya usa la página (`btn`, `btn-md`, `btn-primary` en el activo): «Presupuesto Excel» pone `origenAlta = 'excel'` y «Pedido de compra» pone `origenAlta = 'pedido'`.

El título y la ayuda dependen de `origenAlta`. En pedido, el texto es: «Sube los pedidos de compra. Cada PDF es una nave. Entran montaje, colocación e instalación, y quedan pendientes de confirmar.» El input acepta `application/pdf` cuando el origen es pedido y sigue aceptando Excel cuando no.

`soltar` y el click llaman a `leerPedidos(lista)` si `origenAlta === 'pedido'`.

```javascript
async leerPedidos(lista) {
  if (this.up === "reading") return;
  const nombre = (this.nombreObra || "").trim();
  if (!this.proyectoId && !nombre) {
    this.error = "Escribe el nombre de la obra antes de subir los pedidos.";
    return;
  }
  this.up = "reading";
  this.error = "";
  const fd = new FormData();
  try {
    let alta;
    if (this.proyectoId) {
      fd.append("fichero", lista[0], lista[0].name);
      alta = await GestorApi.postForm("/proyectos/" + this.proyectoId + "/pedidos", fd);
    } else {
      fd.append("nombre", nombre);
      lista.forEach((fichero) => fd.append("ficheros", fichero, fichero.name));
      alta = await GestorApi.postForm("/proyectos/importar-pedidos", fd);
    }
    this.proyectoId = alta.proyecto_id;
    await this._cargarVistaProyecto(alta.proyecto_id);
  } catch (err) {
    this.error = err.message || "No se ha podido leer el pedido";
  }
  this.up = "empty";
},
```

En la ficha de la obra, si `vista.pedidos` tiene elementos, una lista: número, rótulo, aviso y un botón «Confirmar líneas» por pedido `pendiente`. El botón hace `POST /proyectos/{id}/pedidos/{pedido_id}/confirmar` y vuelve a cargar la vista. No añadas otro flujo para el contrato con el cliente.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_el_alta_ofrece_el_pedido_de_compra -q`

Expected: PASS.

Arranca `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` y, en el navegador, entra con el usuario de prueba. Elige «Pedido de compra», pon el nombre «Obra ficticia de prueba» y sube un PDF generado con `pdf_pedido` guardado en un temporal, no uno real. Comprueba que salen la nave `1-10001` y la línea de montaje, que el transporte no está, y que «Confirmar líneas» pasa la línea a confirmada. Sube un segundo PDF `1-10002` a la misma obra y comprueba que es otra nave. Borra la obra al terminar.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html app/static/js/obras.js tests/test_pedidos.py
git commit -m "feat: da de alta la obra desde pedidos de compra"
```

---

### Task 10: El flujo deja de decir que la pantalla no existe

**Files:**
- Modify: `docs/flujo_ui_proyecto.md`
- Test: `tests/test_pedidos.py`

- [ ] **Step 1: Write the failing test**

```python
def test_el_flujo_ya_no_dice_que_falta_la_pantalla():
    texto = Path("docs/flujo_ui_proyecto.md").read_text(encoding="utf-8")
    assert "La pantalla de alta desde el pedido no está construida." not in texto
    assert "POST /proyectos/importar-pedidos" in texto
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py::test_el_flujo_ya_no_dice_que_falta_la_pantalla -v`

Expected: FAIL. La frase sigue en el documento.

- [ ] **Step 3: Write minimal implementation**

En la sección «Obra de serie 1, sin presupuesto», sustituye «La pantalla de alta desde el pedido no está construida.» por las tres rutas: `POST /proyectos/importar-pedidos`, `POST /proyectos/{id}/pedidos` y `POST /proyectos/{id}/pedidos/{pedido_id}/confirmar`. No cambies la regla de qué línea entra ni la del código.

Quita la misma frase de `docs/contexto_proyecto_obra.md` («El alta desde el pedido todavía no está construida.»).

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pedidos.py tests/test_pedido_compra.py tests/test_codigo_contrato.py tests/test_sello_factura.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/flujo_ui_proyecto.md docs/contexto_proyecto_obra.md tests/test_pedidos.py
git commit -m "docs: la obra de serie 1 ya se abre desde el pedido"
```
