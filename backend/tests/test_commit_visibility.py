"""Uma oferta 201 fica visível na ligação seguinte, sem espera.

O TestClient só devolve o resultado quando a aplicação termina, já depois
do commit do gerador. Este teste observa a linha de corpo: se a oferta
não estiver confirmada antes de a resposta sair, a outra sessão não a vê.
"""

import json
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.accounts import create_active_user
from app.db import engine
from app.identity import Actor, ActorRole, User, UserActorAccess
from app.main import app
from app.offers import Offer
from app.products import Product

PASSWORD = "palavra-de-teste"
ZERO_AVAILABLE = {"detail": "Quantidade zero não pode estar disponível."}
BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")


def test_a_created_offer_is_visible_before_the_response_finishes(migrated_database):
    stamp = uuid.uuid4().hex
    email = f"i55-commit-{stamp}@example.com"
    user_id = None
    actor_id = None
    try:
        user_id = _create_user(email)
        with TestClient(app) as client:
            token = _login(client, email)
            actor_id = _create_actor(client, token, f"Visibilidade {stamp}")
            product_id = _create_product(client, token, actor_id, f"Milho {stamp}")
            _assert_rejected_offer_leaves_no_row(client, token, actor_id, product_id)
            created = _post_offer_and_observe(token, actor_id, product_id)
            seen = client.get(
                f"/actors/{actor_id}/offers/{created['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert seen.status_code == 200
        assert seen.json()["id"] == created["id"]
        assert seen.json()["price"] == "45.00"
        assert seen.json()["status"] == "draft"
    finally:
        _erase(user_id, actor_id)


def _create_user(email: str) -> uuid.UUID:
    with Session(engine) as session:
        user = create_active_user(session, email, PASSWORD)
        session.commit()
        return user.id


def _login(client: TestClient, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_actor(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/actors",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "person", "display_name": name, "roles": ["producer"]},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_product(client: TestClient, token: str, actor_id: str, name: str) -> str:
    response = client.post(
        f"/actors/{actor_id}/products",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "description": "Grão", "category": "cereal"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _assert_rejected_offer_leaves_no_row(client, token, actor_id, product_id) -> None:
    rejected = client.post(
        f"/actors/{actor_id}/offers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "product_id": product_id,
            "price": "45.00",
            "currency": "MZN",
            "quantity": "0",
            "unit": "kg",
            "availability": "available",
        },
    )
    assert rejected.status_code == 422
    assert rejected.json() == ZERO_AVAILABLE
    with Session(engine) as session:
        count = session.scalar(
            select(func.count()).select_from(Offer).where(Offer.product_id == uuid.UUID(product_id))
        )
    assert count == 0


def _post_offer_and_observe(token: str, actor_id: str, product_id: str) -> dict:
    payload = json.dumps(
        {
            "product_id": product_id,
            "price": "45.00",
            "currency": "MZN",
            "quantity": "120.00",
            "unit": "kg",
            "availability": "available",
        }
    ).encode()
    observed: dict = {}
    sent = {"done": False}

    async def receive():
        if sent["done"]:
            return {"type": "http.disconnect"}
        sent["done"] = True
        return {"type": "http.request", "body": payload, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            observed["status"] = message["status"]
            return
        if message["type"] != "http.response.body":
            return
        body = json.loads(message.get("body") or b"{}")
        with Session(engine) as session:
            row = session.get(Offer, uuid.UUID(body["id"]))
        observed["visible"] = row is not None
        observed["body"] = body

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": f"/actors/{actor_id}/offers",
        "raw_path": f"/actors/{actor_id}/offers".encode(),
        "query_string": b"",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"application/json"),
            (b"authorization", f"Bearer {token}".encode()),
        ],
        "client": ("127.0.0.1", 9),
        "server": ("test", 80),
    }

    import asyncio

    asyncio.run(app(scope, receive, send))
    assert observed["status"] == 201
    assert observed["visible"] is True
    return observed["body"]


def _erase(user_id: uuid.UUID | None, actor_id: str | None) -> None:
    with Session(engine) as session:
        if actor_id is not None:
            owner = uuid.UUID(actor_id)
            session.execute(delete(Offer).where(Offer.owner_actor_id == owner))
            session.execute(delete(Product).where(Product.owner_actor_id == owner))
            session.execute(delete(ActorRole).where(ActorRole.actor_id == owner))
            session.execute(delete(UserActorAccess).where(UserActorAccess.actor_id == owner))
            actor = session.get(Actor, owner)
            if actor is not None:
                session.delete(actor)
        if user_id is not None:
            session.execute(delete(UserActorAccess).where(UserActorAccess.user_id == user_id))
            user = session.get(User, user_id)
            if user is not None:
                session.delete(user)
        session.commit()
