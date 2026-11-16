# PDF con texto a Haiku Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Si un PDF de presupuesto o de contrato ya trae texto seleccionable, Haiku rellena los campos sobre ese texto y Sonnet no ve el fichero. Sonnet sigue transcribiendo el escaneo, la foto y cualquier PDF en el que pueda haber un tachón.

**Architecture:** Una función nueva, `decidir_lectura_pdf`, elige la vía antes de llamar al modelo. Sin texto útil, con la casilla de manuscrito, con una anotación de corrección en el PDF, o si un vistazo barato de Haiku marca bolígrafo, se mantiene la transcripción actual de Sonnet y, detrás, la extracción de Haiku. Si el vistazo falla, también se mantiene Sonnet: ante la duda se paga la lectura cara y no se pierde el tachón. El texto local sale de PyMuPDF (y de pdfplumber si el primero viene vacío). La extracción, la revisión humana, el Excel, las facturas y el proveedor que no es Claude no se tocan.

**Tech Stack:** FastAPI, PyMuPDF, pdfplumber, Claude (Sonnet 5 para ver la página, Haiku 4.5 para el vistazo y para el JSON), Alpine.js, Alembic, pytest.

---

## Qué no puede cambiar

| Caso | Comportamiento que hay que seguir viendo |
| --- | --- |
| PDF sin texto, con clave de Claude | Sonnet transcribe el documento. `es_escaneado = true`. Revisión obligatoria. |
| PDF sin texto, sin clave de Claude | OCR por página, como ahora (`leer_documento`). |
| Imagen JPG/PNG/TIFF | OCR. No entra en esta decisión. |
| Fixture `.md` | Parser de fixture, sin modelo. |
| PDF con texto y proveedor que no es Claude | `leer_documento`. No se fuerza Sonnet. |
| Excel Expertis | Rejilla local. Haiku solo si queda montaje sin casar, solo con nombres. |
| Factura con texto | Reglas locales, 0 llamadas. |
| Factura escaneada | OCR o visión por página. Fuera de este plan. |
| Extracción | Los mismos prompts y los mismos esquemas de presupuesto y de contrato. |
| Revisión humana | Escaneado, manuscrito y contrato siguen pendientes de confirmar. |
| PDF en blanco de `test_pdf_sonnet_transcribe_y_haiku_extrae` | Sigue siendo dos llamadas: Sonnet y luego Haiku. No tiene texto, así que no se llama al vistazo. |
| Firma digital | Un widget de firma no es un tachón. No manda el contrato a Sonnet por sí solo. |

La única diferencia buscada: un PDF con texto, sin casilla, sin anotación de corrección y con el vistazo en `false`, no llama a Sonnet. Haiku recibe el texto del PDF.

Riesgo que el plan cubre y no esconde: si Haiku dice que no hay bolígrafo y lo hay, y nadie marcó la casilla, el tachón no entra. Por eso el vistazo, ante un error, cae en Sonnet, y la casilla fuerza la vía antigua.

## Ficheros

- Create: `app/services/lectura_pdf.py` — decide la vía y hace el vistazo.
- Create: `tests/test_lectura_pdf.py`
- Create: `migrations/versions/0013_presupuesto_ver_pagina.py`
- Modify: `app/services/ingesta.py` — `leer_presupuesto`, `leer_contrato`, `importar_presupuesto`, `importar_contrato`, `persistir_presupuesto`.
- Modify: `app/services/presupuesto_excel.py` — `contrastar_presupuesto_cliente`, `obtener_contraste_cliente`.
- Modify: `app/models/presupuesto.py`
- Modify: `app/routers/proyectos.py` — campo de formulario `ver_pagina`.
- Modify: `app/static/presupuesto.html`, `app/static/js/presupuesto.js`
- Modify: `app/static/contrato.html`, `app/static/js/contrato.js`
- Modify: `app/static/proyecto.html`, `app/static/js/proyecto.js`
- Modify: `app/static/index.html`, `app/static/js/obras.js`
- Modify: `tests/test_extraccion_contrato_llm.py` — el test que hoy exige Sonnet en un PDF con texto.
- Modify: `docs/eficiencia_coste_analisis_ia.md` — el párrafo que dice que el PDF nativo sigue pagando Sonnet.

No se modifican `app/services/facturas.py`, `app/services/ocr.py`, `app/services/excel_expertis.py`, `app/services/extraccion.py` ni `app/services/extraccion_contrato.py`.

---

### Task 1: Decidir la vía sin llamar a la red

**Files:**
- Create: `tests/test_lectura_pdf.py`
- Create: `app/services/lectura_pdf.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_lectura_pdf.py`:

