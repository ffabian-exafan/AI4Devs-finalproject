"""Alta, edición y baja de quien usa la app.

[VERIFICAR] Quién puede gestionar usuarios no está cerrado en docs/readme.md.
De momento basta con haber entrado: los tres roles pueden hacerlo.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_actual
from app.models import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioRead, UsuarioUpdate
from app.services import usuarios as usuarios_svc

router = APIRouter(tags=["usuarios"])


@router.get("/usuarios", response_model=list[UsuarioRead])
def listar(
    db: Session = Depends(get_db),
    _actual: Usuario = Depends(usuario_actual),
) -> list[Usuario]:
    return usuarios_svc.listar(db)


@router.post("/usuarios", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def crear(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    _actual: Usuario = Depends(usuario_actual),
) -> Usuario:
    try:
        return usuarios_svc.crear(db, datos)
    except usuarios_svc.EmailDuplicado as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay un usuario con ese correo.",
        ) from exc


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioRead)
def actualizar(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: Session = Depends(get_db),
    _actual: Usuario = Depends(usuario_actual),
) -> Usuario:
    try:
        return usuarios_svc.actualizar(db, usuario_id, datos)
    except usuarios_svc.UsuarioNoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe ese usuario.",
        ) from exc
    except usuarios_svc.EmailDuplicado as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay un usuario con ese correo.",
        ) from exc


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(
    usuario_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> None:
    try:
        usuarios_svc.borrar(db, usuario_id, actual.id)
    except usuarios_svc.NoPuedeBorrarse as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes borrar tu propio usuario.",
        ) from exc
    except usuarios_svc.UsuarioNoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe ese usuario.",
        ) from exc
    except usuarios_svc.UsuarioConRevisiones as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este usuario tiene revisiones y no se puede borrar.",
        ) from exc
