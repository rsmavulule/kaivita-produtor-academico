"""Ofertas comerciais, com PostgreSQL real.

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
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import CheckConstraint, UniqueConstraint

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
from app.offers import AvailabilityStatus, Offer, OfferStatus
from app.products import Product, ProductStatus
from app.tokens import issue_access_token

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "palavra-de-teste"
NOT_FOUND = {"detail": "Actor não encontrado."}
OFFER_MISSING = {"detail": "Oferta não encontrada."}
PRODUCT_MISSING = {"detail": "Produto não encontrado."}
NO_PRODUCER = {"detail": "O actor não tem o papel producer."}
ARCHIVED = {"detail": "O produto está arquivado."}
WITHDRAWN = {"detail": "A oferta retirada não pode ser alterada."}
TRANSITION = {"detail": "Transição de estado não permitida."}
NOT_PUBLISHABLE = {
    "detail": (
        "A publicação exige preço, moeda, quantidade, unidade e "
        "disponibilidade válidos."
    )
}
ZERO_AVAILABLE = {"detail": "Quantidade zero não pode estar disponível."}
PUBLISHED_INVALID = {"detail": "A oferta publicada tem de permanecer válida."}
OFFER_KEYS = {
    "id",
    "product_id",
    "owner_actor_id",
    "price",
    "currency",
    "quantity",
    "unit",
    "availability",
    "delivery_terms",
    "status",
}
THROWAWAY_NAME = re.compile(r"kaivita_i4_[0-9a-f]{12}")
QUOTED_LITERAL = re.compile(r"'([a-z_]+)'")


@pytest.fixture(scope="session")
def migrated_database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    from alembic import command
    from alembic.config import Config

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


def _actor(api, user: User, *, name: str = "Marta", roles: list[str] | None = None) -> uuid.UUID:
    created = api.post(
        "/actors",
        headers=_bearer(user),
        json={
            "kind": "person",
            "display_name": name,
            "general_location": "Inhambane",
            "roles": ["producer"] if roles is None else roles,
        },
    )
    assert created.status_code == 201, created.text
    return uuid.UUID(created.json()["id"])


def _product(api, user: User, actor_id: uuid.UUID, **overrides) -> uuid.UUID:
    body = {
        "name": "Mel",
        "description": "Mel de miombo",
        "category": "mel",
    }
    body.update(overrides)
    created = api.post(
        f"/actors/{actor_id}/products",
        headers=_bearer(user),
        json=body,
    )
    assert created.status_code == 201, created.text
    return uuid.UUID(created.json()["id"])


def _offer_body(product_id: uuid.UUID, **overrides) -> dict:
    body = {
        "product_id": str(product_id),
        "price": "150.00",
        "currency": "MZN",
        "quantity": "2.50",
        "unit": "kg",
        "availability": "available",
        "delivery_terms": "Recolha no mercado",
    }
    body.update(overrides)
    return body


def _add(api, user: User, actor_id: uuid.UUID, product_id: uuid.UUID, **overrides):
    return api.post(
        f"/actors/{actor_id}/offers",
        headers=_bearer(user),
        json=_offer_body(product_id, **overrides),
    )


def _rows(session: Session, actor_id: uuid.UUID) -> list[Offer]:
    return list(
        session.scalars(
            select(Offer)
            .where(Offer.owner_actor_id == actor_id)
            .order_by(Offer.id)
        )
    )


def _links(session: Session, actor_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        session.scalars(
            select(ActorRole.role_id).where(ActorRole.actor_id == actor_id)
        ).all()
    )


def _commercial(offer: Offer) -> tuple:
    return (
        offer.product_id,
        offer.owner_actor_id,
        offer.price,
        offer.currency,
        offer.quantity,
        offer.unit,
        offer.availability,
        offer.delivery_terms,
    )


def _reject(session: Session, statement: str, params: dict, constraint: str | None = None) -> None:
    with pytest.raises(IntegrityError) as caught:
        with session.begin_nested():
            session.execute(text(statement), params)
    if constraint is not None:
        assert caught.value.orig.diag.constraint_name == constraint


def test_mapped_offer_declares_the_contract():
    table = Offer.__table__

    assert [column.name for column in table.columns] == [
        "id",
        "product_id",
        "owner_actor_id",
        "price",
        "currency",
        "quantity",
        "unit",
        "availability",
        "delivery_terms",
        "status",
    ]
    assert table.primary_key.name == "pk_offers"
    for name in ("price", "currency", "quantity", "unit", "availability", "delivery_terms"):
        assert table.columns[name].nullable is True
    for name in ("id", "product_id", "owner_actor_id", "status"):
        assert table.columns[name].nullable is False
    assert {member.value for member in OfferStatus} == {
        "draft",
        "published",
        "suspended",
        "withdrawn",
    }
    assert {member.value for member in AvailabilityStatus} == {
        "available",
        "unavailable",
    }
    assert {index.name for index in table.indexes} == {
        "ix_offers_owner_actor_id",
        "ix_offers_product_id",
    }
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_offers_price",
        "ck_offers_quantity",
        "ck_offers_currency",
        "ck_offers_unit",
        "ck_offers_delivery_terms",
        "ck_offers_availability",
        "ck_offers_status",
        "ck_offers_quantity_availability",
        "ck_offers_published",
    }
    foreign_keys = {key.constraint.name: key.constraint.ondelete for key in table.foreign_keys}
    assert foreign_keys["fk_offers_owner_actor_id"] == "RESTRICT"
    assert foreign_keys["fk_offers_product_owner"] == "RESTRICT"
    composite = next(
        constraint
        for constraint in table.foreign_key_constraints
        if constraint.name == "fk_offers_product_owner"
    )
    assert composite.onupdate == "RESTRICT"
    assert any(
        isinstance(constraint, UniqueConstraint) and constraint.name == "uq_products_id_owner"
        for constraint in Product.__table__.constraints
    )


def test_openapi_exposes_private_offer_routes_without_delete(client):
    document = client.get("/openapi.json").json()
    collection = "/actors/{actor_id}/offers"
    single = "/actors/{actor_id}/offers/{offer_id}"
    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}

    assert set(document["paths"][collection]) & methods == {"get", "post"}
    assert set(document["paths"][single]) & methods == {"get", "patch"}
    for action in ("publish", "suspend", "withdraw"):
        path = f"{single}/{action}"
        assert set(document["paths"][path]) & methods == {"post"}
        assert document["paths"][path]["post"]["security"] == [{"HTTPBearer": []}]
    assert document["paths"][collection]["post"]["security"] == [{"HTTPBearer": []}]
    assert "/offers" not in document["paths"]
    assert not any("/offers" in path and path.endswith("/archive") for path in document["paths"])
    for model, price_example, quantity_example in (
        ("OfferCreate", "150.00", "2.50"),
        ("OfferUpdate", "150.00", "2.50"),
        ("OfferResponse", "150.00", "2.50"),
    ):
        properties = document["components"]["schemas"][model]["properties"]
        _assert_decimal_string(properties["price"], price_example)
        _assert_decimal_string(properties["quantity"], quantity_example)


def _assert_decimal_string(schema: dict, example: str) -> None:
    variants = schema.get("anyOf", [schema])
    types = {item.get("type") for item in variants}
    assert "number" not in types
    assert schema.get("type") != "number"
    assert "string" in types
    assert schema["examples"] == [example]
    assert all(isinstance(item, str) for item in schema["examples"])


def test_offers_migration_preserves_existing_rows_on_a_throwaway_database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    name = f"kaivita_i4_{uuid.uuid4().hex[:12]}"
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
        planted = _plant_product(target)
        # 0004_offers, e não head: a cabeça passou a 0006_publication_authorizations.
        _alembic(environment, "upgrade", "0004_offers")
        upgraded = _offer_state(target)
        assert upgraded["version"] == "0004_offers"
        assert upgraded["offers"] is not None
        assert upgraded["offer_count"] == 0
        assert upgraded["unique"] == "uq_products_id_owner"
        assert upgraded["product"]["product_id"] == planted["product_id"]
        assert upgraded["product"]["name"] == planted["name"]
        assert upgraded["roles"] == 3

        _alembic(environment, "downgrade", "0003_products")
        restored = _offer_state(target)
        assert restored["version"] == "0003_products"
        assert restored["offers"] is None
        assert restored["unique"] is None
        assert restored["product"]["product_id"] == planted["product_id"]
        assert restored["product"]["name"] == planted["name"]

        _alembic(environment, "downgrade", "0002_identity_access")
        identity = _offer_state(target)
        assert identity["version"] == "0002_identity_access"
        assert identity["products"] is None
        assert identity["offers"] is None
        assert identity["roles"] == 3

        _alembic(environment, "upgrade", "0004_offers")
        again = _offer_state(target)
        assert again["version"] == "0004_offers"
        assert again["offers"] is not None
        assert again["products"] is not None
        assert again["roles"] == 3
        assert again["product"] is None
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
        detail = re.sub(r"://[^:\s]+:[^@\s]+@", "://", completed.stderr or completed.stdout)
        raise AssertionError(f"alembic {' '.join(args)} falhou\n{detail}")


def _plant_product(database_url: str) -> dict[str, str]:
    checked = create_engine(database_url)
    try:
        with checked.begin() as connection:
            user_id = connection.execute(
                text(
                    """
                    INSERT INTO users (email, password_hash, status)
                    VALUES ('preservar-i4@example.com', 'hash-de-teste', 'active')
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
                        :actor_id, 'Mel antigo', 'Antes das ofertas', 'mel', 'active'
                    )
                    RETURNING id
                    """
                ),
                {"actor_id": actor_id},
            ).scalar_one()
        return {
            "user_id": str(user_id),
            "actor_id": str(actor_id),
            "product_id": str(product_id),
            "name": "Mel antigo",
        }
    finally:
        checked.dispose()


def _offer_state(database_url: str) -> dict:
    checked = create_engine(database_url)
    try:
        with checked.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            offers = connection.execute(
                text("SELECT to_regclass('public.offers')")
            ).scalar_one()
            products = connection.execute(
                text("SELECT to_regclass('public.products')")
            ).scalar_one()
            roles = connection.execute(text("SELECT count(*) FROM roles")).scalar_one()
            unique = connection.execute(
                text(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE conname = 'uq_products_id_owner'
                    """
                )
            ).scalar_one_or_none()
            offer_count = 0
            if offers is not None:
                offer_count = connection.execute(
                    text("SELECT count(*) FROM offers")
                ).scalar_one()
            product = None
            if products is not None:
                product_row = connection.execute(
                    text(
                        """
                        SELECT id::text AS id, name
                        FROM products
                        WHERE name = 'Mel antigo'
                        """
                    )
                ).one_or_none()
                if product_row is not None:
                    product = {"product_id": product_row.id, "name": product_row.name}
                    user = connection.execute(
                        text(
                            """
                            SELECT email FROM users
                            WHERE email = 'preservar-i4@example.com'
                            """
                        )
                    ).scalar_one()
                    actor = connection.execute(
                        text(
                            """
                            SELECT display_name FROM actors
                            WHERE display_name = 'Casa antiga'
                            """
                        )
                    ).scalar_one()
                    assert user == "preservar-i4@example.com"
                    assert actor == "Casa antiga"
        return {
            "version": version,
            "offers": offers,
            "products": products,
            "roles": roles,
            "unique": unique,
            "offer_count": offer_count,
            "product": product,
        }
    finally:
        checked.dispose()


