"""Catálogo de produtos, com PostgreSQL real.

Cada teste de API corre numa transacção desfeita no fim.
Sem RUN_DB_TESTS=1 esses testes não contactam a base.
O upgrade e o downgrade da migração usam uma base criada para o efeito
e apagada a seguir. A base de desenvolvimento não é despromovida.
"""

import os
import re
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import CheckConstraint

from app.accounts import create_active_user
from app.config import settings
from app.db import engine, get_session
from app.identity import (
    COMMERCIAL_ROLE_IDS,
    AccessLevel,
    AccessStatus,
    ActorRole,
    RoleCode,
    User,
    UserActorAccess,
)
from app.main import app
from app.products import Product, ProductStatus
from app.tokens import issue_access_token

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "palavra-de-teste"
NOT_FOUND = {"detail": "Actor não encontrado."}
PRODUCT_MISSING = {"detail": "Produto não encontrado."}
NO_PRODUCER = {"detail": "O actor não tem o papel producer."}
PRODUCT_KEYS = {
    "id",
    "owner_actor_id",
    "name",
    "description",
    "category",
    "image_ref",
    "status",
}
THROWAWAY_NAME = re.compile(r"kaivita_i3_[0-9a-f]{12}")
QUOTED_LITERAL = re.compile(r"'([a-z_]+)'")


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
) -> None:
    session.add(
        UserActorAccess(
            user_id=user.id,
            actor_id=actor_id,
            access_level=level,
            status=access_status,
        )
    )
    session.flush()


def _assert_exclusive_manage(session, user, own_actor, other_actor) -> None:
    accesses = session.scalars(
        select(UserActorAccess).where(UserActorAccess.user_id == user.id)
    ).all()
    assert len(accesses) == 1
    assert accesses[0].actor_id == own_actor
    assert accesses[0].access_level is AccessLevel.MANAGE
    assert accesses[0].status is AccessStatus.ACTIVE
    assert session.get(UserActorAccess, (user.id, other_actor)) is None


def _create_actor(api, user: User, *, name: str = "Marta", roles: list[str] | None = None):
    return api.post(
        "/actors",
        headers=_bearer(user),
        json={
            "kind": "person",
            "display_name": name,
            "general_location": "Inhambane",
            "roles": ["producer"] if roles is None else roles,
        },
    )


def _actor(api, user: User, *, name: str = "Marta", roles: list[str] | None = None) -> uuid.UUID:
    created = _create_actor(api, user, name=name, roles=roles)
    assert created.status_code == 201, created.text
    return uuid.UUID(created.json()["id"])


def _body(**overrides) -> dict:
    body = {
        "name": "Mel",
        "description": "Mel de miombo",
        "category": "mel",
    }
    body.update(overrides)
    return body


def _add(api, user: User, actor_id: uuid.UUID, **overrides):
    return api.post(
        f"/actors/{actor_id}/products",
        headers=_bearer(user),
        json=_body(**overrides),
    )


def _rows(session: Session, actor_id: uuid.UUID) -> list[Product]:
    return list(
        session.scalars(
            select(Product)
            .where(Product.owner_actor_id == actor_id)
            .order_by(Product.name, Product.id)
        )
    )


def _links(session: Session, actor_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        session.scalars(
            select(ActorRole.role_id).where(ActorRole.actor_id == actor_id)
        ).all()
    )


def _snapshot(product: Product) -> tuple:
    return (
        product.id,
        product.owner_actor_id,
        product.name,
        product.description,
        product.category,
        product.image_ref,
    )


def _reject(session: Session, statement: str, params: dict) -> None:
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(text(statement), params)


def test_mapped_product_declares_the_catalog_contract():
    table = Product.__table__

    assert [column.name for column in table.columns] == [
        "id",
        "owner_actor_id",
        "name",
        "description",
        "category",
        "image_ref",
        "status",
    ]
    assert table.primary_key.name == "pk_products"
    assert table.columns["image_ref"].nullable is True
    assert table.columns["name"].nullable is False
    assert "price" not in table.columns
    assert "quantity" not in table.columns
    assert {member.value for member in ProductStatus} == {"active", "archived"}
    assert [index.name for index in table.indexes] == ["ix_products_owner_actor_id"]
    foreign_key = next(iter(table.foreign_keys))
    assert foreign_key.constraint.name == "fk_products_owner_actor_id"
    assert foreign_key.constraint.ondelete == "RESTRICT"
    assert {constraint.name for constraint in table.constraints if isinstance(constraint, CheckConstraint)} == {
        "ck_products_name",
        "ck_products_description",
        "ck_products_category",
        "ck_products_image_ref",
        "ck_products_status",
    }


