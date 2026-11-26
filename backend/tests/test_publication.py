"""Autorização de divulgação e consulta pública dos contactos.

Os testes de API com ``db_session`` desfazem a transacção no fim.
Concorrência, visibilidade após commit e migração usam transacções
próprias e apagam só as linhas que criaram.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, inspect, select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import CheckConstraint

from app.accounts import create_active_user
from app.config import settings
from app.contacts import (
    ContactChannel,
    ContactStatus,
    ContactVisibility,
    PublicContact,
    create_contact,
)
from app.db import engine, get_session
from app.identity import (
    COMMERCIAL_ROLE_IDS,
    AccessLevel,
    AccessStatus,
    Actor,
    ActorKind,
    ActorRole,
    ActorStatus,
    RoleCode,
    User,
    UserActorAccess,
    UserStatus,
)
from app.main import app
from app.offers import Offer
from app.products import Product
from app.publication import (
    INCONSISTENT_AUTHORIZATION,
    INACTIVE_DISCLOSURE,
    NOTICE_V1_TEXT,
    STALE_REVISION,
    DisclosurePurpose,
    PublicationAuthorization,
    RevocationReason,
    grant_authorization,
)
from app.tokens import issue_access_token

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "palavra-de-teste"
PHONE = "+258840000311"
OTHER_PHONE = "+258840000322"
EMAIL = "Produtor.Divulgacao@example.com"
ALT_EMAIL = "Outro.Contacto@example.com"
ACTOR_MISSING = {"detail": "Actor não encontrado."}
CONTACT_MISSING = {"detail": "Contacto não encontrado."}
AUTH_MISSING = {"detail": "Autorização não encontrada."}
OFFER_MISSING = {"detail": "Oferta não encontrada."}
UNAUTHORIZED = {"detail": "Token inválido."}
GRANT_BODY = {
    "contact_revision": 1,
    "purpose": "commercial_discovery",
    "notice_version": "v1",
    "confirmed": True,
}
AUTH_KEYS = {
    "id",
    "contact_id",
    "contact_revision",
    "channel",
    "purpose",
    "notice_version",
    "status",
    "granted_at",
    "granted_by_user_id",
    "revoked_at",
    "revoked_by_user_id",
    "revocation_reason",
}
PUBLIC_CONTACT_KEYS = {"channel", "value"}
PUBLIC_OFFER_KEYS = {
    "id",
    "price",
    "currency",
    "quantity",
    "unit",
    "availability",
    "delivery_terms",
    "product",
    "producer",
}
THROWAWAY_NAME = re.compile(r"kaivita_i72_[0-9a-f]{12}")


@pytest.fixture(scope="module")
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


def _actor(api, user: User, *, name: str = "Casa Divulgada", roles: list[str] | None = None):
    created = api.post(
        "/actors",
        headers=_bearer(user),
        json={
            "kind": "organization",
            "display_name": name,
            "general_location": "Inhambane",
            "roles": ["producer"] if roles is None else roles,
        },
    )
    assert created.status_code == 201, created.text
    return uuid.UUID(created.json()["id"])


def _read_access(session: Session, user: User, actor_id: uuid.UUID) -> None:
    session.add(
        UserActorAccess(
            user_id=user.id,
            actor_id=actor_id,
            access_level=AccessLevel.READ,
            status=AccessStatus.ACTIVE,
        )
    )
    session.flush()


def _contact(api, user: User, actor_id: uuid.UUID, **overrides) -> dict:
    body = {"channel": "phone", "value": PHONE}
    body.update(overrides)
    created = api.post(
        f"/actors/{actor_id}/contacts",
        headers=_bearer(user),
        json=body,
    )
    assert created.status_code == 201, created.text
    return created.json()


def _grant(api, user: User, actor_id: uuid.UUID, contact_id: str, **overrides):
    body = dict(GRANT_BODY)
    body.update(overrides)
    return api.post(
        f"/actors/{actor_id}/contacts/{contact_id}/authorizations",
        headers=_bearer(user),
        json=body,
    )


def _history(api, user: User, actor_id: uuid.UUID, contact_id: str):
    return api.get(
        f"/actors/{actor_id}/contacts/{contact_id}/authorizations",
        headers=_bearer(user),
    )


def _revoke(api, user: User, actor_id: uuid.UUID, contact_id: str, authorization_id: str):
    return api.post(
        f"/actors/{actor_id}/contacts/{contact_id}/authorizations/{authorization_id}/revoke",
        headers=_bearer(user),
    )


def _publish(api, user: User, actor_id: uuid.UUID, **offer_fields) -> str:
    token = uuid.uuid4().hex[:8]
    product = api.post(
        f"/actors/{actor_id}/products",
        headers=_bearer(user),
        json={
            "name": f"Mel {token}",
            "description": "Mel de exemplo",
            "category": "mel",
        },
    )
    assert product.status_code == 201, product.text
    payload = {
        "product_id": product.json()["id"],
        "price": "10.00",
        "currency": "MZN",
        "quantity": "1.00",
        "unit": "kg",
        "availability": "available",
    }
    payload.update(offer_fields)
    offer = api.post(
        f"/actors/{actor_id}/offers",
        headers=_bearer(user),
        json=payload,
    )
    assert offer.status_code == 201, offer.text
    published = api.post(
        f"/actors/{actor_id}/offers/{offer.json()['id']}/publish",
        headers=_bearer(user),
    )
    assert published.status_code == 200, published.text
    return offer.json()["id"]


def _public(api, offer_id: str, **headers):
    return api.get(f"/public/offers/{offer_id}/contacts", headers=headers or None)


def _rows(session: Session, contact_id: str) -> list[PublicationAuthorization]:
    return list(
        session.scalars(
            select(PublicationAuthorization)
            .where(PublicationAuthorization.contact_id == uuid.UUID(contact_id))
            .order_by(PublicationAuthorization.granted_at.desc())
        )
    )


def _reject(session: Session, statement: str, params: dict) -> None:
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(text(statement), params)


def test_grant_stores_one_current_authorization_without_the_contact_value(api, db_session):
    user = _user(db_session, "i72-conceder@example.com")
    actor_id = _actor(api, user)
    contact = _contact(api, user, actor_id)
    granted = _grant(api, user, actor_id, contact["id"])
    stored = _rows(db_session, contact["id"])
    contact_row = db_session.get(PublicContact, uuid.UUID(contact["id"]))
    columns = {
        column["name"] for column in inspect(db_session.get_bind()).get_columns(
            "publication_authorizations"
        )
    }

    assert granted.status_code == 201
    assert set(granted.json()) == AUTH_KEYS
    assert granted.json()["status"] == "granted"
    assert granted.json()["contact_revision"] == 1
    assert granted.json()["channel"] == "phone"
    assert granted.json()["purpose"] == "commercial_discovery"
    assert granted.json()["notice_version"] == "v1"
    assert granted.json()["granted_by_user_id"] == str(user.id)
    assert granted.json()["revoked_at"] is None
    assert granted.json()["revocation_reason"] is None
    assert "value" not in granted.json()
    assert PHONE not in granted.text
    assert user.email not in granted.text
    assert len(stored) == 1
    assert stored[0].revoked_at is None
    assert "value" not in columns
    assert contact_row is not None
    assert contact_row.visibility is ContactVisibility.PUBLIC
    assert contact_row.revision == 1
    assert NOTICE_V1_TEXT.startswith("O representante confirma")


def test_postgres_rejects_invalid_authorizations(api, db_session):
    owner = _user(db_session, "i72-restricao@example.com")
    other = _user(db_session, "i72-outro-actor@example.com")
    actor_id = _actor(api, owner, name="Titular")
    other_actor = _actor(api, other, name="Alheio")
    contact = _contact(api, owner, actor_id)
    foreign = _contact(api, other, other_actor, value=OTHER_PHONE)
    base = {
        "actor_id": actor_id,
        "contact_id": contact["id"],
        "contact_revision": 1,
        "channel": "phone",
        "purpose": "commercial_discovery",
        "notice_version": "v1",
        "granted_by_user_id": owner.id,
        "revoked_by_user_id": None,
        "revoked_at": None,
        "revocation_reason": None,
    }
    insert = """
        INSERT INTO publication_authorizations (
            actor_id, contact_id, contact_revision, channel, purpose,
            notice_version, granted_by_user_id, revoked_by_user_id,
            revoked_at, revocation_reason
        ) VALUES (
            :actor_id, :contact_id, :contact_revision, :channel, :purpose,
            :notice_version, :granted_by_user_id, :revoked_by_user_id,
            :revoked_at, :revocation_reason
        )
    """
    cases = [
        {**base, "actor_id": other_actor, "contact_id": contact["id"]},
        {**base, "contact_id": uuid.uuid4()},
        {**base, "granted_by_user_id": uuid.uuid4()},
        {**base, "contact_revision": 0},
        {**base, "channel": "fax"},
        {**base, "purpose": "marketing"},
        {**base, "notice_version": " "},
        {**base, "revoked_at": "2026-11-25T12:00:00Z", "revocation_reason": None},
        {
            **base,
            "revoked_at": "2020-01-01T00:00:00Z",
            "revoked_by_user_id": owner.id,
            "revocation_reason": "manual",
        },
    ]
    for payload in cases:
        _reject(db_session, insert, payload)

    db_session.execute(text(insert), base)
    db_session.flush()
    _reject(db_session, insert, base)
    historical = {
        **base,
        "revoked_at": "2099-01-01T00:00:00Z",
        "revoked_by_user_id": owner.id,
        "revocation_reason": "manual",
    }
    db_session.execute(text(insert), historical)
    db_session.flush()
    assert len(_rows(db_session, contact["id"])) == 2
    assert len(_rows(db_session, foreign["id"])) == 0
    assert PHONE not in " ".join(
        " ".join("" if value is None else str(value) for value in row)
        for row in db_session.execute(
            text(
                """
                SELECT contact_revision::text, channel, purpose, notice_version,
                       revocation_reason
                FROM publication_authorizations
                """
            )
        )
    )


def test_authorization_schema_matches_the_model(db_session):
    inspector = inspect(db_session.get_bind())
    table = PublicationAuthorization.__table__
    columns = inspector.get_columns(table.name)

    assert [column["name"] for column in columns] == [column.name for column in table.columns]
    assert {column["name"]: column["nullable"] for column in columns} == {
        column.name: column.nullable for column in table.columns
    }
    assert inspector.get_pk_constraint(table.name)["name"] == "pk_publication_authorizations"
    assert inspector.get_table_comment(table.name)["text"] == table.comment
    foreign_keys = inspector.get_foreign_keys(table.name)
    assert sorted(item["name"] for item in foreign_keys) == [
        "fk_publication_authorizations_contact_actor",
        "fk_publication_authorizations_granted_by",
        "fk_publication_authorizations_revoked_by",
    ]
    composite = next(
        item
        for item in foreign_keys
        if item["name"] == "fk_publication_authorizations_contact_actor"
    )
    assert composite["constrained_columns"] == ["contact_id", "actor_id"]
    assert composite["referred_table"] == "public_contacts"
    assert composite["options"]["ondelete"] == "RESTRICT"
    assert all(item["referred_columns"] != ["id"] or item["referred_table"] != "actors"
               for item in foreign_keys)
    indexes = {item["name"]: item for item in inspector.get_indexes(table.name)}
    assert indexes["ix_publication_authorizations_contact_history"]["column_names"] == [
        "contact_id",
        "granted_at",
        "id",
    ]
    assert indexes["uq_publication_authorizations_current"]["unique"] is True
    partial = db_session.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE indexname = 'uq_publication_authorizations_current'
            """
        )
    ).scalar_one()
    assert "UNIQUE" in partial
    assert "revoked_at IS NULL" in partial
    names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert names <= {
        item["name"] for item in inspector.get_check_constraints(table.name)
    }


