"""Barrido diario de la carpeta de facturas pendientes.

La carpeta de red solo se lee. No se mueve, renombra, borra ni modifica ningún PDF.
La copia queda en uploads/bandeja. La factura de obra se crea más adelante, al asignar
el proyecto. El contrato se enlaza entonces con el código que ya implementa facturas.py.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BandejaFactura, BarridoFactura
from app.services import almacen as almacen_svc
from app.services.codigo_contrato import (
    AVISO_SIN_CODIGO_FACTURA,
    AVISO_VARIOS,
    codigos_en_texto,
)
from app.services.facturas import _extraer_texto, _parsear_factura

logger = logging.getLogger(__name__)

AVISO_SIN_MES = "Sin carpeta de mes."
AVISO_CARPETA = "La carpeta no es un mes."
AVISO_MES_DISTINTO = "El mes de la carpeta no coincide con la fecha de la factura."
AVISO_SIN_FECHA = "La factura no trae fecha para contrastar con la carpeta."
AVISO_CARPETA_ILEGIBLE = "No se puede leer la carpeta de facturas."
AVISO_EN_CURSO = "Ya hay un barrido en curso."

_MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_candado = threading.Lock()


@dataclass
class ResultadoBarrido:
    nuevos: int = 0
    ya_vistos: int = 0
    omitidos: int = 0
    errores: int = 0
    aviso: str | None = None


def mes_de_carpeta(nombre: str) -> int | None:
    clave = unicodedata.normalize("NFD", nombre.strip())
    clave = "".join(c for c in clave if unicodedata.category(c) != "Mn")
    return _MESES.get(clave.casefold())


def espera_segundos(ahora: datetime, hora: int, ya_corrio_hoy: bool) -> float:
    """Segundos hasta el próximo barrido. 0 si hoy toca y aún no ha corrido."""
    slot = ahora.replace(hour=hora, minute=0, second=0, microsecond=0)
    if ahora >= slot and not ya_corrio_hoy:
        return 0
    if ahora < slot:
        return (slot - ahora).total_seconds()
    return (slot + timedelta(days=1) - ahora).total_seconds()


def programar_barrido() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return bool(get_settings().facturas_red_dir.strip())


def carpeta_configurada() -> Path | None:
    texto = get_settings().facturas_red_dir.strip()
    if not texto:
        return None
    return Path(texto)


def barrer_configurado(db: Session) -> ResultadoBarrido:
    carpeta = carpeta_configurada()
    if carpeta is None:
        return ResultadoBarrido(aviso="No hay carpeta de facturas configurada.")
    return barrer(db, carpeta)


def barrer(db: Session, raiz: Path) -> ResultadoBarrido:
    if not _candado.acquire(blocking=False):
        return ResultadoBarrido(aviso=AVISO_EN_CURSO)
    iniciado = datetime.now(timezone.utc)
    try:
        resultado = _barrer(db, raiz)
        db.add(
            BarridoFactura(
                iniciado_en=iniciado,
                terminado_en=datetime.now(timezone.utc),
                nuevos=resultado.nuevos,
                ya_vistos=resultado.ya_vistos,
                omitidos=resultado.omitidos,
                errores=resultado.errores,
                aviso=resultado.aviso,
            )
        )
        db.commit()
        logger.info(
            "Barrido de facturas: nuevos=%s ya_vistos=%s omitidos=%s errores=%s",
            resultado.nuevos,
            resultado.ya_vistos,
            resultado.omitidos,
            resultado.errores,
        )
        return resultado
    except Exception:
        db.rollback()
        logger.exception("El barrido de facturas no ha terminado")
        raise
    finally:
        _candado.release()


def ya_corrio_hoy(db: Session, ahora: datetime | None = None) -> bool:
    ahora = ahora or datetime.now().astimezone()
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    fin = inicio + timedelta(days=1)
    return (
        db.query(BarridoFactura.id)
        .filter(BarridoFactura.iniciado_en >= inicio, BarridoFactura.iniciado_en < fin)
        .first()
        is not None
    )


def _barrer(db: Session, raiz: Path) -> ResultadoBarrido:
    resultado = ResultadoBarrido()
    try:
        if not raiz.is_dir():
            resultado.aviso = AVISO_CARPETA_ILEGIBLE
            return resultado
        candidatos = list(_candidatos(raiz))
    except OSError:
        resultado.aviso = AVISO_CARPETA_ILEGIBLE
        return resultado

    estabilidad = get_settings().facturas_barrido_estabilidad_segundos
    ahora = datetime.now(timezone.utc).timestamp()
    for ruta, mes, aviso_carpeta in candidatos:
        try:
            _leer_uno(db, ruta, mes, aviso_carpeta, ahora, estabilidad, resultado)
            db.commit()
        except Exception:
            db.rollback()
            resultado.errores += 1
            logger.exception("No se pudo registrar un PDF del barrido")
    return resultado


def _candidatos(raiz: Path):
    for entrada in raiz.iterdir():
        if entrada.is_symlink():
            continue
        if entrada.is_file() and _es_pdf(entrada):
            yield entrada, None, AVISO_SIN_MES
            continue
        if not entrada.is_dir():
            continue
        mes = mes_de_carpeta(entrada.name)
        aviso = None if mes is not None else AVISO_CARPETA
        try:
            hijos = list(entrada.iterdir())
        except OSError:
            continue
        for hijo in hijos:
            if hijo.is_symlink() or not hijo.is_file() or not _es_pdf(hijo):
                continue
            yield hijo, mes, aviso


def _leer_uno(
    db: Session,
    ruta: Path,
    mes: int | None,
    aviso_carpeta: str | None,
    ahora_ts: float,
    estabilidad: int,
    resultado: ResultadoBarrido,
) -> None:
    info = ruta.stat()
    edad = ahora_ts - info.st_mtime
    if edad < estabilidad:
        resultado.omitidos += 1
        return

    clave = _clave_ruta(ruta)
    previo = (
        db.query(BandejaFactura)
        .filter(BandejaFactura.ruta_red == clave)
        .order_by(BandejaFactura.id.desc())
        .first()
    )
    if (
        previo is not None
        and not previo.reintentar
        and previo.tamano == info.st_size
        and int(previo.modificado_en.timestamp()) == int(info.st_mtime)
    ):
        resultado.ya_vistos += 1
        return

    contenido = _leer_sin_modificar(ruta)
    firma = hashlib.sha256(contenido).hexdigest()
    conocido = (
        db.query(BandejaFactura).filter(BandejaFactura.hash_sha256 == firma).one_or_none()
    )
    modificado = datetime.fromtimestamp(info.st_mtime, tz=timezone.utc)
    if conocido is not None and not conocido.reintentar:
        conocido.ruta_red = clave
        conocido.nombre_fichero = ruta.name
        conocido.tamano = info.st_size
        conocido.modificado_en = modificado
        conocido.mes_carpeta = mes
        conocido.aviso_mes = _aviso_mes(mes, aviso_carpeta, conocido.fecha_emision)
        resultado.ya_vistos += 1
        return

    if not contenido:
        _guardar_fila(
            db,
            conocido,
            firma=firma,
            ruta=ruta,
            clave=clave,
            tamano=info.st_size,
            modificado=modificado,
            mes=mes,
            aviso_mes=_aviso_mes(mes, aviso_carpeta, None),
            es_escaneada=False,
            estado="error",
            reintentar=False,
            aviso="El fichero está vacío",
            ruta_copia=None,
            datos=None,
            codigo=None,
            aviso_codigo=None,
        )
        resultado.errores += 1
        return

    try:
        texto, es_escaneada = _extraer_texto(contenido, ruta.name)
    except ValueError as exc:
        copia = almacen_svc.guardar_bandeja(firma, ruta.name, contenido)
        _guardar_fila(
            db,
            conocido,
            firma=firma,
            ruta=ruta,
            clave=clave,
            tamano=info.st_size,
            modificado=modificado,
            mes=mes,
            aviso_mes=_aviso_mes(mes, aviso_carpeta, None),
            es_escaneada=False,
            estado="error",
            reintentar=True,
            aviso=str(exc),
            ruta_copia=copia,
            datos=None,
            codigo=None,
            aviso_codigo=None,
        )
        resultado.errores += 1
        return

    codigo, aviso_codigo = _codigo_leido(texto)
    try:
        datos = _parsear_factura(texto)
    except ValueError as exc:
        copia = almacen_svc.guardar_bandeja(firma, ruta.name, contenido)
        _guardar_fila(
            db,
            conocido,
            firma=firma,
            ruta=ruta,
            clave=clave,
            tamano=info.st_size,
            modificado=modificado,
            mes=mes,
            aviso_mes=_aviso_mes(mes, aviso_carpeta, None),
            es_escaneada=es_escaneada,
            estado="error",
            reintentar=False,
            aviso=str(exc),
            ruta_copia=copia,
            datos=None,
            codigo=codigo,
            aviso_codigo=aviso_codigo,
        )
        resultado.errores += 1
        return

    copia = almacen_svc.guardar_bandeja(firma, ruta.name, contenido)
    _guardar_fila(
        db,
        conocido,
        firma=firma,
        ruta=ruta,
        clave=clave,
        tamano=info.st_size,
        modificado=modificado,
        mes=mes,
        aviso_mes=_aviso_mes(mes, aviso_carpeta, datos["fecha_emision"]),
        es_escaneada=es_escaneada,
        estado="leida",
        reintentar=False,
        aviso=None,
        ruta_copia=copia,
        datos=datos,
        codigo=codigo,
        aviso_codigo=aviso_codigo,
    )
    if conocido is None:
        resultado.nuevos += 1
    else:
        resultado.ya_vistos += 1


def _guardar_fila(
    db: Session,
    conocido: BandejaFactura | None,
    *,
    firma: str,
    ruta: Path,
    clave: str,
    tamano: int,
    modificado: datetime,
    mes: int | None,
    aviso_mes: str | None,
    es_escaneada: bool,
    estado: str,
    reintentar: bool,
    aviso: str | None,
    ruta_copia: str | None,
    datos: dict | None,
    codigo: str | None,
    aviso_codigo: str | None,
) -> None:
    fila = conocido or BandejaFactura(hash_sha256=firma, leido_en=datetime.now(timezone.utc))
    fila.ruta_red = clave
    fila.nombre_fichero = ruta.name
    fila.tamano = tamano
    fila.modificado_en = modificado
    fila.mes_carpeta = mes
    fila.aviso_mes = aviso_mes
    fila.es_escaneada = es_escaneada
    fila.estado = estado
    fila.reintentar = reintentar
    fila.aviso = aviso
    fila.ruta_copia = ruta_copia
    fila.codigo_contrato = codigo
    fila.aviso_codigo = aviso_codigo
    fila.leido_en = datetime.now(timezone.utc)
    if datos is None:
        fila.nif_detectado = None
        fila.numero = None
        fila.fecha_emision = None
        fila.base_imponible = None
        fila.iva = None
        fila.irpf = None
        fila.retencion_garantia = None
        fila.total = None
        fila.tipo = None
    else:
        fila.nif_detectado = datos["contratista_nif"]
        fila.numero = datos["numero"]
        fila.fecha_emision = datos["fecha_emision"]
        fila.base_imponible = datos["base_imponible"]
        fila.iva = datos["iva"]
        fila.irpf = datos["irpf"]
        fila.retencion_garantia = datos["retencion_garantia"]
        fila.total = datos["total"]
        fila.tipo = datos["tipo"]
    if conocido is None:
        fila.factura_id = None
        db.add(fila)


def _codigo_leido(texto: str) -> tuple[str | None, str | None]:
    """Lee el código del PDF. No busca ni modifica el contrato."""
    encontrados = codigos_en_texto(texto)
    if len(encontrados) > 1:
        return None, AVISO_VARIOS
    if not encontrados:
        return None, AVISO_SIN_CODIGO_FACTURA
    return encontrados[0], None


def _aviso_mes(mes: int | None, aviso_carpeta: str | None, fecha) -> str | None:
    if aviso_carpeta:
        return aviso_carpeta
    if mes is None:
        return None
    if fecha is None:
        return AVISO_SIN_FECHA
    if fecha.month != mes:
        return AVISO_MES_DISTINTO
    return None


def _leer_sin_modificar(ruta: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    fd = os.open(ruta, flags)
    try:
        trozos: list[bytes] = []
        while True:
            bloque = os.read(fd, 1024 * 1024)
            if not bloque:
                break
            trozos.append(bloque)
        return b"".join(trozos)
    finally:
        os.close(fd)


def _clave_ruta(ruta: Path) -> str:
    return os.path.normcase(os.path.abspath(str(ruta)))


def _es_pdf(ruta: Path) -> bool:
    return ruta.suffix.lower() == ".pdf"


def listar_bandeja(db: Session) -> list[BandejaFactura]:
    return (
        db.query(BandejaFactura)
        .order_by(BandejaFactura.mes_carpeta.asc().nullsfirst(), BandejaFactura.nombre_fichero)
        .all()
    )


async def bucle_barrido_diario() -> None:
    """Duerme hasta la hora configurada y lee la carpeta una vez al día."""
    import asyncio

    while True:
        try:
            espera = await asyncio.to_thread(_espera_de_hoy)
        except Exception:
            logger.exception("No se pudo calcular el próximo barrido")
            espera = 300
        await asyncio.sleep(max(espera, 1))
        try:
            await asyncio.to_thread(_ejecutar_programado)
        except Exception:
            logger.exception("El barrido programado ha fallado")
            await asyncio.sleep(300)


def _espera_de_hoy() -> float:
    from app.db import SessionLocal

    hora = get_settings().facturas_barrido_hora
    db = SessionLocal()
    try:
        corrio = ya_corrio_hoy(db)
    finally:
        db.close()
    return espera_segundos(datetime.now().astimezone(), hora, corrio)


def _ejecutar_programado() -> ResultadoBarrido:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        return barrer_configurado(db)
    finally:
        db.close()
