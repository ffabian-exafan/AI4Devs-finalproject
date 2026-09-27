"""Tests OCR cloud-first (sin Tesseract de sistema)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import ocr as ocr_svc
from app.services.ocr import ResultadoOcr

FIXTURE_MD = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "presupuesto_nave_destete_anonimizado.md"
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _limpiar_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_ocr_usa_llm_vision_sin_tesseract(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_API_BASE", "https://ejemplo.test/v1")
    monkeypatch.delenv("OCR_API_KEY", raising=False)
    monkeypatch.delenv("OCR_API_BASE", raising=False)
    get_settings.cache_clear()

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

    with patch("app.services.ocr._a_png", return_value=(png, "image/png")):
        with patch(
            "app.services.ocr._ocr_llm_vision",
            return_value=ResultadoOcr(texto="Apartado 8.2 Electricidad", motor="llm_vision"),
        ) as mock_vision:
            with patch(
                "app.services.ocr._ocr_tesseract_opcional",
                side_effect=ValueError("no tesseract"),
            ):
                r = ocr_svc.ocr_imagen(png)

    assert r.motor == "llm_vision"
    assert "Electricidad" in r.texto
    mock_vision.assert_called_once()


def test_ocr_prioriza_api_dedicada(monkeypatch):
    monkeypatch.setenv("OCR_API_KEY", "ocr-key")
    monkeypatch.setenv("OCR_API_BASE", "https://ocr.test/v1/ocr")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.setenv("LLM_API_BASE", "https://llm.test/v1")
    get_settings.cache_clear()

    png = b"fake"
    with patch("app.services.ocr._a_png", return_value=(png, "image/png")):
        with patch(
            "app.services.ocr._ocr_api_dedicada",
            return_value=ResultadoOcr(texto="texto api", motor="ocr_cloud"),
        ) as mock_api:
            with patch("app.services.ocr._ocr_llm_vision") as mock_llm:
                r = ocr_svc.ocr_imagen(png)

    assert r.motor == "ocr_cloud"
    mock_api.assert_called_once()
    mock_llm.assert_not_called()


def test_importar_jpg_con_vision_mock(client: TestClient, monkeypatch):
    import io

    from PIL import Image

    texto = FIXTURE_MD.read_text(encoding="utf-8")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_API_BASE", "https://ejemplo.test/v1")
    get_settings.cache_clear()

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    with patch(
        "app.services.ocr._ocr_llm_vision",
        return_value=ResultadoOcr(texto=texto, motor="llm_vision"),
    ):
        response = client.post(
            "/proyectos/importar-presupuesto",
            files={"fichero": ("scan.jpg", jpeg_bytes, "image/jpeg")},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["es_escaneado"] is True
    assert body["requiere_revision"] is True


def test_sin_claves_cloud_error_claro(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("OCR_API_KEY", raising=False)
    monkeypatch.delenv("OCR_API_BASE", raising=False)
    get_settings.cache_clear()

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    with patch("app.services.ocr._a_png", return_value=(png, "image/png")):
        with patch(
            "app.services.ocr._ocr_tesseract_opcional",
            side_effect=ValueError("Tesseract/pytesseract no disponible (opcional)"),
        ):
            with pytest.raises(ValueError, match="OCR_API_KEY|LLM_API_KEY"):
                ocr_svc.ocr_imagen(png)


def test_post_json_llm_vision_parsea_choices(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_API_BASE", "https://ejemplo.test/v1")
    monkeypatch.setenv("LLM_PROVEEDOR", "openai")
    get_settings.cache_clear()

    import json

    raw = json.dumps(
        {"choices": [{"message": {"content": "Línea 1\nElectricidad 8.2"}}]}
    ).encode("utf-8")

    class _Resp:
        def read(self):
            return raw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("app.services.llm.request.urlopen", return_value=_Resp()):
        r = ocr_svc._ocr_llm_vision(
            b"abc",
            mime="image/png",
            api_key="k",
            api_base="https://ejemplo.test/v1",
            model="gpt-4o-mini",
        )
    assert "Electricidad" in r.texto
    assert r.motor == "llm_vision"
