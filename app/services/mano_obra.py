"""Líneas y partes de la mano de obra propia."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.models import LineaManoObra, ParteTrabajo, Proyecto
from app.models.usuario import Usuario
from app.schemas.mano_obra import (
    ManoObraOut,
    NombreLineaIn,
    ParteActualizarIn,
    ParteManoObraOut,
    PrecioHoraIn,
)
from app.services import almacen as almacen_svc
from app.services import extraccion_parte
from app.services.extraccion_parte import AVISO_SIN_HORAS, CamposParte
from app.services.registro import registrar
from app.services.vista_obra import eur

_CENTIMO = Decimal("0.01")
_PRECIO = Decimal("0.0001")
_HORA = Decimal("0.01")
_EXTENSIONES = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


class Conflicto(ValueError):
    """El gesto choca con un parte ya confirmado."""


def bloque(db: Session, proyecto_id: int) -> ManoObraOut:
    obra = _obra(db, proyecto_id)
    lineas = _lineas(db, proyecto_id)
    horas_obra = Decimal("0")
    importe_obra = Decimal("0")
    salida = []
    for linea in lineas:
        partes = _orden_partes(linea.partes)
        horas, importe = _suma(partes)
        horas_obra += horas
        importe_obra += importe
        salida.append(
            {
                "id": linea.id,
                "nombre": linea.nombre,
                "horas": _txt_horas(horas),
                "acumulado": eur(importe, 2),
                "partes": [_parte_out(obra.id, parte) for parte in partes],
            }
        )
    return ManoObraOut(
        precio_hora=_txt_precio(obra.precio_hora),
        acumulado_horas=_txt_horas(horas_obra),
        acumulado=eur(importe_obra, 2),
        lineas=salida,
    )


def guardar_precio(
    db: Session,
    proyecto_id: int,
    datos: PrecioHoraIn,
    usuario: Usuario,
) -> ManoObraOut:
    obra = _obra(db, proyecto_id)
    obra.precio_hora = datos.precio_hora.quantize(_PRECIO)
    registrar(
        db,
        usuario,
        "guardar_precio_hora",
        tipo_documento="proyecto",
        documento_id=obra.id,
        etiqueta=obra.nombre,
    )
    db.commit()
    return bloque(db, proyecto_id)


def crear_linea(
    db: Session,
    proyecto_id: int,
    datos: NombreLineaIn,
) -> ManoObraOut:
    _obra(db, proyecto_id)
    db.add(LineaManoObra(proyecto_id=proyecto_id, nombre=datos.nombre))
    db.commit()
    return bloque(db, proyecto_id)


def renombrar_linea(
    db: Session,
    proyecto_id: int,
    linea_id: int,
    datos: NombreLineaIn,
) -> ManoObraOut:
    linea = _linea(db, proyecto_id, linea_id)
    linea.nombre = datos.nombre
    db.commit()
    return bloque(db, proyecto_id)


def borrar_linea(
    db: Session,
    proyecto_id: int,
    linea_id: int,
    usuario: Usuario,
) -> None:
    linea = _linea(db, proyecto_id, linea_id)
    if any(parte.estado_revision == "confirmada" for parte in linea.partes):
        raise Conflicto("Quita antes los partes confirmados.")
    nombre = linea.nombre
    for parte in list(linea.partes):
        almacen_svc.borrar_fichero(parte.ruta_almacen)
        db.delete(parte)
    registrar(
        db,
        usuario,
        "borrar_linea_mano_obra",
        tipo_documento="linea_mano_obra",
        documento_id=linea.id,
        etiqueta=nombre,
    )
    db.delete(linea)
    db.commit()


def subir_parte_directo(
    db: Session,
    proyecto_id: int,
    nombre: str,
    contenido: bytes,
) -> ManoObraOut:
    """El parte se sube a la obra. La línea solo guarda el nombre del fichero."""
    _obra(db, proyecto_id)
    _validar_fichero(nombre, contenido)
    titulo = Path(Path(nombre).name).stem.strip()[:255] or "Parte"
    linea = LineaManoObra(proyecto_id=proyecto_id, nombre=titulo)
    db.add(linea)
    db.flush()
    return subir_parte(db, proyecto_id, linea.id, nombre, contenido)


def subir_parte(
    db: Session,
    proyecto_id: int,
    linea_id: int,
    nombre: str,
    contenido: bytes,
) -> ManoObraOut:
    linea = _linea(db, proyecto_id, linea_id)
    _validar_fichero(nombre, contenido)
    rutas = [
        parte.ruta_almacen
        for parte in (
            db.query(ParteTrabajo)
            .join(LineaManoObra)
            .filter(LineaManoObra.proyecto_id == proyecto_id)
            .all()
        )
    ]
    almacen_svc.exigir_distinto(contenido, nombre, rutas)
    escaneado, campos = extraccion_parte.leer_campos(contenido, nombre)
    horas, aviso = _horas_leidas(campos)
    parte = ParteTrabajo(
        linea_mano_obra_id=linea.id,
        fichero_origen=Path(nombre).name,
        ruta_almacen="",
        es_escaneado=escaneado,
        horas=horas,
        fecha=campos.fecha,
        tiene_anotacion_manual=campos.tiene_anotacion_manual,
        aviso=aviso,
        estado_revision="pendiente",
    )
    db.add(parte)
    db.flush()
    parte.ruta_almacen = almacen_svc.guardar(
        proyecto_id,
        "parte",
        parte.id,
        nombre,
        contenido,
    )
    db.commit()
    return bloque(db, proyecto_id)


def actualizar_parte(
    db: Session,
    proyecto_id: int,
    parte_id: int,
    datos: ParteActualizarIn,
) -> ManoObraOut:
    parte = _parte(db, proyecto_id, parte_id)
    if parte.estado_revision == "confirmada":
        raise Conflicto("El parte ya está confirmado.")
    campos = datos.model_fields_set
    if "horas" in campos:
        parte.horas = None if datos.horas is None else datos.horas.quantize(_HORA)
        parte.aviso = None if parte.horas is not None else AVISO_SIN_HORAS
    if "fecha" in campos:
        parte.fecha = datos.fecha
    db.commit()
    return bloque(db, proyecto_id)


def confirmar_parte(
    db: Session,
    proyecto_id: int,
    parte_id: int,
    usuario: Usuario,
) -> ManoObraOut:
    obra = _obra(db, proyecto_id)
    parte = _parte(db, proyecto_id, parte_id)
    if parte.estado_revision == "confirmada":
        return bloque(db, proyecto_id)
    if obra.precio_hora is None or obra.precio_hora <= 0:
        raise ValueError("Falta el precio por hora de la obra.")
    if parte.horas is None or parte.horas <= 0:
        raise ValueError("Las horas tienen que ser mayores que cero.")
    precio = obra.precio_hora.quantize(_PRECIO)
    parte.precio_hora_aplicado = precio
    parte.importe = (parte.horas * precio).quantize(_CENTIMO, rounding=ROUND_HALF_UP)
    parte.estado_revision = "confirmada"
    parte.confirmada_por = usuario.nombre
    parte.confirmada_en = datetime.now(timezone.utc)
    parte.aviso = None
    registrar(
        db,
        usuario,
        "confirmar_parte",
        tipo_documento="parte_trabajo",
        documento_id=parte.id,
        etiqueta=parte.fichero_origen,
    )
    db.commit()
    return bloque(db, proyecto_id)


def borrar_parte(
    db: Session,
    proyecto_id: int,
    parte_id: int,
    usuario: Usuario,
) -> None:
    parte = _parte(db, proyecto_id, parte_id)
    etiqueta = parte.fichero_origen
    documento_id = parte.id
    almacen_svc.borrar_fichero(parte.ruta_almacen)
    registrar(
        db,
        usuario,
        "borrar_parte",
        tipo_documento="parte_trabajo",
        documento_id=documento_id,
        etiqueta=etiqueta,
    )
    db.delete(parte)
    db.commit()


def borrar_partes_de_la_obra(db: Session, proyecto_id: int) -> None:
    """Las quita antes de borrar la obra. La línea cae en cascada."""
    ids = [
        linea.id
        for linea in db.query(LineaManoObra)
        .filter(LineaManoObra.proyecto_id == proyecto_id)
        .all()
    ]
    if not ids:
        return
    db.query(ParteTrabajo).filter(ParteTrabajo.linea_mano_obra_id.in_(ids)).delete(
        synchronize_session=False
    )


def _lineas(db: Session, proyecto_id: int) -> list[LineaManoObra]:
    filas = (
        db.query(LineaManoObra)
        .options(joinedload(LineaManoObra.partes))
        .filter(LineaManoObra.proyecto_id == proyecto_id)
        .order_by(LineaManoObra.created_at, LineaManoObra.id)
        .all()
    )
    vistas: list[LineaManoObra] = []
    vistos: set[int] = set()
    for linea in filas:
        if linea.id in vistos:
            continue
        vistos.add(linea.id)
        vistas.append(linea)
    return vistas


def _obra(db: Session, proyecto_id: int) -> Proyecto:
    obra = db.get(Proyecto, proyecto_id)
    if obra is None:
        raise ValueError("No está en esta obra")
    return obra


def _linea(db: Session, proyecto_id: int, linea_id: int) -> LineaManoObra:
    linea = (
        db.query(LineaManoObra)
        .options(joinedload(LineaManoObra.partes))
        .filter(LineaManoObra.id == linea_id)
        .first()
    )
    if linea is None or linea.proyecto_id != proyecto_id:
        raise ValueError("No está en esta obra")
    return linea


def _parte(db: Session, proyecto_id: int, parte_id: int) -> ParteTrabajo:
    parte = (
        db.query(ParteTrabajo)
        .join(LineaManoObra)
        .filter(
            ParteTrabajo.id == parte_id,
            LineaManoObra.proyecto_id == proyecto_id,
        )
        .first()
    )
    if parte is None:
        raise ValueError("No está en esta obra")
    return parte


def _validar_fichero(nombre: str, contenido: bytes) -> None:
    if not contenido:
        raise ValueError("El fichero está vacío.")
    extension = Path(nombre).suffix.lower()
    if extension not in _EXTENSIONES:
        raise ValueError("El parte tiene que ser un PDF o una imagen.")
    if extension == ".pdf" and not contenido.startswith(b"%PDF"):
        raise ValueError("El PDF no es válido.")


def _horas_leidas(campos: CamposParte) -> tuple[Decimal | None, str | None]:
    if campos.horas is None or campos.horas <= 0:
        return None, AVISO_SIN_HORAS
    return campos.horas.quantize(_HORA), None


def _orden_partes(partes: list[ParteTrabajo]) -> list[ParteTrabajo]:
    return sorted(partes, key=lambda parte: (parte.fecha is None, parte.fecha or date.min, parte.id))


def _suma(partes: list[ParteTrabajo]) -> tuple[Decimal, Decimal]:
    confirmados = [parte for parte in partes if parte.estado_revision == "confirmada"]
    horas = sum((parte.horas or Decimal("0") for parte in confirmados), Decimal("0"))
    importe = sum((parte.importe or Decimal("0") for parte in confirmados), Decimal("0"))
    return horas, importe


def _parte_out(proyecto_id: int, parte: ParteTrabajo) -> ParteManoObraOut:
    return ParteManoObraOut(
        id=parte.id,
        archivo=parte.fichero_origen,
        tiene_fichero=bool(parte.ruta_almacen),
        url_fichero=f"/proyectos/{proyecto_id}/partes/{parte.id}/fichero",
        horas=_txt_horas(parte.horas) if parte.horas is not None else None,
        fecha=parte.fecha.isoformat() if parte.fecha else None,
        estado_revision=parte.estado_revision,
        es_escaneado=parte.es_escaneado,
        tiene_anotacion_manual=parte.tiene_anotacion_manual,
        aviso=parte.aviso,
        precio_hora_aplicado=_txt_precio(parte.precio_hora_aplicado),
        importe=eur(parte.importe, 2) if parte.importe is not None else None,
    )


def _txt_horas(valor: Decimal | None) -> str:
    cifra = Decimal("0") if valor is None else valor
    return f"{cifra.quantize(_HORA):.2f}"


def _txt_precio(valor: Decimal | None) -> str | None:
    if valor is None:
        return None
    return f"{valor.quantize(_PRECIO):.4f}"
