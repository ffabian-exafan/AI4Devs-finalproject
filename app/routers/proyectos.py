"""Endpoints de proyectos (ingesta de presupuesto y contrato)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.casado import EnlazarApartadoIn, EnlazarApartadoOut
from app.schemas.contrato import ImportarContratoOut
from app.schemas.control_economico import ControlEconomicoOut
from app.schemas.presupuesto import ImportarPresupuestoOut
from app.schemas.proyecto import ProyectoDetalleOut, ProyectoRead
from app.services import casado as casado_svc
from app.services import economico as economico_svc
from app.services import ingesta as ingesta_svc
from app.services import proyectos as proyectos_svc

router = APIRouter(tags=["proyectos"])


@router.get("/proyectos", response_model=list[ProyectoRead])
def listar_proyectos(db: Session = Depends(get_db)) -> list[ProyectoRead]:
    return proyectos_svc.listar_proyectos(db)


@router.get("/proyectos/{proyecto_id}", response_model=ProyectoDetalleOut)
def obtener_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db),
) -> ProyectoDetalleOut:
    try:
        return proyectos_svc.obtener_proyecto(db, proyecto_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/proyectos/importar-presupuesto",
    response_model=ImportarPresupuestoOut,
    status_code=status.HTTP_201_CREATED,
)
async def importar_presupuesto(
    fichero: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportarPresupuestoOut:
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
        return ingesta_svc.importar_presupuesto(db, contenido, fichero.filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/proyectos/{proyecto_id}/importar-contrato",
    response_model=ImportarContratoOut,
    status_code=status.HTTP_201_CREATED,
)
async def importar_contrato(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    nave_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> ImportarContratoOut:
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
        return ingesta_svc.importar_contrato(
            db,
            proyecto_id,
            contenido,
            fichero.filename,
            nave_id=nave_id,
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.post(
    "/proyectos/{proyecto_id}/contratos/{contrato_id}/enlazar-apartado",
    response_model=EnlazarApartadoOut,
)
def enlazar_apartado(
    proyecto_id: int,
    contrato_id: int,
    body: EnlazarApartadoIn,
    db: Session = Depends(get_db),
) -> EnlazarApartadoOut:
    try:
        contrato, apartado = casado_svc.enlazar_contrato_apartado(
            db,
            proyecto_id,
            contrato_id,
            body.tarea_apartado_id,
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc

    return EnlazarApartadoOut(
        contrato_id=contrato.id,
        tarea_apartado_id=apartado.id,
        codigo_apartado=apartado.codigo,
        descripcion_apartado=apartado.descripcion,
    )


@router.get(
    "/proyectos/{proyecto_id}/control-economico",
    response_model=ControlEconomicoOut,
)
def control_economico(
    proyecto_id: int,
    db: Session = Depends(get_db),
) -> ControlEconomicoOut:
    try:
        return economico_svc.control_economico(db, proyecto_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