def test_openapi_exposes_the_product_catalog_without_delete(client):
    document = client.get("/openapi.json").json()
    collection = "/actors/{actor_id}/products"
    single = "/actors/{actor_id}/products/{product_id}"
    archive = "/actors/{actor_id}/products/{product_id}/archive"

    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    assert set(document["paths"][collection]) & methods == {"get", "post"}
    assert set(document["paths"][single]) & methods == {"get", "patch"}
    assert set(document["paths"][archive]) & methods == {"post"}
    assert document["paths"][collection]["post"]["security"] == [{"HTTPBearer": []}]


def test_products_migration_upgrades_and_downgrades_on_a_throwaway_database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    name = f"kaivita_i3_{uuid.uuid4().hex[:12]}"
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

        _alembic(environment, "upgrade", "0003_products")
        version, products, roles, users = _catalog_state(target)
        assert version == "0003_products"
        assert products is not None
        assert roles == 3
        assert users is not None

        _alembic(environment, "downgrade", "0002_identity_access")
        version, products, roles, users = _catalog_state(target)
        assert version == "0002_identity_access"
        assert products is None
        assert roles == 3
        assert users is not None

        _alembic(environment, "upgrade", "0003_products")
        version, products, roles, users = _catalog_state(target)
        assert version == "0003_products"
        assert products is not None
        assert roles == 3
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
        detail = _redact(completed.stderr or completed.stdout)
        raise AssertionError(f"alembic {' '.join(args)} falhou\n{detail}")


def _redact(value: str) -> str:
    return re.sub(r"://[^:\s]+:[^@\s]+@", "://", value)


def _catalog_state(database_url: str) -> tuple:
    checked = create_engine(database_url)
    try:
        with checked.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            products = connection.execute(
                text("SELECT to_regclass('public.products')")
            ).scalar_one()
            roles = connection.execute(text("SELECT count(*) FROM roles")).scalar_one()
            users = connection.execute(
                text("SELECT to_regclass('public.users')")
            ).scalar_one()
            for table in ("actors", "actor_roles", "user_actor_access"):
                found = connection.execute(
                    text(f"SELECT to_regclass('public.{table}')")
                ).scalar_one()
                assert found is not None
        return version, products, roles, users
    finally:
        checked.dispose()


def test_manager_creates_a_product(api, db_session):
    user = _user(db_session, "gestor-produto@example.com")
    actor_id = _actor(
        api,
        user,
        name="Casa do mel",
        roles=["partner", "buyer", "producer"],
    )

    created = _add(api, user, actor_id)
    again = _add(api, user, actor_id, name="Mel")

    assert created.status_code == 201
    body = created.json()
    assert set(body) == PRODUCT_KEYS
    assert body["owner_actor_id"] == str(actor_id)
    assert body["name"] == "Mel"
    assert body["description"] == "Mel de miombo"
    assert body["category"] == "mel"
    assert body["image_ref"] is None
    assert body["status"] == "active"
    assert again.status_code == 201
    assert again.json()["id"] != body["id"]
    assert user.email not in created.text
    assert PASSWORD not in created.text
    stored = _rows(db_session, actor_id)
    assert len(stored) == 2
    assert {item.owner_actor_id for item in stored} == {actor_id}
    assert _links(db_session, actor_id) == set(COMMERCIAL_ROLE_IDS.values())
    access = db_session.get(UserActorAccess, (user.id, actor_id))
    assert access is not None
    assert access.access_level is AccessLevel.MANAGE
    assert access.status is AccessStatus.ACTIVE


def test_reader_cannot_create_a_product(api, db_session):
    owner = _user(db_session, "dono-leitura@example.com")
    reader = _user(db_session, "leitor-produto@example.com")
    actor_id = _actor(api, owner, name="Actor lido")
    _grant(db_session, reader, actor_id, AccessLevel.READ)

    response = _add(api, reader, actor_id, name="Não entra")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert _rows(db_session, actor_id) == []


def test_user_without_active_representation_cannot_use_products(api, db_session):
    owner = _user(db_session, "dono-produto@example.com")
    stranger = _user(db_session, "sem-acesso@example.com")
    revoked = _user(db_session, "acesso-revogado@example.com")
    actor_id = _actor(api, owner)
    created = _add(api, owner, actor_id, name="MelSecreto")
    product_id = created.json()["id"]
    _grant(db_session, revoked, actor_id, AccessLevel.MANAGE, AccessStatus.REVOKED)

    for user in (stranger, revoked):
        for response in _calls(api, user, actor_id, product_id):
            assert response.status_code == 404
            assert response.json() == NOT_FOUND
            assert "MelSecreto" not in response.text

    stored = db_session.get(Product, uuid.UUID(product_id))
    assert stored is not None
    assert stored.name == "MelSecreto"
    assert stored.status is ProductStatus.ACTIVE


