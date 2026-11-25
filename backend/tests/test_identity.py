"""Persistência e integridade do modelo de identidade, com PostgreSQL real.

Os testes que abrem a base só correm com RUN_DB_TESTS=1, como no I0.
As rejeições são INSERT/DELETE em SQL, para a restrição provada ser a
da base e não a validação do enumerado em Python.
"""

import os
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import CheckConstraint, UniqueConstraint

from app.db import engine
from app.identity import (
    COMMERCIAL_ROLE_IDS,
    AccessLevel,
    AccessStatus,
    Actor,
    ActorKind,
    ActorRole,
    ActorStatus,
    Role,
    RoleCode,
    User,
    UserActorAccess,
    UserStatus,
    seed_commercial_roles,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD_HASH = "stored-hash-not-checked-here"
QUOTED_LITERAL = re.compile(r"'([a-z_]+)'")


def test_mapped_model_declares_the_identity_contract():
    tables = {
        "users": User.__table__,
        "actors": Actor.__table__,
        "roles": Role.__table__,
        "actor_roles": ActorRole.__table__,
        "user_actor_access": UserActorAccess.__table__,
    }

    assert {name: table.primary_key.name for name, table in tables.items()} == {
        name: f"pk_{name}" for name in tables
    }
    assert [column.name for column in tables["users"].columns] == [
        "id",
        "email",
        "password_hash",
        "status",
    ]
    assert [column.name for column in tables["actors"].columns] == [
        "id",
        "kind",
        "display_name",
        "general_location",
        "status",
    ]
    assert [column.name for column in tables["roles"].columns] == ["id", "code"]
    assert [column.name for column in tables["actor_roles"].primary_key.columns] == [
        "actor_id",
        "role_id",
    ]
    assert [
        column.name for column in tables["user_actor_access"].primary_key.columns
    ] == ["user_id", "actor_id"]
    assert tables["actors"].columns["general_location"].nullable is True

    unique_names = {
        constraint.name
        for table in tables.values()
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_names = {
        constraint.name
        for table in tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    foreign_keys = {
        foreign_key.constraint.name: foreign_key.constraint.ondelete
        for table in tables.values()
        for foreign_key in table.foreign_keys
    }

    assert unique_names == {"uq_users_email", "uq_roles_code"}
    assert check_names == {
        "ck_users_email",
        "ck_users_password_hash",
        "ck_users_status",
        "ck_actors_kind",
        "ck_actors_display_name",
        "ck_actors_general_location",
        "ck_actors_status",
        "ck_roles_code",
        "ck_user_actor_access_level",
        "ck_user_actor_access_status",
    }
    assert foreign_keys == {
        "fk_actor_roles_actor_id": "RESTRICT",
        "fk_actor_roles_role_id": "RESTRICT",
        "fk_user_actor_access_user_id": "RESTRICT",
        "fk_user_actor_access_actor_id": "RESTRICT",
    }
    assert {code.value for code in RoleCode} == {"producer", "buyer", "partner"}
    assert len(set(COMMERCIAL_ROLE_IDS.values())) == 3


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
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def _reject(session: Session, statement: str, params: dict | None = None) -> None:
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(text(statement), params or {})


def test_role_catalog_remains_after_the_products_revision(db_session):
    version = db_session.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one()
    roles = db_session.execute(select(Role).order_by(Role.code)).scalars().all()

    # A cabeça corrente é a dos contactos. Os papéis semeados no 0002 mantêm-se.
    assert version == "0005_contacts"
    assert [role.code for role in roles] == [
        RoleCode.BUYER,
        RoleCode.PARTNER,
        RoleCode.PRODUCER,
    ]
    assert {role.code: role.id for role in roles} == COMMERCIAL_ROLE_IDS


def test_commercial_role_seed_is_idempotent(db_session):
    # A transacção do teste desfaz estes DELETE. Associações já gravadas
    # na base de desenvolvimento não ficam apagadas.
    db_session.execute(text("DELETE FROM actor_roles"))
    db_session.execute(text("DELETE FROM roles"))
    seed_commercial_roles(db_session.connection())
    seed_commercial_roles(db_session.connection())
    db_session.execute(
        text(
            """
            INSERT INTO roles (id, code)
            VALUES (:id, 'producer')
            ON CONFLICT ON CONSTRAINT uq_roles_code DO NOTHING
            """
        ),
        {"id": uuid.uuid4()},
    )

    rows = db_session.execute(
        text("SELECT code, id FROM roles ORDER BY code")
    ).all()

    assert len(rows) == 3
    assert {row.code: row.id for row in rows} == {
        code.value: role_id for code, role_id in COMMERCIAL_ROLE_IDS.items()
    }


def test_persists_roles_and_representation_and_reads_them_back(db_session):
    association = Actor(
        kind=ActorKind.ORGANIZATION,
        display_name="Associação dos Apicultores",
        general_location=None,
        status=ActorStatus.ACTIVE,
    )
    producer = Actor(
        kind=ActorKind.PERSON,
        display_name="Marta",
        general_location="Maputo",
        status=ActorStatus.ACTIVE,
    )
    ana = User(
        email="ana@example.com",
        password_hash=PASSWORD_HASH,
        status=UserStatus.ACTIVE,
    )
    bia = User(
        email="bia@example.com",
        password_hash=PASSWORD_HASH,
        status=UserStatus.DISABLED,
    )
    db_session.add_all([association, producer, ana, bia])
    db_session.flush()

    roles = {
        role.code: role
        for role in db_session.execute(select(Role)).scalars()
    }
    db_session.add_all(
        [
            ActorRole(actor_id=association.id, role_id=roles[RoleCode.PRODUCER].id),
            ActorRole(actor_id=association.id, role_id=roles[RoleCode.BUYER].id),
            ActorRole(actor_id=producer.id, role_id=roles[RoleCode.PRODUCER].id),
            UserActorAccess(
                user_id=ana.id,
                actor_id=association.id,
                access_level=AccessLevel.MANAGE,
                status=AccessStatus.ACTIVE,
            ),
            UserActorAccess(
                user_id=bia.id,
                actor_id=association.id,
                access_level=AccessLevel.READ,
                status=AccessStatus.REVOKED,
            ),
            UserActorAccess(
                user_id=ana.id,
                actor_id=producer.id,
                access_level=AccessLevel.MANAGE,
                status=AccessStatus.ACTIVE,
            ),
        ]
    )
    db_session.flush()

    generated_id = db_session.execute(
        text(
            """
            INSERT INTO actors (kind, display_name, status)
            VALUES ('person', 'Sem id explícito', 'active')
            RETURNING id
            """
        )
    ).scalar_one()
    stored_status = db_session.execute(
        text("SELECT status FROM users WHERE id = :id"),
        {"id": ana.id},
    ).scalar_one()

    db_session.expire_all()
    loaded = db_session.get(Actor, association.id)

    assert isinstance(generated_id, uuid.UUID)
    assert stored_status == "active"
    assert loaded is not None
    assert loaded.general_location is None
    assert {link.role.code for link in loaded.role_links} == {
        RoleCode.PRODUCER,
        RoleCode.BUYER,
    }
    assert {(access.user.email, access.access_level) for access in loaded.accesses} == {
        ("ana@example.com", AccessLevel.MANAGE),
        ("bia@example.com", AccessLevel.READ),
    }
    assert {access.actor_id for access in db_session.get(User, ana.id).accesses} == {
        association.id,
        producer.id,
    }


@pytest.mark.parametrize(
    ("statement", "params"),
    [
        (
            """
            INSERT INTO users (email, password_hash, status)
            VALUES ('ana@example.com', :password_hash, 'active')
            """,
            {"password_hash": PASSWORD_HASH},
        ),
        (
            """
            INSERT INTO users (email, password_hash, status)
            VALUES ('Ana@example.com', :password_hash, 'active')
            """,
            {"password_hash": PASSWORD_HASH},
        ),
        (
            """
            INSERT INTO users (email, password_hash, status)
            VALUES ('ana@example.com ', :password_hash, 'active')
            """,
            {"password_hash": PASSWORD_HASH},
        ),
        (
            """
            INSERT INTO users (email, password_hash, status)
            VALUES ('sem-arroba.example.com', :password_hash, 'active')
            """,
            {"password_hash": PASSWORD_HASH},
        ),
        (
            """
            INSERT INTO users (email, password_hash, status)
            VALUES ('carla@example.com', '   ', 'active')
            """,
            {},
        ),
        (
            """
            INSERT INTO users (email, password_hash, status)
            VALUES ('carla@example.com', :password_hash, 'archived')
            """,
            {"password_hash": PASSWORD_HASH},
        ),
        (
            """
            INSERT INTO actors (kind, display_name, status)
            VALUES ('company', 'Nome', 'active')
            """,
            {},
        ),
        (
            """
            INSERT INTO actors (kind, display_name, status)
            VALUES ('person', '   ', 'active')
            """,
            {},
        ),
        (
            """
            INSERT INTO actors (kind, display_name, general_location, status)
            VALUES ('person', 'Nome', '   ', 'active')
            """,
            {},
        ),
        (
            """
            INSERT INTO actors (kind, display_name, status)
            VALUES ('person', 'Nome', 'published')
            """,
            {},
        ),
        (
            """
            INSERT INTO roles (code)
            VALUES ('admin')
            """,
            {},
        ),
        (
            """
            INSERT INTO actor_roles (actor_id, role_id)
            VALUES (:actor_id, :role_id)
            """,
            "duplicate-role",
        ),
        (
            """
            INSERT INTO user_actor_access (user_id, actor_id, access_level, status)
            VALUES (:user_id, :actor_id, 'manage', 'active')
            """,
            "duplicate-access",
        ),
        (
            """
            INSERT INTO user_actor_access (user_id, actor_id, access_level, status)
            VALUES (:user_id, :actor_id, 'owner', 'active')
            """,
            "fresh-pair",
        ),
        (
            """
            INSERT INTO user_actor_access (user_id, actor_id, access_level, status)
            VALUES (:user_id, :actor_id, 'read', 'pending')
            """,
            "fresh-pair",
        ),
        (
            """
            INSERT INTO user_actor_access (user_id, actor_id, access_level, status)
            VALUES (:user_id, :missing_id, 'read', 'active')
            """,
            "missing-actor",
        ),
    ],
    ids=[
        "duplicate-email",
        "uppercase-email",
        "email-with-space",
        "email-without-at",
        "blank-password-hash",
        "unknown-user-status",
        "unknown-actor-kind",
        "blank-display-name",
        "blank-location",
        "unknown-actor-status",
        "unknown-role-code",
        "duplicate-actor-role",
        "duplicate-user-actor-access",
        "unknown-access-level",
        "unknown-access-status",
        "access-to-missing-actor",
    ],
)
def test_database_rejects_invalid_identity_rows(db_session, statement, params):
    user = User(
        email="ana@example.com",
        password_hash=PASSWORD_HASH,
        status=UserStatus.ACTIVE,
    )
    other = User(
        email="bia@example.com",
        password_hash=PASSWORD_HASH,
        status=UserStatus.ACTIVE,
    )
    actor = Actor(
        kind=ActorKind.PERSON,
        display_name="Marta",
        general_location="Maputo",
        status=ActorStatus.ACTIVE,
    )
    db_session.add_all([user, other, actor])
    db_session.flush()
    producer_id = db_session.execute(
        select(Role.id).where(Role.code == RoleCode.PRODUCER)
    ).scalar_one()
    db_session.add(
        ActorRole(actor_id=actor.id, role_id=producer_id)
    )
    db_session.add(
        UserActorAccess(
            user_id=user.id,
            actor_id=actor.id,
            access_level=AccessLevel.MANAGE,
            status=AccessStatus.ACTIVE,
        )
    )
    db_session.flush()

    if params == "duplicate-role":
        resolved_params = {"actor_id": actor.id, "role_id": producer_id}
    elif params == "duplicate-access":
        resolved_params = {"user_id": user.id, "actor_id": actor.id}
    elif params == "fresh-pair":
        resolved_params = {"user_id": other.id, "actor_id": actor.id}
    elif params == "missing-actor":
        resolved_params = {"user_id": user.id, "missing_id": uuid.uuid4()}
    else:
        resolved_params = params

    _reject(db_session, statement, resolved_params)


def test_database_restricts_delete_while_a_link_exists(db_session):
    user = User(
        email="ana@example.com",
        password_hash=PASSWORD_HASH,
        status=UserStatus.ACTIVE,
    )
    actor = Actor(
        kind=ActorKind.ORGANIZATION,
        display_name="Cooperativa",
        status=ActorStatus.ACTIVE,
    )
    db_session.add_all([user, actor])
    db_session.flush()
    producer_id = db_session.execute(
        select(Role.id).where(Role.code == RoleCode.PRODUCER)
    ).scalar_one()
    db_session.add(ActorRole(actor_id=actor.id, role_id=producer_id))
    db_session.add(
        UserActorAccess(
            user_id=user.id,
            actor_id=actor.id,
            access_level=AccessLevel.READ,
            status=AccessStatus.ACTIVE,
        )
    )
    db_session.flush()

    _reject(db_session, "DELETE FROM actors WHERE id = :id", {"id": actor.id})
    _reject(db_session, "DELETE FROM users WHERE id = :id", {"id": user.id})
    _reject(db_session, "DELETE FROM roles WHERE id = :id", {"id": producer_id})


def test_migrated_schema_matches_the_mapped_model(db_session):
    inspector = inspect(db_session.get_bind())
    tables = [
        User.__table__,
        Actor.__table__,
        Role.__table__,
        ActorRole.__table__,
        UserActorAccess.__table__,
    ]

    for table in tables:
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
        assert inspector.get_pk_constraint(table.name)["name"] == (
            f"pk_{table.name}"
        )
        assert inspector.get_pk_constraint(table.name)["constrained_columns"] == [
            column.name for column in table.primary_key.columns
        ]
        assert inspector.get_table_comment(table.name)["text"] == table.comment

        assert sorted(
            constraint["name"]
            for constraint in inspector.get_unique_constraints(table.name)
        ) == sorted(
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        )
        assert sorted(
            constraint["name"]
            for constraint in inspector.get_check_constraints(table.name)
        ) == sorted(
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        )
        assert sorted(
            foreign_key["name"]
            for foreign_key in inspector.get_foreign_keys(table.name)
        ) == sorted({foreign_key.constraint.name for foreign_key in table.foreign_keys})
        assert sorted(
            index["name"]
            for index in inspector.get_indexes(table.name)
            if not index["unique"]
        ) == sorted(index.name for index in table.indexes if not index.unique)

    definitions = db_session.execute(
        text(
            """
            SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE contype IN ('c', 'f')
              AND conrelid IN (
                'users'::regclass,
                'actors'::regclass,
                'roles'::regclass,
                'actor_roles'::regclass,
                'user_actor_access'::regclass
              )
            """
        )
    ).all()
    by_name = {row.conname: row.definition for row in definitions}

    expected_literals = {
        "ck_users_status": UserStatus,
        "ck_actors_kind": ActorKind,
        "ck_actors_status": ActorStatus,
        "ck_roles_code": RoleCode,
        "ck_user_actor_access_level": AccessLevel,
        "ck_user_actor_access_status": AccessStatus,
    }
    for constraint_name, enum_cls in expected_literals.items():
        assert set(QUOTED_LITERAL.findall(by_name[constraint_name])) == {
            member.value for member in enum_cls
        }

    for constraint_name in (
        "fk_actor_roles_actor_id",
        "fk_actor_roles_role_id",
        "fk_user_actor_access_user_id",
        "fk_user_actor_access_actor_id",
    ):
        assert "ON DELETE RESTRICT" in by_name[constraint_name]
