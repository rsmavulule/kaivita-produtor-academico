"""Contactos comerciais privados, com PostgreSQL real.

Cada teste de API que usa ``db_session`` corre numa transacção desfeita
no fim. Os testes de concorrência, de visibilidade após commit e de
migração usam transacções próprias e apagam só as linhas que criaram.
Sem RUN_DB_TESTS=1 esses testes não contactam a base.
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
from sqlalchemy import create_engine, delete, func, inspect, select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import CheckConstraint

from app.accounts import create_active_user
from app.config import settings
from app.contacts import (
    DUPLICATE_CONTACT,
    INACTIVE_CONTACT,
    ContactChannel,
    ContactDuplicate,
    ContactStatus,
    ContactVisibility,
    PublicContact,
    create_contact,
    update_contact,
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
from app.tokens import issue_access_token

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "palavra-de-teste"
ACTOR_MISSING = {"detail": "Actor não encontrado."}
CONTACT_MISSING = {"detail": "Contacto não encontrado."}
DUPLICATE = {"detail": DUPLICATE_CONTACT}
INACTIVE = {"detail": INACTIVE_CONTACT}
UNAUTHORIZED = {"detail": "Token inválido."}
CONTACT_KEYS = {
    "id",
    "channel",
    "value",
    "visibility",
    "status",
    "revision",
    "created_at",
    "updated_at",
}
PUBLIC_KEYS = {
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
THROWAWAY_NAME = re.compile(r"kaivita_i71_[0-9a-f]{12}")
QUOTED_LITERAL = re.compile(r"'([a-z_]+)'")
PHONE = "+258840000111"
OTHER_PHONE = "+258840000222"
WHATSAPP = "+258870000111"
EMAIL = "Produtor.Sintetico@example.com"


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


def _actor(
    api,
    user: User,
    *,
    name: str = "Casa Sintética",
    roles: list[str] | None = None,
) -> uuid.UUID:
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


def _add(api, user: User, actor_id: uuid.UUID, **overrides):
    body = {"channel": "phone", "value": PHONE}
    body.update(overrides)
    return api.post(
        f"/actors/{actor_id}/contacts",
        headers=_bearer(user),
        json=body,
    )


def _rows(session: Session, actor_id: uuid.UUID) -> list[PublicContact]:
    return list(
        session.scalars(
            select(PublicContact)
            .where(PublicContact.actor_id == actor_id)
            .order_by(PublicContact.channel, PublicContact.value, PublicContact.id)
        )
    )


def _reject_sql(session: Session, payload: dict) -> None:
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(
                text(
                    """
                    INSERT INTO public_contacts (
                        actor_id, channel, value, visibility, status, revision
                    )
                    VALUES (
                        :actor_id, :channel, :value, :visibility, :status, :revision
                    )
                    """
                ),
                payload,
            )


def test_creation_stores_private_active_revision_one(api, db_session):
    user = _user(db_session, "i71-criar@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id, value="  +258 84 000 0111  ")

    assert created.status_code == 201
    body = created.json()
    assert set(body) == CONTACT_KEYS
    assert body["channel"] == "phone"
    assert body["value"] == PHONE
    assert body["visibility"] == "private"
    assert body["status"] == "active"
    assert body["revision"] == 1
    assert body["created_at"] == body["updated_at"]
    assert "actor_id" not in body
    stored = db_session.get(PublicContact, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.actor_id == actor_id
    assert stored.visibility is ContactVisibility.PRIVATE
    assert stored.status is ContactStatus.ACTIVE
    assert stored.revision == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"actor_id": uuid.uuid4()},
        {"channel": "fax"},
        {"status": "archived"},
        {"visibility": "secret"},
        {"revision": 0},
        {"revision": -1},
        {"value": "   "},
        {"value": "a" * 321},
        {"status": "inactive", "visibility": "public"},
    ],
)
def test_postgres_rejects_invalid_contact_rows(db_session, overrides):
    actor = Actor(
        kind=ActorKind.PERSON,
        display_name="Titular",
        general_location=None,
        status=ActorStatus.ACTIVE,
    )
    db_session.add(actor)
    db_session.flush()
    payload = {
        "actor_id": actor.id,
        "channel": "phone",
        "value": PHONE,
        "visibility": "private",
        "status": "active",
        "revision": 1,
    }
    payload.update(overrides)
    _reject_sql(db_session, payload)
    assert _rows(db_session, actor.id) == []


def test_uniqueness_allows_the_documented_repetitions(db_session):
    first = Actor(
        kind=ActorKind.PERSON,
        display_name="Primeiro",
        status=ActorStatus.ACTIVE,
    )
    second = Actor(
        kind=ActorKind.ORGANIZATION,
        display_name="Segundo",
        status=ActorStatus.ACTIVE,
    )
    db_session.add_all([first, second])
    db_session.flush()

    def insert(actor_id, channel, value, contact_status="active"):
        db_session.execute(
            text(
                """
                INSERT INTO public_contacts (
                    actor_id, channel, value, visibility, status, revision
                )
                VALUES (
                    :actor_id, :channel, :value, 'private', :status, 1
                )
                """
            ),
            {
                "actor_id": actor_id,
                "channel": channel,
                "value": value,
                "status": contact_status,
            },
        )

    insert(first.id, "phone", PHONE)
    insert(second.id, "phone", PHONE)
    insert(first.id, "whatsapp", PHONE)
    insert(first.id, "phone", PHONE, "inactive")
    insert(first.id, "phone", PHONE, "inactive")
    db_session.flush()
    _reject_sql(
        db_session,
        {
            "actor_id": first.id,
            "channel": "phone",
            "value": PHONE,
            "visibility": "private",
            "status": "active",
            "revision": 1,
        },
    )

    values = [row.value for row in _rows(db_session, first.id)]
    assert values.count(PHONE) == 4
    assert [row.value for row in _rows(db_session, second.id)] == [PHONE]


def test_migrated_contact_schema_matches_the_model(db_session):
    inspector = inspect(db_session.get_bind())
    table = PublicContact.__table__
    columns = inspector.get_columns(table.name)

    assert [column["name"] for column in columns] == [
        column.name for column in table.columns
    ]
    assert {column["name"]: column["nullable"] for column in columns} == {
        column.name: column.nullable for column in table.columns
    }
    assert {column["name"]: column["comment"] for column in columns} == {
        column.name: column.comment for column in table.columns
    }
    assert inspector.get_pk_constraint(table.name)["name"] == "pk_public_contacts"
    assert inspector.get_table_comment(table.name)["text"] == table.comment
    assert sorted(
        constraint["name"] for constraint in inspector.get_check_constraints(table.name)
    ) == sorted(
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )
    unique_names = sorted(
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table.name)
    )
    assert unique_names == ["uq_public_contacts_id_actor"]
    assert sorted(
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table.name)
    ) == ["fk_public_contacts_actor_id"]
    indexes = inspector.get_indexes(table.name)
    assert sorted(
        index["name"] for index in indexes if not index["unique"]
    ) == ["ix_public_contacts_actor_id"]
    assert "uq_public_contacts_active_channel_value" in {
        index["name"] for index in indexes if index["unique"]
    }

    definitions = db_session.execute(
        text(
            """
            SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'public_contacts'::regclass
            """
        )
    ).all()
    by_name = {row.conname: row.definition for row in definitions}
    assert set(QUOTED_LITERAL.findall(by_name["ck_public_contacts_channel"])) == {
        "phone",
        "email",
        "whatsapp",
    }
    assert set(QUOTED_LITERAL.findall(by_name["ck_public_contacts_visibility"])) == {
        "private",
        "public",
    }
    assert set(QUOTED_LITERAL.findall(by_name["ck_public_contacts_status"])) == {
        "active",
        "inactive",
    }
    assert "revision >= 1" in by_name["ck_public_contacts_revision"]
    assert "char_length(value) <= 320" in by_name["ck_public_contacts_value"]
    assert "ON DELETE RESTRICT" in by_name["fk_public_contacts_actor_id"]
    partial = db_session.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE indexname = 'uq_public_contacts_active_channel_value'
            """
        )
    ).scalar_one()
    assert "UNIQUE" in partial
    assert "status" in partial
    assert "active" in partial


