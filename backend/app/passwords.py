"""Resumo Argon2id das palavras-passe.

O texto simples só existe em memória durante a criação da conta ou o
login. A base guarda o resumo. Um resumo inválido ou diferente recusa
a verificação, sem distinguir o motivo ao chamador.
"""

import secrets

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
_dummy_hash = _hasher.hash(secrets.token_urlsafe(32))


def password_is_valid(password: str) -> bool:
    return PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH


def hash_password(password: str) -> str:
    """Calcula um resumo Argon2id. Não regista a palavra-passe."""

    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Devolve True só quando o resumo corresponde à palavra-passe."""

    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, TypeError, ValueError):
        return False


def dummy_password_hash() -> str:
    """Resumo fictício para contas inexistentes.

    Verificar este resumo aproxima o tempo de resposta do de uma conta
    real, sem revelar se o email existe.
    """

    return _dummy_hash