def test_manager_creates_a_complete_draft(api, db_session):
    user = _user(db_session, "gestor-oferta@example.com")
    actor_id = _actor(api, user, name="Casa do mel", roles=["partner", "buyer", "producer"])
    product_id = _product(api, user, actor_id)

    created = _add(api, user, actor_id, product_id)
    integer_price = _add(api, user, actor_id, product_id, price=10, quantity=0, availability="unavailable")

    assert created.status_code == 201
    body = created.json()
    assert set(body) == OFFER_KEYS
    assert body["owner_actor_id"] == str(actor_id)
    assert body["product_id"] == str(product_id)
    assert body["price"] == "150.00"
    assert body["currency"] == "MZN"
    assert body["quantity"] == "2.50"
    assert body["unit"] == "kg"
    assert body["availability"] == "available"
    assert body["delivery_terms"] == "Recolha no mercado"
    assert body["status"] == "draft"
    assert integer_price.status_code == 201
    assert integer_price.json()["price"] == "10"
    assert integer_price.json()["quantity"] == "0"
    assert integer_price.json()["id"] != body["id"]
    assert PASSWORD not in created.text
    stored = _rows(db_session, actor_id)
    assert len(stored) == 2
    assert {item.owner_actor_id for item in stored} == {actor_id}
    assert {item.product_id for item in stored} == {product_id}
    assert stored[0].price == Decimal("150.00") or stored[1].price == Decimal("150.00")
    assert _links(db_session, actor_id) == set(COMMERCIAL_ROLE_IDS.values())