def test_grant_validation_and_conflicts(api, db_session):
    user = _user(db_session, "i72-validar@example.com")
    actor_id = _actor(api, user)
    contact = _contact(api, user, actor_id)
    secret = "+25884SEGREDO72"
    rejected = [
        _grant(api, user, actor_id, contact["id"], confirmed=False),
        _grant(api, user, actor_id, contact["id"], confirmed="true"),
        _grant(api, user, actor_id, contact["id"], confirmed=1),
        _grant(api, user, actor_id, contact["id"], notice_version="v2"),
        _grant(api, user, actor_id, contact["id"], notice_version=" "),
        _grant(api, user, actor_id, contact["id"], purpose="marketing"),
        _grant(api, user, actor_id, contact["id"], contact_revision="1"),
        _grant(api, user, actor_id, contact["id"], value=secret, channel="phone"),
    ]
    omitted = api.post(
        f"/actors/{actor_id}/contacts/{contact['id']}/authorizations",
        headers=_bearer(user),
        json={"purpose": "commercial_discovery", "notice_version": "v1", "confirmed": True},
    )
    for response in [*rejected, omitted]:
        assert response.status_code == 422, response.text
        assert secret not in response.text
        assert PHONE not in response.text
        assert all("input" not in error for error in response.json()["detail"])
    assert _rows(db_session, contact["id"]) == []

    first = _grant(api, user, actor_id, contact["id"])
    repeat = _grant(api, user, actor_id, contact["id"])
    assert first.status_code == 201
    assert repeat.status_code == 200
    assert repeat.json()["id"] == first.json()["id"]
    assert repeat.json()["granted_at"] == first.json()["granted_at"]
    assert repeat.json()["granted_by_user_id"] == first.json()["granted_by_user_id"]
    assert len(_rows(db_session, contact["id"])) == 1

    changed = api.patch(
        f"/actors/{actor_id}/contacts/{contact['id']}",
        headers=_bearer(user),
        json={"value": OTHER_PHONE},
    )
    assert changed.status_code == 200
    assert changed.json()["revision"] == 2
    assert changed.json()["visibility"] == "private"
    stale = _grant(api, user, actor_id, contact["id"], contact_revision=1)
    assert stale.status_code == 409
    assert stale.json() == {"detail": STALE_REVISION}
    assert PHONE not in stale.text
    current = _grant(api, user, actor_id, contact["id"], contact_revision=2)
    assert current.status_code == 201
    assert current.json()["id"] != first.json()["id"]
    _revoke(api, user, actor_id, contact["id"], current.json()["id"])
    inactive = api.post(
        f"/actors/{actor_id}/contacts/{contact['id']}/deactivate",
        headers=_bearer(user),
    )
    assert inactive.status_code == 200
    blocked = _grant(api, user, actor_id, contact["id"], contact_revision=2)
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": INACTIVE_DISCLOSURE}


