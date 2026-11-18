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
