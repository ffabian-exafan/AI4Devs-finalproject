"""Barrido de la carpeta de facturas. No usa la unidad de red real."""

import hashlib
import os
import time
from datetime import datetime
from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import BandejaFactura, BarridoFactura, Factura
from app.services.barrido_facturas import (
    AVISO_CARPETA,
    AVISO_CARPETA_ILEGIBLE,
    AVISO_MES_DISTINTO,
    AVISO_SIN_CODIGO_FACTURA,
    AVISO_SIN_MES,
    barrer,
    espera_segundos,
    mes_de_carpeta,
)
from app.services.codigo_contrato import AVISO_SIN_CODIGO_FACTURA as AVISO_CODIGO
from tests.sesion import entrar

NUMEROS = (
    "F-BARRIDO-MAYO",
    "F-BARRIDO-SEPT",
    "F-BARRIDO-RAIZ",
    "F-BARRIDO-OTRA",
)


def test_mes_y_espera():
    assert mes_de_carpeta("MAYO") == 5
    assert mes_de_carpeta("septiembre") == 9
    assert mes_de_carpeta("OTRA") is None

    hora = 7
    antes = datetime(2026, 5, 2, 6, 30)
    assert espera_segundos(antes, hora, False) == 30 * 60
    a_la_hora = datetime(2026, 5, 2, 7, 0)
    assert espera_segundos(a_la_hora, hora, False) == 0
    assert espera_segundos(a_la_hora, hora, True) == 24 * 60 * 60
    despues = datetime(2026, 5, 2, 11, 0)
    assert espera_segundos(despues, hora, False) == 0
    assert espera_segundos(despues, hora, True) == 20 * 60 * 60


def test_barrido_lee_sin_tocar_el_original(tmp_path, monkeypatch):
    origen = tmp_path / "red"
    (origen / "MAYO").mkdir(parents=True)
    (origen / "OTRA").mkdir()
    _escribir(origen / "MAYO" / "mayo.pdf", "F-BARRIDO-MAYO", "02/05/2026", "PYCON000099")
    _escribir(origen / "MAYO" / "sept.pdf", "F-BARRIDO-SEPT", "15/09/2026")
    _escribir(origen / "raiz.pdf", "F-BARRIDO-RAIZ", "02/05/2026")
    _escribir(origen / "OTRA" / "otra.pdf", "F-BARRIDO-OTRA", "02/05/2026")
    recien = origen / "recien.pdf"
    _escribir(recien, "F-BARRIDO-RECIEN", "02/05/2026")

    viejo = time.time() - 86400
    for ruta in origen.rglob("*.pdf"):
        if ruta != recien:
            os.utime(ruta, (viejo, viejo))
    antes = _foto(origen)

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path / "uploads"))
    db = SessionLocal()
    ultimo = db.query(BarridoFactura.id).order_by(BarridoFactura.id.desc()).first()
    anterior = ultimo[0] if ultimo else 0
    try:
        primero = barrer(db, origen)
        assert primero.aviso is None
        assert primero.nuevos == 4
        assert primero.omitidos == 1
        assert primero.errores == 0
        assert _foto(origen) == antes

        mayo = _fila(db, origen / "MAYO" / "mayo.pdf")
        assert mayo.estado == "leida"
        assert mayo.mes_carpeta == 5
        assert mayo.aviso_mes is None
        assert mayo.numero == "F-BARRIDO-MAYO"
        assert mayo.nif_detectado == "B00000001"
        assert mayo.codigo_contrato == "PYCON000099"
        assert mayo.aviso_codigo is None
        assert mayo.factura_id is None
        assert mayo.ruta_copia
        copia = tmp_path / "uploads" / mayo.ruta_copia
        assert copia.read_bytes() == (origen / "MAYO" / "mayo.pdf").read_bytes()

        sept = _fila(db, origen / "MAYO" / "sept.pdf")
        assert sept.aviso_mes == AVISO_MES_DISTINTO
        assert sept.aviso_codigo == AVISO_SIN_CODIGO_FACTURA

        raiz = _fila(db, origen / "raiz.pdf")
        assert raiz.mes_carpeta is None
        assert raiz.aviso_mes == AVISO_SIN_MES

        otra = _fila(db, origen / "OTRA" / "otra.pdf")
        assert otra.aviso_mes == AVISO_CARPETA

        assert _fila(db, recien) is None
        assert (
            db.query(Factura).filter(Factura.numero.in_(NUMEROS)).count() == 0
        )

        segundo = barrer(db, origen)
        assert segundo.nuevos == 0
        assert segundo.ya_vistos == 4
        assert segundo.omitidos == 1
        assert _foto(origen) == antes
        assert db.query(BandejaFactura).filter(
            BandejaFactura.numero == "F-BARRIDO-MAYO"
        ).count() == 1
    finally:
        prefijo = os.path.normcase(os.path.abspath(str(origen))) + os.sep
        db.query(BandejaFactura).filter(BandejaFactura.ruta_red.startswith(prefijo)).delete(
            synchronize_session=False
        )
        db.query(BarridoFactura).filter(BarridoFactura.id > anterior).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_carpeta_ilegible_no_rompe(tmp_path):
    db = SessionLocal()
    ultimo = db.query(BarridoFactura.id).order_by(BarridoFactura.id.desc()).first()
    anterior = ultimo[0] if ultimo else 0
    try:
        resultado = barrer(db, tmp_path / "no-existe")
        assert resultado.aviso == AVISO_CARPETA_ILEGIBLE
        assert resultado.nuevos == 0
    finally:
        db.query(BarridoFactura).filter(BarridoFactura.id > anterior).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_endpoint_pide_sesion_y_carpeta(tmp_path, monkeypatch):
    origen = tmp_path / "red"
    origen.mkdir()
    _escribir(origen / "raiz.pdf", "F-BARRIDO-API", "02/05/2026")
    os.utime(origen / "raiz.pdf", (time.time() - 86400, time.time() - 86400))
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(get_settings(), "facturas_red_dir", "")

    db = SessionLocal()
    ultimo = db.query(BarridoFactura.id).order_by(BarridoFactura.id.desc()).first()
    anterior = ultimo[0] if ultimo else 0
    try:
        with TestClient(app) as client:
            assert client.post("/facturas/bandeja/barrer").status_code == 401
            entrar(client, db)
            vacio = client.post("/facturas/bandeja/barrer")
            assert vacio.status_code == 422

            monkeypatch.setattr(get_settings(), "facturas_red_dir", str(origen))
            hecho = client.post("/facturas/bandeja/barrer")
            assert hecho.status_code == 200, hecho.text
            assert hecho.json()["nuevos"] == 1
            assert hecho.json()["aviso"] is None

            lista = client.get("/facturas/bandeja")
            assert lista.status_code == 200
            nombres = [fila["nombre_fichero"] for fila in lista.json()]
            assert "raiz.pdf" in nombres
            fila = next(item for item in lista.json() if item["numero"] == "F-BARRIDO-API")
            assert fila["factura_id"] is None
            assert fila["aviso_mes"] == AVISO_SIN_MES
    finally:
        prefijo = os.path.normcase(os.path.abspath(str(origen))) + os.sep
        db.query(BandejaFactura).filter(BandejaFactura.ruta_red.startswith(prefijo)).delete(
            synchronize_session=False
        )
        db.query(BarridoFactura).filter(BarridoFactura.id > anterior).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def _escribir(ruta: Path, numero: str, fecha: str, codigo: str | None = None) -> None:
    lineas = [
        "Emisor: SUBCONTRATISTA_1",
        "NIF: B00000001",
        f"Factura: {numero}",
        f"Fecha de emisión: {fecha}",
        "Tipo: certificacion",
        "Base imponible: 100,00 EUR",
        "IVA 21%: 21,00 EUR",
        "Total factura: 121,00 EUR",
    ]
    if codigo:
        lineas.append(codigo)
    documento = pymupdf.open()
    pagina = documento.new_page()
    y = 72
    for linea in lineas:
        pagina.insert_text((72, y), linea, fontsize=11)
        y += 18
    ruta.write_bytes(documento.tobytes())
    documento.close()


def _foto(carpeta: Path) -> dict[str, tuple[int, str]]:
    foto: dict[str, tuple[int, str]] = {}
    for ruta in carpeta.rglob("*"):
        if not ruta.is_file():
            continue
        foto[ruta.relative_to(carpeta).as_posix()] = (
            ruta.stat().st_mtime_ns,
            hashlib.sha256(ruta.read_bytes()).hexdigest(),
        )
    return foto


def _fila(db: Session, ruta: Path) -> BandejaFactura | None:
    clave = os.path.normcase(os.path.abspath(str(ruta)))
    return db.query(BandejaFactura).filter(BandejaFactura.ruta_red == clave).one_or_none()


def test_aviso_codigo_es_el_del_modulo():
    assert AVISO_SIN_CODIGO_FACTURA == AVISO_CODIGO