def test_inconsistent_current_authorization_is_not_reused(api, db_session):
    user = _user(db_session, "i72-incoerente@example.com")
    actor_id = _actor(api, user)
    contact = _contact(api, user, actor_id)
    offer_id = _publish(api, user, actor_id)
    granted = _grant(api, user, actor_id, contact["id"])
    authorization = db_session.get(PublicationAuthorization, uuid.UUID(granted.json()["id"]))
    authorization.contact_revision = 9
    db_session.flush()

    conflict = _grant(api, user, actor_id, contact["id"])
    visible = _public(api, offer_id)
    again = db_session.get(PublicationAuthorization, authorization.id)

    assert conflict.status_code == 409
    assert conflict.json() == {"detail": INCONSISTENT_AUTHORIZATION}
    assert again is not None
    assert again.revoked_at is None
    assert again.contact_revision == 9
    assert visible.status_code == 200
    assert visible.json() == {"items": []}
    assert len(_rows(db_session, contact["id"])) == 1


def test_history_revoke_and_a_later_grant(api, db_session):
    user = _user(db_session, "i72-historico@example.com")
    actor_id = _actor(api, user)
    contact = _contact(api, user, actor_id)
    empty = _history(api, user, actor_id, contact["id"])
    first = _grant(api, user, actor_id, contact["id"])
    revoked = _revoke(api, user, actor_id, contact["id"], first.json()["id"])
    repeated = _revoke(api, user, actor_id, contact["id"], first.json()["id"])
    second = _grant(api, user, actor_id, contact["id"])
    historical = _revoke(api, user, actor_id, contact["id"], first.json()["id"])
    listing = _history(api, user, actor_id, contact["id"])
    contact_row = db_session.get(PublicContact, uuid.UUID(contact["id"]))

    assert empty.status_code == 200
    assert empty.json() == {"items": []}
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert revoked.json()["revocation_reason"] == "manual"
    assert revoked.json()["revoked_by_user_id"] == str(user.id)
    assert repeated.json() == revoked.json()
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    assert historical.json()["id"] == first.json()["id"]
    assert historical.json()["revoked_at"] == revoked.json()["revoked_at"]
    assert contact_row is not None
    assert contact_row.visibility is ContactVisibility.PUBLIC
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert [item["id"] for item in items] == [second.json()["id"], first.json()["id"]]
    assert [item["status"] for item in items] == ["granted", "revoked"]
    assert items == sorted(sorted(items, key=lambda item: item["id"]), key=lambda item: item["granted_at"], reverse=True)
    assert "value" not in listing.text
    activate = api.post(
        f"/actors/{actor_id}/contacts/{contact['id']}/authorizations/{first.json()['id']}/activate",
        headers=_bearer(user),
    )
    assert activate.status_code == 404


def test_effective_change_revokes_and_invalid_change_does_not(api, db_session):
    user = _user(db_session, "i72-alterar@example.com")
    actor_id = _actor(api, user)
    contact = _contact(api, user, actor_id)
    twin = _contact(api, user, actor_id, value=OTHER_PHONE)
    granted = _grant(api, user, actor_id, contact["id"])
    same = api.patch(
        f"/actors/{actor_id}/contacts/{contact['id']}",
        headers=_bearer(user),
        json={"value": " +258 84 000 0311 "},
    )
    invalid = api.patch(
        f"/actors/{actor_id}/contacts/{contact['id']}",
        headers=_bearer(user),
        json={"value": "sem-indicativo"},
    )
    duplicate = api.patch(
        f"/actors/{actor_id}/contacts/{contact['id']}",
        headers=_bearer(user),
        json={"value": OTHER_PHONE},
    )
    db_session.expire_all()
    stored_revoked = db_session.execute(
        text(
            """
            SELECT revoked_at IS NOT NULL
            FROM publication_authorizations
            WHERE contact_id = :contact_id
            """
        ),
        {"contact_id": contact["id"]},
    ).scalar_one()
    kept = _rows(db_session, contact["id"])[0]
    kept_was_current = kept.revoked_at is None and kept.revocation_reason is None
    contact_before = db_session.get(PublicContact, uuid.UUID(contact["id"]))
    value_before = contact_before.value
    changed = api.patch(
        f"/actors/{actor_id}/contacts/{contact['id']}",
        headers=_bearer(user),
        json={"channel": "email", "value": EMAIL},
    )
    after_channel = _rows(db_session, contact["id"])[0]

    assert same.status_code == 200
    assert same.json()["revision"] == 1
    assert same.json()["visibility"] == "public"
    assert invalid.status_code == 422
    assert duplicate.status_code == 422
    assert stored_revoked is False
    assert kept_was_current is True
    assert value_before == PHONE
    assert changed.status_code == 200
    assert changed.json()["revision"] == 2
    assert changed.json()["visibility"] == "private"
    assert changed.json()["channel"] == "email"
    assert after_channel.revocation_reason is RevocationReason.CONTACT_CHANGED
    assert after_channel.revoked_by_user_id == user.id
    assert after_channel.contact_revision == 1
    assert after_channel.channel is ContactChannel.PHONE
    fresh = _grant(api, user, actor_id, contact["id"], contact_revision=2)
    value_change = api.patch(
        f"/actors/{actor_id}/contacts/{contact['id']}",
        headers=_bearer(user),
        json={"value": ALT_EMAIL},
    )
    revoked_value = db_session.get(PublicationAuthorization, uuid.UUID(fresh.json()["id"]))
    assert value_change.status_code == 200
    assert value_change.json()["revision"] == 3
    assert revoked_value is not None
    assert revoked_value.revocation_reason is RevocationReason.CONTACT_CHANGED
    assert twin["value"] == OTHER_PHONE


