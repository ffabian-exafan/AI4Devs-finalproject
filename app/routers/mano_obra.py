"""Precio por hora, líneas y partes de la mano de obra propia."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_actual
from app.models import ParteTrabajo, Usuario
from app.routers.proyectos import _responder_fichero
from app.schemas.mano_obra import ManoObraOut, NombreLineaIn, ParteActualizarIn, PrecioHoraIn
from app.services import mano_obra as mano_obra_svc
from app.services.mano_obra import Conflicto

router = APIRouter()


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, Conflicto):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    detail = str(exc)
    codigo = (
        status.HTTP_404_NOT_FOUND
        if detail == "No está en esta obra"
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return HTTPException(status_code=codigo, detail=detail)


@router.patch("/proyectos/{proyecto_id}/precio-hora", response_model=ManoObraOut)
def guardar_precio(
    proyecto_id: int,
    datos: PrecioHoraIn,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ManoObraOut:
    try:
        return mano_obra_svc.guardar_precio(db, proyecto_id, datos, actual)
    except (Conflicto, ValueError) as exc:
        raise _http(exc) from exc


@router.post(
    "/proyectos/{proyecto_id}/lineas-mano-obra",
    response_model=ManoObraOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_linea(
    proyecto_id: int,
    datos: NombreLineaIn,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ManoObraOut:
    del actual
    try:
        return mano_obra_svc.crear_linea(db, proyecto_id, datos)
    except (Conflicto, ValueError) as exc:
        raise _http(exc) from exc


@router.patch(
    "/proyectos/{proyecto_id}/lineas-mano-obra/{linea_id}",
    response_model=ManoObraOut,
)
def renombrar_linea(
    proyecto_id: int,
    linea_id: int,
    datos: NombreLineaIn,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ManoObraOut:
    del actual
    try:
        return mano_obra_svc.renombrar_linea(db, proyecto_id, linea_id, datos)
    except (Conflicto, ValueError) as exc:
        raise _http(exc) from exc


@router.delete(
    "/proyectos/{proyecto_id}/lineas-mano-obra/{linea_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def borrar_linea(
    proyecto_id: int,
    linea_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> Response:
    try:
        mano_obra_svc.borrar_linea(db, proyecto_id, linea_id, actual)
    except (Conflicto, ValueError) as exc:
        raise _http(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/proyectos/{proyecto_id}/partes",
    response_model=ManoObraOut,
    status_code=status.HTTP_201_CREATED,
)
async def subir_parte_directo(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ManoObraOut:
    del actual
    contenido = await fichero.read()
    try:
        return mano_obra_svc.subir_parte_directo(
            db,
            proyecto_id,
            fichero.filename or "parte",
            contenido,
        )
    except (Conflicto, ValueError) as exc:
        raise _http(exc) from exc


@router.post(
    "/proyectos/{proyecto_id}/lineas-mano-obra/{linea_id}/partes",
    response_model=ManoObraOut,
    status_code=status.HTTP_201_CREATED,
)
async def subir_parte(
    proyecto_id: int,
    linea_id: int,
    fichero: UploadFile = File(...),
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ManoObraOut:
    del actual
    contenido = await fichero.read()
    try:
        return mano_obra_svc.subir_parte(
            db,
            proyecto_id,
            linea_id,
            fichero.filename or "parte",
            contenido,
        )
    except (Conflicto, ValueError) as exc:
        raise _http(exc) from exc


@router.get("/proyectos/{proyecto_id}/partes/{parte_id}/fichero")
def descargar_parte(
    proyecto_id: int,
    parte_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> FileResponse:
    del actual
    parte = (
        db.query(ParteTrabajo)
        .join(ParteTrabajo.linea)
        .filter(
            ParteTrabajo.id == parte_id,
            ParteTrabajo.linea.has(proyecto_id=proyecto_id),
        )
        .first()
    )
    if parte is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No está en esta obra")
    return _responder_fichero(parte.ruta_almacen, parte.fichero_origen)


@router.patch(
    "/proyectos/{proyecto_id}/partes/{parte_id}",
    response_model=ManoObraOut,
)
def actualizar_parte(
    proyecto_id: int,
    parte_id: int,
    datos: ParteActualizarIn,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ManoObraOut:
    del actual
    try:
        return mano_obra_svc.actualizar_parte(db, proyecto_id, parte_id, datos)
    except (Conflicto, ValueError) as exc:
        raise _http(exc) from exc


@router.post(
    "/proyectos/{proyecto_id}/partes/{parte_id}/confirmar",
    response_model=ManoObraOut,
)
def confirmar_parte(
    proyecto_id: int,
    parte_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ManoObraOut:
    try:
        return mano_obra_svc.confirmar_parte(db, proyecto_id, parte_id, actual)
    except (Conflicto, ValueError) as exc:
        raise _http(exc) from exc


@router.delete(
    "/proyectos/{proyecto_id}/partes/{parte_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def borrar_parte(
    proyecto_id: int,
    parte_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> Response:
    try:
        mano_obra_svc.borrar_parte(db, proyecto_id, parte_id, actual)
    except (Conflicto, ValueError) as exc:
        raise _http(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
