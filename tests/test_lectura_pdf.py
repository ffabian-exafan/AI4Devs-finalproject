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
