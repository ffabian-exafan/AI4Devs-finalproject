"""Contrato: Sonnet transcribe, Haiku extrae y propone el apartado."""

from decimal import Decimal

from app.schemas.extraccion import ContratoExtraido
from app.services import extraccion_contrato as extraccion_svc
from app.services.ingesta import leer_contrato
from app.services.llm import parsear_json_llm


_JSON = """
{
  "contratista_nif": "B00000111",
  "contratista_nombre": "Gremio de prueba",
  "contratista_tipo": "externo",
  "referencia_presupuesto": "REF-1",
  "precio_total": 1200,
  "fecha_firma": "2026-03-01",
  "plazo_ejecucion": "no-es-fecha",
  "condiciones_facturacion": "Factura mensual",
  "requiere_revision": false,
  "apartado_sugerido_codigo": "2.1",
  "apartado_sugerido_motivo": "El objeto es la instalacion electrica",
  "arbol_tareas": [
    {
      "codigo": "1",
      "nivel": "apartado",
      "descripcion": "Cuadro de prueba",
      "importe": 1200,
      "hijos": [
        {
          "codigo": "1.1",
          "nivel": "partida",
          "descripcion": "Cable de prueba",
          "importe": 1200,
          "unidad": "ML",
          "cantidad": 10,
          "precio_unitario": 120
        }
      ]
    }
  ]
}
"""


def test_haiku_extrae_y_asigna_un_apartado_de_la_lista(monkeypatch):
    def falso(**_kwargs):
        assert _kwargs["model"]
        assert "2.1 · Electricidad de prueba" in _kwargs["user"]
        assert "Contrato de prueba" in _kwargs["user"]
        assert _kwargs["max_tokens"] >= 32000
        return _JSON

    monkeypatch.setattr(extraccion_svc.llm_svc, "hay_llm", lambda _settings: True)
    monkeypatch.setattr(extraccion_svc.llm_svc, "completar_texto", falso)
    monkeypatch.setattr(
        extraccion_svc.llm_svc,
        "modelo_extraccion",
        lambda _settings: "claude-haiku-4-5",
    )
    monkeypatch.setattr(extraccion_svc.llm_svc, "es_anthropic", lambda _settings: True)

    extraido = extraccion_svc.extraer_contrato(
        "Contrato de prueba",
        [("1.1", "Cubierta de prueba"), ("2.1", "Electricidad de prueba")],
    )

    assert isinstance(extraido, ContratoExtraido)
    assert extraido.contratista_nif == "B00000111"
    assert extraido.precio_total == Decimal("1200")
    assert extraido.requiere_revision is True
    assert extraido.plazo_ejecucion is None
    assert extraido.apartado_sugerido_codigo == "2.1"
    assert extraido.arbol_tareas[0].hijos[0].nivel == "partida"
    assert extraido.partidas_detalle == 1


def test_un_codigo_que_no_esta_en_el_presupuesto_no_se_asigna(monkeypatch):
    def falso(**_kwargs):
        return _JSON.replace("2.1", "9.9")

    monkeypatch.setattr(extraccion_svc.llm_svc, "hay_llm", lambda _settings: True)
    monkeypatch.setattr(extraccion_svc.llm_svc, "completar_texto", falso)
    monkeypatch.setattr(
        extraccion_svc.llm_svc,
        "modelo_extraccion",
        lambda _settings: "claude-haiku-4-5",
    )
    monkeypatch.setattr(extraccion_svc.llm_svc, "es_anthropic", lambda _settings: True)

    extraido = extraccion_svc.extraer_contrato(
        "Contrato de prueba",
        [("2.1", "Electricidad de prueba")],
    )
    assert extraido.apartado_sugerido_codigo is None


def _pdf_texto(frase: str) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    pagina = doc.new_page()
    pagina.insert_text((72, 72), frase)
    contenido = doc.tobytes()
    doc.close()
    return contenido


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


def test_un_json_cortado_a_mitad_de_texto_conserva_lo_completo():
    cortado = (
        "{\n"
        '  "contratista_nif": "B00000111",\n'
        '  "contratista_nombre": "Gremio de prueba",\n'
        '  "precio_total": 100,\n'
        '  "arbol_tareas": [\n'
        '    {"codigo": "1", "nivel": "apartado", "descripcion": "Linea completa", '
        '"importe": 100, "hijos": []},\n'
        '    {"codigo": "2", "nivel": "partida", "descripcion": "Texto que se corta'
    )
    parsed = parsear_json_llm(cortado)
    assert parsed["contratista_nif"] == "B00000111"
    assert parsed["precio_total"] == 100
    assert parsed["arbol_tareas"][0]["descripcion"] == "Linea completa"
    assert "Texto que se corta" not in str(parsed)
