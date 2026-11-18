"""Carta del promotor y regla de IVA cero. No lee el PDF."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Factura, Proyecto, Usuario
from app.schemas.proyecto import ProyectoDetalleOut
from app.services import almacen as almacen_svc
from app.services import proyectos as proyectos_svc
from app.services.registro import registrar

AVISO_ISP = "La obra está en inversión del sujeto pasivo. El IVA tiene que ser 0."


def aviso_de(marcada: bool, iva) -> str | None:
    if marcada and iva != 0:
        return AVISO_ISP
    return None


def _exigir_pdf(nombre: str, contenido: bytes) -> None:
    if not contenido or not nombre.lower().endswith(".pdf") or not contenido.startswith(b"%PDF"):
        raise ValueError("La carta tiene que ser un PDF")


def marcar(
    db: Session,
    proyecto_id: int,
    usuario: Usuario,
    nombre: str,
    contenido: bytes,
) -> ProyectoDetalleOut:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    _exigir_pdf(nombre, contenido)
    if proyecto.ruta_carta_isp:
        almacen_svc.borrar_fichero(proyecto.ruta_carta_isp)
    proyecto.ruta_carta_isp = almacen_svc.guardar(
        proyecto_id, "carta_isp", proyecto_id, nombre, contenido
    )
    proyecto.fichero_carta_isp = Path(nombre).name[:512]
    proyecto.inversion_sujeto_pasivo = True
    db.query(Factura).filter(
        Factura.proyecto_id == proyecto_id,
        Factura.estado_revision == "confirmada",
        Factura.iva != 0,
    ).update({Factura.estado_revision: "pendiente"}, synchronize_session="fetch")
    registrar(
        db,
        usuario,
        "marcar_isp",
        tipo_documento="proyecto",
        documento_id=proyecto_id,
        etiqueta=proyecto.nombre,
    )
    db.commit()
    return proyectos_svc.obtener_proyecto(db, proyecto_id)


def quitar(db: Session, proyecto_id: int, usuario: Usuario) -> None:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    if proyecto.inversion_sujeto_pasivo or proyecto.ruta_carta_isp:
        almacen_svc.borrar_fichero(proyecto.ruta_carta_isp)
        proyecto.inversion_sujeto_pasivo = False
        proyecto.ruta_carta_isp = None
        proyecto.fichero_carta_isp = None
        registrar(
            db,
            usuario,
            "quitar_isp",
            tipo_documento="proyecto",
            documento_id=proyecto_id,
            etiqueta=proyecto.nombre,
        )
    db.commit()


def carta(db: Session, proyecto_id: int) -> tuple[str, str]:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None or not proyecto.ruta_carta_isp:
        raise ValueError(f"Carta {proyecto_id} no encontrado")
    return proyecto.ruta_carta_isp, proyecto.fichero_carta_isp or "carta.pdf"