def test_contacts_migration_preserves_existing_rows_on_a_throwaway_database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    name = f"kaivita_i71_{uuid.uuid4().hex[:12]}"
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

        _alembic(environment, "upgrade", "0004_offers")
        planted = _plant_offer(target)
        _alembic(environment, "upgrade", "0005_contacts")
        upgraded = _contact_state(target)
        assert upgraded["version"] == "0005_contacts"
        assert upgraded["contacts"] is not None
        assert upgraded["contact_count"] == 0
        assert upgraded["offer"]["offer_id"] == planted["offer_id"]
        assert upgraded["product"]["name"] == planted["name"]
        assert upgraded["partial"] is not None
        assert "uq_public_contacts_id_actor" in upgraded["constraints"]
        assert "ck_public_contacts_inactive_private" in upgraded["constraints"]

        _alembic(environment, "downgrade", "0004_offers")
        restored = _contact_state(target)
        assert restored["version"] == "0004_offers"
        assert restored["contacts"] is None
        assert restored["offer"]["offer_id"] == planted["offer_id"]
        assert restored["product"]["name"] == planted["name"]

        _alembic(environment, "upgrade", "0005_contacts")
        again = _contact_state(target)
        assert again["version"] == "0005_contacts"
        assert again["contacts"] is not None
        assert again["contact_count"] == 0
        assert again["offer"]["offer_id"] == planted["offer_id"]
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