def test_product_routes_require_a_token(api, db_session):
    owner = _user(db_session, "dono-token@example.com")
    actor_id = _actor(api, owner)
    created = _add(api, owner, actor_id)
    product_id = created.json()["id"]
    calls = [
        api.post(f"/actors/{actor_id}/products", json=_body()),
        api.get(f"/actors/{actor_id}/products"),
        api.get(f"/actors/{actor_id}/products/{product_id}"),
        api.patch(
            f"/actors/{actor_id}/products/{product_id}",
            json={"name": "Não entra"},
        ),
        api.post(f"/actors/{actor_id}/products/{product_id}/archive"),
    ]

    for response in calls:
        assert response.status_code == 401
        assert response.json()["detail"] == "Token inválido."
    assert len(_rows(db_session, actor_id)) == 1


def test_listing_returns_only_the_authorized_actors_products(api, db_session):
    user = _user(db_session, "lista-produtos@example.com")
    reader = _user(db_session, "lista-leitor@example.com")
    outsider = _user(db_session, "lista-fora@example.com")
    first = _actor(api, user, name="Casa A")
    second = _actor(api, user, name="Casa B")
    _grant(db_session, reader, first, AccessLevel.READ)
    milho = _add(api, user, first, name="Milho", category="cereal")
    arroz = _add(api, user, first, name="Arroz", category="cereal")
    caju = _add(api, user, second, name="Caju", category="fruto")

    own = api.get(f"/actors/{first}/products", headers=_bearer(user))
    shared = api.get(f"/actors/{first}/products", headers=_bearer(reader))
    other = api.get(f"/actors/{second}/products", headers=_bearer(user))
    hidden = api.get(f"/actors/{first}/products", headers=_bearer(outsider))

    expected = [arroz.json()["id"], milho.json()["id"]]
    assert own.status_code == 200
    assert [item["id"] for item in own.json()] == expected
    assert [item["name"] for item in own.json()] == ["Arroz", "Milho"]
    assert all(item["owner_actor_id"] == str(first) for item in own.json())
    assert shared.status_code == 200
    assert [item["id"] for item in shared.json()] == expected
    assert [item["id"] for item in other.json()] == [caju.json()["id"]]
    assert "Caju" not in own.text
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND
    assert "Arroz" not in hidden.text


def test_authorized_user_can_read_one_product(api, db_session):
    owner = _user(db_session, "consulta-dono@example.com")
    reader = _user(db_session, "consulta-leitor@example.com")
    actor_id = _actor(api, owner)
    _grant(db_session, reader, actor_id, AccessLevel.READ)
    created = _add(api, owner, actor_id, image_ref="foto-mel")
    product_id = created.json()["id"]

    as_owner = api.get(
        f"/actors/{actor_id}/products/{product_id}",
        headers=_bearer(owner),
    )
    as_reader = api.get(
        f"/actors/{actor_id}/products/{product_id}",
        headers=_bearer(reader),
    )

    for response in (as_owner, as_reader):
        assert response.status_code == 200
        assert set(response.json()) == PRODUCT_KEYS
        assert response.json()["id"] == product_id
        assert response.json()["image_ref"] == "foto-mel"
        assert response.json()["status"] == "active"


def test_product_of_another_actor_is_not_disclosed(api, db_session):
    owner = _user(db_session, "dono-a@example.com")
    other = _user(db_session, "dono-b@example.com")
    actor_a = _actor(api, owner, name="Actor A")
    actor_b = _actor(api, other, name="Actor B")
    secret = _add(api, owner, actor_a, name="MelSecreto")
    foreign = _add(api, other, actor_b, name="CajuAlheio")
    secret_id = secret.json()["id"]
    foreign_id = foreign.json()["id"]

    on_own_path = api.get(
        f"/actors/{actor_b}/products/{secret_id}",
        headers=_bearer(other),
    )
    on_foreign_actor = api.get(
        f"/actors/{actor_a}/products/{secret_id}",
        headers=_bearer(other),
    )
    missing = api.get(
        f"/actors/{actor_a}/products/{uuid.uuid4()}",
        headers=_bearer(owner),
    )
    swapped = api.get(
        f"/actors/{actor_a}/products/{foreign_id}",
        headers=_bearer(owner),
    )

    assert on_own_path.status_code == 404
    assert on_own_path.json() == PRODUCT_MISSING
    assert on_foreign_actor.status_code == 404
    assert on_foreign_actor.json() == NOT_FOUND
    assert missing.status_code == 404
    assert missing.json() == PRODUCT_MISSING
    assert swapped.status_code == 404
    assert swapped.json() == PRODUCT_MISSING
    for response in (on_own_path, on_foreign_actor, missing, swapped):
        assert "MelSecreto" not in response.text
        assert "CajuAlheio" not in response.text
    assert db_session.get(Product, uuid.UUID(secret_id)).name == "MelSecreto"


