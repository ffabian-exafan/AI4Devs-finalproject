"""Único escritor del registro. No hace commit."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models import Usuario
from app.models.registro_accion import ACCIONES, RegistroAccion

ZONA = ZoneInfo("Europe/Madrid")
PAGE_SIZE = 50

ETIQUETAS = {
    "confirmar_revision": "Confirmó la revisión",
    "confirmar_factura": "Confirmó la factura",
    "certificar_montaje": "Certificó el montaje",
    "omitir_certificacion_montaje": "Marcó que el montaje no necesita sello",
    "confirmar_importe_cliente": "Confirmó el importe de cliente",
    "confirmar_importes_cliente": "Confirmó los importes de cliente",
    "confirmar_solo_gestion": "Confirmó el apartado de solo gestión",
    "borrar_proyecto": "Borró el proyecto",
    "borrar_contrato": "Borró el contrato",
    "borrar_factura": "Borró la factura",
    "borrar_linea": "Borró la línea",
    "inicio_sesion": "Entró",
    "marcar_isp": "Marcó la inversión del sujeto pasivo",
    "quitar_isp": "Quitó la inversión del sujeto pasivo",
    "guardar_precio_hora": "Guardó el precio por hora",
    "borrar_linea_mano_obra": "Borró la línea de mano de obra",
    "confirmar_parte": "Confirmó el parte",
    "borrar_parte": "Borró el parte",
}

if set(ETIQUETAS) != set(ACCIONES):
    raise RuntimeError("El catálogo de etiquetas no coincide con las acciones")


def registrar(
    db: Session,
    usuario: Usuario,
    accion: str,
    tipo_documento: str | None = None,
    documento_id: int | None = None,
    etiqueta: str | None = None,
) -> RegistroAccion:
    if accion not in ACCIONES:
        raise ValueError(f"Acción desconocida: {accion}")
    if accion == "inicio_sesion":
        if tipo_documento is not None or documento_id is not None or etiqueta is not None:
            raise ValueError("El inicio de sesión no lleva documento")
    else:
        if not tipo_documento or documento_id is None or not etiqueta or not etiqueta.strip():
            raise ValueError("La acción de obra exige documento y etiqueta")
        etiqueta = etiqueta.strip()[:255]
    fila = RegistroAccion(
        usuario_id=usuario.id,
        nombre_en_el_momento=usuario.nombre,
        accion=accion,
        tipo_documento=tipo_documento,
        documento_id=documento_id,
        etiqueta=etiqueta,
    )
    db.add(fila)
    return fila


def dia_hora(instante: datetime) -> str:
    return instante.astimezone(ZONA).strftime("%d/%m/%Y %H:%M")


def consultar(
    db: Session,
    *,
    page: int,
    usuario_id: int | None = None,
    accion: str | None = None,
    tipo_documento: str | None = None,
    dia: date | None = None,
) -> tuple[list[RegistroAccion], int]:
    consulta = db.query(RegistroAccion)
    if usuario_id is not None:
        consulta = consulta.filter(RegistroAccion.usuario_id == usuario_id)
    if accion:
        consulta = consulta.filter(RegistroAccion.accion == accion)
    if tipo_documento:
        consulta = consulta.filter(RegistroAccion.tipo_documento == tipo_documento)
    if dia is not None:
        inicio = datetime.combine(dia, time.min, tzinfo=ZONA)
        fin = inicio + timedelta(days=1)
        consulta = consulta.filter(
            RegistroAccion.ocurrido_en >= inicio,
            RegistroAccion.ocurrido_en < fin,
        )
    total = consulta.count()
    filas = (
        consulta.order_by(RegistroAccion.ocurrido_en.desc(), RegistroAccion.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )
    return filas, total