@pytest.mark.parametrize(
    ("channel", "raw", "stored"),
    [
        ("phone", "+258840000111", PHONE),
        ("whatsapp", "+258870000111", WHATSAPP),
        ("phone", "+258 84-000.0111", PHONE),
        ("phone", "+(258) 84 000 0111", PHONE),
        ("whatsapp", " +258 87 000 0111 ", WHATSAPP),
    ],
)
def test_phone_and_whatsapp_accept_unambiguous_forms(api, db_session, channel, raw, stored):
    user = _user(db_session, f"i71-valido-{channel}-{uuid.uuid4().hex[:6]}@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id, channel=channel, value=raw)

    assert created.status_code == 201, created.text
    assert created.json()["value"] == stored
    assert created.json()["channel"] == channel
    assert created.json()["visibility"] == "private"


@pytest.mark.parametrize(
    ("channel", "raw", "secret"),
    [
        ("phone", "258840000111", "258840000111"),
        ("phone", "+2588400", "+2588400"),
        ("whatsapp", "+25884000011123456", "23456"),
        ("phone", "+258８４０００００１１１", "８４０"),
        ("phone", "+012345678", "+012345678"),
        ("whatsapp", "+258840000111 ext 9", "ext 9"),
        ("phone", "https://wa.me/258840000111", "wa.me"),
        ("phone", "<b>+258840000111</b>", "<b>"),
        ("email", "a@example.com,b@example.com", "b@example.com"),
        ("email", "Nome <produtor@example.com>", "Nome <"),
        ("email", "produtor@example.com\nsecundo@example.com", "secundo@example.com"),
        ("email", "produtor@example.com?assunto=1", "assunto=1"),
        ("email", "produtor@example.com<script>", "<script>"),
        ("email", "a@example.com\x00", "example.com"),
    ],
)
def test_rejected_contact_values_are_not_echoed(api, db_session, channel, raw, secret):
    user = _user(db_session, f"i71-eco-{uuid.uuid4().hex[:8]}@example.com")
    actor_id = _actor(api, user)
    rejected = _add(api, user, actor_id, channel=channel, value=raw)

    assert rejected.status_code == 422
    assert secret not in rejected.text
    assert all("input" not in error for error in rejected.json()["detail"])
    assert _rows(db_session, actor_id) == []


def test_email_preserves_the_local_part_and_lowercases_the_domain(api, db_session):
    user = _user(db_session, "i71-email@example.com")
    actor_id = _actor(api, user)
    created = _add(
        api,
        user,
        actor_id,
        channel="email",
        value="  Produtor.Sintetico@Example.COM ",
    )

    assert created.status_code == 201, created.text
    assert created.json()["value"] == EMAIL
    assert created.json()["value"] != user.email


def test_duplicate_after_normalization_is_rejected_without_the_value(api, db_session):
    user = _user(db_session, "i71-duplicado@example.com")
    actor_id = _actor(api, user)
    first = _add(api, user, actor_id, value=PHONE)
    second = _add(api, user, actor_id, value="+258 84-000.0111")

    assert first.status_code == 201
    assert second.status_code == 422
    assert second.json() == DUPLICATE
    assert PHONE not in second.text
    assert len(_rows(db_session, actor_id)) == 1


def test_omitted_null_and_extra_fields_are_rejected(api, db_session):
    user = _user(db_session, "i71-campos@example.com")
    actor_id = _actor(api, user)
    headers = _bearer(user)
    path = f"/actors/{actor_id}/contacts"
    secret = "+258849999999"
    rejected = [
        api.post(path, headers=headers, json={"channel": "phone"}),
        api.post(path, headers=headers, json={"value": secret}),
        api.post(path, headers=headers, json={"channel": None, "value": secret}),
        api.post(path, headers=headers, json={"channel": "phone", "value": None}),
        api.post(
            path,
            headers=headers,
            json={
                "channel": "phone",
                "value": secret,
                "visibility": "public",
                "status": "inactive",
                "revision": 9,
                "actor_id": str(uuid.uuid4()),
            },
        ),
    ]

    for response in rejected:
        assert response.status_code == 422
        assert secret not in response.text
        assert "public" not in response.text or "visibility" not in response.text
        assert all("input" not in error for error in response.json()["detail"])
    assert _rows(db_session, actor_id) == []


def test_manage_creates_and_read_only_consults(api, db_session):
    manager = _user(db_session, "i71-gere@example.com")
    reader = _user(db_session, "i71-le@example.com")
    actor_id = _actor(api, manager)
    access = db_session.get(UserActorAccess, (reader.id, actor_id))
    assert access is None
    db_session.add(
        UserActorAccess(
            user_id=reader.id,
            actor_id=actor_id,
            access_level=AccessLevel.READ,
            status=AccessStatus.ACTIVE,
        )
    )
    db_session.flush()
    created = _add(api, manager, actor_id, channel="email", value=EMAIL)
    contact_id = created.json()["id"]
    headers = _bearer(reader)
    base = f"/actors/{actor_id}/contacts"

    listing = api.get(base, headers=headers)
    single = api.get(f"{base}/{contact_id}", headers=headers)
    denied_create = api.post(
        base,
        headers=headers,
        json={"channel": "phone", "value": OTHER_PHONE},
    )
    denied_update = api.patch(
        f"{base}/{contact_id}",
        headers=headers,
        json={"value": OTHER_PHONE},
    )
    denied_deactivate = api.post(f"{base}/{contact_id}/deactivate", headers=headers)

    assert listing.status_code == 200
    assert listing.json()["items"][0]["value"] == EMAIL
    assert single.status_code == 200
    assert denied_create.status_code == 404
    assert denied_update.status_code == 404
    assert denied_deactivate.status_code == 404
    assert denied_create.json() == ACTOR_MISSING
    stored = db_session.get(PublicContact, uuid.UUID(contact_id))
    assert stored.value == EMAIL
    assert stored.status is ContactStatus.ACTIVE
    assert len(_rows(db_session, actor_id)) == 1


def test_inaccessible_actors_and_accounts_stay_opaque(api, db_session):
    owner = _user(db_session, "i71-dono@example.com")
    outsider = _user(db_session, "i71-fora@example.com")
    revoked = _user(db_session, "i71-revogado@example.com")
    disabled = _user(db_session, "i71-desactivado@example.com")
    actor_id = _actor(api, owner)
    created = _add(api, owner, actor_id)
    contact_id = created.json()["id"]
    for user in (revoked, disabled):
        db_session.add(
            UserActorAccess(
                user_id=user.id,
                actor_id=actor_id,
                access_level=AccessLevel.MANAGE,
                status=AccessStatus.ACTIVE,
            )
        )
    db_session.flush()
    revoked_access = db_session.get(UserActorAccess, (revoked.id, actor_id))
    revoked_access.status = AccessStatus.REVOKED
    disabled.status = UserStatus.DISABLED
    db_session.flush()
    base = f"/actors/{actor_id}/contacts"

    anonymous = api.get(base)
    stranger = api.get(base, headers=_bearer(outsider))
    lost = api.get(base, headers=_bearer(revoked))
    closed = api.get(base, headers=_bearer(disabled))
    missing_actor = api.get(
        f"/actors/{uuid.uuid4()}/contacts",
        headers=_bearer(owner),
    )
    missing_contact = api.get(
        f"{base}/{uuid.uuid4()}",
        headers=_bearer(owner),
    )

    assert anonymous.status_code == 401
    assert anonymous.json() == UNAUTHORIZED
    assert anonymous.headers["cache-control"] == "private, no-store"
    assert stranger.status_code == 404
    assert stranger.json() == ACTOR_MISSING
    assert PHONE not in stranger.text
    assert lost.status_code == 404
    assert lost.json() == ACTOR_MISSING
    assert closed.status_code == 401
    assert missing_actor.status_code == 404
    assert missing_actor.json() == ACTOR_MISSING
    assert missing_contact.status_code == 404
    assert missing_contact.json() == CONTACT_MISSING
    assert db_session.get(PublicContact, uuid.UUID(contact_id)).value == PHONE


def test_a_user_who_represents_both_actors_cannot_cross_contacts(api, db_session):
    user = _user(db_session, "i71-ambos@example.com")
    first = _actor(api, user, name="Casa A")
    second = _actor(api, user, name="Casa B")
    created = _add(api, user, first, value=PHONE)
    contact_id = created.json()["id"]
    headers = _bearer(user)

    own = api.get(f"/actors/{first}/contacts/{contact_id}", headers=headers)
    crossed = api.get(f"/actors/{second}/contacts/{contact_id}", headers=headers)
    listed = api.get(f"/actors/{second}/contacts", headers=headers)
    moved = api.patch(
        f"/actors/{second}/contacts/{contact_id}",
        headers=headers,
        json={"value": OTHER_PHONE},
    )

    assert own.status_code == 200
    assert crossed.status_code == 404
    assert crossed.json() == CONTACT_MISSING
    assert PHONE not in crossed.text
    assert listed.json() == {"items": []}
    assert moved.status_code == 404
    assert db_session.get(PublicContact, uuid.UUID(contact_id)).actor_id == first
    assert db_session.get(PublicContact, uuid.UUID(contact_id)).value == PHONE


def test_buyer_and_inactive_actor_can_keep_private_contacts(api, db_session):
    user = _user(db_session, "i71-comprador@example.com")
    buyer = _actor(api, user, name="Só comprador", roles=["buyer"])
    created = _add(api, user, buyer, channel="email", value=EMAIL)
    actor = db_session.get(Actor, buyer)
    actor.status = ActorStatus.INACTIVE
    db_session.flush()
    another = _add(api, user, buyer, value=OTHER_PHONE)

    assert created.status_code == 201
    assert another.status_code == 201
    assert another.json()["visibility"] == "private"
    assert {row.channel.value for row in _rows(db_session, buyer)} == {"email", "phone"}


def test_revision_tracks_only_effective_channel_or_value_changes(api, db_session):
    user = _user(db_session, "i71-revisao@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id, value=PHONE)
    contact_id = created.json()["id"]
    path = f"/actors/{actor_id}/contacts/{contact_id}"
    headers = _bearer(user)
    equivalent = api.patch(path, headers=headers, json={"value": "+258 84-000.0111"})
    empty = api.patch(path, headers=headers, json={})
    changed = api.patch(path, headers=headers, json={"value": OTHER_PHONE})
    switched = api.patch(path, headers=headers, json={"channel": "whatsapp"})

    assert equivalent.status_code == 200
    assert equivalent.json()["revision"] == 1
    assert equivalent.json()["updated_at"] == created.json()["updated_at"]
    assert empty.status_code == 200
    assert empty.json()["revision"] == 1
    assert changed.status_code == 200
    assert changed.json()["revision"] == 2
    assert changed.json()["value"] == OTHER_PHONE
    assert changed.json()["visibility"] == "private"
    assert switched.status_code == 200
    assert switched.json()["channel"] == "whatsapp"
    assert switched.json()["value"] == OTHER_PHONE
    assert switched.json()["revision"] == 3
    stored = db_session.get(PublicContact, uuid.UUID(contact_id))
    db_session.refresh(stored)
    assert stored.revision == 3
    assert stored.visibility is ContactVisibility.PRIVATE


def test_invalid_or_duplicate_updates_do_not_change_the_row(api, db_session):
    user = _user(db_session, "i71-inalterado@example.com")
    actor_id = _actor(api, user)
    first = _add(api, user, actor_id, value=PHONE)
    second = _add(api, user, actor_id, value=OTHER_PHONE)
    path = f"/actors/{actor_id}/contacts/{second.json()['id']}"
    headers = _bearer(user)
    wrong_channel = api.patch(path, headers=headers, json={"channel": "email"})
    db_session.expire_all()
    after_channel = db_session.get(PublicContact, uuid.UUID(second.json()["id"]))
    duplicate = api.patch(path, headers=headers, json={"value": "+258 84 000 0111"})
    db_session.expire_all()
    after_duplicate = db_session.get(PublicContact, uuid.UUID(second.json()["id"]))

    assert wrong_channel.status_code == 422
    assert "Email inválido." in wrong_channel.text
    assert OTHER_PHONE not in wrong_channel.text
    assert after_channel.channel is ContactChannel.PHONE
    assert after_channel.value == OTHER_PHONE
    assert after_channel.revision == 1
    assert duplicate.status_code == 422
    assert duplicate.json() == DUPLICATE
    assert PHONE not in duplicate.text
    assert after_duplicate.value == OTHER_PHONE
    assert after_duplicate.revision == 1
    assert db_session.get(PublicContact, uuid.UUID(first.json()["id"])).value == PHONE


def test_deactivation_is_idempotent_and_blocks_later_edits(api, db_session):
    user = _user(db_session, "i71-desactivar@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id, value=PHONE)
    contact_id = created.json()["id"]
    changed = api.patch(
        f"/actors/{actor_id}/contacts/{contact_id}",
        headers=_bearer(user),
        json={"value": OTHER_PHONE},
    )
    path = f"/actors/{actor_id}/contacts/{contact_id}/deactivate"
    first = api.post(path, headers=_bearer(user))
    second = api.post(path, headers=_bearer(user))
    edited = api.patch(
        f"/actors/{actor_id}/contacts/{contact_id}",
        headers=_bearer(user),
        json={"value": PHONE},
    )
    removed = api.delete(
        f"/actors/{actor_id}/contacts/{contact_id}",
        headers=_bearer(user),
    )
    restored = api.post(
        f"/actors/{actor_id}/contacts/{contact_id}/activate",
        headers=_bearer(user),
    )

    assert changed.json()["revision"] == 2
    assert first.status_code == 200
    assert first.json()["status"] == "inactive"
    assert first.json()["visibility"] == "private"
    assert first.json()["revision"] == 2
    assert first.json()["value"] == OTHER_PHONE
    assert second.status_code == 200
    assert second.json()["revision"] == 2
    assert second.json()["updated_at"] == first.json()["updated_at"]
    assert edited.status_code == 409
    assert edited.json() == INACTIVE
    assert removed.status_code == 405
    assert restored.status_code == 404
    stored = db_session.get(PublicContact, uuid.UUID(contact_id))
    db_session.refresh(stored)
    assert stored.status is ContactStatus.INACTIVE
    assert stored.revision == 2
    replacement = _add(api, user, actor_id, value=OTHER_PHONE)
    assert replacement.status_code == 201
    assert replacement.json()["revision"] == 1


def test_listing_is_deterministic_and_empty_when_there_are_no_contacts(api, db_session):
    user = _user(db_session, "i71-lista@example.com")
    actor_id = _actor(api, user)
    empty = api.get(f"/actors/{actor_id}/contacts", headers=_bearer(user))
    _add(api, user, actor_id, channel="whatsapp", value=WHATSAPP)
    _add(api, user, actor_id, channel="email", value=EMAIL)
    _add(api, user, actor_id, channel="phone", value=PHONE)
    listed = api.get(f"/actors/{actor_id}/contacts", headers=_bearer(user))

    assert empty.status_code == 200
    assert empty.json() == {"items": []}
    assert [
        (item["channel"], item["value"]) for item in listed.json()["items"]
    ] == [
        ("email", EMAIL),
        ("phone", PHONE),
        ("whatsapp", WHATSAPP),
    ]


def test_concurrent_creates_and_updates_keep_one_active_value(migrated_database):
    stamp = uuid.uuid4().hex[:8]
    email = f"i71-conc-{stamp}@example.com"
    user_id, actor_id = _commit_actor(email)
    try:
        created = _race(
            lambda: _create_same(actor_id, "+258840000303"),
            lambda: _create_same(actor_id, "+258840000303"),
        )
        assert sorted(created) == ["created", "duplicate"]

        with Session(engine) as session:
            actor = session.get(Actor, actor_id)
            left = create_contact(session, actor, ContactChannel.PHONE, "+258840000301")
            right = create_contact(session, actor, ContactChannel.PHONE, "+258840000302")
            session.commit()
            left_id, right_id = left.id, right.id

        duplicated = _race(
            lambda: _retarget(actor_id, left_id, "+258840000399"),
            lambda: _retarget(actor_id, right_id, "+258840000399"),
        )
        assert sorted(duplicated) == ["duplicate", "updated"]

        with Session(engine) as session:
            actor = session.get(Actor, actor_id)
            moving = create_contact(session, actor, ContactChannel.PHONE, "+258840000304")
            session.commit()
            moving_id = moving.id

        revised = _race(
            lambda: _retarget(actor_id, moving_id, "+258840000401"),
            lambda: _retarget(actor_id, moving_id, "+258840000402"),
        )
        assert revised == ["updated", "updated"]

        with Session(engine) as session:
            rows = list(
                session.scalars(
                    select(PublicContact).where(PublicContact.actor_id == actor_id)
                )
            )
            winner = session.get(PublicContact, moving_id)
        assert sum(
            row.value == "+258840000303" and row.status is ContactStatus.ACTIVE
            for row in rows
        ) == 1
        assert sum(
            row.value == "+258840000399" and row.status is ContactStatus.ACTIVE
            for row in rows
        ) == 1
        assert winner is not None
        assert winner.revision == 3
        assert winner.value in {"+258840000401", "+258840000402"}
    finally:
        _erase(user_id, actor_id)


def test_committed_contact_is_visible_before_the_response_finishes(migrated_database):
    stamp = uuid.uuid4().hex[:8]
    email = f"i71-visivel-{stamp}@example.com"
    user_id = None
    actor_id = None
    try:
        user_id = _create_user(email)
        with TestClient(app) as client:
            token = _login(client, email)
            actor_id = _create_actor(client, token, f"Visível {stamp}")
            created = _observe_write(
                "POST",
                f"/actors/{actor_id}/contacts",
                token,
                {"channel": "phone", "value": PHONE},
            )
            assert created["status"] == 201, created
            changed = _observe_write(
                "PATCH",
                f"/actors/{actor_id}/contacts/{created['body']['id']}",
                token,
                {"value": OTHER_PHONE},
            )
            assert changed["status"] == 200, changed
        assert created["visible"] is True
        assert created["body"]["visibility"] == "private"
        assert changed["visible"] is True
        assert changed["body"]["revision"] == 2
        assert changed["body"]["value"] == OTHER_PHONE
    finally:
        _erase(user_id, actor_id)


def test_login_email_is_not_copied_and_public_offers_omit_contacts(api, db_session):
    token = uuid.uuid4().hex
    user = _user(db_session, f"i71-login-{token[:8]}@example.com")
    actor_id = _actor(api, user, name=f"Produtor {token}")
    empty = api.get(f"/actors/{actor_id}/contacts", headers=_bearer(user))
    created = _add(api, user, actor_id, value=PHONE)
    contact = db_session.get(PublicContact, uuid.UUID(created.json()["id"]))
    contact.visibility = ContactVisibility.PUBLIC
    db_session.flush()
    product = api.post(
        f"/actors/{actor_id}/products",
        headers=_bearer(user),
        json={
            "name": f"Mel {token}",
            "description": "Mel de exemplo",
            "category": "mel",
        },
    )
    offer = api.post(
        f"/actors/{actor_id}/offers",
        headers=_bearer(user),
        json={
            "product_id": product.json()["id"],
            "price": "150.00",
            "currency": "MZN",
            "quantity": "2.50",
            "unit": "kg",
            "availability": "available",
        },
    )
    published = api.post(
        f"/actors/{actor_id}/offers/{offer.json()['id']}/publish",
        headers=_bearer(user),
    )
    listing = api.get("/public/offers", params={"q": token})
    detail = api.get(f"/public/offers/{offer.json()['id']}")
    absent = api.get(f"/public/offers/{offer.json()['id']}/contacts")

    assert empty.json() == {"items": []}
    assert user.email not in empty.text
    assert created.json()["value"] != user.email
    assert published.status_code == 200
    assert listing.status_code == 200
    assert detail.status_code == 200
    assert set(detail.json()) == PUBLIC_KEYS
    assert PHONE not in listing.text
    assert PHONE not in detail.text
    assert user.email not in detail.text
    assert "visibility" not in detail.text
    assert detail.headers["cache-control"] == "no-store"
    assert PHONE not in absent.text
    private = api.get(
        f"/actors/{actor_id}/contacts/{created.json()['id']}",
        headers=_bearer(user),
    )
    assert private.headers["cache-control"] == "private, no-store"
    assert private.json()["visibility"] == "public"


def test_private_contact_errors_are_not_cached_and_logs_omit_the_value(
    api, db_session, caplog
):
    user = _user(db_session, "i71-log@example.com")
    actor_id = _actor(api, user)
    secret = "+25884SEGREDO71"
    with caplog.at_level(logging.DEBUG):
        rejected = _add(api, user, actor_id, value=secret)
        missing = api.get(
            f"/actors/{actor_id}/contacts/{uuid.uuid4()}",
            headers=_bearer(user),
        )

    assert rejected.status_code == 422
    assert secret not in rejected.text
    assert rejected.headers["cache-control"] == "private, no-store"
    assert missing.status_code == 404
    assert missing.headers["cache-control"] == "private, no-store"
    assert secret not in caplog.text


def test_openapi_documents_the_private_contact_contract(client):
    document = client.get("/openapi.json").json()
    paths = document["paths"]
    collection = "/actors/{actor_id}/contacts"
    single = "/actors/{actor_id}/contacts/{contact_id}"
    deactivate = f"{single}/deactivate"
    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    schemas = document["components"]["schemas"]

    assert set(paths[collection]) & methods == {"get", "post"}
    assert set(paths[single]) & methods == {"get", "patch"}
    assert set(paths[deactivate]) & methods == {"post"}
    assert "/public/offers/{offer_id}/contacts" not in paths
    for path in (collection, single, deactivate):
        for operation in paths[path].values():
            if isinstance(operation, dict) and "responses" in operation:
                assert operation["security"] == [{"HTTPBearer": []}]
    assert set(schemas["ContactResponse"]["properties"]) == CONTACT_KEYS
    assert set(schemas["ContactResponse"]["required"]) == CONTACT_KEYS
    assert schemas["ContactResponse"]["additionalProperties"] is False
    assert "actor_id" not in schemas["ContactResponse"]["properties"]
    assert set(schemas["ContactListResponse"]["required"]) == {"items"}
    assert set(schemas["ContactCreate"]["properties"]) == {"channel", "value"}
    assert schemas["ContactCreate"]["additionalProperties"] is False
    assert set(schemas["ContactUpdate"]["properties"]) == {"channel", "value"}
    assert "authorization_id" not in schemas["ContactResponse"]["properties"]


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


def _plant_offer(database_url: str) -> dict[str, str]:
    checked = create_engine(database_url)
    try:
        with checked.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (email, password_hash, status)
                    VALUES ('preservar-i71@example.com', 'hash-de-teste', 'active')
                    """
                )
            )
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
                {
                    "actor_id": actor_id,
                    "role_id": COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER],
                },
            )
            product_id = connection.execute(
                text(
                    """
                    INSERT INTO products (
                        owner_actor_id, name, description, category, status
                    )
                    VALUES (
                        :actor_id, 'Mel antigo', 'Antes dos contactos', 'mel', 'active'
                    )
                    RETURNING id
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
        return {
            "actor_id": str(actor_id),
            "product_id": str(product_id),
            "offer_id": str(offer_id),
            "name": "Mel antigo",
        }
    finally:
        checked.dispose()


def _contact_state(database_url: str) -> dict:
    checked = create_engine(database_url)
    try:
        with checked.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            contacts = connection.execute(
                text("SELECT to_regclass('public.public_contacts')")
            ).scalar_one()
            contact_count = 0
            if contacts is not None:
                contact_count = connection.execute(
                    text("SELECT count(*) FROM public_contacts")
                ).scalar_one()
            constraints = {
                row[0]
                for row in connection.execute(
                    text(
                        """
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid = to_regclass('public.public_contacts')
                        """
                    )
                )
            }
            partial = connection.execute(
                text(
                    """
                    SELECT indexdef
                    FROM pg_indexes
                    WHERE indexname = 'uq_public_contacts_active_channel_value'
                    """
                )
            ).scalar_one_or_none()
            product = connection.execute(
                text(
                    """
                    SELECT name
                    FROM products
                    WHERE name = 'Mel antigo'
                    """
                )
            ).one_or_none()
            offer = connection.execute(
                text(
                    """
                    SELECT id::text AS id
                    FROM offers
                    WHERE status = 'draft'
                    """
                )
            ).one_or_none()
        return {
            "version": version,
            "contacts": contacts,
            "contact_count": contact_count,
            "constraints": constraints,
            "partial": partial,
            "product": None if product is None else {"name": product.name},
            "offer": None if offer is None else {"offer_id": offer.id},
        }
    finally:
        checked.dispose()


def _create_same(actor_id: uuid.UUID, value: str) -> str:
    with Session(engine) as session:
        try:
            actor = session.get(Actor, actor_id)
            create_contact(session, actor, ContactChannel.PHONE, value)
            session.commit()
        except ContactDuplicate:
            session.rollback()
            return "duplicate"
    return "created"


def _retarget(actor_id: uuid.UUID, contact_id: uuid.UUID, value: str) -> str:
    with Session(engine) as session:
        try:
            actor = session.get(Actor, actor_id)
            update_contact(session, actor, contact_id, {"value": value})
            session.commit()
        except ContactDuplicate:
            session.rollback()
            return "duplicate"
    return "updated"


def _race(first, second) -> list[str]:
    barrier = threading.Barrier(2)
    results: list[str] = []

    def run(operation):
        try:
            barrier.wait(timeout=5)
            results.append(operation())
        except Exception as exc:
            results.append(f"error:{type(exc).__name__}:{exc}")

    threads = [
        threading.Thread(target=run, args=(first,)),
        threading.Thread(target=run, args=(second,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def _commit_actor(email: str) -> tuple[uuid.UUID, uuid.UUID]:
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
        session.commit()
        return user.id, actor.id


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


def _observe_write(method: str, path: str, token: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
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
            row = None
            if "id" in parsed:
                row = session.get(PublicContact, uuid.UUID(parsed["id"]))
        observed["visible"] = row is not None and row.value == parsed.get("value")
        observed["body"] = parsed

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"application/json"),
            (b"authorization", f"Bearer {token}".encode()),
        ],
        "client": ("127.0.0.1", 9),
        "server": ("test", 80),
    }
    asyncio.run(app(scope, receive, send))
    return observed


def _erase(user_id: uuid.UUID | None, actor_id: uuid.UUID | str | None) -> None:
    with Session(engine) as session:
        if actor_id is not None:
            owner = actor_id if isinstance(actor_id, uuid.UUID) else uuid.UUID(actor_id)
            session.execute(delete(PublicContact).where(PublicContact.actor_id == owner))
            session.execute(delete(Offer).where(Offer.owner_actor_id == owner))
            session.execute(delete(Product).where(Product.owner_actor_id == owner))
            session.execute(delete(ActorRole).where(ActorRole.actor_id == owner))
            session.execute(
                delete(UserActorAccess).where(UserActorAccess.actor_id == owner)
            )
            actor = session.get(Actor, owner)
            if actor is not None:
                session.delete(actor)
        if user_id is not None:
            session.execute(
                delete(UserActorAccess).where(UserActorAccess.user_id == user_id)
            )
            user = session.get(User, user_id)
            if user is not None:
                session.delete(user)
        session.commit()
