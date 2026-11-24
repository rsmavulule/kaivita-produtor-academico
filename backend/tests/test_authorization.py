"""Autorização de representação, com PostgreSQL real.

Cada teste corre dentro de uma transacção desfeita no fim.
Sem RUN_DB_TESTS=1 a suite não contacta a base.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.actors as actors_api
from app.accounts import create_active_user
from app.db import engine, get_session
from app.identity import (
    AccessLevel,
    AccessStatus,
    Actor,
    ActorKind,
    ActorStatus,
    User,
    UserActorAccess,
    UserStatus,
)
from app.main import app
from app.tokens import issue_access_token

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "palavra-de-teste"
NOT_FOUND = {"detail": "Actor não encontrado."}
ACTOR_KEYS = {"id", "kind", "display_name", "general_location", "status"}
VIEW_KEYS = ACTOR_KEYS | {"representation"}


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
def api(db_session):
    def override_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _user(session: Session, email: str) -> User:
    user = create_active_user(session, email, PASSWORD)
    session.flush()
    return user


def _actor(session: Session, name: str, location: str | None = "Maputo") -> Actor:
    actor = Actor(
        kind=ActorKind.PERSON,
        display_name=name,
        general_location=location,
        status=ActorStatus.ACTIVE,
    )
    session.add(actor)
    session.flush()
    return actor


def _grant(
    session: Session,
    user: User,
    actor: Actor,
    level: AccessLevel,
    access_status: AccessStatus = AccessStatus.ACTIVE,
) -> UserActorAccess:
    access = UserActorAccess(
        user_id=user.id,
        actor_id=actor.id,
        access_level=level,
        status=access_status,
    )
    session.add(access)
    session.flush()
    return access


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_access_token(user.id)}"}


def test_reader_can_consult_the_actor(api, db_session):
    user = _user(db_session, "leitor@example.com")
    actor = _actor(db_session, "Cooperativa do Sul")
    _grant(db_session, user, actor, AccessLevel.READ)

    response = api.get(f"/actors/{actor.id}", headers=_bearer(user))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == VIEW_KEYS
    assert body["id"] == str(actor.id)
    assert body["display_name"] == "Cooperativa do Sul"
    assert body["kind"] == "person"
    assert body["status"] == "active"
    assert body["representation"] == "read"
    assert "access_level" not in body
    assert "user_id" not in body
    assert PASSWORD not in response.text


def test_reader_cannot_modify_the_actor(api, db_session):
    user = _user(db_session, "leitor-edicao@example.com")
    actor = _actor(db_session, "Nome original", "Inhambane")
    _grant(db_session, user, actor, AccessLevel.READ)

    response = api.patch(
        f"/actors/{actor.id}",
        headers=_bearer(user),
        json={"display_name": "Nome recusado"},
    )

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert actor.display_name == "Nome original"
    assert actor.general_location == "Inhambane"


def test_manager_can_consult_and_modify(api, db_session):
    user = _user(db_session, "gestor@example.com")
    actor = _actor(db_session, "Nome antigo", "Gaza")
    _grant(db_session, user, actor, AccessLevel.MANAGE)
    headers = _bearer(user)

    read = api.get(f"/actors/{actor.id}", headers=headers)
    updated = api.patch(
        f"/actors/{actor.id}",
        headers=headers,
        json={"display_name": "Nome novo", "general_location": None},
    )

    assert read.status_code == 200
    assert read.json()["display_name"] == "Nome antigo"
    assert read.json()["representation"] == "manage"
    assert updated.status_code == 200
    assert set(updated.json()) == ACTOR_KEYS
    assert "representation" not in updated.json()
    assert updated.json()["display_name"] == "Nome novo"
    assert updated.json()["general_location"] is None
    assert updated.json()["kind"] == "person"
    assert updated.json()["status"] == "active"
    assert actor.display_name == "Nome novo"
    assert actor.general_location is None


def test_revoked_access_blocks_read_and_update(api, db_session):
    user = _user(db_session, "revogado@example.com")
    actor = _actor(db_session, "Actor retirado")
    _grant(
        db_session,
        user,
        actor,
        AccessLevel.MANAGE,
        AccessStatus.REVOKED,
    )
    headers = _bearer(user)

    read = api.get(f"/actors/{actor.id}", headers=headers)
    updated = api.patch(
        f"/actors/{actor.id}",
        headers=headers,
        json={"display_name": "Não entra"},
    )
    listing = api.get("/actors", headers=headers)

    assert read.status_code == 404
    assert read.json() == NOT_FOUND
    assert updated.status_code == 404
    assert updated.json() == NOT_FOUND
    assert listing.status_code == 200
    assert listing.json() == []
    assert actor.display_name == "Actor retirado"


def test_user_without_access_cannot_reach_the_actor(api, db_session):
    outsider = _user(db_session, "sem-acesso@example.com")
    owner = _user(db_session, "com-acesso@example.com")
    actor = _actor(db_session, "Actor alheio")
    _grant(db_session, owner, actor, AccessLevel.MANAGE)

    response = api.get(f"/actors/{actor.id}", headers=_bearer(outsider))

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert str(owner.id) not in response.text
    assert owner.email not in response.text


def test_disabled_account_cannot_use_a_previously_issued_token(api, db_session):
    user = _user(db_session, "desactivado@example.com")
    actor = _actor(db_session, "Actor da conta")
    _grant(db_session, user, actor, AccessLevel.MANAGE)
    headers = _bearer(user)
    user.status = UserStatus.DISABLED
    db_session.flush()

    response = api.get(f"/actors/{actor.id}", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Token inválido."}
    assert response.headers["www-authenticate"] == "Bearer"


def test_missing_or_invalid_token_is_rejected(api, db_session):
    actor = _actor(db_session, "Actor protegido")

    missing = api.get(f"/actors/{actor.id}")
    invalid = api.get(
        f"/actors/{actor.id}",
        headers={"Authorization": "Bearer nao-e-um-token"},
    )
    listing = api.get("/actors")

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert listing.status_code == 401
    assert missing.json()["detail"] == "Token inválido."
    assert actor.display_name not in missing.text
    assert actor.display_name not in invalid.text


def test_unknown_actor_returns_404(api, db_session):
    user = _user(db_session, "consulta-vazio@example.com")

    response = api.get(f"/actors/{uuid.uuid4()}", headers=_bearer(user))

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_unauthorized_actor_returns_the_same_404(api, db_session):
    user = _user(db_session, "nao-autorizado@example.com")
    hidden = _actor(db_session, "Não deve aparecer")

    response = api.get(f"/actors/{hidden.id}", headers=_bearer(user))

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert "Não deve aparecer" not in response.text


def test_listing_contains_only_authorized_actors(api, db_session):
    user = _user(db_session, "lista@example.com")
    other = _user(db_session, "outro-lista@example.com")
    visible = _actor(db_session, "Visível")
    also_visible = _actor(db_session, "Também visível")
    revoked = _actor(db_session, "Revogado na lista")
    foreign = _actor(db_session, "De outra conta")
    _grant(db_session, user, visible, AccessLevel.READ)
    _grant(db_session, user, also_visible, AccessLevel.MANAGE)
    _grant(db_session, user, revoked, AccessLevel.READ, AccessStatus.REVOKED)
    _grant(db_session, other, foreign, AccessLevel.MANAGE)

    response = api.get("/actors", headers=_bearer(user))

    assert response.status_code == 200
    names = [item["display_name"] for item in response.json()]
    assert names == ["Também visível", "Visível"]
    assert all(set(item) == VIEW_KEYS for item in response.json())
    levels = {item["display_name"]: item["representation"] for item in response.json()}
    assert levels == {"Também visível": "manage", "Visível": "read"}


def test_update_rejects_fields_outside_the_contract(api, db_session):
    user = _user(db_session, "contrato@example.com")
    actor = _actor(db_session, "Nome estável", "Niassa")
    _grant(db_session, user, actor, AccessLevel.MANAGE)
    secret = "palavra-que-nao-pode-sair"

    response = api.patch(
        f"/actors/{actor.id}",
        headers=_bearer(user),
        json={
            "display_name": "Nome que não entra",
            "kind": "organization",
            "status": "inactive",
            "password": secret,
        },
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    assert actor.display_name == "Nome estável"
    assert actor.kind is ActorKind.PERSON
    assert actor.status is ActorStatus.ACTIVE
    assert actor.general_location == "Niassa"


def test_revocation_after_the_token_applies_on_the_next_request(api, db_session):
    user = _user(db_session, "revoga-depois@example.com")
    actor = _actor(db_session, "Ainda autorizado")
    access = _grant(db_session, user, actor, AccessLevel.MANAGE)
    headers = _bearer(user)

    before = api.get(f"/actors/{actor.id}", headers=headers)
    access.status = AccessStatus.REVOKED
    db_session.flush()
    after = api.patch(
        f"/actors/{actor.id}",
        headers=headers,
        json={"display_name": "Tarde demais"},
    )

    assert before.status_code == 200
    assert after.status_code == 404
    assert after.json() == NOT_FOUND
    assert actor.display_name == "Ainda autorizado"


def test_one_user_can_represent_several_actors(api, db_session):
    user = _user(db_session, "varios-actores@example.com")
    first = _actor(db_session, "Primeiro actor")
    second = _actor(db_session, "Segundo actor")
    _grant(db_session, user, first, AccessLevel.READ)
    _grant(db_session, user, second, AccessLevel.MANAGE)
    headers = _bearer(user)

    listing = api.get("/actors", headers=headers)
    second_update = api.patch(
        f"/actors/{second.id}",
        headers=headers,
        json={"display_name": "Segundo actualizado"},
    )
    first_update = api.patch(
        f"/actors/{first.id}",
        headers=headers,
        json={"display_name": "Primeiro recusado"},
    )

    assert [item["id"] for item in listing.json()] == [str(first.id), str(second.id)]
    assert second_update.status_code == 200
    assert second.display_name == "Segundo actualizado"
    assert first_update.status_code == 404
    assert first.display_name == "Primeiro actor"


def test_several_users_can_represent_the_same_actor(api, db_session):
    reader = _user(db_session, "leitor-partilhado@example.com")
    manager = _user(db_session, "gestor-partilhado@example.com")
    actor = _actor(db_session, "Actor partilhado", "Sofala")
    _grant(db_session, reader, actor, AccessLevel.READ)
    _grant(db_session, manager, actor, AccessLevel.MANAGE)

    reader_view = api.get(f"/actors/{actor.id}", headers=_bearer(reader))
    reader_edit = api.patch(
        f"/actors/{actor.id}",
        headers=_bearer(reader),
        json={"general_location": "Cabo Delgado"},
    )
    manager_edit = api.patch(
        f"/actors/{actor.id}",
        headers=_bearer(manager),
        json={"general_location": "Nampula"},
    )

    assert reader_view.status_code == 200
    assert reader_view.json()["general_location"] == "Sofala"
    assert reader_edit.status_code == 404
    assert manager_edit.status_code == 200
    assert manager_edit.json()["general_location"] == "Nampula"
    assert actor.general_location == "Nampula"


def test_empty_patch_does_not_change_the_actor(api, db_session):
    user = _user(db_session, "vazio@example.com")
    actor = _actor(db_session, "Nome estável", "Tete")
    _grant(db_session, user, actor, AccessLevel.MANAGE)
    before = (actor.kind, actor.display_name, actor.general_location, actor.status)

    response = api.patch(f"/actors/{actor.id}", headers=_bearer(user), json={})

    db_session.expire(actor)
    assert response.status_code == 200
    assert response.json()["display_name"] == "Nome estável"
    assert response.json()["general_location"] == "Tete"
    assert response.json()["kind"] == "person"
    assert response.json()["status"] == "active"
    assert (actor.kind, actor.display_name, actor.general_location, actor.status) == before


def test_malformed_actor_id_is_rejected_without_a_server_error(api, db_session):
    user = _user(db_session, "uuid-invalido@example.com")
    headers = _bearer(user)

    read = api.get("/actors/nao-e-um-uuid", headers=headers)
    updated = api.patch(
        "/actors/nao-e-um-uuid",
        headers=headers,
        json={"display_name": "Não entra"},
    )

    for response in (read, updated):
        assert response.status_code == 422
        assert "Traceback" not in response.text
        assert all("input" not in error for error in response.json()["detail"])


def test_authorization_and_update_share_one_database_session(api, db_session, monkeypatch):
    """A autorização e a escrita deste pedido usam a mesma sessão.

    Não há SELECT FOR UPDATE. Outra transacção pode confirmar uma revogação
    depois da leitura e antes da escrita. Este incremento não acrescenta
    bloqueio nem muda o isolamento.
    """

    user = _user(db_session, "mesma-sessao@example.com")
    actor = _actor(db_session, "Actor da sessão", "Sofala")
    _grant(db_session, user, actor, AccessLevel.MANAGE)
    seen: dict[str, object] = {}
    calls = {"n": 0}
    original = actors_api.actor_for_manage

    def spy(session, current, actor_id):
        seen["session"] = session
        seen["transaction"] = session.get_transaction()
        found = original(session, current, actor_id)
        seen["actor"] = found
        return found

    monkeypatch.setattr("app.actors.actor_for_manage", spy)

    def override_session() -> Iterator[Session]:
        calls["n"] += 1
        yield db_session

    app.dependency_overrides[get_session] = override_session
    response = api.patch(
        f"/actors/{actor.id}",
        headers=_bearer(user),
        json={"display_name": "Nome na mesma sessão"},
    )

    assert response.status_code == 200
    assert calls["n"] == 1
    assert seen["session"] is db_session
    assert seen["transaction"] is db_session.get_transaction()
    assert seen["actor"] is actor
    assert actor.display_name == "Nome na mesma sessão"


def test_representation_stays_with_the_authenticated_user(api, db_session):
    reader = _user(db_session, "nivel-leitor@example.com")
    manager = _user(db_session, "nivel-gestor@example.com")
    actor = _actor(db_session, "Actor com dois níveis")
    _grant(db_session, reader, actor, AccessLevel.READ)
    _grant(db_session, manager, actor, AccessLevel.MANAGE)

    reader_view = api.get(f"/actors/{actor.id}", headers=_bearer(reader))
    manager_view = api.get(f"/actors/{actor.id}", headers=_bearer(manager))

    assert reader_view.status_code == 200
    assert reader_view.json()["representation"] == "read"
    assert manager_view.status_code == 200
    assert manager_view.json()["representation"] == "manage"
    for response in (reader_view, manager_view):
        body = response.json()
        assert set(body) == VIEW_KEYS
        assert "user_id" not in body
        assert "access_level" not in body
        assert str(reader.id) not in response.text
        assert str(manager.id) not in response.text
        assert reader.email not in response.text
        assert manager.email not in response.text


def test_revoked_association_is_absent_from_representation(api, db_session):
    user = _user(db_session, "nivel-revogado@example.com")
    actor = _actor(db_session, "Já não representa")
    _grant(db_session, user, actor, AccessLevel.MANAGE, AccessStatus.REVOKED)
    headers = _bearer(user)

    read = api.get(f"/actors/{actor.id}", headers=headers)
    listing = api.get("/actors", headers=headers)

    assert read.status_code == 404
    assert read.json() == NOT_FOUND
    assert "representation" not in read.text
    assert listing.json() == []


def test_client_cannot_set_representation(api, db_session):
    user = _user(db_session, "nivel-corpo@example.com")
    headers = _bearer(user)
    created = api.post(
        "/actors",
        headers=headers,
        json={
            "kind": "person",
            "display_name": "Não escolhe o nível",
            "roles": ["producer"],
            "representation": "read",
        },
    )

    assert created.status_code == 422
    assert "read" not in created.text
    assert all("input" not in error for error in created.json()["detail"])

    actor = _actor(db_session, "Nível fixo", "Maputo")
    _grant(db_session, user, actor, AccessLevel.MANAGE)
    updated = api.patch(
        f"/actors/{actor.id}",
        headers=headers,
        json={"display_name": "Continua gestor", "representation": "read"},
    )

    assert updated.status_code == 422
    assert "read" not in updated.text
    assert actor.display_name == "Nível fixo"
    access = db_session.get(UserActorAccess, (user.id, actor.id))
    assert access is not None
    assert access.access_level is AccessLevel.MANAGE
    assert access.status is AccessStatus.ACTIVE


def test_write_responses_keep_the_previous_contract(api, db_session):
    user = _user(db_session, "contrato-escrita@example.com")
    headers = _bearer(user)
    created = api.post(
        "/actors",
        headers=headers,
        json={
            "kind": "organization",
            "display_name": "Contrato antigo",
            "general_location": "Beira",
            "roles": ["buyer"],
        },
    )
    actor_id = created.json()["id"]
    updated = api.patch(
        f"/actors/{actor_id}",
        headers=headers,
        json={"general_location": None},
    )

    assert created.status_code == 201
    assert set(created.json()) == {"id", "kind", "display_name", "general_location", "status", "roles"}
    assert "representation" not in created.json()
    assert updated.status_code == 200
    assert set(updated.json()) == ACTOR_KEYS
    assert updated.json()["general_location"] is None
    assert "representation" not in updated.json()
