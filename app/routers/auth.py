"""Entrada y salida de la sesión."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_actual
from app.models import Usuario
from app.schemas.usuario import LoginIn, UsuarioRead
from app.services import usuarios as usuarios_svc
from app.services.registro import registrar

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=UsuarioRead)
def login(datos: LoginIn, request: Request, db: Session = Depends(get_db)) -> Usuario:
    usuario = usuarios_svc.autenticar(db, str(datos.email), datos.password)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El correo o la clave no son válidos.",
        )
    registrar(db, usuario, "inicio_sesion")
    db.commit()
    request.session["usuario_id"] = usuario.id
    return usuario


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/yo", response_model=UsuarioRead)
def yo(actual: Usuario = Depends(usuario_actual)) -> Usuario:
    return actual
