"""Regras de conta partilhadas pelo comando local e pelo login.

Não há registo público. A criação fica no comando administrativo.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.identity import User, UserStatus
from app.passwords import (
    dummy_password_hash,
    hash_password,
    password_is_valid,
    verify_password,
)

EMAIL_MAX_LENGTH = 320


class AccountExists(Exception):
    """Já há uma conta com o mesmo email."""


def normalize_email(value: str) -> str:
    return value.strip().lower()


def email_is_valid(email: str) -> bool:
    """A mesma forma exigida pelo CHECK ``ck_users_email``."""

    if email != email.strip() or email != email.lower():
        return False
    if " " in email or not 3 <= len(email) <= EMAIL_MAX_LENGTH:
        return False
    at_sign = email.find("@")
    return at_sign > 0 and at_sign < len(email) - 1


def create_active_user(session: Session, email: str, password: str) -> User:
    """Cria uma conta ``active``. A palavra-passe fica só como resumo Argon2id."""

    normalized = normalize_email(email)
    if not email_is_valid(normalized):
        raise ValueError("Email inválido.")
    if not password_is_valid(password):
        raise ValueError("A palavra-passe não cumpre os requisitos.")

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
    )
    try:
        with session.begin_nested():
            session.add(user)
            session.flush()
    except IntegrityError as exc:
        raise AccountExists("Já existe uma conta com esse email.") from exc
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    """Devolve o utilizador activo ou None, sem distinguir o motivo.

    Conta inexistente, palavra-passe errada e conta desactivada percorrem
    todas uma verificação Argon2. A conta inexistente usa um resumo fictício.
    """

    normalized = normalize_email(email)
    user = session.scalar(select(User).where(User.email == normalized))
    stored_hash = user.password_hash if user is not None else dummy_password_hash()
    password_matches = verify_password(stored_hash, password)
    if user is None or not password_matches or user.status is not UserStatus.ACTIVE:
        return None
    return user