def test_manager_creates_an_incomplete_draft(api, db_session):
    user = _user(db_session, "rascunho-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)

    created = api.post(
        f"/actors/{actor_id}/offers",
        headers=_bearer(user),
        json={"product_id": str(product_id)},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["price"] is None
    assert body["currency"] is None
    assert body["quantity"] is None
    assert body["unit"] is None
    assert body["availability"] is None
    assert body["delivery_terms"] is None
    stored = _rows(db_session, actor_id)
    assert len(stored) == 1
    assert stored[0].status is OfferStatus.DRAFT
    assert stored[0].price is None


def test_reader_cannot_create_an_offer(api, db_session):
    owner = _user(db_session, "dono-leitura-oferta@example.com")
    reader = _user(db_session, "leitor-oferta@example.com")
    actor_id = _actor(api, owner)
    product_id = _product(api, owner, actor_id)
    _grant(db_session, reader, actor_id, AccessLevel.READ)

    response = _add(api, reader, actor_id, product_id)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert _rows(db_session, actor_id) == []


def test_user_without_active_representation_cannot_use_offers(api, db_session):
    owner = _user(db_session, "dono-oferta@example.com")
    stranger = _user(db_session, "sem-acesso-oferta@example.com")
    revoked = _user(db_session, "acesso-revogado-oferta@example.com")
    actor_id = _actor(api, owner)
    product_id = _product(api, owner, actor_id, name="Mel secreto")
    created = _add(api, owner, actor_id, product_id, price="88.00")
    offer_id = created.json()["id"]
    _grant(db_session, revoked, actor_id, AccessLevel.MANAGE, AccessStatus.REVOKED)

    for user in (stranger, revoked):
        for response in _calls(api, user, actor_id, product_id, offer_id):
            assert response.status_code == 404
            assert response.json() == NOT_FOUND
            assert "88.00" not in response.text
            assert "Mel secreto" not in response.text

    stored = db_session.get(Offer, uuid.UUID(offer_id))
    assert stored is not None
    assert stored.price == Decimal("88.00")
    assert stored.status is OfferStatus.DRAFT


def test_offer_routes_require_a_token(api, db_session):
    owner = _user(db_session, "dono-token-oferta@example.com")
    actor_id = _actor(api, owner)
    product_id = _product(api, owner, actor_id)
    created = _add(api, owner, actor_id, product_id)
    offer_id = created.json()["id"]
    calls = [
        api.post(
            f"/actors/{actor_id}/offers",
            json=_offer_body(product_id),
        ),
        api.get(f"/actors/{actor_id}/offers"),
        api.get(f"/actors/{actor_id}/offers/{offer_id}"),
        api.patch(
            f"/actors/{actor_id}/offers/{offer_id}",
            json={"unit": "não entra"},
        ),
        api.post(f"/actors/{actor_id}/offers/{offer_id}/publish"),
        api.post(f"/actors/{actor_id}/offers/{offer_id}/suspend"),
        api.post(f"/actors/{actor_id}/offers/{offer_id}/withdraw"),
    ]

    for response in calls:
        assert response.status_code == 401
        assert response.json()["detail"] == "Token inválido."


def test_listing_returns_only_the_authorized_actors_offers(api, db_session):
    user = _user(db_session, "lista-oferta@example.com")
    reader = _user(db_session, "lista-leitor-oferta@example.com")
    outsider = _user(db_session, "lista-fora-oferta@example.com")
    first = _actor(api, user, name="Primeira casa")
    second = _actor(api, user, name="Segunda casa")
    _grant(db_session, reader, first, AccessLevel.READ)
    first_product = _product(api, user, first, name="Mel A")
    second_product = _product(api, user, second, name="Mel B")
    first_offer = _add(api, user, first, first_product, price="1.00")
    second_offer = _add(api, user, second, second_product, price="2.00")
    third_offer = _add(api, user, first, first_product, price="3.00")

    own = api.get(f"/actors/{first}/offers", headers=_bearer(user))
    shared = api.get(f"/actors/{first}/offers", headers=_bearer(reader))
    other = api.get(f"/actors/{second}/offers", headers=_bearer(user))
    hidden = api.get(f"/actors/{first}/offers", headers=_bearer(outsider))

    expected = sorted([first_offer.json()["id"], third_offer.json()["id"]])
    assert own.status_code == 200
    assert [item["id"] for item in own.json()] == expected
    assert shared.json() == own.json()
    assert [item["id"] for item in other.json()] == [second_offer.json()["id"]]
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND
    assert "1.00" not in hidden.text


def test_authorized_user_can_read_one_offer(api, db_session):
    owner = _user(db_session, "leitura-dono-oferta@example.com")
    reader = _user(db_session, "leitura-oferta@example.com")
    actor_id = _actor(api, owner)
    _grant(db_session, reader, actor_id, AccessLevel.READ)
    product_id = _product(api, owner, actor_id)
    created = _add(api, owner, actor_id, product_id)
    offer_id = created.json()["id"]

    by_owner = api.get(
        f"/actors/{actor_id}/offers/{offer_id}",
        headers=_bearer(owner),
    )
    by_reader = api.get(
        f"/actors/{actor_id}/offers/{offer_id}",
        headers=_bearer(reader),
    )

    assert by_owner.status_code == 200
    assert by_reader.status_code == 200
    assert set(by_owner.json()) == OFFER_KEYS
    assert by_reader.json() == by_owner.json()


def test_offer_of_another_actor_is_not_disclosed(api, db_session):
    owner = _user(db_session, "oferta-privada@example.com")
    other = _user(db_session, "oferta-alheia@example.com")
    owned = _actor(api, owner, name="Casa do dono")
    foreign = _actor(api, other, name="Casa alheia")
    product_id = _product(api, owner, owned, name="Mel privado")
    created = _add(api, owner, owned, product_id, price="77.00", unit="frasco")
    offer_id = created.json()["id"]

    on_foreign_actor = api.get(
        f"/actors/{foreign}/offers/{offer_id}",
        headers=_bearer(other),
    )
    on_inaccessible_actor = api.get(
        f"/actors/{owned}/offers/{offer_id}",
        headers=_bearer(other),
    )

    assert on_foreign_actor.status_code == 404
    assert on_foreign_actor.json() == OFFER_MISSING
    assert on_inaccessible_actor.status_code == 404
    assert on_inaccessible_actor.json() == NOT_FOUND
    assert "77.00" not in on_foreign_actor.text
    assert "frasco" not in on_inaccessible_actor.text
    assert "Mel privado" not in on_foreign_actor.text


def test_product_of_another_actor_is_rejected(api, db_session):
    user = _user(db_session, "produto-cruzado@example.com")
    actor_id = _actor(api, user, name="Casa A")
    other_actor = _actor(api, user, name="Casa B")
    foreign_product = _product(api, user, other_actor, name="Mel da outra casa")
    missing = uuid.uuid4()

    crossed = _add(api, user, actor_id, foreign_product)
    absent = _add(api, user, actor_id, missing)

    assert crossed.status_code == 404
    assert crossed.json() == PRODUCT_MISSING
    assert absent.status_code == 404
    assert absent.json() == PRODUCT_MISSING
    assert "Mel da outra casa" not in crossed.text
    assert _rows(db_session, actor_id) == []
    assert len(_rows(db_session, other_actor)) == 0


def test_managers_are_isolated_between_actors(api, db_session):
    user_a = _user(db_session, "isolado-a-oferta@example.com")
    user_b = _user(db_session, "isolado-b-oferta@example.com")
    actor_a = _actor(api, user_a, name="Actor A")
    actor_b = _actor(api, user_b, name="Actor B")
    product_a = _product(api, user_a, actor_a, name="Mel A")
    product_b = _product(api, user_b, actor_b, name="Mel B")
    created_a = _add(api, user_a, actor_a, product_a, price="11.00", unit="kg A")
    offer_a = created_a.json()["id"]
    headers_a = _bearer(user_a)
    path_a = f"/actors/{actor_a}/offers/{offer_a}"

    assert api.get(f"/actors/{actor_a}/offers", headers=headers_a).status_code == 200
    assert api.get(path_a, headers=headers_a).status_code == 200
    revised = api.patch(path_a, headers=headers_a, json={"unit": "kg A revisto"})
    published = api.post(f"{path_a}/publish", headers=headers_a)
    assert revised.status_code == 200
    assert published.status_code == 200

    headers_b = _bearer(user_b)
    created_b = _add(api, user_b, actor_b, product_b, price="22.00", unit="kg B")
    offer_b = created_b.json()["id"]
    path_b = f"/actors/{actor_b}/offers/{offer_b}"
    assert api.get(path_b, headers=headers_b).status_code == 200
    assert api.patch(path_b, headers=headers_b, json={"unit": "kg B revisto"}).status_code == 200

    for response in (
        api.get(f"/actors/{actor_b}/offers", headers=headers_a),
        api.get(path_b, headers=headers_a),
        api.patch(path_b, headers=headers_a, json={"unit": "não entra"}),
        api.post(f"{path_b}/publish", headers=headers_a),
        api.post(f"{path_b}/suspend", headers=headers_a),
        api.post(f"{path_b}/withdraw", headers=headers_a),
        _add(api, user_a, actor_a, product_b, price="99.00"),
        api.get(f"/actors/{actor_a}/offers/{offer_b}", headers=headers_a),
    ):
        assert response.status_code == 404
        assert "kg B" not in response.text
        assert "22.00" not in response.text
        assert "Mel B" not in response.text

    for response in (
        api.get(f"/actors/{actor_a}/offers", headers=headers_b),
        api.get(path_a, headers=headers_b),
        api.patch(path_a, headers=headers_b, json={"unit": "não entra"}),
        api.post(f"{path_a}/suspend", headers=headers_b),
    ):
        assert response.status_code == 404
        assert "kg A" not in response.text

    db_session.expire_all()
    stored_a = db_session.get(Offer, uuid.UUID(offer_a))
    stored_b = db_session.get(Offer, uuid.UUID(offer_b))
    assert stored_a.owner_actor_id == actor_a
    assert stored_a.status is OfferStatus.PUBLISHED
    assert stored_a.unit == "kg A revisto"
    assert stored_b.owner_actor_id == actor_b
    assert stored_b.status is OfferStatus.DRAFT
    assert stored_b.unit == "kg B revisto"


def test_manager_updates_a_draft(api, db_session):
    user = _user(db_session, "edita-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    other_product = _product(api, user, actor_id, name="Outro mel")
    created = api.post(
        f"/actors/{actor_id}/offers",
        headers=_bearer(user),
        json={"product_id": str(product_id)},
    )
    offer_id = uuid.UUID(created.json()["id"])
    headers = _bearer(user)
    path = f"/actors/{actor_id}/offers/{offer_id}"

    untouched = api.patch(path, headers=headers, json={})
    filled = api.patch(
        path,
        headers=headers,
        json={
            "price": "12.00",
            "currency": "MZN",
            "quantity": "1",
            "unit": "lata",
            "availability": "available",
            "delivery_terms": "Entrega na vila",
        },
    )
    cleared = api.patch(path, headers=headers, json={"delivery_terms": None})

    assert untouched.status_code == 200
    assert untouched.json()["price"] is None
    assert untouched.json()["status"] == "draft"
    assert filled.status_code == 200
    assert filled.json()["price"] == "12.00"
    assert filled.json()["unit"] == "lata"
    assert filled.json()["product_id"] == str(product_id)
    assert cleared.status_code == 200
    assert cleared.json()["delivery_terms"] is None
    assert cleared.json()["status"] == "draft"
    db_session.expire_all()
    stored = db_session.get(Offer, offer_id)
    assert stored.product_id == product_id
    assert stored.product_id != other_product
    assert stored.delivery_terms is None
    assert stored.status is OfferStatus.DRAFT


def test_published_offer_must_remain_valid(api, db_session):
    user = _user(db_session, "publicada-valida@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    created = _add(api, user, actor_id, product_id)
    offer_id = uuid.UUID(created.json()["id"])
    headers = _bearer(user)
    path = f"/actors/{actor_id}/offers/{offer_id}"
    assert api.post(f"{path}/publish", headers=headers).status_code == 200
    before = _commercial(db_session.get(Offer, offer_id))

    cleared = api.patch(path, headers=headers, json={"price": None})
    zero_available = api.patch(
        path,
        headers=headers,
        json={"quantity": "0", "availability": "available"},
    )
    corrected = api.patch(
        path,
        headers=headers,
        json={"quantity": "0", "availability": "unavailable", "price": "9.00"},
    )

    assert cleared.status_code == 422
    assert cleared.json() == PUBLISHED_INVALID
    assert zero_available.status_code == 422
    assert zero_available.json() == ZERO_AVAILABLE
    assert corrected.status_code == 200
    assert corrected.json()["status"] == "published"
    assert corrected.json()["quantity"] == "0"
    assert corrected.json()["availability"] == "unavailable"
    assert corrected.json()["price"] == "9.00"
    db_session.expire_all()
    stored = db_session.get(Offer, offer_id)
    assert stored.status is OfferStatus.PUBLISHED
    assert stored.price == Decimal("9.00")
    assert before[0] == stored.product_id
    assert stored.owner_actor_id == actor_id


def test_invalid_update_does_not_persist(api, db_session):
    user = _user(db_session, "edicao-invalida@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    created = _add(api, user, actor_id, product_id, quantity="4", availability="available")
    offer_id = uuid.UUID(created.json()["id"])
    headers = _bearer(user)
    path = f"/actors/{actor_id}/offers/{offer_id}"

    rejected = api.patch(
        path,
        headers=headers,
        json={"quantity": "0", "availability": "available", "price": "1.00"},
    )

    assert rejected.status_code == 422
    assert rejected.json() == ZERO_AVAILABLE
    db_session.expire_all()
    stored = db_session.get(Offer, offer_id)
    assert stored.quantity == Decimal("4")
    assert stored.price == Decimal("150.00")
    assert stored.availability is AvailabilityStatus.AVAILABLE
    assert stored.status is OfferStatus.DRAFT


def test_reader_cannot_change_an_offer(api, db_session):
    owner = _user(db_session, "dono-escrita-oferta@example.com")
    reader = _user(db_session, "leitor-escrita-oferta@example.com")
    actor_id = _actor(api, owner)
    product_id = _product(api, owner, actor_id)
    created = _add(api, owner, actor_id, product_id)
    offer_id = created.json()["id"]
    _grant(db_session, reader, actor_id, AccessLevel.READ)
    headers = _bearer(reader)
    path = f"/actors/{actor_id}/offers/{offer_id}"

    updated = api.patch(path, headers=headers, json={"unit": "não entra"})
    published = api.post(f"{path}/publish", headers=headers)

    assert updated.status_code == 404
    assert published.status_code == 404
    stored = db_session.get(Offer, uuid.UUID(offer_id))
    assert stored.unit == "kg"
    assert stored.status is OfferStatus.DRAFT


def test_invalid_offer_input_is_rejected(api, db_session):
    user = _user(db_session, "invalida-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    headers = _bearer(user)
    rejected = [
        _add(api, user, actor_id, product_id, price="-1"),
        _add(api, user, actor_id, product_id, price=10.5),
        _add(api, user, actor_id, product_id, price="NaN"),
        _add(api, user, actor_id, product_id, price="1e2"),
        _add(api, user, actor_id, product_id, quantity="-0.1"),
        _add(api, user, actor_id, product_id, currency="mzn"),
        _add(api, user, actor_id, product_id, currency="MZ"),
        _add(api, user, actor_id, product_id, currency="MZN1"),
        _add(api, user, actor_id, product_id, unit="   "),
        _add(api, user, actor_id, product_id, delivery_terms=" "),
        _add(api, user, actor_id, product_id, availability="seasonal"),
        _add(api, user, actor_id, product_id, status="published"),
        _add(
            api,
            user,
            actor_id,
            product_id,
            quantity="0",
            availability="available",
        ),
        api.post(
            f"/actors/{actor_id}/offers",
            headers=headers,
            json={"currency": "MZN"},
        ),
        api.post("/actors/nao-e-uuid/offers", headers=headers, json=_offer_body(product_id)),
    ]

    for response in rejected:
        assert response.status_code == 422, response.text
        assert "Traceback" not in response.text
        assert "10.5" not in response.text
        assert "mzn" not in response.text
        assert "seasonal" not in response.text
        assert all("input" not in error for error in response.json()["detail"])
    assert _rows(db_session, actor_id) == []


def test_owner_and_status_in_the_body_are_rejected(api, db_session):
    user = _user(db_session, "dono-corpo-oferta@example.com")
    actor_id = _actor(api, user)
    other_actor = _actor(api, user, name="Outra casa")
    product_id = _product(api, user, actor_id)
    other_product = _product(api, user, other_actor, name="Mel alheio")
    planted = uuid.uuid4()
    headers = _bearer(user)

    created = _add(api, user, actor_id, product_id, owner_actor_id=str(planted))
    existing = _add(api, user, actor_id, product_id, unit="lata")
    offer_id = existing.json()["id"]
    updated = api.patch(
        f"/actors/{actor_id}/offers/{offer_id}",
        headers=headers,
        json={
            "unit": "não muda",
            "owner_actor_id": str(other_actor),
            "status": "published",
            "product_id": str(other_product),
        },
    )

    assert created.status_code == 422
    assert str(planted) not in created.text
    assert updated.status_code == 422
    assert str(other_actor) not in updated.text
    assert str(other_product) not in updated.text
    stored = _rows(db_session, actor_id)
    assert len(stored) == 1
    assert stored[0].unit == "lata"
    assert stored[0].owner_actor_id == actor_id
    assert stored[0].product_id == product_id
    assert stored[0].status is OfferStatus.DRAFT
    assert _rows(db_session, other_actor) == []


def test_lifecycle_follows_the_approved_state_diagram(api, db_session):
    user = _user(db_session, "ciclo-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    headers = _bearer(user)
    created = api.post(
        f"/actors/{actor_id}/offers",
        headers=headers,
        json={"product_id": str(product_id), "price": "5.00"},
    )
    offer_id = uuid.UUID(created.json()["id"])
    path = f"/actors/{actor_id}/offers/{offer_id}"
    before = _commercial(db_session.get(Offer, offer_id))

    refused = api.post(f"{path}/publish", headers=headers)
    completed = api.patch(
        path,
        headers=headers,
        json={
            "currency": "MZN",
            "quantity": "1",
            "unit": "kg",
            "availability": "available",
        },
    )
    published = api.post(f"{path}/publish", headers=headers)
    suspended = api.post(f"{path}/suspend", headers=headers)
    republished = api.post(f"{path}/publish", headers=headers)
    withdrawn = api.post(f"{path}/withdraw", headers=headers)
    removed = api.delete(path, headers=headers)

    assert refused.status_code == 422
    assert refused.json() == NOT_PUBLISHABLE
    assert completed.status_code == 200
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["price"] == "5.00"
    assert published.json()["currency"] == "MZN"
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    assert suspended.json()["price"] == "5.00"
    assert republished.status_code == 200
    assert republished.json()["status"] == "published"
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    assert removed.status_code == 405
    db_session.expire_all()
    stored = db_session.get(Offer, offer_id)
    assert stored.status is OfferStatus.WITHDRAWN
    assert stored.price == Decimal("5.00")
    assert _commercial(stored)[:2] == before[:2]
    assert len(_rows(db_session, actor_id)) == 1

    blocked = [
        api.post(f"{path}/publish", headers=headers),
        api.post(f"{path}/suspend", headers=headers),
        api.post(f"{path}/withdraw", headers=headers),
        api.patch(path, headers=headers, json={"unit": "não muda"}),
    ]
    for response in blocked:
        assert response.status_code == 422
    assert blocked[-1].json() == WITHDRAWN
    db_session.expire_all()
    assert db_session.get(Offer, offer_id).status is OfferStatus.WITHDRAWN
    assert db_session.get(Offer, offer_id).unit == "kg"


def test_repeated_transition_does_not_write(api, db_session, monkeypatch):
    user = _user(db_session, "repetida-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    created = _add(api, user, actor_id, product_id)
    offer_id = created.json()["id"]
    headers = _bearer(user)
    path = f"/actors/{actor_id}/offers/{offer_id}/publish"
    assert api.post(path, headers=headers).status_code == 200

    def fail(session, offer):
        raise AssertionError("transição repetida não deve escrever")

    monkeypatch.setattr("app.offers.mark_published", fail)
    repeated = api.post(path, headers=headers)

    assert repeated.status_code == 422
    assert repeated.json() == TRANSITION
    db_session.expire_all()
    assert db_session.get(Offer, uuid.UUID(offer_id)).status is OfferStatus.PUBLISHED


def test_draft_can_be_withdrawn_without_publication_data(api, db_session):
    user = _user(db_session, "retirar-rascunho@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    created = api.post(
        f"/actors/{actor_id}/offers",
        headers=_bearer(user),
        json={"product_id": str(product_id)},
    )
    offer_id = created.json()["id"]

    withdrawn = api.post(
        f"/actors/{actor_id}/offers/{offer_id}/withdraw",
        headers=_bearer(user),
    )
    suspended = api.post(
        f"/actors/{actor_id}/offers/{offer_id}/suspend",
        headers=_bearer(user),
    )

    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    assert withdrawn.json()["price"] is None
    assert suspended.status_code == 422
    assert suspended.json() == TRANSITION


def test_archived_product_blocks_new_offers_and_publication(api, db_session):
    user = _user(db_session, "arquivo-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id, name="Mel vivo")
    headers = _bearer(user)
    draft = _add(api, user, actor_id, product_id, delivery_terms="Texto inicial")
    offer_id = uuid.UUID(draft.json()["id"])
    path = f"/actors/{actor_id}/offers/{offer_id}"
    published = api.post(f"{path}/publish", headers=headers)
    archived = api.post(
        f"/actors/{actor_id}/products/{product_id}/archive",
        headers=headers,
    )
    another = _add(api, user, actor_id, product_id, price="4.00")
    corrected = api.patch(path, headers=headers, json={"delivery_terms": "Texto corrigido"})
    cleared = api.patch(path, headers=headers, json={"price": None})
    suspended = api.post(f"{path}/suspend", headers=headers)
    republished = api.post(f"{path}/publish", headers=headers)

    fresh_product = _product(api, user, actor_id, name="Mel depois")
    api.post(
        f"/actors/{actor_id}/products/{fresh_product}/archive",
        headers=headers,
    )
    blocked_draft = api.post(
        f"/actors/{actor_id}/offers",
        headers=headers,
        json={"product_id": str(fresh_product)},
    )

    assert published.status_code == 200
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert another.status_code == 422
    assert another.json() == ARCHIVED
    assert corrected.status_code == 200
    assert corrected.json()["status"] == "published"
    assert corrected.json()["delivery_terms"] == "Texto corrigido"
    assert cleared.status_code == 422
    assert cleared.json() == PUBLISHED_INVALID
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    assert republished.status_code == 422
    assert republished.json() == ARCHIVED
    assert blocked_draft.status_code == 422
    assert blocked_draft.json() == ARCHIVED
    db_session.expire_all()
    stored = db_session.get(Offer, offer_id)
    product = db_session.get(Product, product_id)
    assert stored.status is OfferStatus.SUSPENDED
    assert stored.price == Decimal("150.00")
    assert stored.delivery_terms == "Texto corrigido"
    assert product.status is ProductStatus.ARCHIVED
    assert len(_rows(db_session, actor_id)) == 1


def test_published_offer_of_an_archived_product_can_be_withdrawn(api, db_session):
    user = _user(db_session, "retirar-arquivo-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    created = _add(api, user, actor_id, product_id)
    offer_id = uuid.UUID(created.json()["id"])
    headers = _bearer(user)
    path = f"/actors/{actor_id}/offers/{offer_id}"
    assert api.post(f"{path}/publish", headers=headers).status_code == 200
    assert (
        api.post(
            f"/actors/{actor_id}/products/{product_id}/archive",
            headers=headers,
        ).status_code
        == 200
    )
    before = _commercial(db_session.get(Offer, offer_id))

    withdrawn = api.post(f"{path}/withdraw", headers=headers)

    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    assert withdrawn.json()["price"] == "150.00"
    assert withdrawn.json()["quantity"] == "2.50"
    db_session.expire_all()
    stored = db_session.get(Offer, offer_id)
    assert stored.status is OfferStatus.WITHDRAWN
    assert _commercial(stored) == before
    assert db_session.get(Product, product_id).status is ProductStatus.ARCHIVED


def test_database_rejects_invalid_offer_rows(api, db_session):
    user = _user(db_session, "restricao-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    valid = _add(api, user, actor_id, product_id, price="6.00")
    params = {
        "actor_id": actor_id,
        "product_id": product_id,
        "missing_actor": uuid.uuid4(),
        "missing_product": uuid.uuid4(),
    }
    statements = [
        """
        INSERT INTO offers (product_id, owner_actor_id, status)
        VALUES (:missing_product, :actor_id, 'draft')
        """,
        """
        INSERT INTO offers (product_id, owner_actor_id, status)
        VALUES (:product_id, :missing_actor, 'draft')
        """,
        """
        INSERT INTO offers (product_id, owner_actor_id, price, status)
        VALUES (:product_id, :actor_id, -1, 'draft')
        """,
        """
        INSERT INTO offers (product_id, owner_actor_id, currency, status)
        VALUES (:product_id, :actor_id, 'mzn', 'draft')
        """,
        """
        INSERT INTO offers (product_id, owner_actor_id, unit, status)
        VALUES (:product_id, :actor_id, '   ', 'draft')
        """,
        """
        INSERT INTO offers (product_id, owner_actor_id, availability, status)
        VALUES (:product_id, :actor_id, 'seasonal', 'draft')
        """,
        """
        INSERT INTO offers (product_id, owner_actor_id, status)
        VALUES (:product_id, :actor_id, 'archived')
        """,
        """
        INSERT INTO offers (
            product_id, owner_actor_id, quantity, availability, status
        )
        VALUES (:product_id, :actor_id, 0, 'available', 'draft')
        """,
        """
        INSERT INTO offers (product_id, owner_actor_id, price, currency, status)
        VALUES (:product_id, :actor_id, 10, 'MZN', 'published')
        """,
    ]

    for statement in statements:
        _reject(db_session, statement, params)

    stored = db_session.get(Offer, uuid.UUID(valid.json()["id"]))
    assert stored is not None
    assert stored.price == Decimal("6.00")


def test_database_enforces_the_same_owner(api, db_session):
    user = _user(db_session, "dono-base-oferta@example.com")
    actor_id = _actor(api, user, name="Dono")
    other_actor = _actor(api, user, name="Outro dono")
    product_id = _product(api, user, actor_id)
    other_product = _product(api, user, other_actor)
    created = _add(api, user, actor_id, product_id)
    params = {
        "actor_id": actor_id,
        "other_actor": other_actor,
        "product_id": product_id,
        "other_product": other_product,
    }

    _reject(
        db_session,
        """
        INSERT INTO offers (product_id, owner_actor_id, status)
        VALUES (:other_product, :actor_id, 'draft')
        """,
        params,
        "fk_offers_product_owner",
    )
    _reject(
        db_session,
        """
        INSERT INTO offers (product_id, owner_actor_id, status)
        VALUES (:product_id, :other_actor, 'draft')
        """,
        params,
        "fk_offers_product_owner",
    )
    _reject(
        db_session,
        "UPDATE products SET owner_actor_id = :other_actor WHERE id = :product_id",
        params,
        "fk_offers_product_owner",
    )

    db_session.expire_all()
    offer = db_session.get(Offer, uuid.UUID(created.json()["id"]))
    product = db_session.get(Product, product_id)
    assert offer.owner_actor_id == actor_id
    assert offer.product_id == product_id
    assert product.owner_actor_id == actor_id


def test_database_restricts_delete_while_an_offer_exists(api, db_session):
    user = _user(db_session, "restricao-apagar-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    created = _add(api, user, actor_id, product_id)

    _reject(db_session, "DELETE FROM products WHERE id = :product_id", {"product_id": product_id})
    _reject(db_session, "DELETE FROM actors WHERE id = :actor_id", {"actor_id": actor_id})

    assert db_session.get(Offer, uuid.UUID(created.json()["id"])) is not None
    assert db_session.get(Product, product_id) is not None


def test_failed_creation_rolls_back_the_offer(api, db_session, monkeypatch):
    user = _user(db_session, "falha-oferta@example.com")
    actor_id = _actor(api, user, roles=["producer", "buyer"])
    product_id = _product(api, user, actor_id)

    def explode(session, offer):
        session.flush()
        raise RuntimeError("falha na oferta")

    monkeypatch.setattr("app.offers.remember_new_offer", explode)

    with pytest.raises(RuntimeError, match="falha na oferta"):
        _add(api, user, actor_id, product_id, unit="não fica")

    db_session.expire_all()
    assert _rows(db_session, actor_id) == []
    assert db_session.get(Product, product_id) is not None


def test_failed_update_rolls_back_the_offer(api, db_session, monkeypatch):
    user = _user(db_session, "falha-edicao-oferta@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    created = _add(api, user, actor_id, product_id, unit="original", price="8.00")
    offer_id = uuid.UUID(created.json()["id"])

    def explode(session, offer, fields):
        offer.unit = "não fica"
        offer.price = Decimal("1.00")
        session.flush()
        raise RuntimeError("falha na actualização")

    monkeypatch.setattr("app.offers.apply_offer_changes", explode)

    with pytest.raises(RuntimeError, match="falha na actualização"):
        api.patch(
            f"/actors/{actor_id}/offers/{offer_id}",
            headers=_bearer(user),
            json={"unit": "novo", "price": "3.00"},
        )

    db_session.expire_all()
    stored = db_session.get(Offer, offer_id)
    assert stored.unit == "original"
    assert stored.price == Decimal("8.00")
    assert stored.status is OfferStatus.DRAFT


def test_failed_publish_rolls_back_the_status(api, db_session, monkeypatch):
    user = _user(db_session, "falha-publicar@example.com")
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id)
    created = _add(api, user, actor_id, product_id)
    offer_id = uuid.UUID(created.json()["id"])

    def explode(session, offer):
        offer.status = OfferStatus.PUBLISHED
        session.flush()
        raise RuntimeError("falha na publicação")

    monkeypatch.setattr("app.offers.mark_published", explode)

    with pytest.raises(RuntimeError, match="falha na publicação"):
        api.post(
            f"/actors/{actor_id}/offers/{offer_id}/publish",
            headers=_bearer(user),
        )

    db_session.expire_all()
    stored = db_session.get(Offer, offer_id)
    assert stored.status is OfferStatus.DRAFT
    assert stored.price == Decimal("150.00")


def test_actor_without_producer_role_cannot_write_offers(api, db_session):
    user = _user(db_session, "sem-producer-oferta@example.com")
    buyer_only = _actor(api, user, name="Só comprador", roles=["buyer"])
    producer = _actor(api, user, name="Era produtor", roles=["producer", "buyer"])
    product_id = _product(api, user, producer, name="Mel existente")
    created = _add(api, user, producer, product_id, unit="fica")
    offer_id = created.json()["id"]
    buyer_product = Product(
        owner_actor_id=buyer_only,
        name="Via SQL",
        description="A base não consulta actor_roles.",
        category="mel",
        status=ProductStatus.ACTIVE,
    )
    db_session.add(buyer_product)
    db_session.flush()

    rejected = _add(api, user, buyer_only, buyer_product.id, unit="não entra")
    visible = api.get(f"/actors/{buyer_only}/offers", headers=_bearer(user))
    removed = api.put(
        f"/actors/{producer}/roles",
        headers=_bearer(user),
        json={"roles": ["buyer"]},
    )
    path = f"/actors/{producer}/offers/{offer_id}"
    headers = _bearer(user)
    another = _add(api, user, producer, product_id, unit="segundo")
    renamed = api.patch(path, headers=headers, json={"unit": "não muda"})
    published = api.post(f"{path}/publish", headers=headers)
    kept = api.get(path, headers=headers)

    assert rejected.status_code == 422
    assert rejected.json() == NO_PRODUCER
    assert visible.status_code == 200
    assert visible.json() == []
    assert removed.status_code == 200
    assert another.status_code == 422
    assert renamed.status_code == 422
    assert published.status_code == 422
    assert kept.status_code == 200
    assert kept.json()["unit"] == "fica"
    assert kept.json()["status"] == "draft"
    assert len(_rows(db_session, producer)) == 1
    assert _rows(db_session, buyer_only) == []


def test_producer_role_does_not_grant_access_to_another_actor(api, db_session):
    owner = _user(db_session, "produtor-dono-oferta@example.com")
    outsider = _user(db_session, "produtor-alheio-oferta@example.com")
    owned = _actor(api, owner, name="Casa do dono")
    _actor(api, outsider, name="Casa alheia", roles=["producer"])
    product_id = _product(api, owner, owned)
    created = _add(api, owner, owned, product_id, price="45.00")
    offer_id = created.json()["id"]
    headers = _bearer(outsider)

    listing = api.get(f"/actors/{owned}/offers", headers=headers)
    single = api.get(f"/actors/{owned}/offers/{offer_id}", headers=headers)
    updated = api.patch(
        f"/actors/{owned}/offers/{offer_id}",
        headers=headers,
        json={"unit": "não entra"},
    )

    assert listing.status_code == 404
    assert single.status_code == 404
    assert updated.status_code == 404
    assert listing.json() == NOT_FOUND
    assert "45.00" not in listing.text
    stored = db_session.get(Offer, uuid.UUID(offer_id))
    assert stored.price == Decimal("45.00")


def test_database_accepts_a_direct_row_without_the_producer_role(api, db_session):
    user = _user(db_session, "regra-api-oferta@example.com")
    actor_id = _actor(api, user, name="Comprador", roles=["buyer"])
    product = Product(
        owner_actor_id=actor_id,
        name="Via SQL",
        description="A base não consulta actor_roles.",
        category="mel",
        status=ProductStatus.ACTIVE,
    )
    db_session.add(product)
    db_session.flush()
    rejected = _add(api, user, actor_id, product.id)

    direct = Offer(
        product_id=product.id,
        owner_actor_id=actor_id,
        price=Decimal("3.00"),
        currency="MZN",
        quantity=Decimal("1"),
        unit="kg",
        availability=AvailabilityStatus.AVAILABLE,
        delivery_terms=None,
        status=OfferStatus.DRAFT,
    )
    db_session.add(direct)
    db_session.flush()

    assert rejected.status_code == 422
    assert rejected.json() == NO_PRODUCER
    assert [item.unit for item in _rows(db_session, actor_id)] == ["kg"]


def test_migrated_offer_schema_matches_the_model(db_session):
    inspector = inspect(db_session.get_bind())
    table = Offer.__table__
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
    assert inspector.get_pk_constraint(table.name)["name"] == "pk_offers"
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
    ) == ["fk_offers_owner_actor_id", "fk_offers_product_owner"]
    assert sorted(
        index["name"]
        for index in inspector.get_indexes(table.name)
        if not index["unique"]
    ) == ["ix_offers_owner_actor_id", "ix_offers_product_id"]
    assert "uq_products_id_owner" in {
        item["name"] for item in inspector.get_unique_constraints("products")
    }

    definitions = db_session.execute(
        text(
            """
            SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'offers'::regclass
            """
        )
    ).all()
    by_name = {row.conname: row.definition for row in definitions}
    assert set(QUOTED_LITERAL.findall(by_name["ck_offers_status"])) == {
        "draft",
        "published",
        "suspended",
        "withdrawn",
    }
    assert set(QUOTED_LITERAL.findall(by_name["ck_offers_availability"])) == {
        "available",
        "unavailable",
    }
    assert "ON DELETE RESTRICT" in by_name["fk_offers_product_owner"]
    assert "ON UPDATE RESTRICT" in by_name["fk_offers_product_owner"]
    assert "ON DELETE RESTRICT" in by_name["fk_offers_owner_actor_id"]


def _calls(api, user: User, actor_id: uuid.UUID, product_id: uuid.UUID, offer_id: str):
    headers = _bearer(user)
    return [
        api.post(
            f"/actors/{actor_id}/offers",
            headers=headers,
            json=_offer_body(product_id, unit="intruso"),
        ),
        api.get(f"/actors/{actor_id}/offers", headers=headers),
        api.get(f"/actors/{actor_id}/offers/{offer_id}", headers=headers),
        api.patch(
            f"/actors/{actor_id}/offers/{offer_id}",
            headers=headers,
            json={"unit": "não entra"},
        ),
        api.post(f"/actors/{actor_id}/offers/{offer_id}/publish", headers=headers),
        api.post(f"/actors/{actor_id}/offers/{offer_id}/suspend", headers=headers),
        api.post(f"/actors/{actor_id}/offers/{offer_id}/withdraw", headers=headers),
    ]