def test_managers_are_isolated_between_actors(api, db_session):
    """U1 gere só A e U2 gere só B. O produto de um não se alcança pelo outro."""

    user_a = _user(db_session, "u1-actor-a@example.com")
    user_b = _user(db_session, "u2-actor-b@example.com")
    actor_a = _actor(api, user_a, name="Actor A", roles=["producer"])
    actor_b = _actor(api, user_b, name="Actor B", roles=["producer"])
    _assert_exclusive_manage(db_session, user_a, actor_a, actor_b)
    _assert_exclusive_manage(db_session, user_b, actor_b, actor_a)

    created = _add(
        api,
        user_a,
        actor_a,
        name="MelDeA",
        description="Ficha A",
        category="mel",
    )
    assert created.status_code == 201
    product_a = created.json()["id"]
    headers_a = _bearer(user_a)
    path_a = f"/actors/{actor_a}/products/{product_a}"

    listing = api.get(f"/actors/{actor_a}/products", headers=headers_a)
    single = api.get(path_a, headers=headers_a)
    updated = api.patch(path_a, headers=headers_a, json={"name": "MelDeA revisto"})
    archived = api.post(f"{path_a}/archive", headers=headers_a)

    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [product_a]
    assert single.status_code == 200
    assert single.json()["owner_actor_id"] == str(actor_a)
    assert updated.status_code == 200
    assert updated.json()["name"] == "MelDeA revisto"
    assert updated.json()["status"] == "active"
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["description"] == "Ficha A"

    foreign = _add(
        api,
        user_b,
        actor_b,
        name="CajuDeB",
        description="Ficha B",
        category="fruto",
    )
    assert foreign.status_code == 201
    product_b = foreign.json()["id"]
    headers_b = _bearer(user_b)
    path_b = f"/actors/{actor_b}/products/{product_b}"

    seen = api.get(path_b, headers=headers_b)
    listed_b = api.get(f"/actors/{actor_b}/products", headers=headers_b)
    renamed = api.patch(path_b, headers=headers_b, json={"description": "Ficha B revista"})
    archived_b = api.post(f"{path_b}/archive", headers=headers_b)

    assert seen.status_code == 200
    assert seen.json()["owner_actor_id"] == str(actor_b)
    assert [item["id"] for item in listed_b.json()] == [product_b]
    assert renamed.status_code == 200
    assert renamed.json()["description"] == "Ficha B revista"
    assert renamed.json()["name"] == "CajuDeB"
    assert archived_b.status_code == 200
    assert archived_b.json()["status"] == "archived"

    for response in (
        _add(api, user_a, actor_b, name="IntrusoDeU1"),
        api.get(f"/actors/{actor_b}/products", headers=headers_a),
        api.get(path_b, headers=headers_a),
        api.patch(path_b, headers=headers_a, json={"name": "Não entra"}),
        api.post(f"{path_b}/archive", headers=headers_a),
    ):
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
        assert "CajuDeB" not in response.text
        assert "Ficha B" not in response.text

    own_after = api.get(f"/actors/{actor_a}/products", headers=headers_a)
    assert [item["id"] for item in own_after.json()] == [product_a]
    assert "CajuDeB" not in own_after.text
    for response in (
        api.get(f"/actors/{actor_a}/products/{product_b}", headers=headers_a),
        api.patch(
            f"/actors/{actor_a}/products/{product_b}",
            headers=headers_a,
            json={"name": "Não entra"},
        ),
        api.post(
            f"/actors/{actor_a}/products/{product_b}/archive",
            headers=headers_a,
        ),
    ):
        assert response.status_code == 404
        assert response.json() == PRODUCT_MISSING
        assert "CajuDeB" not in response.text

    for response in (
        _add(api, user_b, actor_a, name="IntrusoDeU2"),
        api.get(f"/actors/{actor_a}/products", headers=headers_b),
        api.get(path_a, headers=headers_b),
        api.patch(path_a, headers=headers_b, json={"name": "Não entra"}),
        api.post(f"{path_a}/archive", headers=headers_b),
    ):
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
        assert "MelDeA" not in response.text

    stored_a = db_session.get(Product, uuid.UUID(product_a))
    stored_b = db_session.get(Product, uuid.UUID(product_b))
    assert stored_a.owner_actor_id == actor_a
    assert stored_a.name == "MelDeA revisto"
    assert stored_a.status is ProductStatus.ARCHIVED
    assert stored_b.owner_actor_id == actor_b
    assert stored_b.name == "CajuDeB"
    assert stored_b.description == "Ficha B revista"
    assert stored_b.status is ProductStatus.ARCHIVED
    assert [item.name for item in _rows(db_session, actor_a)] == ["MelDeA revisto"]
    assert [item.name for item in _rows(db_session, actor_b)] == ["CajuDeB"]


