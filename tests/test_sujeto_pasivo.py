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
