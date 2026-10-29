"""Guarda en disco los documentos subidos a la obra."""

from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Iterable
from pathlib import Path

from app.config import get_settings

_TIPOS = frozenset({"presupuesto", "contrato", "factura"})
_RE_NOMBRE = re.compile(r"[^\w.\-]+", re.UNICODE)


def raiz() -> Path:
    return Path(get_settings().uploads_dir).expanduser().resolve()


def guardar(
    proyecto_id: int,
    tipo: str,
    registro_id: int,
    nombre_original: str,
    contenido: bytes,
) -> str:
    """Escribe el fichero y devuelve la ruta relativa a la raíz de uploads."""
    if tipo not in _TIPOS:
        raise ValueError(f"Tipo de documento no válido: {tipo}")
    if not contenido:
        raise ValueError("El fichero está vacío")

    seguro = _nombre_seguro(nombre_original)
    relativo = Path(str(proyecto_id)) / tipo / f"{registro_id}_{seguro}"
    destino = _dentro_raiz(relativo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".tmp")
    try:
        temporal.write_bytes(contenido)
        temporal.replace(destino)
    except Exception:
        if temporal.exists():
            temporal.unlink(missing_ok=True)
        raise
    return relativo.as_posix()


def ruta_absoluta(ruta_relativa: str) -> Path:
    return _dentro_raiz(Path(ruta_relativa))


def exigir_distinto(contenido: bytes, nombre: str, rutas: Iterable[str | None]) -> None:
    """No guarda otra vez un fichero que ya está en la obra. El nombre no decide."""
    if _ya_guardado(contenido, rutas):
        raise ValueError(f"«{_nombre_visible(nombre)}» ya está en esta obra")


def exigir_lote_distinto(ficheros: Iterable[tuple[str, bytes]]) -> None:
    """Rechaza el lote si dos ficheros traen los mismos bytes."""
    vistos: dict[bytes, str] = {}
    for nombre, contenido in ficheros:
        if not contenido:
            continue
        firma = hashlib.sha256(contenido).digest()
        visible = _nombre_visible(nombre)
        previo = vistos.get(firma)
        if previo is not None:
            raise ValueError(f"«{visible}» es el mismo fichero que «{previo}»")
        vistos[firma] = visible


def _ya_guardado(contenido: bytes, rutas: Iterable[str | None]) -> bool:
    if not contenido:
        return False
    firma = hashlib.sha256(contenido).digest()
    for relativa in rutas:
        ruta = abrir_si_existe(relativa)
        if ruta is None:
            continue
        if hashlib.sha256(ruta.read_bytes()).digest() == firma:
            return True
    return False


def _nombre_visible(nombre: str) -> str:
    base = Path(str(nombre).replace("\\", "/")).name.strip()
    return base or "El fichero"


def abrir_si_existe(ruta_relativa: str | None) -> Path | None:
    if not ruta_relativa:
        return None
    try:
        ruta = ruta_absoluta(ruta_relativa)
    except ValueError:
        return None
    if not ruta.is_file():
        return None
    return ruta


def borrar_proyecto(proyecto_id: int) -> None:
    """Borra la carpeta uploads/{proyecto_id} si existe."""
    carpeta = _dentro_raiz(Path(str(proyecto_id)))
    if carpeta == raiz():
        return
    if carpeta.is_dir():
        shutil.rmtree(carpeta)


def _nombre_seguro(nombre: str) -> str:
    base = Path(nombre.replace("\\", "/")).name.strip() or "documento"
    limpio = _RE_NOMBRE.sub("_", base).strip("._") or "documento"
    return limpio[:200]


def _dentro_raiz(relativo: Path) -> Path:
    raiz_abs = raiz()
    destino = (raiz_abs / relativo).resolve()
    if destino != raiz_abs and raiz_abs not in destino.parents:
        raise ValueError("Ruta de almacén fuera de la carpeta de uploads")
    return destino
