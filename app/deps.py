"""Dependencias de autenticación."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    usuario_id = request.session.get("usuario_id")
    if not isinstance(usuario_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tienes que entrar para continuar.",
        )
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tienes que entrar para continuar.",
        )
    return usuario
