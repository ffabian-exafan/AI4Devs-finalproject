"""Endpoints de carga, consulta y confirmación de facturas."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_actual
from app.models import Factura, Usuario
from app.schemas.bandeja_factura import BandejaFacturaOut, BarridoOut
from app.schemas.factura import (
    CertificarMontajeOut,
    OmitirCertificacionOut,
    CodigoFacturaIn,
    CodigoFacturaOut,
    ConfirmarFacturaIn,
    ConfirmarFacturaOut,
    EnlazarContratoFacturaIn,
    FacturaImportacionOut,
    FacturaRevisionOut,
    FacturaResumenOut,
)
from app.routers.proyectos import _responder_fichero
from app.services import barrido_facturas as barrido_svc
from app.services import facturas as facturas_svc

router = APIRouter(prefix="/facturas", tags=["facturas"])


@router.post(
    "",
    response_model=FacturaImportacionOut,
    status_code=status.HTTP_201_CREATED,
)
async def importar_factura(
    proyecto_id: int = Form(..., ge=1),
    fichero: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> FacturaImportacionOut:
    if not fichero.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta el nombre del fichero",
        )
    contenido = await fichero.read()
    if not contenido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero está vacío",
        )
    try:
        return facturas_svc.importar_factura(
            db, proyecto_id, contenido, fichero.filename
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.get("", response_model=list[FacturaResumenOut])
def listar_facturas(
    proyecto_id: int,
    db: Session = Depends(get_db),
) -> list[FacturaResumenOut]:
    try:
        return facturas_svc.listar_facturas(db, proyecto_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/bandeja", response_model=list[BandejaFacturaOut])
def listar_bandeja(
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_actual),
) -> list[BandejaFacturaOut]:
    return barrido_svc.listar_bandeja(db)


@router.post("/bandeja/barrer", response_model=BarridoOut)
def barrer_bandeja(
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_actual),
) -> BarridoOut:
    if barrido_svc.carpeta_configurada() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No hay carpeta de facturas configurada.",
        )
    resultado = barrido_svc.barrer_configurado(db)
    return BarridoOut(
        nuevos=resultado.nuevos,
        ya_vistos=resultado.ya_vistos,
        omitidos=resultado.omitidos,
        errores=resultado.errores,
        aviso=resultado.aviso,
    )


@router.get("/{factura_id}", response_model=FacturaRevisionOut)
def obtener_factura(
    factura_id: int,
    db: Session = Depends(get_db),
) -> FacturaRevisionOut:
    try:
        return facturas_svc.obtener_factura(db, factura_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{factura_id}/omitir-certificacion-montaje",
    response_model=OmitirCertificacionOut,
)
def omitir_certificacion_montaje(
    factura_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> OmitirCertificacionOut:
    try:
        return facturas_svc.omitir_certificacion_montaje(db, factura_id, actual)
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrad" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.post("/{factura_id}/certificar-montaje", response_model=CertificarMontajeOut)
def certificar_montaje(
    factura_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> CertificarMontajeOut:
    try:
        return facturas_svc.certificar_montaje(db, factura_id, actual)
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrad" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.get("/{factura_id}/certificacion")
def descargar_certificacion(
    factura_id: int,
    ver: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    factura = db.get(Factura, factura_id)
    if factura is None or not factura.ruta_certificacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La certificación de montaje no está generada",
        )
    return _responder_fichero(
        factura.ruta_certificacion,
        "certificacion-montaje.pdf",
        ver=ver,
        ausente="La certificación de montaje no está generada",
    )


@router.get("/{factura_id}/sello")
def descargar_sello(
    factura_id: int,
    ver: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    factura = db.get(Factura, factura_id)
    if factura is None or not factura.ruta_sello:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El sello no está generado",
        )
    return _responder_fichero(
        factura.ruta_sello,
        "sello-factura.pdf",
        ver=ver,
        ausente="El sello no está generado",
    )


@router.post("/{factura_id}/codigo", response_model=CodigoFacturaOut)
def guardar_codigo_factura(
    factura_id: int,
    payload: CodigoFacturaIn,
    db: Session = Depends(get_db),
) -> CodigoFacturaOut:
    try:
        factura = facturas_svc.guardar_codigo_factura(db, factura_id, payload.codigo)
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrad" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc
    return CodigoFacturaOut(
        factura_id=factura.id,
        codigo_contrato=factura.codigo_contrato or payload.codigo,
        contrato_id=factura.contrato_id,
        aviso_codigo=factura.aviso_codigo,
    )


@router.post("/{factura_id}/contrato", response_model=FacturaResumenOut)
def enlazar_contrato(
    factura_id: int,
    payload: EnlazarContratoFacturaIn,
    db: Session = Depends(get_db),
) -> FacturaResumenOut:
    try:
        return facturas_svc.enlazar_contrato(db, factura_id, payload)
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.delete("/{factura_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_factura(
    factura_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> None:
    try:
        facturas_svc.borrar_factura(db, factura_id, actual)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{factura_id}/confirmar", response_model=ConfirmarFacturaOut)
def confirmar_factura(
    factura_id: int,
    payload: ConfirmarFacturaIn,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ConfirmarFacturaOut:
    try:
        return facturas_svc.confirmar_factura(db, factura_id, payload, actual)
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc
