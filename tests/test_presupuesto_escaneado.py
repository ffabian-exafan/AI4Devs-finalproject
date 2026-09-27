"""Tests de ingesta de presupuestos escaneados / imagen."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models import Presupuesto
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


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_fixture_md_no_es_escaneado(client: TestClient, db: Session):
    with FIXTURE_MD.open("rb") as fh:
        response = client.post(
            "/proyectos/importar-presupuesto",
            files={"fichero": (FIXTURE_MD.name, fh, "text/markdown")},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["es_escaneado"] is False
    assert body["requiere_revision"] is True

    db.expire_all()
    presupuestos = (
        db.query(Presupuesto)
        .filter(Presupuesto.proyecto_id == body["proyecto_id"])
        .all()
    )
    assert len(presupuestos) == 1
    assert presupuestos[0].es_escaneado is False


def test_imagen_jpg_pasa_por_ocr_y_marca_escaneado(client: TestClient, db: Session):
    texto_fixture = FIXTURE_MD.read_text(encoding="utf-8")
    # Cabecera JPEG mínima + bytes basura (el OCR está mockeado)
    jpeg_falso = b"\xff\xd8\xff\xe0" + b"\x00" * 64

    with patch(
        "app.services.ocr.ocr_imagen",
        return_value=ResultadoOcr(texto=texto_fixture, motor="mock"),
    ) as mock_ocr:
        response = client.post(
            "/proyectos/importar-presupuesto",
            files={"fichero": ("presupuesto_escaneado.jpg", jpeg_falso, "image/jpeg")},
        )

    assert response.status_code == 201, response.text
    mock_ocr.assert_called_once()
    body = response.json()
    assert body["es_escaneado"] is True
    assert body["requiere_revision"] is True
    assert body["partidas_detectadas"] >= 1

    db.expire_all()
    p = (
        db.query(Presupuesto)
        .filter(Presupuesto.proyecto_id == body["proyecto_id"])
        .one()
    )
    assert p.es_escaneado is True


def test_pdf_sin_texto_se_trata_como_escaneado(client: TestClient, db: Session):
    """PDF vacío de texto → OCR de páginas (mock)."""
    import pymupdf

    texto_fixture = FIXTURE_MD.read_text(encoding="utf-8")
    doc = pymupdf.open()
    page = doc.new_page()
    # Sin insertar texto: PDF “escaneado” vacío
    _ = page
    pdf_bytes = doc.tobytes()
    doc.close()

    with patch(
        "app.services.ingesta.transcribir_pdf_a_markdown",
        return_value=texto_fixture,
    ) as mock_md:
        with patch(
            "app.services.ocr.ocr_paginas_pdf",
            return_value=ResultadoOcr(texto=texto_fixture, motor="mock"),
        ) as mock_ocr:
            response = client.post(
                "/proyectos/importar-presupuesto",
                files={"fichero": ("presupuesto_scan.pdf", pdf_bytes, "application/pdf")},
            )

    assert response.status_code == 201, response.text
    from app.config import get_settings
    from app.services.llm import es_anthropic, hay_llm

    get_settings.cache_clear()
    if hay_llm(get_settings()) and es_anthropic(get_settings()):
        mock_md.assert_called_once()
        mock_ocr.assert_not_called()
    else:
        mock_ocr.assert_called_once()
    body = response.json()
    assert body["es_escaneado"] is True
    assert body["requiere_revision"] is True


def test_imagen_sin_ocr_disponible_devuelve_error_claro(client: TestClient, monkeypatch):
    import io

    from PIL import Image

    from app.config import get_settings

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("OCR_API_KEY", raising=False)
    monkeypatch.delenv("OCR_API_BASE", raising=False)
    get_settings.cache_clear()

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(200, 200, 200)).save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    with patch(
        "app.services.ocr._ocr_tesseract_opcional",
        side_effect=ValueError("Tesseract/pytesseract no disponible (opcional)"),
    ):
        response = client.post(
            "/proyectos/importar-presupuesto",
            files={"fichero": ("scan.jpg", jpeg_bytes, "image/jpeg")},
        )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "OCR" in detail or "LLM_API" in detail
