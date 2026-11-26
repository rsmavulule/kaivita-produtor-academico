"""Área de actuação, fotografia HTTPS e declaração de direitos.

A declaração é uma afirmação do representante sobre a referência gravada.
Não usa publication_authorizations. A consulta pública só recebe a
fotografia quando a oferta é elegível, o URL é HTTPS e a declaração
corresponde a essa referência.
"""

import os
import re
import subprocess
import sys
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from app.accounts import create_active_user
from app.config import settings
from app.db import engine, get_session
from app.identity import AccessLevel, AccessStatus, Actor, User, UserActorAccess
from app.main import app
from app.products import Product
from app.tokens import issue_access_token

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "palavra-de-teste"
NOT_FOUND = {"detail": "Actor não encontrado."}
OFFER_NOT_FOUND = {"detail": "Oferta não encontrada."}
PHOTO = "https://example.com/mel-sintetico.jpg"
OTHER_PHOTO = "https://example.com/mel-novo.jpg"
THROWAWAY_NAME = re.compile(r"kaivita_i81_[0-9a-f]{12}")


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


def _user(session: Session) -> User:
    user = create_active_user(
        session,
        f"i81-{uuid.uuid4().hex[:12]}@example.com",
        PASSWORD,
    )
    session.flush()
    return user


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_access_token(user.id)}"}


def _actor(api, user: User, **extra) -> dict:
    body = {
        "kind": "person",
        "display_name": "Produtor Exemplo",
        "general_location": "Inhambane",
        "roles": ["producer"],
    }
    body.update(extra)
    created = api.post("/actors", headers=_bearer(user), json=body)
    assert created.status_code == 201, created.text
    return created.json()


def _product(api, user: User, actor_id: str, **extra) -> dict:
    body = {
        "name": "Mel",
        "description": "Mel de exemplo",
        "category": "mel",
    }
    body.update(extra)
    created = api.post(
        f"/actors/{actor_id}/products",
        headers=_bearer(user),
        json=body,
    )
    assert created.status_code == 201, created.text
    return created.json()


