"""Descoberta pública de ofertas, com PostgreSQL real.

Cada teste de API corre numa transacção desfeita no fim.
Sem RUN_DB_TESTS=1 esses testes não contactam a base.
Os dados são sintéticos e o predicado é filtrado por um token
próprio de cada teste, para não depender de linhas já confirmadas.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from unittest.mock import patch

from app.accounts import create_active_user
from app.db import engine, get_session
from app.identity import (
    AccessStatus,
    Actor,
    ActorStatus,
    User,
    UserActorAccess,
)
from app.main import app
from app.offers import Offer
from app.products import Product
from app.public_offers import like_pattern, normalize_search_text
from app.tokens import issue_access_token

PASSWORD = "palavra-de-teste"
NOT_FOUND = {"detail": "Oferta não encontrada."}
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
PRODUCT_KEYS = {"name", "description", "category"}
PRODUCER_KEYS = {"display_name", "kind", "general_location"}
PRIVATE_KEYS = {
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


@pytest.fixture(scope="session")
def migrated_database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
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


def _token() -> str:
    return f"i61{uuid.uuid4().hex[:12]}"


def _user(session: Session) -> User:
    user = create_active_user(
        session,
        f"i61-{uuid.uuid4().hex[:12]}@example.com",
        PASSWORD,
    )
    session.flush()
    return user


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_access_token(user.id)}"}


def _actor(
    api,
    user: User,
    *,
    name: str = "Produtor Exemplo",
    location: str | None = "Inhambane",
    roles: list[str] | None = None,
) -> uuid.UUID:
    created = api.post(
        "/actors",
        headers=_bearer(user),
        json={
            "kind": "person",
            "display_name": name,
            "general_location": location,
            "roles": ["producer"] if roles is None else roles,
        },
    )
    assert created.status_code == 201, created.text
    return uuid.UUID(created.json()["id"])


def _product(api, user: User, actor_id: uuid.UUID, **overrides) -> uuid.UUID:
    body = {
        "name": "Mel",
        "description": "Mel de exemplo",
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


def _offer(
    api,
    user: User,
    actor_id: uuid.UUID,
    product_id: uuid.UUID,
    **overrides,
):
    body = {
        "product_id": str(product_id),
        "price": "150.00",
        "currency": "MZN",
        "quantity": "2.50",
        "unit": "kg",
        "availability": "available",
        "delivery_terms": "Levantamento na sede de exemplo",
    }
    body.update(overrides)
    return api.post(
        f"/actors/{actor_id}/offers",
        headers=_bearer(user),
        json=body,
    )


def _publish(api, user: User, actor_id: uuid.UUID, offer_id: str):
    response = api.post(
        f"/actors/{actor_id}/offers/{offer_id}/publish",
        headers=_bearer(user),
    )
    assert response.status_code == 200, response.text
    return response


def _catalog(api, token: str, **params):
    query = {"q": token}
    query.update(params)
    response = api.get("/public/offers", params=query)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def _assert_hidden(api, offer_id: str, token: str) -> None:
    body = _catalog(api, token)
    assert body["items"] == []
    assert body["total"] == 0
    hidden = api.get(f"/public/offers/{offer_id}")
    missing = api.get(f"/public/offers/{uuid.uuid4()}")
    assert hidden.status_code == 404
    assert missing.status_code == 404
    assert hidden.json() == missing.json() == NOT_FOUND
    assert hidden.headers["cache-control"] == "no-store"
    assert missing.headers["cache-control"] == "no-store"


def _assert_error_shape(response, secret: str) -> None:
    assert response.status_code == 422, response.text
    assert response.headers["cache-control"] == "no-store"
    assert secret not in response.text
    assert "input" not in response.text
    assert "ctx" not in response.text
    for error in response.json()["detail"]:
        assert set(error) == {"loc", "msg", "type"}


def test_normalization_folds_portuguese_accents_and_escapes_wildcards():
    assert normalize_search_text("  AÇÚCAR   mascavado ") == "acucar mascavado"
    assert normalize_search_text("MéL") == "mel"
    assert normalize_search_text("lingüiça") == "linguica"
    assert normalize_search_text("   ") == ""
    assert normalize_search_text("100%_puro") == "100%_puro"
    assert normalize_search_text("a\u0301") == "a\u0301"
    assert normalize_search_text("ñ") == "ñ"
    assert normalize_search_text("Ñ") == "Ñ"
    assert like_pattern("100%") == "%100\\%%"
    assert like_pattern("a_b") == "%a\\_b%"
    assert like_pattern("\\") == "%\\\\%"


def test_openapi_documents_the_public_contract(client):
    document = client.get("/openapi.json").json()
    collection = document["paths"]["/public/offers"]["get"]
    single = document["paths"]["/public/offers/{offer_id}"]["get"]
    schemas = document["components"]["schemas"]

    assert "security" not in collection
    assert "security" not in single
    assert [item["name"] for item in collection["parameters"]] == [
        "q",
        "category",
        "location",
        "limit",
        "offset",
    ]
    assert collection["parameters"][3]["schema"]["default"] == 20
    assert collection["parameters"][4]["schema"]["default"] == 0
    assert single["parameters"][0]["schema"]["format"] == "uuid"
    assert set(schemas["PublicOffer"]["properties"]) == PUBLIC_KEYS
    assert set(schemas["PublicOffer"]["required"]) == PUBLIC_KEYS
    assert schemas["PublicOffer"]["additionalProperties"] is False
    assert set(schemas["PublicProduct"]["properties"]) == PRODUCT_KEYS
    assert set(schemas["PublicProducer"]["properties"]) == PRODUCER_KEYS
    assert set(schemas["PublicOfferPage"]["required"]) == {
        "items",
        "limit",
        "offset",
        "total",
    }
    assert schemas["PublicOffer"]["properties"]["price"]["type"] == "string"
    assert schemas["PublicOffer"]["properties"]["price"]["examples"] == ["150.00"]
    assert schemas["PublicOffer"]["properties"]["quantity"]["examples"] == ["2.50"]
    assert "number" not in str(schemas["PublicOffer"]["properties"]["price"])
    private = document["paths"]["/actors/{actor_id}/offers"]["get"]
    assert private["security"] == [{"HTTPBearer": []}]


def test_health_does_not_receive_the_public_cache_header(client):
    with patch("app.main.check_database", return_value=True):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("cache-control") != "no-store"


def test_published_available_offer_is_public_without_authentication(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    product_id = _product(
        api,
        user,
        actor_id,
        name=f"{token} Mel claro",
        description="Mel claro de exemplo",
        category="mel",
        image_ref=f"foto-secreta-{token}",
    )
    created = _offer(
        api,
        user,
        actor_id,
        product_id,
        delivery_terms=f"Combinar pelo 840000001 {token}",
    )
    offer_id = created.json()["id"]
    _publish(api, user, actor_id, offer_id)
    offers_before = db_session.scalar(select(func.count()).select_from(Offer))

    anonymous = api.get("/public/offers", params={"q": token})
    garbage = api.get(
        "/public/offers",
        params={"q": token},
        headers={"Authorization": "Bearer isto-nao-e-um-token"},
    )
    owned = api.get("/public/offers", params={"q": token}, headers=_bearer(user))
    detail = api.get(f"/public/offers/{offer_id}")

    assert anonymous.status_code == 200
    assert anonymous.headers["cache-control"] == "no-store"
    assert garbage.json() == anonymous.json()
    assert owned.json() == anonymous.json()
    body = anonymous.json()
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["total"] == 1
    item = body["items"][0]
    assert detail.json() == item
    assert detail.headers["cache-control"] == "no-store"
    assert set(item) == PUBLIC_KEYS
    assert set(item["product"]) == PRODUCT_KEYS
    assert set(item["producer"]) == PRODUCER_KEYS
    assert item["id"] == offer_id
    assert item["price"] == "150.00"
    assert item["quantity"] == "2.50"
    assert item["currency"] == "MZN"
    assert item["unit"] == "kg"
    assert item["availability"] == "available"
    assert item["delivery_terms"] == f"Combinar pelo 840000001 {token}"
    assert "840000001" in detail.text
    assert item["product"] == {
        "name": f"{token} Mel claro",
        "description": "Mel claro de exemplo",
        "category": "mel",
    }
    assert item["producer"]["display_name"] == "Produtor Exemplo"
    assert item["producer"]["kind"] == "person"
    assert item["producer"]["general_location"] == "Inhambane"
    for fragment in (
        user.email,
        str(user.id),
        str(actor_id),
        str(product_id),
        f"foto-secreta-{token}",
        PASSWORD,
        "owner_actor_id",
        "product_id",
        "image_ref",
        "representation",
        "access_level",
        "password_hash",
        "user_id",
        '"status"',
    ):
        assert fragment not in detail.text
    private = api.get(
        f"/actors/{actor_id}/offers/{offer_id}",
        headers=_bearer(user),
    )
    assert private.status_code == 200
    assert set(private.json()) == PRIVATE_KEYS
    assert api.get(f"/actors/{actor_id}/offers/{offer_id}").status_code == 401
    db_session.expire_all()
    stored = db_session.get(Offer, uuid.UUID(offer_id))
    assert stored is not None
    assert stored.status.value == "published"
    assert format(stored.price, "f") == "150.00"
    assert db_session.scalar(select(func.count()).select_from(Offer)) == offers_before


@pytest.mark.parametrize(
    ("quantity", "availability"),
    [("3.00", "unavailable"), ("0", "unavailable")],
)
def test_unavailable_published_offers_stay_visible(api, db_session, quantity, availability):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id, name=f"{token} reserva")
    created = _offer(
        api,
        user,
        actor_id,
        product_id,
        quantity=quantity,
        availability=availability,
        delivery_terms=None,
    )
    offer_id = created.json()["id"]
    _publish(api, user, actor_id, offer_id)

    item = _catalog(api, token)["items"][0]

    assert item["quantity"] == quantity
    assert item["availability"] == "unavailable"
    assert item["delivery_terms"] is None
    assert api.get(f"/public/offers/{offer_id}").status_code == 200


@pytest.mark.parametrize("state", ["draft", "suspended", "withdrawn"])
def test_unpublished_states_are_hidden_on_list_and_detail(api, db_session, state):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id, name=f"{token} oculto")
    created = _offer(api, user, actor_id, product_id)
    offer_id = created.json()["id"]
    if state != "draft":
        _publish(api, user, actor_id, offer_id)
        action = "suspend" if state == "suspended" else "withdraw"
        changed = api.post(
            f"/actors/{actor_id}/offers/{offer_id}/{action}",
            headers=_bearer(user),
        )
        assert changed.status_code == 200, changed.text

    _assert_hidden(api, offer_id, token)


def test_publication_cycle_and_later_edits_are_visible_on_the_next_read(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id, name=f"{token} ciclo")
    created = _offer(api, user, actor_id, product_id)
    offer_id = created.json()["id"]
    path = f"/actors/{actor_id}/offers/{offer_id}"
    headers = _bearer(user)

    _assert_hidden(api, offer_id, token)
    assert _publish(api, user, actor_id, offer_id).json()["status"] == "published"
    assert _catalog(api, token)["total"] == 1

    suspended = api.post(f"{path}/suspend", headers=headers)
    assert suspended.status_code == 200
    _assert_hidden(api, offer_id, token)

    assert _publish(api, user, actor_id, offer_id).json()["status"] == "published"
    visible = api.get(f"/public/offers/{offer_id}")
    assert visible.status_code == 200
    assert visible.json()["price"] == "150.00"
    assert visible.json()["availability"] == "available"

    edited = api.patch(
        path,
        headers=headers,
        json={"price": "45.00", "availability": "unavailable"},
    )
    assert edited.status_code == 200, edited.text
    reread = api.get(f"/public/offers/{offer_id}")
    assert reread.status_code == 200
    assert reread.json()["price"] == "45.00"
    assert reread.json()["availability"] == "unavailable"
    assert reread.json()["quantity"] == "2.50"

    withdrawn = api.post(f"{path}/withdraw", headers=headers)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    _assert_hidden(api, offer_id, token)


def test_archiving_the_product_hides_the_offer_without_changing_it(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id, name=f"{token} arquivo")
    created = _offer(api, user, actor_id, product_id)
    offer_id = created.json()["id"]
    _publish(api, user, actor_id, offer_id)
    archived = api.post(
        f"/actors/{actor_id}/products/{product_id}/archive",
        headers=_bearer(user),
    )

    assert archived.status_code == 200
    _assert_hidden(api, offer_id, token)
    private = api.get(
        f"/actors/{actor_id}/offers/{offer_id}",
        headers=_bearer(user),
    )
    assert private.json()["status"] == "published"
    db_session.expire_all()
    assert db_session.get(Offer, uuid.UUID(offer_id)).status.value == "published"
    assert db_session.get(Product, product_id).status.value == "archived"


def test_inactive_actor_is_hidden_from_public_discovery(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id, name=f"{token} inactivo")
    created = _offer(api, user, actor_id, product_id)
    offer_id = created.json()["id"]
    _publish(api, user, actor_id, offer_id)
    actor = db_session.get(Actor, actor_id)
    actor.status = ActorStatus.INACTIVE
    db_session.flush()

    _assert_hidden(api, offer_id, token)
    private = api.get(
        f"/actors/{actor_id}/offers/{offer_id}",
        headers=_bearer(user),
    )
    assert private.status_code == 200
    assert private.json()["status"] == "published"


def test_losing_and_restoring_the_producer_role(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user, roles=["producer", "buyer"])
    product_id = _product(api, user, actor_id, name=f"{token} papel")
    created = _offer(api, user, actor_id, product_id)
    offer_id = created.json()["id"]
    _publish(api, user, actor_id, offer_id)
    headers = _bearer(user)

    removed = api.put(
        f"/actors/{actor_id}/roles",
        headers=headers,
        json={"roles": ["buyer"]},
    )
    assert removed.status_code == 200, removed.text
    _assert_hidden(api, offer_id, token)
    private = api.get(f"/actors/{actor_id}/offers/{offer_id}", headers=headers)
    assert private.json()["status"] == "published"

    restored = api.put(
        f"/actors/{actor_id}/roles",
        headers=headers,
        json={"roles": ["producer", "buyer"]},
    )
    assert restored.status_code == 200, restored.text
    assert api.get(f"/public/offers/{offer_id}").status_code == 200
    assert api.get(
        f"/actors/{actor_id}/offers/{offer_id}",
        headers=headers,
    ).json()["status"] == "published"


def test_revoked_representation_does_not_hide_the_public_offer(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id, name=f"{token} acesso")
    created = _offer(api, user, actor_id, product_id)
    offer_id = created.json()["id"]
    _publish(api, user, actor_id, offer_id)
    access = db_session.scalar(
        select(UserActorAccess).where(UserActorAccess.actor_id == actor_id)
    )
    access.status = AccessStatus.REVOKED
    db_session.flush()

    assert _catalog(api, token)["items"][0]["id"] == offer_id
    assert api.get(f"/public/offers/{offer_id}").status_code == 200
    private = api.get(
        f"/actors/{actor_id}/offers/{offer_id}",
        headers=_bearer(user),
    )
    assert private.status_code == 404


def test_search_combines_text_category_and_location(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user, location=f"Loc {token}")
    sugar_id = _product(
        api,
        user,
        actor_id,
        name=f"{token} Açúcar mascavado",
        description="Panela de exemplo",
        category=f"Cat {token}",
    )
    honey = _product(
        api,
        user,
        actor_id,
        name=f"{token}  mel  claro",
        description=f"Descricao {token} de miombo",
        category="mel",
    )
    other = _product(
        api,
        user,
        actor_id,
        name=f"{token} caju",
        description="Fruto",
        category="fruto",
    )
    sugar = _offer(api, user, actor_id, sugar_id)
    honey_offer = _offer(api, user, actor_id, honey)
    other_offer = _offer(api, user, actor_id, other)
    for offer in (sugar, honey_offer, other_offer):
        _publish(api, user, actor_id, offer.json()["id"])

    by_name = _catalog(api, f"  {token}   acucar   mascavado ")
    by_description = _catalog(api, f"descricao {token}")
    by_spaces = _catalog(api, f"{token} mel claro")
    by_category = api.get("/public/offers", params={"category": f"  CAT   {token} "})
    by_location = api.get("/public/offers", params={"location": f"loc {token}"})
    combined = api.get(
        "/public/offers",
        params={
            "q": token,
            "category": f"cat {token}",
            "location": f"loc {token}",
        },
    )
    empty_text = api.get(
        "/public/offers",
        params={"q": "   ", "category": f"cat {token}"},
    )
    none = _catalog(api, f"{token}-nenhum")

    assert [item["id"] for item in by_name["items"]] == [sugar.json()["id"]]
    assert [item["id"] for item in by_description["items"]] == [honey_offer.json()["id"]]
    assert [item["id"] for item in by_spaces["items"]] == [honey_offer.json()["id"]]
    assert by_category.status_code == 200
    assert [item["id"] for item in by_category.json()["items"]] == [sugar.json()["id"]]
    assert by_location.status_code == 200
    assert {item["id"] for item in by_location.json()["items"]} == {
        sugar.json()["id"],
        honey_offer.json()["id"],
        other_offer.json()["id"],
    }
    assert combined.status_code == 200
    assert [item["id"] for item in combined.json()["items"]] == [sugar.json()["id"]]
    assert combined.json()["total"] == 1
    assert empty_text.json() == by_category.json()
    assert none["items"] == []
    assert none["total"] == 0


def test_null_location_stays_visible_until_a_location_filter_is_used(api, db_session):
    token = _token()
    user = _user(db_session)
    located = _actor(api, user, name="Produtor Local", location="Nampula")
    missing = _actor(api, user, name="Produtor Sem Lugar", location=None)
    located_product = _product(api, user, located, name=f"{token} local")
    missing_product = _product(api, user, missing, name=f"{token} sem lugar")
    located_offer = _offer(api, user, located, located_product)
    missing_offer = _offer(api, user, missing, missing_product)
    _publish(api, user, located, located_offer.json()["id"])
    _publish(api, user, missing, missing_offer.json()["id"])

    both = _catalog(api, token)
    filtered = api.get(
        "/public/offers",
        params={"q": token, "location": "nampula"},
    )

    assert {item["id"] for item in both["items"]} == {
        located_offer.json()["id"],
        missing_offer.json()["id"],
    }
    assert both["items"][0]["producer"]["general_location"] in {"Nampula", None}
    assert any(item["producer"]["general_location"] is None for item in both["items"])
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [located_offer.json()["id"]]


def test_wildcards_and_sql_like_text_stay_literal(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    literal = _product(api, user, actor_id, name=f"{token} 100%_puro")
    plain = _product(api, user, actor_id, name=f"{token} 100x puro")
    literal_offer = _offer(api, user, actor_id, literal)
    plain_offer = _offer(api, user, actor_id, plain)
    _publish(api, user, actor_id, literal_offer.json()["id"])
    _publish(api, user, actor_id, plain_offer.json()["id"])
    injection = f"{token}'; DELETE FROM offers; --"

    percent = _catalog(api, f"{token} 100%")
    underscore = _catalog(api, f"{token} 100%_")
    attacked = api.get("/public/offers", params={"q": injection})
    survived = _catalog(api, token)

    assert [item["id"] for item in percent["items"]] == [literal_offer.json()["id"]]
    assert [item["id"] for item in underscore["items"]] == [literal_offer.json()["id"]]
    assert attacked.status_code == 200
    assert attacked.json()["items"] == []
    assert plain_offer.json()["id"] in {item["id"] for item in survived["items"]}
    assert db_session.get(Offer, uuid.UUID(plain_offer.json()["id"])) is not None


def test_ordering_pagination_and_bounds(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    created = []
    for name in (f"{token} banana", f"{token} Água", f"{token} agua"):
        product_id = _product(api, user, actor_id, name=name)
        offer = _offer(api, user, actor_id, product_id)
        _publish(api, user, actor_id, offer.json()["id"])
        created.append({"id": offer.json()["id"], "name": name})
    expected = [
        item["id"]
        for item in sorted(
            created,
            key=lambda item: (normalize_search_text(item["name"]), uuid.UUID(item["id"])),
        )
    ]

    page = _catalog(api, token)
    first = _catalog(api, token, limit=1, offset=0)
    middle = _catalog(api, token, limit=2, offset=0)
    last = _catalog(api, token, limit=2, offset=2)
    beyond = _catalog(api, token, limit=1, offset=3)
    capped = _catalog(api, token, limit=50, offset=1000)

    assert [item["id"] for item in page["items"]] == expected
    assert page["total"] == 3
    assert page["limit"] == 20
    assert page["offset"] == 0
    assert [item["id"] for item in first["items"]] == expected[:1]
    assert first["total"] == 3
    assert [item["id"] for item in middle["items"]] == expected[:2]
    assert [item["id"] for item in last["items"]] == expected[2:]
    assert last["total"] == 3
    assert beyond["items"] == []
    assert beyond["total"] == 3
    assert beyond["offset"] == 3
    assert capped["items"] == []
    assert capped["total"] == 3
    assert capped["limit"] == 50
    assert capped["offset"] == 1000


def test_invalid_parameters_do_not_echo_the_rejected_value(api):
    secret = "SEGREDO-QUE-NAO-PODE-SAIR"
    rejected = [
        api.get("/public/offers", params={"extra": secret}),
        api.get("/public/offers", params=[("q", secret), ("q", f"{secret}-2")]),
        api.get("/public/offers", params={"limit": "abc"}),
        api.get("/public/offers", params={"limit": "0"}),
        api.get("/public/offers", params={"limit": "51"}),
        api.get("/public/offers", params={"limit": "1.5"}),
        api.get("/public/offers", params={"offset": "-1"}),
        api.get("/public/offers", params={"offset": "1001"}),
        api.get("/public/offers", params={"q": "x" * 90 + secret}),
        api.get(f"/public/offers/{secret}"),
        api.get(f"/public/offers/{uuid.uuid4()}", params={"extra": secret}),
    ]

    assert rejected[0].json()["detail"][0]["msg"] == "Parâmetro desconhecido."
    assert rejected[1].json()["detail"][0]["msg"] == "Parâmetro repetido."
    for response in rejected:
        _assert_error_shape(response, secret)


def test_several_offers_and_roles_do_not_duplicate_rows(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user, roles=["partner", "producer", "buyer"])
    product_id = _product(api, user, actor_id, name=f"{token} repetido")
    first = _offer(api, user, actor_id, product_id, price="10.00")
    second = _offer(api, user, actor_id, product_id, price="11.00")
    _publish(api, user, actor_id, first.json()["id"])
    _publish(api, user, actor_id, second.json()["id"])

    body = _catalog(api, token)

    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == sorted(
        [first.json()["id"], second.json()["id"]],
        key=uuid.UUID,
    )
    prices = {item["id"]: item["price"] for item in body["items"]}
    assert prices == {first.json()["id"]: "10.00", second.json()["id"]: "11.00"}


def test_list_and_detail_each_execute_one_select(api, db_session):
    token = _token()
    user = _user(db_session)
    actor_id = _actor(api, user)
    product_id = _product(api, user, actor_id, name=f"{token} consulta")
    created = _offer(api, user, actor_id, product_id)
    offer_id = created.json()["id"]
    _publish(api, user, actor_id, offer_id)

    def _count(call) -> int:
        selects: list[str] = []

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            head = statement.lstrip().upper()
            if head.startswith("SELECT") or head.startswith("WITH"):
                selects.append(statement)

        event.listen(db_session.connection(), "before_cursor_execute", before_cursor_execute)
        try:
            call()
        finally:
            event.remove(db_session.connection(), "before_cursor_execute", before_cursor_execute)
        return len(selects)

    assert _count(lambda: api.get("/public/offers", params={"q": token})) == 1
    assert _count(lambda: api.get(f"/public/offers/{offer_id}")) == 1
    empty = _count(lambda: api.get("/public/offers", params={"q": token, "offset": 1000}))
    assert empty == 1
