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


def test_el_vistazo_de_haiku_lee_el_json_y_no_pide_markdown():
    from unittest.mock import patch

    from app.services.lectura_pdf import detectar_manuscrito_haiku

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
    from unittest.mock import patch

    from app.services.lectura_pdf import detectar_manuscrito_haiku

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


import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.schemas.extraccion import ContratoExtraido


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


def _contrato_falso(_texto: str, _apartados: list) -> ContratoExtraido:
    return ContratoExtraido(
        contratista_nif="B00000001",
        contratista_nombre="Gremio de prueba",
        contratista_tipo="externo",
        precio_total=Decimal("1000.00"),
        requiere_revision=True,
        arbol_tareas=[],
    )


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