def _offer(api, user: User, actor_id: str, product_id: str) -> str:
    created = api.post(
        f"/actors/{actor_id}/offers",
        headers=_bearer(user),
        json={
            "product_id": product_id,
            "price": "10.00",
            "currency": "MZN",
            "quantity": "1.00",
            "unit": "kg",
            "availability": "available",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _transition(api, user: User, actor_id: str, offer_id: str, action: str) -> None:
    response = api.post(
        f"/actors/{actor_id}/offers/{offer_id}/{action}",
        headers=_bearer(user),
    )
    assert response.status_code == 200, response.text


def test_coverage_area_is_independent_of_general_location(api, db_session):
    user = _user(db_session)
    created = _actor(api, user, coverage_area="Sul de Moçambique")
    actor_id = created["id"]

    assert created["coverage_area"] == "Sul de Moçambique"
    assert created["general_location"] == "Inhambane"
    assert "user_id" not in created

    listed = api.get("/actors", headers=_bearer(user))
    assert listed.status_code == 200
    match = next(item for item in listed.json() if item["id"] == actor_id)
    assert match["coverage_area"] == "Sul de Moçambique"
    assert match["representation"] == "manage"

    renamed = api.patch(
        f"/actors/{actor_id}",
        headers=_bearer(user),
        json={"coverage_area": "Norte e centro"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["coverage_area"] == "Norte e centro"
    assert renamed.json()["general_location"] == "Inhambane"

    cleared = api.patch(
        f"/actors/{actor_id}",
        headers=_bearer(user),
        json={"coverage_area": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["coverage_area"] is None
    assert cleared.json()["general_location"] == "Inhambane"

    db_session.expire_all()
    stored = db_session.get(Actor, uuid.UUID(actor_id))
    assert stored.general_location == "Inhambane"
    assert stored.coverage_area is None

    blank = api.patch(
        f"/actors/{actor_id}",
        headers=_bearer(user),
        json={"coverage_area": "   "},
    )
    assert blank.status_code == 422
    assert "   " not in blank.text


def test_existing_actor_keeps_a_null_coverage_area(api, db_session):
    user = _user(db_session)
    created = _actor(api, user)
    assert "coverage_area" not in {
        "kind",
        "display_name",
        "general_location",
        "roles",
    }
    assert created["coverage_area"] is None
    assert created["general_location"] == "Inhambane"
    db_session.expire_all()
    stored = db_session.get(Actor, uuid.UUID(created["id"]))
    assert stored.coverage_area is None
    assert stored.general_location == "Inhambane"


def test_coverage_area_respects_representation_and_actor_isolation(api, db_session):
    owner = _user(db_session)
    reader = _user(db_session)
    other = _user(db_session)
    own = _actor(api, owner, display_name="Produtor A", coverage_area="Gaza")
    foreign = _actor(api, other, display_name="Produtor B", coverage_area="Niassa")
    db_session.add(
        UserActorAccess(
            user_id=reader.id,
            actor_id=uuid.UUID(own["id"]),
            access_level=AccessLevel.READ,
            status=AccessStatus.ACTIVE,
        )
    )
    db_session.flush()

    viewed = api.get(f"/actors/{own['id']}", headers=_bearer(reader))
    assert viewed.status_code == 200
    assert viewed.json()["coverage_area"] == "Gaza"
    assert viewed.json()["representation"] == "read"

    blocked = api.patch(
        f"/actors/{own['id']}",
        headers=_bearer(reader),
        json={"coverage_area": "Maputo"},
    )
    hidden = api.get(f"/actors/{foreign['id']}", headers=_bearer(owner))
    assert blocked.status_code == 404
    assert hidden.status_code == 404
    assert blocked.json() == hidden.json() == NOT_FOUND
    assert "Niassa" not in hidden.text
    assert "Gaza" not in hidden.text

    db_session.expire_all()
    assert db_session.get(Actor, uuid.UUID(own["id"])).coverage_area == "Gaza"


def test_photograph_stays_optional_until_a_matching_declaration(api, db_session):
    user = _user(db_session)
    actor = _actor(api, user)
    actor_id = actor["id"]
    headers = _bearer(user)
    without = _product(api, user, actor_id)
    assert without["image_ref"] is None
    assert without["image_use_confirmed"] is False

    secret = "javascript:alert(1)"
    rejected = [
        {"image_ref": "   "},
        {"image_ref": secret},
        {"image_ref": "http://example.com/mel.jpg"},
        {"image_ref": "https://user:secret@example.com/mel.jpg"},
        {"image_ref": "nota-interna"},
        {"image_ref": None, "image_use_confirmed": True},
    ]
    for body in rejected:
        response = api.post(
            f"/actors/{actor_id}/products",
            headers=headers,
            json={"name": "Mel", "description": "Texto", "category": "mel", **body},
        )
        assert response.status_code == 422, response.text
        assert secret not in response.text
        assert "user:secret" not in response.text
        assert "input" not in response.text

    private = _product(api, user, actor_id, image_ref=PHOTO)
    assert private["image_ref"] == PHOTO
    assert private["image_use_confirmed"] is False
    product_id = private["id"]
    offer_id = _offer(api, user, actor_id, product_id)
    _transition(api, user, actor_id, offer_id, "publish")
    published = api.get(f"/public/offers/{offer_id}")
    assert published.status_code == 200
    assert published.json()["product"]["image_ref"] is None
    assert PHOTO not in published.text
    assert published.json()["producer"]["coverage_area"] is None

    confirmed = api.patch(
        f"/actors/{actor_id}/products/{product_id}",
        headers=headers,
        json={"image_use_confirmed": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["image_use_confirmed"] is True
    assert str(user.id) not in confirmed.text
    db_session.expire_all()
    stored = db_session.get(Product, uuid.UUID(product_id))
    first_at = stored.image_rights_declared_at
    assert stored.image_rights_ref == PHOTO
    assert stored.image_rights_declared_by == user.id
    assert first_at is not None

    repeated = api.patch(
        f"/actors/{actor_id}/products/{product_id}",
        headers=headers,
        json={"image_ref": PHOTO, "image_use_confirmed": True},
    )
    assert repeated.status_code == 200
    db_session.expire_all()
    stored = db_session.get(Product, uuid.UUID(product_id))
    assert stored.image_rights_declared_at == first_at

    visible = api.get(f"/public/offers/{offer_id}")
    assert visible.json()["product"]["image_ref"] == PHOTO

    changed = api.patch(
        f"/actors/{actor_id}/products/{product_id}",
        headers=headers,
        json={"image_ref": OTHER_PHOTO},
    )
    assert changed.status_code == 200
    assert changed.json()["image_ref"] == OTHER_PHOTO
    assert changed.json()["image_use_confirmed"] is False
    after_change = api.get(f"/public/offers/{offer_id}")
    assert after_change.json()["product"]["image_ref"] is None
    assert PHOTO not in after_change.text
    assert OTHER_PHOTO not in after_change.text

    renewed = api.patch(
        f"/actors/{actor_id}/products/{product_id}",
        headers=headers,
        json={"image_ref": OTHER_PHOTO, "image_use_confirmed": True},
    )
    assert renewed.status_code == 200
    assert renewed.json()["image_use_confirmed"] is True
    assert api.get(f"/public/offers/{offer_id}").json()["product"]["image_ref"] == OTHER_PHOTO

    removed = api.patch(
        f"/actors/{actor_id}/products/{product_id}",
        headers=headers,
        json={"image_ref": None, "image_use_confirmed": False},
    )
    assert removed.status_code == 200
    assert removed.json()["image_ref"] is None
    assert removed.json()["image_use_confirmed"] is False
    db_session.expire_all()
    stored = db_session.get(Product, uuid.UUID(product_id))
    assert stored.image_rights_declared_at is None
    assert stored.image_rights_ref is None
    cleared = api.get(f"/public/offers/{offer_id}")
    assert cleared.json()["product"]["image_ref"] is None
    assert OTHER_PHOTO not in cleared.text


def test_public_photograph_follows_offer_eligibility(api, db_session):
    user = _user(db_session)
    coverage = f"Zambezia {uuid.uuid4().hex[:8]}"
    actor = _actor(api, user, coverage_area=coverage, general_location="Inhambane")
    actor_id = actor["id"]
    product = _product(
        api,
        user,
        actor_id,
        name=f"Mel {coverage}",
        image_ref=PHOTO,
        image_use_confirmed=True,
    )
    offer_id = _offer(api, user, actor_id, product["id"])

    hidden = api.get(f"/public/offers/{offer_id}")
    assert hidden.status_code == 404
    assert hidden.json() == OFFER_NOT_FOUND
    assert PHOTO not in hidden.text

    _transition(api, user, actor_id, offer_id, "publish")
    shown = api.get(f"/public/offers/{offer_id}")
    assert shown.status_code == 200
    assert shown.headers["cache-control"] == "no-store"
    assert shown.json()["product"]["image_ref"] == PHOTO
    assert shown.json()["producer"]["general_location"] == "Inhambane"
    assert shown.json()["producer"]["coverage_area"] == coverage
    assert str(user.id) not in shown.text
    assert actor_id not in shown.text

    by_location = api.get("/public/offers", params={"location": coverage})
    assert by_location.status_code == 200
    assert by_location.json()["total"] == 0
    unknown = api.get("/public/offers", params={"coverage_area": coverage})
    assert unknown.status_code == 422
    assert coverage not in unknown.text

    _transition(api, user, actor_id, offer_id, "suspend")
    suspended = api.get(f"/public/offers/{offer_id}")
    assert suspended.status_code == 404
    assert PHOTO not in suspended.text

    _transition(api, user, actor_id, offer_id, "publish")
    _transition(api, user, actor_id, offer_id, "withdraw")
    withdrawn = api.get(f"/public/offers/{offer_id}")
    assert withdrawn.status_code == 404
    assert PHOTO not in withdrawn.text

    archived_product = _product(
        api,
        user,
        actor_id,
        name="Caju",
        image_ref=OTHER_PHOTO,
        image_use_confirmed=True,
    )
    archived_offer = _offer(api, user, actor_id, archived_product["id"])
    _transition(api, user, actor_id, archived_offer, "publish")
    archive = api.post(
        f"/actors/{actor_id}/products/{archived_product['id']}/archive",
        headers=_bearer(user),
    )
    assert archive.status_code == 200
    gone = api.get(f"/public/offers/{archived_offer}")
    assert gone.status_code == 404
    assert OTHER_PHOTO not in gone.text


def test_historical_image_ref_is_kept_and_stays_private(api, db_session):
    user = _user(db_session)
    actor = _actor(api, user)
    product = _product(api, user, actor["id"])
    product_id = uuid.UUID(product["id"])
    db_session.execute(
        text("UPDATE products SET image_ref = 'foto-historica' WHERE id = :id"),
        {"id": product_id},
    )
    db_session.flush()
    offer_id = _offer(api, user, actor["id"], product["id"])
    _transition(api, user, actor["id"], offer_id, "publish")

    private = api.get(
        f"/actors/{actor['id']}/products/{product['id']}",
        headers=_bearer(user),
    )
    public = api.get(f"/public/offers/{offer_id}")
    assert private.json()["image_ref"] == "foto-historica"
    assert private.json()["image_use_confirmed"] is False
    assert public.json()["product"]["image_ref"] is None
    assert "foto-historica" not in public.text

    rejected = api.patch(
        f"/actors/{actor['id']}/products/{product['id']}",
        headers=_bearer(user),
        json={"image_use_confirmed": True},
    )
    assert rejected.status_code == 422
    assert "foto-historica" not in rejected.text


def test_migration_preserves_rows_and_does_not_publish_old_photos():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    name = f"kaivita_i81_{uuid.uuid4().hex[:12]}"
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
        _alembic(environment, "upgrade", "0006_publication_authorizations")
        _plant(target)
        _alembic(environment, "upgrade", "0007_coverage_and_image_rights")
        upgraded = _state(target)
        assert upgraded["version"] == "0007_coverage_and_image_rights"
        assert upgraded["location"] == "Inhambane"
        assert upgraded["coverage"] is None
        assert upgraded["image_ref"] == "foto-historica"
        assert upgraded["rights_ref"] is None
        assert upgraded["declared_at"] is None

        _alembic(environment, "downgrade", "0006_publication_authorizations")
        restored = _state(target)
        assert restored["version"] == "0006_publication_authorizations"
        assert restored["coverage_column"] is False
        assert restored["location"] == "Inhambane"
        assert restored["image_ref"] == "foto-historica"

        _alembic(environment, "upgrade", "0007_coverage_and_image_rights")
        again = _state(target)
        assert again["version"] == "0007_coverage_and_image_rights"
        assert again["coverage"] is None
        assert again["image_ref"] == "foto-historica"
        assert again["rights_ref"] is None
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
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr


def _plant(target: str) -> None:
    planted = create_engine(target)
    with planted.begin() as connection:
        actor_id = connection.execute(
            text(
                """
                INSERT INTO actors (kind, display_name, general_location, status)
                VALUES ('person', 'Produtor antigo', 'Inhambane', 'active')
                RETURNING id
                """
            )
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO products (
                    owner_actor_id, name, description, category, image_ref, status
                )
                VALUES (:actor_id, 'Mel antigo', 'Texto', 'mel', 'foto-historica', 'active')
                """
            ),
            {"actor_id": actor_id},
        )
    planted.dispose()


def _state(target: str) -> dict:
    inspected = create_engine(target)
    with inspected.connect() as connection:
        version = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        columns = {
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'actors'
                    """
                )
            )
        }
        if "coverage_area" not in columns:
            location, image_ref = connection.execute(
                text(
                    """
                    SELECT actors.general_location, products.image_ref
                    FROM actors
                    JOIN products ON products.owner_actor_id = actors.id
                    """
                )
            ).one()
            inspected.dispose()
            return {
                "version": version,
                "coverage_column": False,
                "location": location,
                "image_ref": image_ref,
            }
        row = connection.execute(
            text(
                """
                SELECT
                    actors.general_location,
                    actors.coverage_area,
                    products.image_ref,
                    products.image_rights_ref,
                    products.image_rights_declared_at
                FROM actors
                JOIN products ON products.owner_actor_id = actors.id
                """
            )
        ).one()
    inspected.dispose()
    return {
        "version": version,
        "coverage_column": True,
        "location": row[0],
        "coverage": row[1],
        "image_ref": row[2],
        "rights_ref": row[3],
        "declared_at": row[4],
    }
