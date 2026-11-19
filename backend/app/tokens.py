"""JWT de acesso HS256.

O token leva só ``sub`` (UUID do utilizador), ``iat``, ``exp`` e ``iss``.
Não leva email, palavra-passe, resumo nem permissões.
"""

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
_REQUIRED_CLAIMS = ["exp", "iat", "iss", "sub"]
# O identificador emitido é str(UUID): minúsculas e hífenes. URN, chavetas
# e a forma sem hífenes não são o formato desta aplicação.
_USER_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


class InvalidToken(Exception):
    """O token não pode ser aceite. A mensagem pública fica no endpoint."""


def _secret() -> str:
    return settings.jwt_secret.get_secret_value()


def issue_access_token(user_id: uuid.UUID, *, expires_in: int | None = None) -> str:
    lifetime = settings.jwt_expires_in if expires_in is None else expires_in
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=lifetime),
        "iss": settings.jwt_issuer,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def _unix_timestamp(value: object) -> None:
    """``iat`` e ``exp`` têm de ser inteiros. Booleano é subclasse de int."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError


def decode_access_token(token: str) -> uuid.UUID:
    """Valida assinatura, algoritmo, emissor, expiração e o UUID em ``sub``.

    A biblioteca aceita ``iat`` e ``exp`` em string, decimal ou booleano.
    Aqui só passa um inteiro. ``sub`` tem de ser o texto canónico do UUID.
    ``iss`` tem de ser a string configurada.
    """

    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer,
            leeway=0,
            options={"require": _REQUIRED_CLAIMS},
        )
        subject = payload["sub"]
        if not isinstance(subject, str) or _USER_ID.fullmatch(subject) is None:
            raise ValueError
        if not isinstance(payload["iss"], str):
            raise ValueError
        _unix_timestamp(payload["iat"])
        _unix_timestamp(payload["exp"])
        return uuid.UUID(subject)
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        logger.warning("Token rejeitado: %s", type(exc).__name__)
        raise InvalidToken from exc
