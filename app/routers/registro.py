"""Consulta de solo lectura del registro."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_actual
from app.models import Usuario
from app.schemas.registro import RegistroFiltro, RegistroItem, RegistroPagina
from app.services.registro import ETIQUETAS, PAGE_SIZE, consultar, dia_hora

router = APIRouter(tags=["registro"])

ROLES_CONSULTA = {"direccion", "superadministrador"}


@router.get("/registro", response_model=RegistroPagina)
def listar_registro(
    page: int = Query(default=1, ge=1),
    usuario_id: int | None = None,
    accion: str | None = None,
    tipo_documento: str | None = None,
    dia: date | None = None,
    actual: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> RegistroPagina:
    if actual.rol not in ROLES_CONSULTA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La consulta es para dirección y el superadministrador.",
        )
    RegistroFiltro(
        page=page,
        usuario_id=usuario_id,
        accion=accion,
        tipo_documento=tipo_documento,
        dia=dia.isoformat() if dia else None,
    )
    filas, total = consultar(
        db,
        page=page,
        usuario_id=usuario_id,
        accion=accion,
        tipo_documento=tipo_documento,
        dia=dia,
    )
    return RegistroPagina(
        page=page,
        page_size=PAGE_SIZE,
        total=total,
        items=[
            RegistroItem(
                id=fila.id,
                ocurrido_en=fila.ocurrido_en,
                dia_hora=dia_hora(fila.ocurrido_en),
                nombre=fila.nombre_en_el_momento,
                accion=fila.accion,
                accion_etiqueta=ETIQUETAS[fila.accion],
                tipo_documento=fila.tipo_documento,
                documento_id=fila.documento_id,
                etiqueta=fila.etiqueta,
            )
            for fila in filas
        ],
    )