```python
"""Vía de lectura de un PDF: texto local o Sonnet."""

import pymupdf

from app.services.lectura_pdf import decidir_lectura_pdf


def _pdf(texto: str | None) -> bytes:
    doc = pymupdf.open()
    pagina = doc.new_page()
    if texto:
        pagina.insert_text((72, 72), texto)
    contenido = doc.tobytes()
    doc.close()
    return contenido


def test_sin_texto_va_a_sonnet_y_no_pregunta_el_vistazo():
    llamadas = {"n": 0}

    def vistazo(_contenido: bytes) -> bool:
        llamadas["n"] += 1
        return False

    decision = decidir_lectura_pdf(_pdf(None), forzar_vision=False, detectar_manuscrito=vistazo)
    assert decision.via == "sonnet"
    assert decision.es_escaneado is True
    assert decision.motivo == "sin_texto"
    assert llamadas["n"] == 0


def test_texto_limpio_se_queda_en_local():
    frase = "Presupuesto de prueba. Cubierta 80000 euros. Texto seleccionable suficiente."
    decision = decidir_lectura_pdf(
        _pdf(frase),
        forzar_vision=False,
        detectar_manuscrito=lambda _contenido: False,
    )
    assert decision.via == "texto_local"
    assert decision.es_escaneado is False
    assert decision.motivo == "limpio"
    assert "Cubierta" in decision.texto_local


def test_la_casilla_fuerza_sonnet_aunque_el_vistazo_diga_que_no():
    frase = "Contrato con texto seleccionable y precio cerrado de prueba suficiente."
    decision = decidir_lectura_pdf(
        _pdf(frase),
        forzar_vision=True,
        detectar_manuscrito=lambda _contenido: False,
    )
    assert decision.via == "sonnet"
    assert decision.es_escaneado is False
    assert decision.motivo == "forzar"


def test_un_tachon_de_ink_fuerza_sonnet_sin_vistazo():
    doc = pymupdf.open()
    pagina = doc.new_page()
    pagina.insert_text((72, 72), "Importe impreso 1000 euros. Texto largo de presupuesto de prueba.")
    pagina.add_ink_annot([[(80, 80), (160, 90), (200, 80)]])
    contenido = doc.tobytes()
    doc.close()
    llamadas = {"n": 0}

    def vistazo(_contenido: bytes) -> bool:
        llamadas["n"] += 1
        return False

    decision = decidir_lectura_pdf(contenido, forzar_vision=False, detectar_manuscrito=vistazo)
    assert decision.via == "sonnet"
    assert decision.motivo == "anotacion"
    assert llamadas["n"] == 0


def test_el_vistazo_en_true_manda_a_sonnet():
    frase = "Presupuesto con texto y una cifra que el vistazo marca como manuscrita."
    decision = decidir_lectura_pdf(
        _pdf(frase),
        forzar_vision=False,
        detectar_manuscrito=lambda _contenido: True,
    )
    assert decision.via == "sonnet"
    assert decision.motivo == "manuscrito"


def test_si_el_vistazo_falla_se_usa_sonnet():
    frase = "Presupuesto con texto. Si el vistazo rompe, no se pierde el tachón."

    def vistazo(_contenido: bytes) -> bool:
        raise RuntimeError("Haiku no aceptó el PDF")

    decision = decidir_lectura_pdf(_pdf(frase), forzar_vision=False, detectar_manuscrito=vistazo)
    assert decision.via == "sonnet"
    assert decision.motivo == "detector_fallo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lectura_pdf.py -v`

Expected: FAIL with `ModuleNotFoundError` on `app.services.lectura_pdf`.

- [ ] **Step 3: Write minimal implementation**

Create `app/services/lectura_pdf.py`:

```python
"""Elige si un PDF se lee del texto local o lo tiene que ver Sonnet.

Sonnet queda para el PDF sin texto, la casilla de manuscrito, una anotación
de corrección y el caso en que el vistazo ve bolígrafo o falla.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import pymupdf

from app.services import ocr as ocr_svc

Via = Literal["texto_local", "sonnet"]

# Tipos de anotación que pueden tapar una cifra. La firma (Widget) y el sello
# (Stamp) no entran: un contrato firmado en digital seguiría pagando Sonnet.
_TIPOS_CORRECCION = frozenset(
    {"Ink", "StrikeOut", "Squiggly", "Caret", "Highlight", "Underline", "FreeText"}
)


@dataclass(frozen=True)
class DecisionLectura:
    via: Via
    es_escaneado: bool
    texto_local: str
    motivo: str


def decidir_lectura_pdf(
    contenido: bytes,
    *,
    forzar_vision: bool,
    detectar_manuscrito: Callable[[bytes], bool],
) -> DecisionLectura:
    texto = _texto_pdf(contenido)
    escaneado = ocr_svc.pdf_parece_escaneado(texto)
    if escaneado:
        return DecisionLectura("sonnet", True, texto, "sin_texto")
    if forzar_vision:
        return DecisionLectura("sonnet", False, texto, "forzar")
    if _tiene_anotacion_de_correccion(contenido):
        return DecisionLectura("sonnet", False, texto, "anotacion")
    try:
        hay_manuscrito = detectar_manuscrito(contenido)
    except Exception:
        return DecisionLectura("sonnet", False, texto, "detector_fallo")
    if hay_manuscrito:
        return DecisionLectura("sonnet", False, texto, "manuscrito")
    return DecisionLectura("texto_local", False, texto, "limpio")


def _texto_pdf(contenido: bytes) -> str:
    doc = pymupdf.open(stream=contenido, filetype="pdf")
    try:
        texto = "\n".join(pagina.get_text() for pagina in doc)
    finally:
        doc.close()
    if not ocr_svc.pdf_parece_escaneado(texto):
        return texto
    return _texto_pdfplumber(contenido) or texto


def _texto_pdfplumber(contenido: bytes) -> str:
    import io

    import pdfplumber

    partes: list[str] = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            extraido = pagina.extract_text() or ""
            if extraido:
                partes.append(extraido)
    return "\n".join(partes)


def _tiene_anotacion_de_correccion(contenido: bytes) -> bool:
    doc = pymupdf.open(stream=contenido, filetype="pdf")
    try:
        for pagina in doc:
            anotaciones = pagina.annots()
            if anotaciones is None:
                continue
            for anotacion in anotaciones:
                nombre = anotacion.type[1] if anotacion.type else ""
                if nombre in _TIPOS_CORRECCION:
                    return True
        return False
    finally:
        doc.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lectura_pdf.py -v`

Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_lectura_pdf.py app/services/lectura_pdf.py
git commit -m "lectura: decide si el PDF con texto evita a Sonnet"
```

---

### Task 2: Vistazo de Haiku, y fallo equivale a Sonnet

**Files:**
- Modify: `app/services/lectura_pdf.py`
- Modify: `tests/test_lectura_pdf.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lectura_pdf.py`:

```python
from unittest.mock import patch