def test_deactivation_revokes_once_and_leaves_the_contact_private(api, db_session):
    user = _user(db_session, "i72-desactivar@example.com")
    actor_id = _actor(api, user)
    contact = _contact(api, user, actor_id)
    granted = _grant(api, user, actor_id, contact["id"])
    first = api.post(
        f"/actors/{actor_id}/contacts/{contact['id']}/deactivate",
        headers=_bearer(user),
    )
    authorization = db_session.get(PublicationAuthorization, uuid.UUID(granted.json()["id"]))
    stamp = authorization.revoked_at
    updated = db_session.get(PublicContact, uuid.UUID(contact["id"])).updated_at
    second = api.post(
        f"/actors/{actor_id}/contacts/{contact['id']}/deactivate",
        headers=_bearer(user),
    )
    db_session.refresh(authorization)
    contact_row = db_session.get(PublicContact, uuid.UUID(contact["id"]))

    assert first.status_code == 200
    assert first.json()["status"] == "inactive"
    assert first.json()["visibility"] == "private"
    assert first.json()["revision"] == 1
    assert authorization.revocation_reason is RevocationReason.CONTACT_DEACTIVATED
    assert authorization.revoked_by_user_id == user.id
    assert second.json()["updated_at"] == first.json()["updated_at"]
    assert authorization.revoked_at == stamp
    assert contact_row.updated_at == updated
    assert contact_row.status is ContactStatus.INACTIVE
    assert contact_row.visibility is ContactVisibility.PRIVATE
    removed = api.delete(
        f"/actors/{actor_id}/contacts/{contact['id']}",
        headers=_bearer(user),
    )
    assert removed.status_code == 405


def test_readers_and_strangers_cannot_cross_authorizations(api, db_session):
    manager = _user(db_session, "i72-gere@example.com")
    reader = _user(db_session, "i72-le@example.com")
    stranger = _user(db_session, "i72-estranho@example.com")
    revoked = _user(db_session, "i72-revogada@example.com")
    disabled = _user(db_session, "i72-desactivado@example.com")
    actor_id = _actor(api, manager)
    other_id = _actor(api, manager, name="Outra casa")
    _read_access(db_session, reader, actor_id)
    _read_access(db_session, revoked, actor_id)
    _read_access(db_session, disabled, actor_id)
    access = db_session.get(UserActorAccess, (revoked.id, actor_id))
    access.status = AccessStatus.REVOKED
    disabled.status = UserStatus.DISABLED
    db_session.flush()
    contact = _contact(api, manager, actor_id)
    other = _contact(api, manager, other_id, value=OTHER_PHONE)
    granted = _grant(api, manager, actor_id, contact["id"])
    second = _contact(api, manager, actor_id, channel="email", value=EMAIL)
    second_grant = _grant(api, manager, actor_id, second["id"])

    assert _history(api, reader, actor_id, contact["id"]).status_code == 200
    assert _grant(api, reader, actor_id, contact["id"]).json() == ACTOR_MISSING
    denied_revoke = _revoke(api, reader, actor_id, contact["id"], granted.json()["id"])
    assert denied_revoke.json() == ACTOR_MISSING
    assert _history(api, stranger, actor_id, contact["id"]).json() == ACTOR_MISSING
    assert _history(api, revoked, actor_id, contact["id"]).json() == ACTOR_MISSING
    assert _history(api, disabled, actor_id, contact["id"]).status_code == 401
    anonymous = _history(api, manager, actor_id, contact["id"])
    anonymous.headers.clear()
    # O pedido acima já foi autenticado. O visitante é um pedido sem cabeçalho.
    assert api.get(
        f"/actors/{actor_id}/contacts/{contact['id']}/authorizations"
    ).json() == UNAUTHORIZED
    assert _history(api, manager, actor_id, str(uuid.uuid4())).json() == CONTACT_MISSING
    crossed_contact = _revoke(api, manager, other_id, other["id"], granted.json()["id"])
    assert crossed_contact.json() == AUTH_MISSING
    crossed_actor = _revoke(api, manager, other_id, contact["id"], granted.json()["id"])
    assert crossed_actor.json() == CONTACT_MISSING
    same_actor = _revoke(api, manager, actor_id, second["id"], granted.json()["id"])
    assert same_actor.json() == AUTH_MISSING
    preserved = db_session.get(PublicationAuthorization, uuid.UUID(granted.json()["id"]))
    assert preserved is not None
    assert preserved.revoked_at is None
    assert second_grant.status_code == 201


def test_buyer_and_inactive_actor_can_manage_authorizations(api, db_session):
    buyer = _user(db_session, "i72-comprador@example.com")
    actor_id = _actor(api, buyer, roles=["buyer"])
    contact = _contact(api, buyer, actor_id)
    granted = _grant(api, buyer, actor_id, contact["id"])
    actor = db_session.get(Actor, actor_id)
    actor.status = ActorStatus.INACTIVE
    db_session.flush()
    repeated = _grant(api, buyer, actor_id, contact["id"])

    assert granted.status_code == 201
    assert repeated.status_code == 200
    assert actor.status is ActorStatus.INACTIVE


