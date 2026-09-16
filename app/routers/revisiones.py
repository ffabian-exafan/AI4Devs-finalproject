"""Endpoints de revisión humana."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.revision import (
    ConfirmarRevisionIn,
    ConfirmarRevisionOut,
    DocumentoRevisionOut,
    RevisionPendienteOut,
)
from app.services import revision as revision_svc

router = APIRouter(prefix="/revisiones", tags=["revisiones"])


@router.get("/pendientes", response_model=list[RevisionPendienteOut])
def listar_pendientes(db: Session = Depends(get_db)) -> list[RevisionPendienteOut]:
    return revision_svc.listar_pendientes(db)


@router.get("/documento", response_model=DocumentoRevisionOut)
def obtener_documento(
    tipo: str = Query(..., pattern="^(presupuesto|contrato)$"),
    documento_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> DocumentoRevisionOut:
    try:
        return revision_svc.obtener_documento(db, tipo, documento_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/confirmar", response_model=ConfirmarRevisionOut)
def confirmar_revision(
    payload: ConfirmarRevisionIn,
    db: Session = Depends(get_db),
) -> ConfirmarRevisionOut:
    # Validación de forma: Pydantic (ConfirmarRevisionIn).
    # La de negocio (manuscritos, pertenencia) se repite en el servicio.
    try:
        return revision_svc.confirmar_revision(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
