"""Almacén de documentos en disco."""

from pathlib import Path

from app.config import get_settings
from app.services import almacen as almacen_svc


def test_guarda_y_abre_el_fichero(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()

    ruta = almacen_svc.guardar(
        7,
        "presupuesto",
        3,
        r"C:\obra\ventilacion ficticia.xlsm",
        b"contenido-ficticio",
    )
    assert ruta == "7/presupuesto/3_ventilacion_ficticia.xlsm"
    absoluto = almacen_svc.abrir_si_existe(ruta)
    assert absoluto is not None
    assert absoluto.read_bytes() == b"contenido-ficticio"
    assert absoluto.parent == Path(tmp_path).resolve() / "7" / "presupuesto"
    get_settings.cache_clear()


def test_rechaza_ruta_fuera_de_uploads(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    assert almacen_svc.abrir_si_existe("../secreto.txt") is None
    assert almacen_svc.abrir_si_existe(None) is None
    get_settings.cache_clear()


def test_borrar_proyecto_quita_su_carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    almacen_svc.guardar(9, "contrato", 1, "contrato-ficticio.pdf", b"pdf")
    carpeta = Path(tmp_path).resolve() / "9"
    assert carpeta.is_dir()
    almacen_svc.borrar_proyecto(9)
    assert not carpeta.exists()
    almacen_svc.borrar_proyecto(9)
    get_settings.cache_clear()