def test_public_disclosure_follows_eligibility_and_authorization(api, db_session):
    user = _user(db_session, "i72-publico@example.com")
    actor_id = _actor(api, user, name="Produtor Público")
    contact = _contact(api, user, actor_id)
    mail = _contact(api, user, actor_id, channel="email", value=EMAIL)
    offer_id = _publish(api, user, actor_id)
    draft_product = api.post(
        f"/actors/{actor_id}/products",
        headers=_bearer(user),
        json={"name": "Rascunho", "description": "Ainda não publicado", "category": "mel"},
    )
    draft = api.post(
        f"/actors/{actor_id}/offers",
        headers=_bearer(user),
        json={"product_id": draft_product.json()["id"]},
    )
    unavailable = _publish(
        api,
        user,
        actor_id,
        availability="unavailable",
        quantity="0.00",
    )

    assert _public(api, offer_id).json() == {"items": []}
    _contact_row = db_session.get(PublicContact, uuid.UUID(contact["id"]))
    _contact_row.visibility = ContactVisibility.PUBLIC
    db_session.flush()
    assert _public(api, offer_id).json() == {"items": []}
    _contact_row.visibility = ContactVisibility.PRIVATE
    db_session.flush()

    phone_grant = _grant(api, user, actor_id, contact["id"])
    mail_grant = _grant(api, user, actor_id, mail["id"])
    disclosed = _public(api, offer_id)
    assert disclosed.status_code == 200
    assert disclosed.headers["cache-control"] == "no-store"
    assert disclosed.json()["items"] == [
        {"channel": "email", "value": EMAIL},
        {"channel": "phone", "value": PHONE},
    ]
    assert set(disclosed.json()["items"][0]) == PUBLIC_CONTACT_KEYS
    listing = api.get("/public/offers", params={"q": "Produtor Público"})
    detail = api.get(f"/public/offers/{offer_id}")
    assert set(detail.json()) == PUBLIC_OFFER_KEYS
    assert PHONE not in listing.text
    assert PHONE not in detail.text

    _revoke(api, user, actor_id, contact["id"], phone_grant.json()["id"])
    assert _public(api, offer_id).json()["items"] == [
        {"channel": "email", "value": EMAIL}
    ]
    private_grant = db_session.get(PublicationAuthorization, uuid.UUID(mail_grant.json()["id"]))
    mail_row = db_session.get(PublicContact, uuid.UUID(mail["id"]))
    mail_row.visibility = ContactVisibility.PRIVATE
    db_session.flush()
    assert _public(api, offer_id).json() == {"items": []}
    mail_row.visibility = ContactVisibility.PUBLIC
    private_grant.contact_revision = 4
    db_session.flush()
    assert _public(api, offer_id).json() == {"items": []}
    private_grant.contact_revision = 1
    private_grant.channel = ContactChannel.PHONE
    db_session.flush()
    assert _public(api, offer_id).json() == {"items": []}
    private_grant.channel = ContactChannel.EMAIL
    db_session.flush()
    _revoke(api, user, actor_id, mail["id"], mail_grant.json()["id"])
    assert _public(api, offer_id).json() == {"items": []}

    restored = _grant(api, user, actor_id, mail["id"])
    mail_row.status = ContactStatus.INACTIVE
    mail_row.visibility = ContactVisibility.PRIVATE
    db_session.flush()
    assert _public(api, offer_id).json() == {"items": []}
    mail_row.status = ContactStatus.ACTIVE
    mail_row.visibility = ContactVisibility.PUBLIC
    db_session.flush()

    other = _user(db_session, "i72-vizinho@example.com")
    other_actor = _actor(api, other, name="Vizinho")
    other_contact = _contact(api, other, other_actor, value=OTHER_PHONE)
    _grant(api, other, other_actor, other_contact["id"])
    assert OTHER_PHONE not in _public(api, offer_id).text

    assert _public(api, draft.json()["id"]).json() == OFFER_MISSING
    suspended = api.post(
        f"/actors/{actor_id}/offers/{offer_id}/suspend",
        headers=_bearer(user),
    )
    assert suspended.status_code == 200
    assert _public(api, offer_id).json() == OFFER_MISSING
    republished = api.post(
        f"/actors/{actor_id}/offers/{offer_id}/publish",
        headers=_bearer(user),
    )
    assert republished.status_code == 200
    assert _public(api, offer_id).json()["items"] == [
        {"channel": "email", "value": EMAIL}
    ]
    withdrawn = api.post(
        f"/actors/{actor_id}/offers/{unavailable}/withdraw",
        headers=_bearer(user),
    )
    assert withdrawn.status_code == 200
    assert _public(api, unavailable).json() == OFFER_MISSING
    assert _public(api, offer_id).json()["items"][0]["value"] == EMAIL

    role = api.put(
        f"/actors/{actor_id}/roles",
        headers=_bearer(user),
        json={"roles": ["buyer"]},
    )
    assert role.status_code == 200
    assert _public(api, offer_id).json() == OFFER_MISSING
    restored_role = api.put(
        f"/actors/{actor_id}/roles",
        headers=_bearer(user),
        json={"roles": ["producer"]},
    )
    assert restored_role.status_code == 200
    assert _public(api, offer_id).json()["items"][0]["value"] == EMAIL
    actor = db_session.get(Actor, actor_id)
    actor.status = ActorStatus.INACTIVE
    db_session.flush()
    assert _public(api, offer_id).json() == OFFER_MISSING
    actor.status = ActorStatus.ACTIVE
    db_session.flush()
    with_token = api.get(
        f"/public/offers/{offer_id}/contacts",
        headers={"Authorization": "Bearer lixo"},
    )
    assert with_token.status_code == 200
    assert with_token.json()["items"][0]["value"] == EMAIL
    private_offer = api.get(
        f"/actors/{actor_id}/offers/{offer_id}",
        headers=_bearer(user),
    )
    archived = api.post(
        f"/actors/{actor_id}/products/{private_offer.json()['product_id']}/archive",
        headers=_bearer(user),
    )
    assert archived.status_code == 200
    assert _public(api, offer_id).json() == OFFER_MISSING
    assert db_session.get(PublicationAuthorization, uuid.UUID(restored.json()["id"])).revoked_at is None
    missing = _public(api, str(uuid.uuid4()))
    invalid = api.get("/public/offers/nao-e-uuid/contacts")
    assert missing.json() == OFFER_MISSING
    assert invalid.status_code == 422
    assert "nao-e-uuid" not in invalid.text
    assert invalid.headers["cache-control"] == "no-store"
    assert _public(api, unavailable).headers["cache-control"] == "no-store"


def test_authorized_contact_of_an_unavailable_offer_is_disclosed(api, db_session):
    user = _user(db_session, "i72-indisponivel@example.com")
    actor_id = _actor(api, user)
    contact = _contact(api, user, actor_id)
    offer_id = _publish(api, user, actor_id, availability="unavailable", quantity="0.00")
    _grant(api, user, actor_id, contact["id"])
    disclosed = _public(api, offer_id)
    detail = api.get(f"/public/offers/{offer_id}")

    assert disclosed.json()["items"] == [{"channel": "phone", "value": PHONE}]
    assert detail.json()["availability"] == "unavailable"
    assert PHONE not in detail.text


def test_public_query_is_one_statement(api, db_session):
    user = _user(db_session, "i72-snapshot@example.com")
    actor_id = _actor(api, user)
    contact = _contact(api, user, actor_id)
    offer_id = _publish(api, user, actor_id)
    _grant(api, user, actor_id, contact["id"])
    statements: list[str] = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if "eligible_offer" in statement and "disclosed_contacts" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        disclosed = _public(api, offer_id)
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert disclosed.json()["items"] == [{"channel": "phone", "value": PHONE}]
    assert len(statements) == 1
    assert "publication_authorizations" in statements[0]


