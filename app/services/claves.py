"""Hash de contraseña. Argon2, como prevé docs/readme.md §2.5."""

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_clave(clave: str) -> str:
    return _hasher.hash(clave)


def clave_valida(hash_guardado: str, clave: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, clave)
    except (VerifyMismatchError, VerificationError):
        return False
