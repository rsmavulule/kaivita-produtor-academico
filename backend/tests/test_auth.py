"""Autenticação: comando local, Argon2id, login e JWT.

Os pedidos HTTP que tocam na base só correm com RUN_DB_TESTS=1.
Cada um usa uma transacção que é desfeita no fim.
"""

import json
import logging
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounts import AccountExists, authenticate, create_active_user
from app.config import settings
from app.create_user import main, read_password
from app.db import engine, get_session
from app.identity import User, UserStatus
from app.main import app
from app.passwords import dummy_password_hash, hash_password, verify_password
from app.tokens import ALGORITHM, InvalidToken, decode_access_token, issue_access_token

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "palavra-de-teste"
OTHER_PASSWORD = "palavra-errada-123"
INVALID_LOGIN = {"detail": "Credenciais inválidas."}
INVALID_TOKEN = {"detail": "Token inválido."}


def test_hash_and_verify_round_trip():
    stored = hash_password(PASSWORD)

    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored
    assert verify_password(stored, PASSWORD) is True
    assert verify_password(stored, OTHER_PASSWORD) is False
    assert verify_password("nao-e-um-resumo", PASSWORD) is False
    assert verify_password("", PASSWORD) is False


def test_token_accepts_only_hs256_from_this_issuer():
    user_id = uuid.uuid4()
    token = issue_access_token(user_id)
    payload = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[ALGORITHM],
        issuer=settings.jwt_issuer,
    )

    assert decode_access_token(token) == user_id
    assert set(payload) == {"sub", "iat", "exp", "iss"}
    assert payload["sub"] == str(user_id)
    assert payload["iss"] == settings.jwt_issuer

    with pytest.raises(InvalidToken):
        decode_access_token(issue_access_token(user_id, expires_in=-30))

    forged = jwt.encode(
        {
            "sub": str(user_id),
            "iss": settings.jwt_issuer,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "outro-segredo-que-nao-e-o-da-aplicacao-32",
        algorithm=ALGORITHM,
    )
    with pytest.raises(InvalidToken):
        decode_access_token(forged)

    other_algorithm = jwt.encode(
        {
            "sub": str(user_id),
            "iss": settings.jwt_issuer,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS512",
    )
    with pytest.raises(InvalidToken):
        decode_access_token(other_algorithm)

    for malformed in ("nao-e-um-token", "a.b", "a.b.c"):
        with pytest.raises(InvalidToken):
            decode_access_token(malformed)

    not_a_uuid = jwt.encode(
        {
            "sub": "utilizador",
            "iss": settings.jwt_issuer,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )
    with pytest.raises(InvalidToken):
        decode_access_token(not_a_uuid)


def test_token_rejects_claims_with_the_wrong_type_or_format():
    user_id = uuid.uuid4()
    now = int(time.time())
    secret = settings.jwt_secret.get_secret_value()
    valid = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + 60,
    }
    invalid = [
        {**valid, "iat": str(now)},
        {**valid, "exp": now + 60.5},
        {**valid, "iat": True},
        {**valid, "sub": str(user_id).upper()},
        {**valid, "sub": str(user_id).replace("-", "")},
    ]

    assert decode_access_token(jwt.encode(valid, secret, algorithm=ALGORITHM)) == user_id
    for claims in invalid:
        token = jwt.encode(claims, secret, algorithm=ALGORITHM)
        with pytest.raises(InvalidToken):
            decode_access_token(token)

    issuer_list = json.dumps({**valid, "iss": [settings.jwt_issuer]}).encode()
    listed_issuer = jwt.PyJWS().encode(issuer_list, secret, algorithm=ALGORITHM)
    with pytest.raises(InvalidToken):
        decode_access_token(listed_issuer)


def test_command_never_takes_the_password_as_an_argument(capsys):
    def reader() -> str:
        raise AssertionError("a palavra-passe não devia ser lida")

    code = main(
        ["--email", "ana@example.com", "--password", PASSWORD],
        password_reader=reader,
    )
    captured = capsys.readouterr()

    assert code == 1
    assert PASSWORD not in captured.out
    assert PASSWORD not in captured.err
    assert captured.err.strip() == "A palavra-passe não é um argumento."


def test_password_prompt_confirms_and_stdin_reads_one_line():
    prompts = iter(["uma-palavra-valida", "outra-palavra"])

    with pytest.raises(ValueError, match="não coincidem"):
        read_password(StringIO(""), isatty=True, prompter=lambda prompt: next(prompts))

    assert (
        read_password(StringIO("palavra-de-teste\n"), isatty=False) == PASSWORD
    )


@pytest.fixture(scope="session")
def migrated_database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture
def db_session(migrated_database):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def auth_client(db_session):
    def override_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@contextmanager
def command_session(db_session: Session):
    """Entrega a sessão do teste ao comando.

    ``commit`` e ``rollback`` da sessão só fecham um savepoint. A transacção
    externa é desfeita no fim do teste.
    """

    yield db_session


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_command_creates_an_active_account_without_printing_secrets(db_session, capsys):
    code = main(
        ["--email", " Ana@Example.com "],
        password_reader=lambda: PASSWORD,
        session_factory=lambda: command_session(db_session),
    )
    captured = capsys.readouterr()
    user = db_session.scalar(select(User).where(User.email == "ana@example.com"))

    assert code == 0
    assert captured.out.strip() == "Conta criada para ana@example.com."
    assert PASSWORD not in captured.out
    assert PASSWORD not in captured.err
    assert "argon" not in captured.out.lower()
    assert user is not None
    assert user.status is UserStatus.ACTIVE
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    assert verify_password(user.password_hash, PASSWORD) is True


def test_duplicate_email_is_rejected(db_session, capsys):
    create_active_user(db_session, "ana@example.com", PASSWORD)
    db_session.commit()

    with pytest.raises(AccountExists):
        create_active_user(db_session, "ANA@example.com", OTHER_PASSWORD)

    code = main(
        ["--email", "ana@example.com"],
        password_reader=lambda: PASSWORD,
        session_factory=lambda: command_session(db_session),
    )
    captured = capsys.readouterr()
    stored = db_session.scalars(select(User).where(User.email == "ana@example.com")).all()

    assert code == 1
    assert captured.err.strip() == "Já existe uma conta com esse email."
    assert PASSWORD not in captured.out
    assert PASSWORD not in captured.err
    assert len(stored) == 1
    assert verify_password(stored[0].password_hash, PASSWORD) is True


def test_missing_account_still_checks_a_dummy_hash(db_session, monkeypatch):
    seen: list[str] = []

    def spy(stored: str, password: str) -> bool:
        seen.append(stored)
        return False

    monkeypatch.setattr("app.accounts.verify_password", spy)
    assert authenticate(db_session, "ninguem@example.com", PASSWORD) is None
    assert seen == [dummy_password_hash()]


def test_disabled_account_is_rejected_after_the_hash_check(db_session, monkeypatch):
    user = create_active_user(db_session, "ana@example.com", PASSWORD)
    user.status = UserStatus.DISABLED
    db_session.flush()
    seen: list[str] = []

    def spy(stored: str, password: str) -> bool:
        seen.append(stored)
        return True

    monkeypatch.setattr("app.accounts.verify_password", spy)

    assert authenticate(db_session, "ana@example.com", PASSWORD) is None
    assert seen == [user.password_hash]


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "sem-arroba", "password": PASSWORD},
        {"email": "ana@example.com", "password": "curta"},
        {"email": "ana@example.com"},
        {"password": PASSWORD},
    ],
)
def test_login_rejects_invalid_input_without_echoing_it(auth_client, payload):
    response = auth_client.post("/auth/login", json=payload)
    body = response.text

    assert response.status_code == 422
    assert "curta" not in body
    assert PASSWORD not in body
    assert all("input" not in error for error in response.json()["detail"])


def test_login_hides_unknown_wrong_and_disabled_accounts(auth_client, db_session):
    create_active_user(db_session, "ana@example.com", PASSWORD)
    disabled = create_active_user(db_session, "bia@example.com", PASSWORD)
    disabled.status = UserStatus.DISABLED
    db_session.flush()

    wrong = auth_client.post(
        "/auth/login",
        json={"email": "ana@example.com", "password": OTHER_PASSWORD},
    )
    missing = auth_client.post(
        "/auth/login",
        json={"email": "ninguem@example.com", "password": OTHER_PASSWORD},
    )
    blocked = auth_client.post(
        "/auth/login",
        json={"email": "bia@example.com", "password": PASSWORD},
    )

    assert wrong.status_code == missing.status_code == blocked.status_code == 401
    assert wrong.json() == missing.json() == blocked.json() == INVALID_LOGIN
    for response in (wrong, missing, blocked):
        assert response.headers["www-authenticate"] == "Bearer"
        assert "ana@example.com" not in response.text
        assert "bia@example.com" not in response.text
        assert PASSWORD not in response.text


def test_login_returns_a_bearer_token(auth_client, db_session, caplog):
    create_active_user(db_session, "ana@example.com", PASSWORD)
    caplog.set_level(logging.DEBUG)

    response = auth_client.post(
        "/auth/login",
        json={"email": " Ana@Example.com ", "password": PASSWORD},
    )
    body = response.json()

    assert response.status_code == 200
    assert set(body) == {"access_token", "token_type", "expires_in"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.jwt_expires_in
    assert decode_access_token(body["access_token"]) is not None
    assert PASSWORD not in caplog.text
    assert body["access_token"] not in caplog.text
    assert "Ana@Example.com" not in response.text


def test_me_returns_only_the_active_account(auth_client, db_session):
    user = create_active_user(db_session, "ana@example.com", PASSWORD)
    token = issue_access_token(user.id)

    response = auth_client.get("/auth/me", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": "ana@example.com",
        "status": "active",
    }
    assert set(response.json()) == {"id", "email", "status"}
    assert "password" not in response.text
    assert "argon" not in response.text
    assert token not in response.text


def test_me_rejects_expired_forged_and_disallowed_tokens(auth_client, db_session):
    user = create_active_user(db_session, "ana@example.com", PASSWORD)
    secret = settings.jwt_secret.get_secret_value()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user.id),
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    forged = jwt.encode(
        claims,
        "outro-segredo-que-nao-e-o-da-aplicacao-32",
        algorithm=ALGORITHM,
    )
    other_algorithm = jwt.encode(claims, secret, algorithm="HS512")
    cases = [
        _bearer(issue_access_token(user.id, expires_in=-30)),
        _bearer(forged),
        _bearer(other_algorithm),
        _bearer("nao-e-um-token"),
        _bearer("a.b.c"),
        {"Authorization": "Bearer"},
        {"Authorization": f"Basic {issue_access_token(user.id)}"},
        {},
    ]

    for headers in cases:
        response = auth_client.get("/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.json() == INVALID_TOKEN
        assert response.headers["www-authenticate"] == "Bearer"
        assert secret not in response.text


def test_me_rejects_a_token_whose_account_disappeared_or_was_disabled(
    auth_client, db_session
):
    removed = create_active_user(db_session, "carla@example.com", PASSWORD)
    disabled = create_active_user(db_session, "bia@example.com", PASSWORD)
    removed_token = issue_access_token(removed.id)
    disabled_token = issue_access_token(disabled.id)
    db_session.delete(removed)
    disabled.status = UserStatus.DISABLED
    db_session.flush()

    for token in (removed_token, disabled_token):
        response = auth_client.get("/auth/me", headers=_bearer(token))
        assert response.status_code == 401
        assert response.json() == INVALID_TOKEN
        assert response.headers["www-authenticate"] == "Bearer"
        assert PASSWORD not in response.text