def test_publication_migration_on_a_throwaway_database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    name = f"kaivita_i72_{uuid.uuid4().hex[:12]}"
    assert THROWAWAY_NAME.fullmatch(name)
    url = make_url(settings.database_url)
    admin = create_engine(
        url.set(database="postgres").render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
    )
    target = url.set(database=name).render_as_string(hide_password=False)
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(text(f"CREATE DATABASE {name}"))
        created = True
        environment = os.environ.copy()
        environment["DATABASE_URL"] = target
        _alembic(environment, "upgrade", "0005_contacts")
        planted = _plant(target)
        _alembic(environment, "upgrade", "0006_publication_authorizations")
        upgraded = _state(target)
        assert upgraded["version"] == "0006_publication_authorizations"
        assert upgraded["authorizations"] == 0
        assert upgraded["public_contacts"] == 0
        assert upgraded["contacts"] == 2
        assert upgraded["offer"] == planted["offer_id"]
        _insert_authorization(target, planted)
        assert _state(target)["authorizations"] == 1
        _alembic(environment, "downgrade", "0005_contacts")
        restored = _state(target)
        assert restored["version"] == "0005_contacts"
        assert restored["table"] is None
        assert restored["public_contacts"] == 0
        assert restored["contacts"] == 2
        assert restored["offer"] == planted["offer_id"]
        _alembic(environment, "upgrade", "0006_publication_authorizations")
        again = _state(target)
        assert again["version"] == "0006_publication_authorizations"
        assert again["authorizations"] == 0
        assert again["contacts"] == 2
        assert again["offer"] == planted["offer_id"]
    finally:
        if created:
            with admin.connect() as connection:
                connection.execute(
                    text(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = :name AND pid <> pg_backend_pid()
                        """
                    ),
                    {"name": name},
                )
                connection.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        admin.dispose()


def test_concurrent_grants_leave_one_current_authorization(migrated_database):
    stamp = uuid.uuid4().hex[:8]
    user_id, actor_id, contact_id = _commit_contact(f"i72-concorrente-{stamp}@example.com")
    try:
        barrier = threading.Barrier(2)
        results: list[str] = []

        def once():
            barrier.wait(timeout=5)
            with Session(engine) as session:
                actor = session.get(Actor, actor_id)
                try:
                    outcome = grant_authorization(
                        session,
                        actor,
                        contact_id,
                        user_id,
                        1,
                        "commercial_discovery",
                        "v1",
                        True,
                    )
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    results.append(f"error:{type(exc).__name__}")
                    return
                results.append("created" if outcome.created else "existing")

        threads = [threading.Thread(target=once), threading.Thread(target=once)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        with Session(engine) as session:
            current = session.scalars(
                select(PublicationAuthorization).where(
                    PublicationAuthorization.contact_id == contact_id,
                    PublicationAuthorization.revoked_at.is_(None),
                )
            ).all()
        assert sorted(results) == ["created", "existing"]
        assert len(current) == 1
    finally:
        _wipe(user_id, actor_id)


def test_grant_and_change_keep_both_orders(migrated_database):
    """Cada operação termina antes da seguinte. A disputa do bloqueio está noutro módulo."""

    stamp = uuid.uuid4().hex[:8]
    user_id, actor_id, contact_id = _commit_contact(f"i72-ordem-{stamp}@example.com")
    try:
        _commit_grant(user_id, actor_id, contact_id)
        _commit_update(user_id, actor_id, contact_id, OTHER_PHONE)
        with Session(engine) as session:
            contact = session.get(PublicContact, contact_id)
            current = session.scalar(
                select(PublicationAuthorization).where(
                    PublicationAuthorization.contact_id == contact_id,
                    PublicationAuthorization.revoked_at.is_(None),
                )
            )
            assert contact is not None
            assert contact.revision == 2
            assert contact.visibility is ContactVisibility.PRIVATE
            assert current is None
        with pytest.raises(Exception) as caught:
            _commit_grant(user_id, actor_id, contact_id, revision=1)
        assert STALE_REVISION in str(caught.value)

        _commit_grant(user_id, actor_id, contact_id, revision=2)
        _commit_deactivate(user_id, actor_id, contact_id)
        with Session(engine) as session:
            contact = session.get(PublicContact, contact_id)
            assert contact is not None
            assert contact.status is ContactStatus.INACTIVE
            assert contact.visibility is ContactVisibility.PRIVATE
            assert session.scalar(
                select(PublicationAuthorization).where(
                    PublicationAuthorization.contact_id == contact_id,
                    PublicationAuthorization.revoked_at.is_(None),
                )
            ) is None
    finally:
        _wipe(user_id, actor_id)


def test_revoke_then_grant_and_grant_then_revoke(migrated_database):
    """Revogação e concessão em sequência, sem espera mútua pelo bloqueio."""

    stamp = uuid.uuid4().hex[:8]
    user_id, actor_id, contact_id = _commit_contact(f"i72-revoga-{stamp}@example.com")
    try:
        first = _commit_grant(user_id, actor_id, contact_id)
        _commit_revoke(user_id, actor_id, contact_id, first)
        second = _commit_grant(user_id, actor_id, contact_id)
        assert second != first
        with Session(engine) as session:
            contact = session.get(PublicContact, contact_id)
            assert contact is not None
            assert contact.visibility is ContactVisibility.PUBLIC
        _commit_revoke(user_id, actor_id, contact_id, first)
        with Session(engine) as session:
            contact = session.get(PublicContact, contact_id)
            assert contact is not None
            assert contact.visibility is ContactVisibility.PUBLIC
        _commit_revoke(user_id, actor_id, contact_id, second)
        with Session(engine) as session:
            contact = session.get(PublicContact, contact_id)
            assert contact is not None
            assert contact.visibility is ContactVisibility.PRIVATE
    finally:
        _wipe(user_id, actor_id)


def test_duplicate_update_preserves_the_current_authorization(migrated_database):
    stamp = uuid.uuid4().hex[:8]
    user_id, actor_id, contact_id = _commit_contact(f"i72-duplicado-{stamp}@example.com")
    other_id = None
    try:
        with Session(engine) as session:
            actor = session.get(Actor, actor_id)
            other = create_contact(session, actor, ContactChannel.PHONE, OTHER_PHONE)
            session.commit()
            other_id = other.id
        granted = _commit_grant(user_id, actor_id, contact_id)
        from decimal import Decimal

        from app.contacts import ContactDuplicate, update_contact
        from app.offers import AvailabilityStatus, create_offer, publish_offer
        from app.products import create_product
        from app.public_offers import public_offer_contacts

        with Session(engine) as session:
            actor = session.get(Actor, actor_id)
            product = create_product(
                session,
                actor,
                f"Mel {stamp}",
                "Produto sintetico para a falha de unicidade",
                "mel",
                None,
            )
            offer = create_offer(
                session,
                actor,
                product,
                Decimal("10.00"),
                "MZN",
                Decimal("1.00"),
                "kg",
                AvailabilityStatus.AVAILABLE,
                None,
            )
            publish_offer(session, actor, offer)
            session.commit()
            offer_id = offer.id
        with Session(engine) as session:
            before = session.get(PublicationAuthorization, granted)
            assert before is not None
            granted_at = before.granted_at
            granted_by = before.granted_by_user_id
        with Session(engine) as session:
            actor = session.get(Actor, actor_id)
            with pytest.raises(ContactDuplicate):
                update_contact(
                    session,
                    actor,
                    contact_id,
                    {"value": OTHER_PHONE},
                    operator_id=user_id,
                )
            session.rollback()
        with Session(engine) as session:
            contact = session.get(PublicContact, contact_id)
            authorization = session.get(PublicationAuthorization, granted)
            disclosed = public_offer_contacts(session, offer_id)
            assert contact is not None
            assert contact.value == PHONE
            assert contact.channel is ContactChannel.PHONE
            assert contact.revision == 1
            assert contact.status is ContactStatus.ACTIVE
            assert contact.visibility is ContactVisibility.PUBLIC
            assert authorization is not None
            assert authorization.granted_at == granted_at
            assert authorization.granted_by_user_id == granted_by
            assert authorization.revoked_at is None
            assert authorization.revoked_by_user_id is None
            assert authorization.revocation_reason is None
            assert disclosed is not None
            assert [(item.channel, item.value) for item in disclosed] == [("phone", PHONE)]
            assert other_id is not None
    finally:
        _wipe(user_id, actor_id)


def test_committed_grant_is_visible_before_the_response_finishes(migrated_database):
    stamp = uuid.uuid4().hex[:8]
    email = f"i72-visivel-{stamp}@example.com"
    user_id = None
    actor_id = None
    try:
        user_id = _create_user(email)
        with TestClient(app) as client:
            token = _login(client, email)
            actor_id = _create_actor(client, token, f"Visível {stamp}")
            contact = client.post(
                f"/actors/{actor_id}/contacts",
                headers={"Authorization": f"Bearer {token}"},
                json={"channel": "phone", "value": PHONE},
            )
            offer = _create_published_offer(client, token, actor_id, stamp)
            observed = _observe_grant(
                actor_id,
                contact.json()["id"],
                offer,
                token,
            )
        assert observed["status"] == 201, observed
        assert observed["visible"] is True
        assert observed["public_value"] == PHONE
        assert observed["body"]["status"] == "granted"
    finally:
        _wipe(user_id, actor_id)


def test_committed_revoke_hides_the_contact_before_the_response_finishes(migrated_database):
    stamp = uuid.uuid4().hex[:8]
    email = f"i72-oculta-{stamp}@example.com"
    user_id = None
    actor_id = None
    try:
        user_id = _create_user(email)
        with TestClient(app) as client:
            token = _login(client, email)
            actor_id = _create_actor(client, token, f"Oculta {stamp}")
            contact = client.post(
                f"/actors/{actor_id}/contacts",
                headers={"Authorization": f"Bearer {token}"},
                json={"channel": "email", "value": EMAIL},
            )
            offer = _create_published_offer(client, token, actor_id, stamp)
            granted = client.post(
                f"/actors/{actor_id}/contacts/{contact.json()['id']}/authorizations",
                headers={"Authorization": f"Bearer {token}"},
                json=GRANT_BODY,
            )
            observed = _observe_revoke(
                actor_id,
                contact.json()["id"],
                granted.json()["id"],
                offer,
                token,
            )
        assert observed["status"] == 200, observed
        assert observed["public_items"] == []
        assert observed["body"]["status"] == "revoked"
    finally:
        _wipe(user_id, actor_id)


def test_logs_and_openapi_do_not_expose_contact_values_or_internal_fields(api, db_session, caplog):
    user = _user(db_session, "i72-log@example.com")
    actor_id = _actor(api, user)
    contact = _contact(api, user, actor_id)
    secret = "+25884SEGREDO72"
    with caplog.at_level(logging.DEBUG):
        rejected = _grant(api, user, actor_id, contact["id"], notice_version=secret)
        granted = _grant(api, user, actor_id, contact["id"])
    document = api.get("/openapi.json").json()
    schemas = document["components"]["schemas"]
    paths = document["paths"]

    assert rejected.status_code == 422
    assert secret not in rejected.text
    assert secret not in caplog.text
    assert PHONE not in caplog.text
    assert granted.status_code == 201
    assert set(schemas["AuthorizationResponse"]["properties"]) == AUTH_KEYS
    assert "email" not in schemas["AuthorizationResponse"]["properties"]
    assert set(schemas["PublicDisclosedContact"]["properties"]) == PUBLIC_CONTACT_KEYS
    assert set(schemas["PublicDisclosedContact"]["required"]) == PUBLIC_CONTACT_KEYS
    assert schemas["PublicDisclosedContact"]["additionalProperties"] is False
    assert set(schemas["PublicOffer"]["properties"]) == PUBLIC_OFFER_KEYS
    assert schemas["GrantRequest"]["additionalProperties"] is False
    history = "/actors/{actor_id}/contacts/{contact_id}/authorizations"
    revoke = history + "/{authorization_id}/revoke"
    assert set(paths[history]) >= {"get", "post"}
    assert set(paths[revoke]) == {"post"}
    assert "security" not in paths["/public/offers/{offer_id}/contacts"]["get"]


def _alembic(environment: dict[str, str], *args: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = re.sub(r"://[^:\s]+:[^@\s]+@", "://", completed.stderr or completed.stdout)
        raise AssertionError(f"alembic {' '.join(args)} falhou\n{detail}")


def _plant(database_url: str) -> dict[str, str]:
    checked = create_engine(database_url)
    try:
        with checked.begin() as connection:
            user_id = connection.execute(
                text(
                    """
                    INSERT INTO users (email, password_hash, status)
                    VALUES ('preservar-i72@example.com', 'hash-de-teste', 'active')
                    RETURNING id
                    """
                )
            ).scalar_one()
            actor_id = connection.execute(
                text(
                    """
                    INSERT INTO actors (kind, display_name, general_location, status)
                    VALUES ('organization', 'Casa antiga', 'Gaza', 'active')
                    RETURNING id
                    """
                )
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO actor_roles (actor_id, role_id)
                    VALUES (:actor_id, :role_id)
                    """
                ),
                {"actor_id": actor_id, "role_id": COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER]},
            )
            product_id = connection.execute(
                text(
                    """
                    INSERT INTO products (
                        owner_actor_id, name, description, category, status
                    ) VALUES (
                        :actor_id, 'Mel antigo', 'Antes das autorizações', 'mel', 'active'
                    ) RETURNING id
                    """
                ),
                {"actor_id": actor_id},
            ).scalar_one()
            offer_id = connection.execute(
                text(
                    """
                    INSERT INTO offers (product_id, owner_actor_id, status)
                    VALUES (:product_id, :actor_id, 'draft')
                    RETURNING id
                    """
                ),
                {"product_id": product_id, "actor_id": actor_id},
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO public_contacts (
                        actor_id, channel, value, visibility, status, revision
                    ) VALUES
                    (:actor_id, 'phone', '+258840000311', 'private', 'active', 1),
                    (:actor_id, 'email', 'preservar-i72@example.com', 'public', 'active', 1)
                    """
                ),
                {"actor_id": actor_id},
            )
        return {
            "user_id": str(user_id),
            "actor_id": str(actor_id),
            "offer_id": str(offer_id),
        }
    finally:
        checked.dispose()


def _insert_authorization(database_url: str, planted: dict[str, str]) -> None:
    checked = create_engine(database_url)
    try:
        with checked.begin() as connection:
            contact_id = connection.execute(
                text(
                    """
                    SELECT id FROM public_contacts
                    WHERE actor_id = :actor_id AND channel = 'phone'
                    """
                ),
                {"actor_id": planted["actor_id"]},
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO publication_authorizations (
                        actor_id, contact_id, contact_revision, channel, purpose,
                        notice_version, granted_by_user_id
                    ) VALUES (
                        :actor_id, :contact_id, 1, 'phone', 'commercial_discovery',
                        'v1', :user_id
                    )
                    """
                ),
                {
                    "actor_id": planted["actor_id"],
                    "contact_id": contact_id,
                    "user_id": planted["user_id"],
                },
            )
    finally:
        checked.dispose()