def test_manager_updates_a_product(api, db_session):
    user = _user(db_session, "edita-produto@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id)
    product_id = uuid.UUID(created.json()["id"])
    headers = _bearer(user)
    path = f"/actors/{actor_id}/products/{product_id}"

    updated = api.patch(
        path,
        headers=headers,
        json={
            "name": "Mel claro",
            "description": "Mel centrifugado",
            "category": "apicultura",
            "image_ref": "foto-1",
        },
    )
    renamed = api.patch(path, headers=headers, json={"name": "Mel escuro"})
    untouched = api.patch(path, headers=headers, json={})
    cleared = api.patch(path, headers=headers, json={"image_ref": None})

    assert updated.status_code == 200
    assert updated.json()["name"] == "Mel claro"
    assert updated.json()["description"] == "Mel centrifugado"
    assert updated.json()["category"] == "apicultura"
    assert updated.json()["image_ref"] == "foto-1"
    assert updated.json()["status"] == "active"
    assert updated.json()["owner_actor_id"] == str(actor_id)
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Mel escuro"
    assert renamed.json()["description"] == "Mel centrifugado"
    assert untouched.status_code == 200
    assert untouched.json()["name"] == "Mel escuro"
    assert cleared.status_code == 200
    assert cleared.json()["image_ref"] is None
    assert cleared.json()["status"] == "active"
    stored = db_session.get(Product, product_id)
    assert stored.name == "Mel escuro"
    assert stored.owner_actor_id == actor_id
    assert stored.status is ProductStatus.ACTIVE


def test_reader_cannot_change_a_product(api, db_session):
    owner = _user(db_session, "edita-dono@example.com")
    reader = _user(db_session, "edita-leitor@example.com")
    actor_id = _actor(api, owner)
    _grant(db_session, reader, actor_id, AccessLevel.READ)
    created = _add(api, owner, actor_id, name="Mel estável", image_ref="foto-estavel")
    product_id = created.json()["id"]
    headers = _bearer(reader)
    path = f"/actors/{actor_id}/products/{product_id}"

    updated = api.patch(path, headers=headers, json={"name": "Não entra"})
    archived = api.post(f"{path}/archive", headers=headers)

    assert updated.status_code == 404
    assert updated.json() == NOT_FOUND
    assert archived.status_code == 404
    assert archived.json() == NOT_FOUND
    stored = db_session.get(Product, uuid.UUID(product_id))
    assert stored.name == "Mel estável"
    assert stored.image_ref == "foto-estavel"
    assert stored.status is ProductStatus.ACTIVE


def test_invalid_product_input_is_rejected(api, db_session):
    user = _user(db_session, "invalido-produto@example.com")
    actor_id = _actor(api, user)
    headers = _bearer(user)
    rejected = [
        _add(api, user, actor_id, name="   "),
        _add(api, user, actor_id, description=" "),
        _add(api, user, actor_id, category=""),
        _add(api, user, actor_id, image_ref="   "),
        _add(api, user, actor_id, price="19.99"),
        _add(api, user, actor_id, status="archived"),
        _add(api, user, actor_id, quantity=4, delivery_terms="recolha no bairro"),
        api.post(
            f"/actors/{actor_id}/products",
            headers=headers,
            json={"name": "Mel", "category": "mel"},
        ),
        api.post("/actors/nao-e-uuid/products", headers=headers, json=_body()),
    ]

    for response in rejected:
        assert response.status_code == 422
        assert "Traceback" not in response.text
        assert "19.99" not in response.text
        assert "recolha no bairro" not in response.text
        assert all("input" not in error for error in response.json()["detail"])
    assert _rows(db_session, actor_id) == []

    created = _add(api, user, actor_id, name="Mel válido")
    product_id = created.json()["id"]
    path = f"/actors/{actor_id}/products/{product_id}"
    kept = [
        api.patch(path, headers=headers, json={"name": "  "}),
        api.patch(path, headers=headers, json={"status": "archived", "name": "Outro"}),
        api.patch(path, headers=headers, json={"price": "19.99"}),
        api.patch(f"/actors/{actor_id}/products/nao-e-uuid", headers=headers, json=_body()),
    ]
    for response in kept:
        assert response.status_code == 422
        assert "19.99" not in response.text
        assert all("input" not in error for error in response.json()["detail"])
    stored = db_session.get(Product, uuid.UUID(product_id))
    assert stored.name == "Mel válido"
    assert stored.status is ProductStatus.ACTIVE


def test_owner_actor_id_in_the_body_is_rejected(api, db_session):
    user = _user(db_session, "dono-corpo@example.com")
    actor_id = _actor(api, user)
    other_actor = _actor(api, user, name="Outra casa")
    planted = uuid.uuid4()
    headers = _bearer(user)

    created = _add(api, user, actor_id, owner_actor_id=str(planted))
    existing = _add(api, user, actor_id, name="Mel fixo")
    product_id = existing.json()["id"]
    updated = api.patch(
        f"/actors/{actor_id}/products/{product_id}",
        headers=headers,
        json={"name": "Mel mudado", "owner_actor_id": str(other_actor)},
    )

    assert created.status_code == 422
    assert str(planted) not in created.text
    assert all("input" not in error for error in created.json()["detail"])
    assert updated.status_code == 422
    assert str(other_actor) not in updated.text
    stored = _rows(db_session, actor_id)
    assert len(stored) == 1
    assert stored[0].name == "Mel fixo"
    assert stored[0].owner_actor_id == actor_id
    assert _rows(db_session, other_actor) == []
    assert db_session.get(Product, planted) is None


def test_manager_archives_a_product(api, db_session):
    user = _user(db_session, "arquivo-produto@example.com")
    actor_id = _actor(api, user)
    created = _add(
        api,
        user,
        actor_id,
        name="Mel arquivado",
        description="Lote da época",
        category="mel",
        image_ref="foto-arquivo",
    )
    product_id = uuid.UUID(created.json()["id"])
    headers = _bearer(user)

    archived = api.post(
        f"/actors/{actor_id}/products/{product_id}/archive",
        headers=headers,
    )
    listed = api.get(f"/actors/{actor_id}/products", headers=headers)
    fetched = api.get(
        f"/actors/{actor_id}/products/{product_id}",
        headers=headers,
    )
    removed = api.delete(
        f"/actors/{actor_id}/products/{product_id}",
        headers=headers,
    )

    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["name"] == "Mel arquivado"
    assert archived.json()["image_ref"] == "foto-arquivo"
    assert [item["status"] for item in listed.json()] == ["archived"]
    assert fetched.json()["status"] == "archived"
    assert removed.status_code == 405
    db_session.expire_all()
    stored = db_session.get(Product, product_id)
    assert stored is not None
    assert stored.status is ProductStatus.ARCHIVED
    assert len(_rows(db_session, actor_id)) == 1


def test_archive_is_idempotent(api, db_session, monkeypatch):
    user = _user(db_session, "arquivo-idempotente@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id, name="Mel estável", image_ref="foto-idem")
    product_id = created.json()["id"]
    headers = _bearer(user)
    path = f"/actors/{actor_id}/products/{product_id}/archive"

    first = api.post(path, headers=headers)

    def fail(session, product):
        raise AssertionError("arquivo repetido não deve escrever")

    monkeypatch.setattr("app.products.mark_archived", fail)
    second = api.post(path, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert second.json()["status"] == "archived"
    assert second.json()["name"] == "Mel estável"
    assert second.json()["image_ref"] == "foto-idem"
    assert len(_rows(db_session, actor_id)) == 1


def test_archive_preserves_the_persisted_fields(api, db_session):
    user = _user(db_session, "arquivo-preserva@example.com")
    actor_id = _actor(api, user)
    created = _add(
        api,
        user,
        actor_id,
        name="Mel completo",
        description="Descrição original",
        category="mel",
        image_ref="foto-original",
    )
    product_id = uuid.UUID(created.json()["id"])
    before = _snapshot(db_session.get(Product, product_id))

    response = api.post(
        f"/actors/{actor_id}/products/{product_id}/archive",
        headers=_bearer(user),
    )
    db_session.expire_all()
    stored = db_session.get(Product, product_id)

    assert response.status_code == 200
    assert _snapshot(stored) == before
    assert stored.status is ProductStatus.ARCHIVED
    assert response.json()["description"] == "Descrição original"
    assert response.json()["category"] == "mel"


def test_archived_product_can_be_corrected_and_stays_archived(api, db_session):
    user = _user(db_session, "arquivo-correcao@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id, name="Mel antigo", description="Texto antigo")
    product_id = created.json()["id"]
    headers = _bearer(user)
    path = f"/actors/{actor_id}/products/{product_id}"
    api.post(f"{path}/archive", headers=headers)

    corrected = api.patch(
        path,
        headers=headers,
        json={"name": "Mel corrigido"},
    )

    assert corrected.status_code == 200
    assert corrected.json()["name"] == "Mel corrigido"
    assert corrected.json()["description"] == "Texto antigo"
    assert corrected.json()["status"] == "archived"
    stored = db_session.get(Product, uuid.UUID(product_id))
    assert stored.status is ProductStatus.ARCHIVED


def test_database_rejects_invalid_product_rows(api, db_session):
    user = _user(db_session, "restricao-produto@example.com")
    actor_id = _actor(api, user)
    valid = _add(api, user, actor_id, name="Mel válido")
    params = {"actor_id": actor_id, "missing_id": uuid.uuid4()}
    statements = [
        """
        INSERT INTO products (owner_actor_id, name, description, category, status)
        VALUES (:missing_id, 'Mel', 'Texto', 'mel', 'active')
        """,
        """
        INSERT INTO products (name, description, category, status)
        VALUES ('Mel', 'Texto', 'mel', 'active')
        """,
        """
        INSERT INTO products (owner_actor_id, name, description, category, status)
        VALUES (:actor_id, '   ', 'Texto', 'mel', 'active')
        """,
        """
        INSERT INTO products (owner_actor_id, name, description, category, status)
        VALUES (:actor_id, 'Mel', '   ', 'mel', 'active')
        """,
        """
        INSERT INTO products (owner_actor_id, name, description, category, status)
        VALUES (:actor_id, 'Mel', 'Texto', '   ', 'active')
        """,
        """
        INSERT INTO products (owner_actor_id, name, description, category, image_ref, status)
        VALUES (:actor_id, 'Mel', 'Texto', 'mel', '   ', 'active')
        """,
        """
        INSERT INTO products (owner_actor_id, name, description, category, status)
        VALUES (:actor_id, 'Mel', 'Texto', 'mel', 'published')
        """,
        """
        INSERT INTO products (owner_actor_id, description, category, status)
        VALUES (:actor_id, 'Texto', 'mel', 'active')
        """,
    ]

    for statement in statements:
        _reject(db_session, statement, params)

    stored = db_session.get(Product, uuid.UUID(valid.json()["id"]))
    assert stored is not None
    assert stored.name == "Mel válido"


def test_database_restricts_actor_delete_while_a_product_exists(api, db_session):
    user = _user(db_session, "restricao-actor@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id)

    _reject(db_session, "DELETE FROM actors WHERE id = :actor_id", {"actor_id": actor_id})

    assert db_session.get(Product, uuid.UUID(created.json()["id"])) is not None
    assert len(_rows(db_session, actor_id)) == 1


def test_failed_creation_rolls_back_the_product(api, db_session, monkeypatch):
    user = _user(db_session, "falha-produto@example.com")
    actor_id = _actor(api, user, roles=["producer", "buyer"])

    def explode(session, product):
        session.flush()
        raise RuntimeError("falha no produto")

    monkeypatch.setattr("app.products.remember_new_product", explode)

    with pytest.raises(RuntimeError, match="falha no produto"):
        _add(api, user, actor_id, name="Não pode ficar")

    db_session.expire_all()
    assert _rows(db_session, actor_id) == []
    assert db_session.get(User, user.id) is not None
    assert _links(db_session, actor_id) == {
        COMMERCIAL_ROLE_IDS[RoleCode.PRODUCER],
        COMMERCIAL_ROLE_IDS[RoleCode.BUYER],
    }


def test_failed_update_rolls_back_the_product(api, db_session, monkeypatch):
    user = _user(db_session, "falha-edicao@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id, name="Mel original", description="Texto original")
    product_id = uuid.UUID(created.json()["id"])

    def explode(session, product, fields):
        product.name = "Não fica"
        session.flush()
        raise RuntimeError("falha na actualização")

    monkeypatch.setattr("app.products.apply_product_changes", explode)

    with pytest.raises(RuntimeError, match="falha na actualização"):
        api.patch(
            f"/actors/{actor_id}/products/{product_id}",
            headers=_bearer(user),
            json={"name": "Mel novo", "description": "Texto novo"},
        )

    db_session.expire_all()
    stored = db_session.get(Product, product_id)
    assert stored.name == "Mel original"
    assert stored.description == "Texto original"
    assert stored.status is ProductStatus.ACTIVE


def test_failed_archive_rolls_back_the_status(api, db_session, monkeypatch):
    user = _user(db_session, "falha-arquivo@example.com")
    actor_id = _actor(api, user)
    created = _add(api, user, actor_id, name="Mel vivo", image_ref="foto-viva")
    product_id = uuid.UUID(created.json()["id"])

    def explode(session, product):
        product.status = ProductStatus.ARCHIVED
        session.flush()
        raise RuntimeError("falha no arquivo")

    monkeypatch.setattr("app.products.mark_archived", explode)

    with pytest.raises(RuntimeError, match="falha no arquivo"):
        api.post(
            f"/actors/{actor_id}/products/{product_id}/archive",
            headers=_bearer(user),
        )

    db_session.expire_all()
    stored = db_session.get(Product, product_id)
    assert stored.status is ProductStatus.ACTIVE
    assert stored.name == "Mel vivo"
    assert stored.image_ref == "foto-viva"


def test_actor_without_producer_role_cannot_create_or_change_products(api, db_session):
    user = _user(db_session, "sem-producer@example.com")
    buyer_only = _actor(api, user, name="Só comprador", roles=["buyer"])
    producer = _actor(api, user, name="Era produtor", roles=["producer", "buyer"])
    created = _add(api, user, producer, name="Mel existente", description="Fica")
    product_id = created.json()["id"]

    rejected = _add(api, user, buyer_only, name="Não entra")
    visible = api.get(f"/actors/{buyer_only}/products", headers=_bearer(user))
    removed = api.put(
        f"/actors/{producer}/roles",
        headers=_bearer(user),
        json={"roles": ["buyer"]},
    )
    another = _add(api, user, producer, name="Segundo")
    renamed = api.patch(
        f"/actors/{producer}/products/{product_id}",
        headers=_bearer(user),
        json={"name": "Não muda"},
    )
    archived = api.post(
        f"/actors/{producer}/products/{product_id}/archive",
        headers=_bearer(user),
    )
    kept = api.get(
        f"/actors/{producer}/products/{product_id}",
        headers=_bearer(user),
    )

    assert rejected.status_code == 422
    assert rejected.json() == NO_PRODUCER
    assert visible.status_code == 200
    assert visible.json() == []
    assert _rows(db_session, buyer_only) == []
    assert removed.status_code == 200
    assert another.status_code == 422
    assert another.json() == NO_PRODUCER
    assert renamed.status_code == 422
    assert archived.status_code == 422
    assert kept.status_code == 200
    assert kept.json()["name"] == "Mel existente"
    assert kept.json()["description"] == "Fica"
    assert kept.json()["status"] == "active"
    assert len(_rows(db_session, producer)) == 1


def test_producer_role_does_not_grant_access_to_another_actor(api, db_session):
    owner = _user(db_session, "produtor-dono-produto@example.com")
    outsider = _user(db_session, "produtor-alheio-produto@example.com")
    owned = _actor(api, owner, name="Casa do dono")
    _actor(api, outsider, name="Casa alheia", roles=["producer"])
    created = _add(api, owner, owned, name="Mel privado")
    product_id = created.json()["id"]
    headers = _bearer(outsider)

    listing = api.get(f"/actors/{owned}/products", headers=headers)
    single = api.get(f"/actors/{owned}/products/{product_id}", headers=headers)
    updated = api.patch(
        f"/actors/{owned}/products/{product_id}",
        headers=headers,
        json={"name": "Não entra"},
    )

    assert listing.status_code == 404
    assert single.status_code == 404
    assert updated.status_code == 404
    assert listing.json() == NOT_FOUND
    assert "Mel privado" not in listing.text
    stored = db_session.get(Product, uuid.UUID(product_id))
    assert stored.name == "Mel privado"
    accesses = db_session.scalars(
        select(UserActorAccess).where(UserActorAccess.user_id == outsider.id)
    ).all()
    assert accesses
    assert all(access.actor_id != owned for access in accesses)


def test_database_accepts_a_direct_row_without_the_producer_role(api, db_session):
    user = _user(db_session, "regra-api@example.com")
    actor_id = _actor(api, user, name="Comprador", roles=["buyer"])
    rejected = _add(api, user, actor_id, name="Via API")

    direct = Product(
        owner_actor_id=actor_id,
        name="Via SQL",
        description="A base não consulta actor_roles.",
        category="mel",
        image_ref=None,
        status=ProductStatus.ACTIVE,
    )
    db_session.add(direct)
    db_session.flush()

    assert rejected.status_code == 422
    assert rejected.json() == NO_PRODUCER
    assert [item.name for item in _rows(db_session, actor_id)] == ["Via SQL"]


def test_migrated_product_schema_matches_the_model(db_session):
    inspector = inspect(db_session.get_bind())
    table = Product.__table__
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
    assert inspector.get_pk_constraint(table.name)["name"] == "pk_products"
    assert inspector.get_table_comment(table.name)["text"] == table.comment
    assert sorted(
        constraint["name"] for constraint in inspector.get_check_constraints(table.name)
    ) == sorted(
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert sorted(
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table.name)
    ) == ["fk_products_owner_actor_id"]
    assert sorted(
        index["name"]
        for index in inspector.get_indexes(table.name)
        if not index["unique"]
    ) == ["ix_products_owner_actor_id"]

    definitions = db_session.execute(
        text(
            """
            SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE contype IN ('c', 'f') AND conrelid = 'products'::regclass
            """
        )
    ).all()
    by_name = {row.conname: row.definition for row in definitions}
    assert set(QUOTED_LITERAL.findall(by_name["ck_products_status"])) == {
        "active",
        "archived",
    }
    assert "ON DELETE RESTRICT" in by_name["fk_products_owner_actor_id"]


def _calls(api, user: User, actor_id: uuid.UUID, product_id: str):
    headers = _bearer(user)
    return [
        api.post(
            f"/actors/{actor_id}/products",
            headers=headers,
            json=_body(name="Intruso"),
        ),
        api.get(f"/actors/{actor_id}/products", headers=headers),
        api.get(f"/actors/{actor_id}/products/{product_id}", headers=headers),
        api.patch(
            f"/actors/{actor_id}/products/{product_id}",
            headers=headers,
            json={"name": "Não entra"},
        ),
        api.post(f"/actors/{actor_id}/products/{product_id}/archive", headers=headers),
    ]
