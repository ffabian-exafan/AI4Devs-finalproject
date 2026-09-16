"""Endpoints de carga, consulta y confirmación de facturas."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.factura import (
    ConfirmarFacturaIn,
    ConfirmarFacturaOut,
    FacturaImportacionOut,
    FacturaRevisionOut,
    FacturaResumenOut,
)
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


@router.post("/{factura_id}/confirmar", response_model=ConfirmarFacturaOut)
def confirmar_factura(
    factura_id: int,
    payload: ConfirmarFacturaIn,
    db: Session = Depends(get_db),
) -> ConfirmarFacturaOut:
    try:
        return facturas_svc.confirmar_factura(db, factura_id, payload)
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc
