"""Criação de actores e papéis comerciais, com PostgreSQL real.

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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounts import create_active_user
from app.db import engine, get_session
from app.identity import (
    COMMERCIAL_ROLE_IDS,
    AccessLevel,
    AccessStatus,
    Actor,
    ActorRole,
    Role,
    RoleCode,
    User,
    UserActorAccess,
)
from app.main import app
from app.tokens import issue_access_token

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "palavra-de-teste"
NOT_FOUND = {"detail": "Actor não encontrado."}
ACTOR_KEYS = {"id", "kind", "display_name", "general_location", "status"}
CREATED_KEYS = ACTOR_KEYS | {"roles"}
ROLE_KEYS = {"id", "code"}
CATALOG = {
    code.value: str(role_id) for code, role_id in COMMERCIAL_ROLE_IDS.items()
}


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


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_access_token(user.id)}"}


def _grant(
    session: Session,
    user: User,
    actor_id: uuid.UUID,
    level: AccessLevel,
    access_status: AccessStatus = AccessStatus.ACTIVE,
) -> UserActorAccess:
    access = UserActorAccess(
        user_id=user.id,
        actor_id=actor_id,
        access_level=level,
        status=access_status,
    )
    session.add(access)
    session.flush()
    return access


def _catalog_rows(session: Session):
    return session.execute(select(Role.id, Role.code).order_by(Role.code)).all()


def _links(session: Session, actor_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        session.scalars(
            select(ActorRole.role_id).where(ActorRole.actor_id == actor_id)
        ).all()
    )


def _codes(items: list[dict]) -> list[str]:
    return [item["code"] for item in items]


def _create(
    api,
    user: User,
    *,
    kind: str = "person",
    name: str = "Marta",
    location: str | None = "Inhambane",
    roles: list[str] | None = None,
    extra: dict | None = None,
):
    body: dict = {
        "kind": kind,
        "display_name": name,
        "roles": ["producer"] if roles is None else roles,
    }
    if location is not None:
        body["general_location"] = location
    if extra:
        body.update(extra)
    return api.post("/actors", headers=_bearer(user), json=body)


def _assert_absent(session: Session, name: str) -> None:
    found = session.scalars(select(Actor).where(Actor.display_name == name)).all()
    assert found == []


def test_creates_a_person_actor(api, db_session):
    user = _user(db_session, "pessoa@example.com")

    response = _create(
        api,
        user,
        name="Marta Sitoe",
        location="Inhambane",
        roles=["buyer", "producer"],
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == CREATED_KEYS
    assert body["kind"] == "person"
    assert body["display_name"] == "Marta Sitoe"
    assert body["general_location"] == "Inhambane"
    assert body["status"] == "active"
    assert _codes(body["roles"]) == ["producer", "buyer"]
    assert {item["code"]: item["id"] for item in body["roles"]} == {
        "producer": CATALOG["producer"],
        "buyer": CATALOG["buyer"],
    }
    assert all(set(item) == ROLE_KEYS for item in body["roles"])
    assert "access_level" not in body
    assert str(user.id) not in response.text
    assert user.email not in response.text
    assert PASSWORD not in response.text


def test_creates_an_organization_actor(api, db_session):
    user = _user(db_session, "organizacao@example.com")

    response = _create(
        api,
        user,
        kind="organization",
        name="Cooperativa do Limpopo",
        location=None,
        roles=["partner"],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "organization"
    assert body["display_name"] == "Cooperativa do Limpopo"
    assert body["general_location"] is None
    assert body["status"] == "active"
    assert _codes(body["roles"]) == ["partner"]
    assert body["roles"][0]["id"] == CATALOG["partner"]


def test_creator_receives_active_manage_access(api, db_session):
    user = _user(db_session, "criador@example.com")
    headers = _bearer(user)

    created = _create(api, user, name="Produtor da criação", roles=["producer"])
    actor_id = created.json()["id"]
    access = db_session.get(UserActorAccess, (user.id, uuid.UUID(actor_id)))

    assert created.status_code == 201
    assert access is not None
    assert access.access_level is AccessLevel.MANAGE
    assert access.status is AccessStatus.ACTIVE

    read = api.get(f"/actors/{actor_id}", headers=headers)
    updated = api.patch(
        f"/actors/{actor_id}",
        headers=headers,
        json={"display_name": "Produtor actualizado"},
    )
    listing = api.get("/actors", headers=headers)

    assert read.status_code == 200
    assert set(read.json()) == ACTOR_KEYS
    assert "roles" not in read.json()
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Produtor actualizado"
    assert updated.json()["kind"] == "person"
    assert updated.json()["status"] == "active"
    assert [item["id"] for item in listing.json()] == [actor_id]
    assert set(listing.json()[0]) == ACTOR_KEYS


def test_actor_roles_and_access_are_created_together(api, db_session):
    user = _user(db_session, "atomico@example.com")
    catalog_before = _catalog_rows(db_session)

    response = _create(
        api,
        user,
        name="Actor atómico",
        roles=["partner", "producer"],
    )
    actor_id = uuid.UUID(response.json()["id"])
    links = db_session.scalars(
        select(ActorRole).where(ActorRole.actor_id == actor_id)
    ).all()
    accesses = db_session.scalars(
        select(UserActorAccess).where(UserActorAccess.actor_id == actor_id)
    ).all()

    assert response.status_code == 201
    assert db_session.get(Actor, actor_id) is not None
    assert {link.role_id for link in links} == {
        COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER],
        COMMERCIAL_ROLE_IDS[RoleCode.PARTNER],
    }
    assert len(accesses) == 1
    assert accesses[0].user_id == user.id
    assert accesses[0].access_level is AccessLevel.MANAGE
    assert accesses[0].status is AccessStatus.ACTIVE
    assert _catalog_rows(db_session) == catalog_before
    assert len(catalog_before) == 3


def test_creation_requires_authentication(api, db_session):
    response = api.post(
        "/actors",
        json={
            "kind": "person",
            "display_name": "Sem token",
            "roles": ["producer"],
        },
    )
    hidden = uuid.uuid4()
    read_roles = api.get(f"/actors/{hidden}/roles")
    update_roles = api.put(
        f"/actors/{hidden}/roles",
        json={"roles": ["producer"]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido."
    assert response.headers["www-authenticate"] == "Bearer"
    assert read_roles.status_code == 401
    assert update_roles.status_code == 401
    _assert_absent(db_session, "Sem token")
    assert "Sem token" not in response.text


def test_invalid_kind_is_rejected(api, db_session):
    user = _user(db_session, "kind@example.com")

    response = _create(api, user, kind="cooperativa", name="Kind recusado")

    assert response.status_code == 422
    assert "cooperativa" not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    _assert_absent(db_session, "Kind recusado")


def test_empty_name_is_rejected(api, db_session):
    user = _user(db_session, "nome-vazio@example.com")

    blank = _create(api, user, name="   ")
    empty = _create(api, user, name="")

    assert blank.status_code == 422
    assert empty.status_code == 422
    assert "Nome inválido." in blank.text
    assert db_session.scalars(select(Actor)).all() == []


def test_unknown_role_is_rejected(api, db_session):
    user = _user(db_session, "papel-desconhecido@example.com")
    catalog_before = _catalog_rows(db_session)

    response = _create(api, user, name="Papel inventado", roles=["admin"])

    assert response.status_code == 422
    assert "Papel desconhecido." in response.text
    assert "admin" not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    _assert_absent(db_session, "Papel inventado")
    assert _catalog_rows(db_session) == catalog_before


def test_duplicate_roles_are_rejected(api, db_session):
    user = _user(db_session, "papel-repetido@example.com")

    response = _create(
        api,
        user,
        name="Papel repetido",
        roles=["producer", "producer"],
    )

    assert response.status_code == 422
    assert "Papel repetido." in response.text
    _assert_absent(db_session, "Papel repetido")
    assert db_session.scalars(select(ActorRole)).all() == []


def test_role_catalog_returns_the_three_seeded_roles(api, db_session):
    before = _catalog_rows(db_session)

    response = api.get("/roles")
    again = api.get("/roles")

    assert response.status_code == 200
    body = response.json()
    assert [item["code"] for item in body] == ["producer", "buyer", "partner"]
    assert {item["code"]: item["id"] for item in body} == CATALOG
    assert all(set(item) == ROLE_KEYS for item in body)
    assert again.json() == body
    assert _catalog_rows(db_session) == before
    assert len(before) == 3


def test_reader_can_list_actor_roles(api, db_session):
    owner = _user(db_session, "dono-leitura@example.com")
    reader = _user(db_session, "leitor-papeis@example.com")
    created = _create(
        api,
        owner,
        name="Actor consultado",
        roles=["partner", "producer"],
    )
    actor_id = uuid.UUID(created.json()["id"])
    _grant(db_session, reader, actor_id, AccessLevel.READ)

    response = api.get(f"/actors/{actor_id}/roles", headers=_bearer(reader))

    assert response.status_code == 200
    assert _codes(response.json()) == ["producer", "partner"]
    assert {item["id"] for item in response.json()} == {
        CATALOG["producer"],
        CATALOG["partner"],
    }
    assert owner.email not in response.text
    assert str(owner.id) not in response.text
    assert "access_level" not in response.text


def test_manager_can_list_actor_roles(api, db_session):
    user = _user(db_session, "gestor-leitura@example.com")
    created = _create(api, user, name="Actor do gestor", roles=["buyer"])
    actor_id = created.json()["id"]

    response = api.get(f"/actors/{actor_id}/roles", headers=_bearer(user))

    assert response.status_code == 200
    assert response.json() == [{"id": CATALOG["buyer"], "code": "buyer"}]


def test_manager_replaces_actor_roles(api, db_session):
    user = _user(db_session, "gestor-papeis@example.com")
    created = _create(
        api,
        user,
        name="Actor a actualizar",
        roles=["producer", "buyer"],
    )
    actor_id = uuid.UUID(created.json()["id"])
    buyer_link = db_session.get(
        ActorRole,
        (actor_id, COMMERCIAL_ROLE_IDS[RoleCode.BUYER]),
    )
    catalog_before = _catalog_rows(db_session)
    access_before = (
        user.id,
        actor_id,
        AccessLevel.MANAGE,
        AccessStatus.ACTIVE,
    )

    response = api.put(
        f"/actors/{actor_id}/roles",
        headers=_bearer(user),
        json={"roles": ["partner", "buyer"]},
    )

    assert response.status_code == 200
    assert _codes(response.json()) == ["buyer", "partner"]
    assert _links(db_session, actor_id) == {
        COMMERCIAL_ROLE_IDS[RoleCode.BUYER],
        COMMERCIAL_ROLE_IDS[RoleCode.PARTNER],
    }
    assert db_session.get(ActorRole, (actor_id, COMMERCIAL_ROLE_IDS[RoleCode.BUYER])) is buyer_link
    assert (
        db_session.get(ActorRole, (actor_id, COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER]))
        is None
    )
    access = db_session.get(UserActorAccess, (user.id, actor_id))
    assert (
        access.user_id,
        access.actor_id,
        access.access_level,
        access.status,
    ) == access_before
    assert _catalog_rows(db_session) == catalog_before


def test_reader_cannot_replace_actor_roles(api, db_session):
    owner = _user(db_session, "dono-recusa@example.com")
    reader = _user(db_session, "leitor-recusa@example.com")
    created = _create(api, owner, name="Só consulta", roles=["producer"])
    actor_id = uuid.UUID(created.json()["id"])
    _grant(db_session, reader, actor_id, AccessLevel.READ)

    response = api.put(
        f"/actors/{actor_id}/roles",
        headers=_bearer(reader),
        json={"roles": ["buyer"]},
    )

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert _links(db_session, actor_id) == {COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER]}
    assert "Só consulta" not in response.text


def test_revoked_access_cannot_replace_actor_roles(api, db_session):
    user = _user(db_session, "revogado-papeis@example.com")
    created = _create(api, user, name="Acesso retirado", roles=["producer"])
    actor_id = uuid.UUID(created.json()["id"])
    access = db_session.get(UserActorAccess, (user.id, actor_id))
    access.status = AccessStatus.REVOKED
    db_session.flush()
    headers = _bearer(user)

    updated = api.put(
        f"/actors/{actor_id}/roles",
        headers=headers,
        json={"roles": ["buyer"]},
    )
    read = api.get(f"/actors/{actor_id}/roles", headers=headers)

    assert updated.status_code == 404
    assert updated.json() == NOT_FOUND
    assert read.status_code == 404
    assert read.json() == NOT_FOUND
    assert _links(db_session, actor_id) == {COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER]}


def test_inaccessible_actor_roles_return_404(api, db_session):
    owner = _user(db_session, "dono-oculto@example.com")
    outsider = _user(db_session, "fora@example.com")
    created = _create(api, owner, name="Actor oculto", roles=["buyer"])
    actor_id = created.json()["id"]
    headers = _bearer(outsider)

    hidden = api.get(f"/actors/{actor_id}/roles", headers=headers)
    missing = api.get(f"/actors/{uuid.uuid4()}/roles", headers=headers)
    denied = api.put(
        f"/actors/{actor_id}/roles",
        headers=headers,
        json={"roles": ["partner"]},
    )
    unknown = api.put(
        f"/actors/{uuid.uuid4()}/roles",
        headers=headers,
        json={"roles": ["partner"]},
    )

    for response in (hidden, missing, denied, unknown):
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
        assert "Actor oculto" not in response.text
    assert _links(db_session, uuid.UUID(actor_id)) == {
        COMMERCIAL_ROLE_IDS[RoleCode.BUYER]
    }


def test_replacing_roles_with_the_same_set_is_idempotent(api, db_session):
    user = _user(db_session, "idempotente@example.com")
    created = _create(
        api,
        user,
        name="Conjunto estável",
        roles=["buyer", "producer"],
    )
    actor_id = uuid.UUID(created.json()["id"])
    before = list(
        db_session.scalars(select(ActorRole).where(ActorRole.actor_id == actor_id))
    )

    response = api.put(
        f"/actors/{actor_id}/roles",
        headers=_bearer(user),
        json={"roles": ["producer", "buyer"]},
    )
    after = list(
        db_session.scalars(select(ActorRole).where(ActorRole.actor_id == actor_id))
    )

    assert response.status_code == 200
    assert _codes(response.json()) == ["producer", "buyer"]
    assert {id(link) for link in after} == {id(link) for link in before}
    assert {(link.actor_id, link.role_id) for link in after} == {
        (link.actor_id, link.role_id) for link in before
    }


def test_failed_creation_leaves_no_partial_rows(api, db_session, monkeypatch):
    user = _user(db_session, "falha-criacao@example.com")

    def explode(session, current, actor):
        raise RuntimeError("falha na representação")

    monkeypatch.setattr("app.actor_roles.grant_creator", explode)

    with pytest.raises(RuntimeError, match="falha na representação"):
        _create(api, user, name="Não pode ficar", roles=["producer", "buyer"])

    db_session.expire_all()
    assert db_session.get(User, user.id) is not None
    assert db_session.scalars(select(Actor)).all() == []
    assert db_session.scalars(select(ActorRole)).all() == []
    assert (
        db_session.scalars(
            select(UserActorAccess).where(UserActorAccess.user_id == user.id)
        ).all()
        == []
    )
    assert len(_catalog_rows(db_session)) == 3


def test_failed_replacement_restores_the_previous_roles(api, db_session, monkeypatch):
    user = _user(db_session, "falha-substituicao@example.com")
    created = _create(api, user, name="Substituição falhada", roles=["producer"])
    actor_id = uuid.UUID(created.json()["id"])

    def explode(session, actor, current_links, selected):
        session.delete(current_links[0])
        session.flush()
        raise RuntimeError("falha na substituição")

    monkeypatch.setattr("app.actor_roles.apply_role_replacement", explode)

    with pytest.raises(RuntimeError, match="falha na substituição"):
        api.put(
            f"/actors/{actor_id}/roles",
            headers=_bearer(user),
            json={"roles": ["buyer"]},
        )

    db_session.expire_all()
    assert _links(db_session, actor_id) == {COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER]}
    access = db_session.get(UserActorAccess, (user.id, actor_id))
    assert access.access_level is AccessLevel.MANAGE
    assert access.status is AccessStatus.ACTIVE
    assert len(_catalog_rows(db_session)) == 3


def test_one_actor_can_hold_several_roles(api, db_session):
    user = _user(db_session, "varios-papeis@example.com")

    response = _create(
        api,
        user,
        name="Actor acumulado",
        roles=["partner", "buyer", "producer"],
    )
    actor_id = uuid.UUID(response.json()["id"])
    actors = db_session.scalars(
        select(Actor).where(Actor.display_name == "Actor acumulado")
    ).all()

    assert response.status_code == 201
    assert _codes(response.json()["roles"]) == ["producer", "buyer", "partner"]
    assert len(actors) == 1
    assert actors[0].id == actor_id
    assert _links(db_session, actor_id) == set(COMMERCIAL_ROLE_IDS.values())


def test_client_cannot_choose_access_or_identity(api, db_session):
    user = _user(db_session, "cliente@example.com")
    other = _user(db_session, "outro-cliente@example.com")
    planted = uuid.uuid4()

    response = _create(
        api,
        user,
        name="Pedido rejeitado",
        extra={
            "user_id": str(other.id),
            "actor_id": str(planted),
            "access_level": "read",
            "status": "inactive",
        },
    )

    assert response.status_code == 422
    assert str(other.id) not in response.text
    assert str(planted) not in response.text
    assert "read" not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    _assert_absent(db_session, "Pedido rejeitado")
    assert db_session.get(Actor, planted) is None
    assert (
        db_session.scalars(
            select(UserActorAccess).where(UserActorAccess.user_id == other.id)
        ).all()
        == []
    )


def test_empty_role_list_is_rejected(api, db_session):
    user = _user(db_session, "lista-vazia@example.com")
    created = _create(api, user, name="Mantém o papel", roles=["producer"])
    actor_id = uuid.UUID(created.json()["id"])

    missing = _create(api, user, name="Sem papéis", roles=[])
    cleared = api.put(
        f"/actors/{actor_id}/roles",
        headers=_bearer(user),
        json={"roles": []},
    )

    assert missing.status_code == 422
    assert "É necessário pelo menos um papel." in missing.text
    assert cleared.status_code == 422
    assert "É necessário pelo menos um papel." in cleared.text
    _assert_absent(db_session, "Sem papéis")
    assert _links(db_session, actor_id) == {COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER]}


def test_invalid_replacement_keeps_the_previous_roles(api, db_session):
    user = _user(db_session, "substituicao-invalida@example.com")
    created = _create(api, user, name="Papéis estáveis", roles=["producer"])
    actor_id = created.json()["id"]
    headers = _bearer(user)
    expected = {COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER]}

    unknown = api.put(
        f"/actors/{actor_id}/roles",
        headers=headers,
        json={"roles": ["producer", "admin"]},
    )
    duplicated = api.put(
        f"/actors/{actor_id}/roles",
        headers=headers,
        json={"roles": ["buyer", "buyer"]},
    )
    extra = api.put(
        f"/actors/{actor_id}/roles",
        headers=headers,
        json={"roles": ["buyer"], "access_level": "read"},
    )

    assert unknown.status_code == 422
    assert "admin" not in unknown.text
    assert duplicated.status_code == 422
    assert extra.status_code == 422
    assert "read" not in extra.text
    assert _links(db_session, uuid.UUID(actor_id)) == expected


def test_producer_role_does_not_grant_manage(api, db_session):
    owner = _user(db_session, "produtor-dono@example.com")
    outsider = _user(db_session, "produtor-alheio@example.com")
    created = _create(api, owner, name="Só o criador gere", roles=["producer"])
    actor_id = created.json()["id"]
    headers = _bearer(outsider)

    read_roles = api.get(f"/actors/{actor_id}/roles", headers=headers)
    replace = api.put(
        f"/actors/{actor_id}/roles",
        headers=headers,
        json={"roles": ["buyer", "partner"]},
    )
    edit = api.patch(
        f"/actors/{actor_id}",
        headers=headers,
        json={"display_name": "Não entra"},
    )

    assert read_roles.status_code == 404
    assert replace.status_code == 404
    assert edit.status_code == 404
    assert replace.json() == NOT_FOUND
    assert _links(db_session, uuid.UUID(actor_id)) == {
        COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER]
    }
    assert db_session.get(Actor, uuid.UUID(actor_id)).display_name == "Só o criador gere"
    assert (
        db_session.scalars(
            select(UserActorAccess).where(UserActorAccess.user_id == outsider.id)
        ).all()
        == []
    )
    owner_access = db_session.get(UserActorAccess, (owner.id, uuid.UUID(actor_id)))
    assert owner_access.access_level is AccessLevel.MANAGE


def test_patch_cannot_change_commercial_roles(api, db_session):
    user = _user(db_session, "patch-papeis@example.com")
    created = _create(api, user, name="Nome do patch", roles=["producer"])
    actor_id = uuid.UUID(created.json()["id"])

    response = api.patch(
        f"/actors/{actor_id}",
        headers=_bearer(user),
        json={"roles": ["buyer"], "display_name": "Nome que não entra"},
    )

    assert response.status_code == 422
    assert db_session.get(Actor, actor_id).display_name == "Nome do patch"
    assert _links(db_session, actor_id) == {COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER]}


def test_malformed_actor_id_on_role_routes_is_422(api, db_session):
    user = _user(db_session, "uuid-papeis@example.com")
    headers = _bearer(user)

    read = api.get("/actors/nao-e-um-uuid/roles", headers=headers)
    updated = api.put(
        "/actors/nao-e-um-uuid/roles",
        headers=headers,
        json={"roles": ["producer"]},
    )

    for response in (read, updated):
        assert response.status_code == 422
        assert "Traceback" not in response.text
        assert all("input" not in error for error in response.json()["detail"])