from app.services.lectura_pdf import detectar_manuscrito_haiku


def test_el_vistazo_de_haiku_lee_el_json_y_no_pide_markdown():
    frase = "Presupuesto con texto seleccionable suficiente para no parecer un escaneo."

    def completar_texto(**kwargs):
        assert kwargs["model"] == "claude-haiku-4-5"
        assert kwargs["documento_b64"]
        assert kwargs["max_tokens"] <= 400
        assert "tiene_manuscrito" in kwargs["system"]
        assert "No transcribas" in kwargs["system"]
        return '{"tiene_manuscrito": false}'

    with patch("app.services.lectura_pdf.llm_svc.completar_texto", side_effect=completar_texto):
        with patch("app.services.lectura_pdf.llm_svc.hay_llm", return_value=True):
            with patch("app.services.lectura_pdf.llm_svc.es_anthropic", return_value=True):
                with patch(
                    "app.services.lectura_pdf.llm_svc.modelo_extraccion",
                    return_value="claude-haiku-4-5",
                ):
                    assert detectar_manuscrito_haiku(_pdf(frase)) is False


def test_un_json_roto_del_vistazo_no_se_traga():
    with patch(
        "app.services.lectura_pdf.llm_svc.completar_texto",
        return_value="no es json",
    ):
        with patch("app.services.lectura_pdf.llm_svc.hay_llm", return_value=True):
            with patch("app.services.lectura_pdf.llm_svc.es_anthropic", return_value=True):
                with patch(
                    "app.services.lectura_pdf.llm_svc.modelo_extraccion",
                    return_value="claude-haiku-4-5",
                ):
                    try:
                        detectar_manuscrito_haiku(_pdf("texto " * 20))
                    except ValueError:
                        return
                    raise AssertionError("un vistazo ilegible tiene que fallar, no devolver false")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lectura_pdf.py::test_el_vistazo_de_haiku_lee_el_json_y_no_pide_markdown tests/test_lectura_pdf.py::test_un_json_roto_del_vistazo_no_se_traga -v`

Expected: FAIL with `ImportError` on `detectar_manuscrito_haiku`.

- [ ] **Step 3: Write minimal implementation**

Add these imports and this function to `app/services/lectura_pdf.py`. Keep `decidir_lectura_pdf` as it is: the caller passes `detectar_manuscrito_haiku` as the callback.

```python
import base64

from app.config import get_settings
from app.services import llm as llm_svc

_PROMPT_VISTA = """\
Miras un PDF de obra solo para detectar bolígrafo.
Respondes solo JSON: {"tiene_manuscrito": true} o {"tiene_manuscrito": false}.
true si un tachón, una cifra escrita a mano o una corrección tapa o cambia un valor impreso.
false si todo es texto impreso, firma digital o sello, sin corrección encima de una cifra.
No transcribas el documento y no inventes importes.
"""


def detectar_manuscrito_haiku(contenido: bytes) -> bool:
    """True si Haiku ve un tachón. Si la respuesta no es un bool, lanza ValueError."""
    settings = get_settings()
    if not (llm_svc.hay_llm(settings) and llm_svc.es_anthropic(settings)):
        raise ValueError("El vistazo de manuscrito pide la API de Claude")
    texto = llm_svc.completar_texto(
        api_key=settings.llm_api_key or "",
        api_base=settings.llm_api_base,
        anthropic=True,
        model=llm_svc.modelo_extraccion(settings),
        system=_PROMPT_VISTA,
        user="¿Hay una corrección manuscrita sobre un valor impreso?",
        documento_b64=base64.b64encode(contenido).decode("ascii"),
        documento_mime="application/pdf",
        max_tokens=200,
    )
    parsed = llm_svc.parsear_json_llm(texto)
    valor = parsed.get("tiene_manuscrito")
    if not isinstance(valor, bool):
        raise ValueError("el vistazo no devolvió tiene_manuscrito como bool")
    return valor
```

`decidir_lectura_pdf` already turns any exception of the callback into `motivo == "detector_fallo"` and `via == "sonnet"`. Do not catch `ValueError` inside `detectar_manuscrito_haiku`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lectura_pdf.py -v`

Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```powershell
git add app/services/lectura_pdf.py tests/test_lectura_pdf.py
git commit -m "lectura: Haiku solo dice si el PDF tiene tachón"
```

