"""Gestión de quien entra en la app."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Asignacion, Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.services.claves import clave_valida, hash_clave


class EmailDuplicado(Exception):
    """El email ya pertenece a otro usuario."""


class UsuarioNoEncontrado(Exception):
    """No hay fila con ese id."""


class NoPuedeBorrarse(Exception):
    """La sesión actual no puede borrarse a sí misma."""


class UsuarioConRevisiones(Exception):
    """Hay asignaciones con revisado_por apuntando a este usuario."""


def buscar_por_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))


def autenticar(db: Session, email: str, password: str) -> Usuario | None:
    usuario = buscar_por_email(db, email)
    if usuario is None or not clave_valida(usuario.password_hash, password):
        return None
    return usuario


def listar(db: Session) -> list[Usuario]:
    return list(db.scalars(select(Usuario).order_by(Usuario.nombre, Usuario.id)))


def crear(db: Session, datos: UsuarioCreate) -> Usuario:
    usuario = Usuario(
        nombre=datos.nombre,
        email=str(datos.email),
        rol=datos.rol,
        password_hash=hash_clave(datos.password),
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailDuplicado from exc
    db.refresh(usuario)
    return usuario


def actualizar(db: Session, usuario_id: int, datos: UsuarioUpdate) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNoEncontrado
    cambios = datos.model_dump(exclude_unset=True)
    if "password" in cambios:
        clave = cambios.pop("password")
        if clave:
            usuario.password_hash = hash_clave(clave)
    if cambios.get("nombre"):
        usuario.nombre = cambios["nombre"]
    if cambios.get("email"):
        usuario.email = str(cambios["email"])
    if cambios.get("rol"):
        usuario.rol = cambios["rol"]
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailDuplicado from exc
    db.refresh(usuario)
    return usuario


def borrar(db: Session, usuario_id: int, actor_id: int) -> None:
    if usuario_id == actor_id:
        raise NoPuedeBorrarse
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNoEncontrado
    tiene_revision = db.scalar(
        select(Asignacion.id).where(Asignacion.revisado_por == usuario_id)
    )
    if tiene_revision is not None:
        raise UsuarioConRevisiones
    db.delete(usuario)
    db.commit()