def _state(database_url: str) -> dict:
    checked = create_engine(database_url)
    try:
        with checked.connect() as connection:
            version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            table = connection.execute(
                text("SELECT to_regclass('public.publication_authorizations')")
            ).scalar_one()
            authorizations = 0
            if table is not None:
                authorizations = connection.execute(
                    text("SELECT count(*) FROM publication_authorizations")
                ).scalar_one()
            contacts = connection.execute(text("SELECT count(*) FROM public_contacts")).scalar_one()
            public_contacts = connection.execute(
                text("SELECT count(*) FROM public_contacts WHERE visibility = 'public'")
            ).scalar_one()
            offer = connection.execute(
                text("SELECT id::text FROM offers WHERE status = 'draft'")
            ).scalar_one()
        return {
            "version": version,
            "table": table,
            "authorizations": authorizations,
            "contacts": contacts,
            "public_contacts": public_contacts,
            "offer": offer,
        }
    finally:
        checked.dispose()


def _commit_contact(email: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with Session(engine) as session:
        user = create_active_user(session, email, PASSWORD)
        actor = Actor(
            kind=ActorKind.ORGANIZATION,
            display_name="Concorrência",
            status=ActorStatus.ACTIVE,
        )
        session.add(actor)
        session.flush()
        session.add(
            UserActorAccess(
                user_id=user.id,
                actor_id=actor.id,
                access_level=AccessLevel.MANAGE,
                status=AccessStatus.ACTIVE,
            )
        )
        session.add(
            ActorRole(actor_id=actor.id, role_id=COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER])
        )
        contact = create_contact(session, actor, ContactChannel.PHONE, PHONE)
        session.commit()
        return user.id, actor.id, contact.id