---

### Task 3: Presupuesto y contrato usan la decisión

**Files:**
- Modify: `app/services/ingesta.py` (`leer_presupuesto` around line 74, `leer_contrato` around line 281)
- Modify: `tests/test_extraccion_contrato_llm.py` (`test_pdf_de_contrato_lo_transcribe_sonnet`)
- Test: `tests/test_lectura_pdf.py` (append the wiring tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lectura_pdf.py`:

```python
def test_un_presupuesto_con_texto_no_llama_a_sonnet(monkeypatch):
    from app.services.ingesta import leer_presupuesto

    monkeypatch.setattr("app.services.ingesta.llm_svc.hay_llm", lambda _s: True)
    monkeypatch.setattr("app.services.ingesta.llm_svc.es_anthropic", lambda _s: True)
    monkeypatch.setattr(
        "app.services.ingesta.detectar_manuscrito_haiku",
        lambda _contenido: False,
    )

    def no_sonnet(_contenido: bytes) -> str:
        raise AssertionError("Sonnet no tiene que ver un PDF con texto limpio")

    monkeypatch.setattr("app.services.ingesta.transcribir_pdf_a_markdown", no_sonnet)
    frase = "Apartado cubierta por 80000 euros. Texto de presupuesto suficientemente largo."
    leido = leer_presupuesto(_pdf(frase), "presupuesto.pdf")
    assert leido.es_escaneado is False
    assert "cubierta" in leido.texto.lower()


def test_un_contrato_con_texto_no_llama_a_sonnet(monkeypatch):
    from app.services.ingesta import leer_contrato

    monkeypatch.setattr("app.services.ingesta.llm_svc.hay_llm", lambda _s: True)
    monkeypatch.setattr("app.services.ingesta.llm_svc.es_anthropic", lambda _s: True)
    monkeypatch.setattr(
        "app.services.ingesta.detectar_manuscrito_haiku",
        lambda _contenido: False,
    )

    def no_sonnet(_contenido: bytes) -> str:
        raise AssertionError("Sonnet no tiene que ver un contrato con texto limpio")

    monkeypatch.setattr("app.services.ingesta.transcribir_contrato_a_markdown", no_sonnet)
    frase = "Contrato de electricidad. Precio cerrado 45000 euros. Texto largo de prueba."
    leido = leer_contrato(_pdf(frase), "contrato.pdf")
    assert leido.es_escaneado is False
    assert "electricidad" in leido.texto.lower()


def test_si_el_vistazo_marca_manuscrito_el_contrato_sigue_en_sonnet(monkeypatch):
    from app.services.ingesta import leer_contrato

    monkeypatch.setattr("app.services.ingesta.llm_svc.hay_llm", lambda _s: True)
    monkeypatch.setattr("app.services.ingesta.llm_svc.es_anthropic", lambda _s: True)
    monkeypatch.setattr(
        "app.services.ingesta.detectar_manuscrito_haiku",
        lambda _contenido: True,
    )
    monkeypatch.setattr(
        "app.services.ingesta.transcribir_contrato_a_markdown",
        lambda _contenido: "markdown con (manuscrito)",
    )
    frase = "Contrato con texto seleccionable suficiente para no parecer escaneado."
    leido = leer_contrato(_pdf(frase), "contrato.pdf", forzar_vision=False)
    assert leido.texto == "markdown con (manuscrito)"
    assert leido.es_escaneado is False
```

Replace `test_pdf_de_contrato_lo_transcribe_sonnet` in `tests/test_extraccion_contrato_llm.py` with this version. The old assertion («un PDF con texto siempre llama a Sonnet») deja de ser el comportamiento:

```python
def test_pdf_de_contrato_con_texto_no_pasa_por_sonnet(monkeypatch):
    monkeypatch.setattr("app.services.ingesta.llm_svc.hay_llm", lambda _settings: True)
    monkeypatch.setattr("app.services.ingesta.llm_svc.es_anthropic", lambda _settings: True)
    monkeypatch.setattr(
        "app.services.ingesta.detectar_manuscrito_haiku",
        lambda _contenido: False,
    )
    llamado = {"sonnet": False}

    def transcribe(_contenido: bytes) -> str:
        llamado["sonnet"] = True
        return "markdown del contrato"

    monkeypatch.setattr("app.services.ingesta.transcribir_contrato_a_markdown", transcribe)
    frase = "Contrato de subcontrata con texto seleccionable y precio cerrado de prueba."
    leido = leer_contrato(_pdf_texto(frase), "contrato_prueba.pdf")
    assert llamado["sonnet"] is False
    assert "precio cerrado" in leido.texto
    assert leido.es_escaneado is False
```

Add this helper next to the imports of that test file:

```python
def _pdf_texto(frase: str) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    pagina = doc.new_page()
    pagina.insert_text((72, 72), frase)
    contenido = doc.tobytes()
    doc.close()
    return contenido
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lectura_pdf.py::test_un_presupuesto_con_texto_no_llama_a_sonnet tests/test_extraccion_contrato_llm.py::test_pdf_de_contrato_con_texto_no_pasa_por_sonnet -v`

Expected: FAIL. `leer_presupuesto` / `leer_contrato` still call Sonnet, or `leer_contrato` does not accept `forzar_vision` yet on the manuscrito test. The contrato test fails because `transcribir_contrato_a_markdown` is still called.

- [ ] **Step 3: Write minimal implementation**

In `app/services/ingesta.py`, import the decision helpers next to the transcription import:

```python
from app.services.lectura_pdf import DecisionLectura, decidir_lectura_pdf, detectar_manuscrito_haiku
```

Replace `leer_presupuesto` with:

```python
def leer_presupuesto(
    contenido: bytes,
    nombre_fichero: str,
    *,
    forzar_vision: bool = False,
) -> DocumentoLeido:
    """
    PDF con Claude y con texto: Haiku lee el texto local.
    PDF sin texto, con tachón o con la casilla marcada: Sonnet lo pasa a markdown.
    Sin clave de Claude, o si no es PDF, sigue la lectura anterior.
    """
    if not nombre_fichero.lower().endswith(".pdf"):
        return leer_documento(contenido, nombre_fichero)

    settings = get_settings()
    if not (llm_svc.hay_llm(settings) and llm_svc.es_anthropic(settings)):
        return leer_documento(contenido, nombre_fichero)

    decision = _decidir(contenido, forzar_vision)
    if decision.via == "sonnet":
        return DocumentoLeido(
            texto=transcribir_pdf_a_markdown(contenido),
            es_escaneado=decision.es_escaneado,
        )
    return DocumentoLeido(texto=decision.texto_local, es_escaneado=False)
```

Replace `leer_contrato` with the same shape, calling `transcribir_contrato_a_markdown`:

```python
def leer_contrato(
    contenido: bytes,
    nombre_fichero: str,
    *,
    forzar_vision: bool = False,
) -> DocumentoLeido:
    """Igual que el presupuesto: Sonnet solo si el texto local no basta."""
    if not nombre_fichero.lower().endswith(".pdf"):
        return leer_documento(contenido, nombre_fichero)

    settings = get_settings()
    if not (llm_svc.hay_llm(settings) and llm_svc.es_anthropic(settings)):
        return leer_documento(contenido, nombre_fichero)

    decision = _decidir(contenido, forzar_vision)
    if decision.via == "sonnet":
        return DocumentoLeido(
            texto=transcribir_contrato_a_markdown(contenido),
            es_escaneado=decision.es_escaneado,
        )
    return DocumentoLeido(texto=decision.texto_local, es_escaneado=False)


def _decidir(contenido: bytes, forzar_vision: bool) -> DecisionLectura:
    return decidir_lectura_pdf(
        contenido,
        forzar_vision=forzar_vision,
        detectar_manuscrito=detectar_manuscrito_haiku,
    )
```

Do not change `importar_presupuesto` or `importar_contrato` in this task: the default `forzar_vision=False` keeps their current call sites compiling.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lectura_pdf.py tests/test_extraccion_contrato_llm.py tests/test_llm_claude.py::test_pdf_sonnet_transcribe_y_haiku_extrae tests/test_presupuesto_escaneado.py -v`

Expected: PASS. The blank PDF test still sees two model calls. The scan test still mocks Sonnet when Claude is configured.

- [ ] **Step 5: Commit**

```powershell
git add app/services/ingesta.py tests/test_lectura_pdf.py tests/test_extraccion_contrato_llm.py
git commit -m "lectura: el PDF con texto del presupuesto y del contrato no pasa por Sonnet"
```

---

### Task 4: La casilla entra por el formulario

**Files:**
- Modify: `app/services/ingesta.py` (`importar_presupuesto`, `importar_contrato`)
- Modify: `app/services/presupuesto_excel.py` (`contrastar_presupuesto_cliente`)
- Modify: `app/routers/proyectos.py`
- Test: `tests/test_lectura_pdf.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lectura_pdf.py`:

```python
def test_la_casilla_del_formulario_fuerza_sonnet_en_el_contrato(client, monkeypatch):
    """POST con ver_pagina=1 transcribe aunque el vistazo diga que no hay tachón."""
    from app.models import Nave, Proyecto

    monkeypatch.setattr("app.services.ingesta.llm_svc.hay_llm", lambda _s: True)
    monkeypatch.setattr("app.services.ingesta.llm_svc.es_anthropic", lambda _s: True)
    monkeypatch.setattr(
        "app.services.ingesta.detectar_manuscrito_haiku",
        lambda _contenido: False,
    )
    visto = {"sonnet": False}

    def transcribe(_contenido: bytes) -> str:
        visto["sonnet"] = True
        return (
            "Contratista B00000001. Precio 1000.\n\n"
            "| codigo | descripcion | importe |\n| 1 | Sala | 1000 |"
        )

    monkeypatch.setattr("app.services.ingesta.transcribir_contrato_a_markdown", transcribe)
    monkeypatch.setattr(
        "app.services.extraccion_contrato.extraer_contrato",
        _contrato_falso,
    )

    from app.db import SessionLocal

    db = SessionLocal()
    proyecto = Proyecto(nombre="Obra casilla", tipo="reforma", estado="activa")
    db.add(proyecto)
    db.flush()
    db.add(Nave(proyecto_id=proyecto.id, codigo="01", descripcion="Nave", importe_presupuestado=0))
    db.commit()
    proyecto_id = proyecto.id
    db.close()

    frase = "Contrato con texto seleccionable suficiente para leerse sin Sonnet."
    response = client.post(
        f"/proyectos/{proyecto_id}/importar-contrato",
        files={"fichero": ("contrato.pdf", _pdf(frase), "application/pdf")},
        data={"ver_pagina": "1"},
    )
    assert response.status_code == 201, response.text
    assert visto["sonnet"] is True
```

Add these fixtures and the helper in the same file. `ContratoExtraido` exige `contratista_nif`, `contratista_nombre` y `precio_total`; el resto tiene valor por defecto.

```python
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

```python
from decimal import Decimal

from app.schemas.extraccion import ContratoExtraido


def _contrato_falso(_texto: str, _apartados: list) -> ContratoExtraido:
    return ContratoExtraido(
        contratista_nif="B00000001",
        contratista_nombre="Gremio de prueba",
        contratista_tipo="externo",
        precio_total=Decimal("1000.00"),
        requiere_revision=True,
        arbol_tareas=[],
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lectura_pdf.py::test_la_casilla_del_formulario_fuerza_sonnet_en_el_contrato -v`

Expected: FAIL. The endpoint ignores `ver_pagina` and the transcription mock is not called.

- [ ] **Step 3: Write minimal implementation**

In `app/routers/proyectos.py`, add a parser under the imports of services:

```python
def _ver_pagina(valor: str | None) -> bool:
    return (valor or "").strip().lower() in {"1", "true", "on", "si", "sí", "yes"}
```

`importar_presupuesto`:

```python
async def importar_presupuesto(
    fichero: UploadFile = File(...),
    ver_pagina: str = Form(""),
    db: Session = Depends(get_db),
) -> ImportarPresupuestoOut:
    # ... the empty-file checks stay ...
    return ingesta_svc.importar_presupuesto(
        db,
        contenido,
        fichero.filename,
        forzar_vision=_ver_pagina(ver_pagina),
    )
```

`contrastar_presupuesto_cliente`:

```python
async def contrastar_presupuesto_cliente(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    ver_pagina: str = Form(""),
    db: Session = Depends(get_db),
) -> ContrastarClienteOut:
    # ... empty checks stay ...
    return presupuesto_excel_svc.contrastar_presupuesto_cliente(
        db,
        proyecto_id,
        contenido,
        fichero.filename,
        forzar_vision=_ver_pagina(ver_pagina),
    )
```

`importar_contrato`:

```python
async def importar_contrato(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    nave_id: int | None = Form(default=None),
    ver_pagina: str = Form(""),
    db: Session = Depends(get_db),
) -> ImportarContratoOut:
    # ... empty checks stay ...
    return ingesta_svc.importar_contrato(
        db,
        proyecto_id,
        contenido,
        fichero.filename,
        nave_id=nave_id,
        forzar_vision=_ver_pagina(ver_pagina),
    )
```

`importar_presupuesto` in `app/services/ingesta.py`:

```python
def importar_presupuesto(
    db: Session,
    contenido: bytes,
    nombre_fichero: str,
    *,
    forzar_vision: bool = False,
) -> ImportarPresupuestoOut:
    leido = leer_presupuesto(contenido, nombre_fichero, forzar_vision=forzar_vision)
    extraido = extraccion_svc.extraer_presupuesto(leido.texto)
    if leido.es_escaneado:
        extraido = extraido.model_copy(update={"requiere_revision": True})
    return persistir_presupuesto(
        db,
        extraido,
        nombre_fichero,
        contenido,
        es_escaneado=leido.es_escaneado,
    )
```

`importar_contrato`: pass `forzar_vision` into `leer_contrato`. The rest of the function stays.

`contrastar_presupuesto_cliente` in `app/services/presupuesto_excel.py` gains `forzar_vision: bool = False` and calls:

```python
leido = leer_presupuesto(contenido, nombre_fichero, forzar_vision=forzar_vision)
```

A missing form field stays `""`, so the old clients keep the new default (text path). That is the change, not a break of the endpoint shape: the file field is still required and the response models do not change.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lectura_pdf.py tests/test_importar_contrato.py tests/test_importar_presupuesto.py tests/test_presupuesto_excel.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/routers/proyectos.py app/services/ingesta.py app/services/presupuesto_excel.py tests/test_lectura_pdf.py
git commit -m "lectura: la casilla ver_pagina fuerza la transcripción de Sonnet"
```

---

### Task 5: La casilla sobrevive si el contraste se relee

`obtener_contraste_cliente` vuelve a llamar a `leer_presupuesto` cuando el PDF del cliente no tiene líneas guardadas. Sin guardar la casilla, esa segunda lectura perdería el manuscrito que la persona marcó.

**Files:**
- Create: `migrations/versions/0013_presupuesto_ver_pagina.py`
- Modify: `app/models/presupuesto.py`
- Modify: `app/services/ingesta.py` (`persistir_presupuesto`)
- Modify: `app/services/presupuesto_excel.py` (`contrastar_presupuesto_cliente`, `obtener_contraste_cliente`)
- Test: `tests/test_lectura_pdf.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_releer_el_contraste_respeta_la_casilla(client, db, monkeypatch):
    from decimal import Decimal

    from app.models import Nave, Presupuesto, Proyecto, Tarea
    from app.schemas.extraccion import ApartadoExtraido, NaveExtraida, PresupuestoExtraido

    monkeypatch.setattr("app.services.ingesta.llm_svc.hay_llm", lambda _s: True)
    monkeypatch.setattr("app.services.ingesta.llm_svc.es_anthropic", lambda _s: True)
    monkeypatch.setattr(
        "app.services.ingesta.detectar_manuscrito_haiku",
        lambda _contenido: False,
    )
    visto = {"n": 0}

    def transcribe(_contenido: bytes) -> str:
        visto["n"] += 1
        return "Cubierta 80000"

    monkeypatch.setattr("app.services.ingesta.transcribir_pdf_a_markdown", transcribe)
    monkeypatch.setattr(
        "app.services.presupuesto_excel.extraccion_svc.extraer_presupuesto",
        lambda _texto: PresupuestoExtraido(
            nombre_proyecto="Obra relectura",
            naves=[
                NaveExtraida(
                    codigo="01",
                    descripcion="Nave",
                    apartados=[
                        ApartadoExtraido(
                            codigo="1.1",
                            descripcion="Cubierta",
                            importe=Decimal("80000"),
                        )
                    ],
                )
            ],
            total_impreso=Decimal("80000"),
        ),
    )
    monkeypatch.setattr(
        "app.services.presupuesto_excel._relacionar_pdf_llm",
        lambda *_args, **_kwargs: None,
    )

    proyecto = Proyecto(nombre="Obra relectura", tipo="reforma", estado="activa")
    db.add(proyecto)
    db.flush()
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="01",
        descripcion="Nave",
        importe_presupuestado=Decimal("0"),
    )
    db.add(nave)
    db.flush()
    excel = Presupuesto(
        proyecto_id=proyecto.id,
        version=1,
        fichero_origen="cubierta.xlsx",
        estado_extraccion="extraido",
        es_escaneado=False,
        formato="excel_expertis",
    )
    db.add(excel)
    db.flush()
    db.add(
        Tarea(
            nave_id=nave.id,
            presupuesto_id=excel.id,
            codigo="01.01",
            nivel="subapartado",
            descripcion="Cubierta",
            importe_presupuestado=Decimal("100"),
            estado_revision="pendiente",
            estado="no_iniciada",
            avance_fisico_pct=Decimal("0"),
        )
    )
    db.commit()

    frase = "PDF de cliente con texto seleccionable y un importe de cubierta."
    alta = client.post(
        f"/proyectos/{proyecto.id}/contrastar-presupuesto-cliente",
        files={"fichero": ("cliente.pdf", _pdf(frase), "application/pdf")},
        data={"ver_pagina": "1"},
    )
    assert alta.status_code == 201, alta.text
    assert visto["n"] == 1

    from app.services.presupuesto_excel import obtener_contraste_cliente

    db.expire_all()
    pdf_cliente = (
        db.query(Presupuesto)
        .filter(
            Presupuesto.proyecto_id == proyecto.id,
            Presupuesto.formato == "pdf_cliente",
        )
        .one()
    )
    from app.models import LineaPdfCliente

    db.query(LineaPdfCliente).filter(
        LineaPdfCliente.presupuesto_id == pdf_cliente.id,
        LineaPdfCliente.tipo == "importe",
    ).delete()
    db.commit()

    obtener_contraste_cliente(db, proyecto.id)
    assert visto["n"] == 2
```

No borres la `Tarea` del Excel: el contraste exige subapartados. `LineaPdfCliente` es el modelo de `app/models/linea_pdf_cliente.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lectura_pdf.py::test_releer_el_contraste_respeta_la_casilla -v`

Expected: FAIL. The second read does not call Sonnet (`visto["n"]` stays 1), or `Presupuesto` has no `ver_pagina`.

- [ ] **Step 3: Write minimal implementation**

`migrations/versions/0013_presupuesto_ver_pagina.py`:

```python
"""Casilla de manuscrito en el PDF de presupuesto.

Revision ID: 0013_presupuesto_ver_pagina
Revises: 0012_linea_pdf_contrato
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_presupuesto_ver_pagina"
down_revision: Union[str, Sequence[str], None] = "0012_linea_pdf_contrato"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "presupuesto",
        sa.Column(
            "ver_pagina",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("presupuesto", "ver_pagina")
```

On `Presupuesto`:

```python
# True si quien subió el PDF pidió que el modelo viera la página (tachón).
ver_pagina: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=False,
    server_default=sa.false(),
)
```

Add `import sqlalchemy as sa` only if the file does not already import it. `Boolean` is already imported. `server_default` needs `sa.false()`. Existing rows and the Excel presupuestos stay `false`.

`persistir_presupuesto` accepts `ver_pagina: bool = False` and sets it on the `Presupuesto(...)` it builds. `importar_presupuesto` passes `ver_pagina=forzar_vision`.

In `contrastar_presupuesto_cliente`, after building the `Presupuesto` of `formato="pdf_cliente"`, set `ver_pagina=forzar_vision` on that object before `db.add`.

In `obtener_contraste_cliente`, the re-read becomes:

```python
leido = leer_presupuesto(
    contenido,
    presupuesto.fichero_origen,
    forzar_vision=bool(presupuesto.ver_pagina),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lectura_pdf.py::test_releer_el_contraste_respeta_la_casilla -v`

Then: `alembic upgrade head` against the local database from `docs/arranque.md`, and `pytest tests/test_presupuesto_excel.py tests/test_lectura_pdf.py -q`.

Expected: PASS. `alembic upgrade head` applies `0013_presupuesto_ver_pagina`.

- [ ] **Step 5: Commit**

```powershell
git add migrations/versions/0013_presupuesto_ver_pagina.py app/models/presupuesto.py app/services/ingesta.py app/services/presupuesto_excel.py tests/test_lectura_pdf.py
git commit -m "lectura: la casilla del PDF de cliente se guarda para la relectura"
```

---

### Task 6: La casilla en las pantallas de subida

La casilla nace desmarcada. No cambia el texto de revisión ni bloquea el envío.

**Files:**
- Modify: `app/static/presupuesto.html`, `app/static/js/presupuesto.js`
- Modify: `app/static/contrato.html`, `app/static/js/contrato.js`
- Modify: `app/static/proyecto.html`, `app/static/js/proyecto.js`
- Modify: `app/static/index.html`, `app/static/js/obras.js`

- [ ] **Step 1: Add the control**

In each upload form, before the submit button, add:

```html
<label class="check-linea">
  <input type="checkbox" x-model="verPagina" />
  Este PDF tiene una corrección escrita a mano
</label>
```

Use the existing checkbox class if `check-linea` is not in `app/static/css/app.css`. Otherwise use a plain `<label>` with the checkbox. Do not add a new CSS file.

On `index.html`, the PDF de cliente is a drop zone, not a form. Put the checkbox just under the drop zone, inside the same `stack`, so a click on the checkbox does not open the file picker:

```html
<label @click.stop>
  <input type="checkbox" x-model="verPagina" />
  Este PDF tiene una corrección escrita a mano
</label>
```

- [ ] **Step 2: Send it only when it is checked**

In `presupuesto.js`, `contrato.js` and `proyecto.js`, add `verPagina: false` to the Alpine state. After appending the file:

```javascript
if (this.verPagina) {
  fd.append("ver_pagina", "1");
}
```

In `obras.js`, add `verPagina: false` to the component state. In `leerContratoCliente`:

```javascript
if (this.verPagina) {
  fd.append("ver_pagina", "1");
}
```

Reset `verPagina` to `false` after a successful contrast, next to `this.up = "done"`.

Unchecked sends nothing. The server treats that as false.

- [ ] **Step 3: Check the four screens in the browser**

With the app running as in `docs/arranque.md`:

1. Presupuesto: the checkbox is visible and unchecked. Submit still posts `fichero`.
2. Contrato, pantalla suelta y ficha de proyecto: igual, y `nave_id` sigue enviándose si se eligió nave.
3. Inicio, PDF del cliente: marcar la casilla y soltar un PDF manda `ver_pagina=1`. Pulsar la casilla no abre el selector de ficheros.

- [ ] **Step 4: Commit**

```powershell
git add app/static/presupuesto.html app/static/js/presupuesto.js app/static/contrato.html app/static/js/contrato.js app/static/proyecto.html app/static/js/proyecto.js app/static/index.html app/static/js/obras.js
git commit -m "lectura: casilla para que Sonnet vea un PDF con tachón"
```

---

### Task 7: La nota de coste dice lo que hace el código

**Files:**
- Modify: `docs/eficiencia_coste_analisis_ia.md`

- [ ] **Step 1: Replace the outdated paragraph**

In the section «Presupuesto y contrato: hoy el formato no cambia la factura», replace the paragraph that says a native PDF is still sent whole to Sonnet with:

```markdown
Con la clave de Claude, un PDF de presupuesto o de contrato que ya trae texto seleccionable no se envía a Sonnet. PyMuPDF (o pdfplumber si hace falta) saca el texto y Haiku rellena los campos. Sonnet sigue viendo el PDF cuando no hay texto útil, cuando la persona marca «corrección escrita a mano», cuando el PDF trae una anotación de corrección (tinta, tachado, resaltado) o cuando un vistazo de Haiku marca bolígrafo. Si ese vistazo falla, también entra Sonnet. Una firma digital no cuenta como tachón. La factura no cambia: la nativa sigue sin modelo y la escaneada sigue por OCR o por visión, una llamada por página.
```

Leave the price tables. They still describe the Sonnet path, which remains the path for scans.

- [ ] **Step 2: Commit**

```powershell
git add docs/eficiencia_coste_analisis_ia.md
git commit -m "docs: el PDF con texto ya no paga la transcripción de Sonnet"
```

---

## Self-review

- Cobertura: texto local, sin texto, casilla, anotación Ink, vistazo true, vistazo roto, contrato, contraste, relectura, pantallas, nota de coste. Facturas, Excel, fixtures e imágenes quedan fuera a propósito y con test viejo que sigue en verde.
- El nombre es `forzar_vision` en servicios, `ver_pagina` en formulario y columna, `detectar_manuscrito_haiku` en el vistazo, `DecisionLectura.motivo` con los seis valores del test.
- Un PDF en blanco no llama al vistazo, así que `test_pdf_sonnet_transcribe_y_haiku_extrae` sigue consumiendo exactamente dos respuestas mock.
- No hay pasos vacíos. `ContratoExtraido` se construye con `contratista_nif`, `contratista_nombre` y `precio_total`. La relectura borra filas de `LineaPdfCliente` con `tipo == "importe"`.