def _commit_grant(user_id, actor_id, contact_id, revision: int = 1) -> uuid.UUID:
    with Session(engine) as session:
        actor = session.get(Actor, actor_id)
        outcome = grant_authorization(
            session,
            actor,
            contact_id,
            user_id,
            revision,
            "commercial_discovery",
            "v1",
            True,
        )
        session.commit()
        return outcome.authorization.id


def _commit_update(user_id, actor_id, contact_id, value: str) -> None:
    from app.contacts import update_contact

    with Session(engine) as session:
        actor = session.get(Actor, actor_id)
        update_contact(
            session,
            actor,
            contact_id,
            {"value": value},
            operator_id=user_id,
        )
        session.commit()


def _commit_deactivate(user_id, actor_id, contact_id) -> None:
    from app.contacts import deactivate_contact

    with Session(engine) as session:
        actor = session.get(Actor, actor_id)
        deactivate_contact(session, actor, contact_id, operator_id=user_id)
        session.commit()


def _commit_revoke(user_id, actor_id, contact_id, authorization_id) -> None:
    from app.publication import revoke_authorization

    with Session(engine) as session:
        actor = session.get(Actor, actor_id)
        revoke_authorization(session, actor, contact_id, authorization_id, user_id)
        session.commit()


def _create_user(email: str) -> uuid.UUID:
    with Session(engine) as session:
        user = create_active_user(session, email, PASSWORD)
        session.commit()
        return user.id


def _login(client: TestClient, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _create_actor(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/actors",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "person", "display_name": name, "roles": ["producer"]},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_published_offer(client: TestClient, token: str, actor_id: str, stamp: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    product = client.post(
        f"/actors/{actor_id}/products",
        headers=headers,
        json={"name": f"Mel {stamp}", "description": "Mel de exemplo", "category": "mel"},
    )
    offer = client.post(
        f"/actors/{actor_id}/offers",
        headers=headers,
        json={
            "product_id": product.json()["id"],
            "price": "10.00",
            "currency": "MZN",
            "quantity": "1.00",
            "unit": "kg",
            "availability": "available",
        },
    )
    published = client.post(
        f"/actors/{actor_id}/offers/{offer.json()['id']}/publish",
        headers=headers,
    )
    assert published.status_code == 200, published.text
    return offer.json()["id"]


def _observe_grant(actor_id: str, contact_id: str, offer_id: str, token: str) -> dict:
    return _observe(
        "POST",
        f"/actors/{actor_id}/contacts/{contact_id}/authorizations",
        token,
        GRANT_BODY,
        offer_id,
    )


def _observe_revoke(
    actor_id: str,
    contact_id: str,
    authorization_id: str,
    offer_id: str,
    token: str,
) -> dict:
    return _observe(
        "POST",
        f"/actors/{actor_id}/contacts/{contact_id}/authorizations/{authorization_id}/revoke",
        token,
        None,
        offer_id,
    )


def _observe(method: str, path: str, token: str, payload: dict | None, offer_id: str) -> dict:
    body = b"" if payload is None else json.dumps(payload).encode()
    observed: dict = {}
    sent = {"done": False}

    async def receive():
        if sent["done"]:
            return {"type": "http.disconnect"}
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            observed["status"] = message["status"]
            return
        if message["type"] != "http.response.body":
            return
        chunk = message.get("body") or b""
        if chunk:
            observed.setdefault("chunks", []).append(chunk)
        if message.get("more_body", False):
            return
        parsed = json.loads(b"".join(observed.get("chunks", [])) or b"{}")
        with Session(engine) as session:
            from app.public_offers import public_offer_contacts

            disclosed = public_offer_contacts(session, uuid.UUID(offer_id))
            row = None
            if "id" in parsed:
                row = session.get(PublicationAuthorization, uuid.UUID(parsed["id"]))
        observed["visible"] = row is not None and row.revoked_at is None
        observed["public_items"] = [] if disclosed is None else [
            {"channel": item.channel, "value": item.value} for item in disclosed
        ]
        observed["public_value"] = None if not observed["public_items"] else observed["public_items"][0]["value"]
        observed["body"] = parsed

    headers = [
        (b"host", b"test"),
        (b"content-type", b"application/json"),
        (b"authorization", f"Bearer {token}".encode()),
    ]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 9),
        "server": ("test", 80),
    }
    asyncio.run(app(scope, receive, send))
    return observed


def _wipe(user_id, actor_id) -> None:
    with Session(engine) as session:
        if actor_id is not None:
            owner = actor_id if isinstance(actor_id, uuid.UUID) else uuid.UUID(str(actor_id))
            session.execute(
                delete(PublicationAuthorization).where(PublicationAuthorization.actor_id == owner)
            )
            session.execute(delete(PublicContact).where(PublicContact.actor_id == owner))
            session.execute(delete(Offer).where(Offer.owner_actor_id == owner))
            session.execute(delete(Product).where(Product.owner_actor_id == owner))
            session.execute(delete(ActorRole).where(ActorRole.actor_id == owner))
            session.execute(delete(UserActorAccess).where(UserActorAccess.actor_id == owner))
            actor = session.get(Actor, owner)
            if actor is not None:
                session.delete(actor)
        if user_id is not None:
            session.execute(
                delete(PublicationAuthorization).where(
                    PublicationAuthorization.granted_by_user_id == user_id
                )
            )
            session.execute(
                delete(PublicationAuthorization).where(
                    PublicationAuthorization.revoked_by_user_id == user_id
                )
            )
            session.execute(delete(UserActorAccess).where(UserActorAccess.user_id == user_id))
            user = session.get(User, user_id)
            if user is not None:
                session.delete(user)
        session.commit()
