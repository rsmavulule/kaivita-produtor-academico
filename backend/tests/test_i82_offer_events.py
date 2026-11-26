"""Transições de oferta, access log e anfitriões locais da fotografia.

Os eventos guardam o estado anterior, o estado novo, o operador e o
instante. Não guardam preço, textos nem contactos. A consulta pública
não os expõe.
"""

import os
import re
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from app.access_log import QuietAccessFormatter, safe_access_path
from app.accounts import create_active_user
from app.actor_roles import create_represented_actor
from app.config import settings
from app.db import engine, get_session
from app.identity import AccessLevel, AccessStatus, Actor, ActorKind, RoleCode, User, UserActorAccess
from app.main import app
from app.offers import (
    AvailabilityStatus,
    Offer,
    OfferRejected,
    OfferStatus,
    OfferStatusEvent,
    create_offer,
    publish_offer,
)
from app.products import create_product
from app.tokens import issue_access_token

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "palavra-de-teste"
MARKER = "i82-marcador-sintetico"
THROWAWAY_NAME = re.compile(r"kaivita_i82_[0-9a-f]{12}")
POLL_SECONDS = 6.0
LOCK_TIMEOUT = "12s"


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


def test_access_path_drops_the_query_and_free_text():
    searched = safe_access_path(f"/public/offers?q={MARKER}&location=Beira")
    assert searched == "/public/offers"
    assert MARKER not in searched

    leaked = safe_access_path(f"/actors/{MARKER}@example.com/offers")
    assert MARKER not in leaked
    assert leaked == f"/actors/{{omitido}}/offers"

    offer_id = "11111111-1111-4111-8111-111111111111"
    actor_id = "22222222-2222-4222-8222-222222222222"
    kept = safe_access_path(f"/actors/{actor_id}/offers/{offer_id}/publish?token={MARKER}")
    assert kept == f"/actors/{actor_id}/offers/{offer_id}/publish"
    assert MARKER not in kept

    record_args = ("127.0.0.1:9", "GET", f"/public/offers?q={MARKER}", "1.1", 200)
    rendered = QuietAccessFormatter(
        fmt='%(client_addr)s - "%(request_line)s" %(status_code)s',
        use_colors=False,
    ).format(_record(record_args))
    assert MARKER not in rendered
    assert "GET /public/offers HTTP/1.1" in rendered
    assert "200" in rendered


def test_private_image_host_is_rejected(api, db_session):
    user = _user(db_session)
    actor_id = _actor(api, user)["id"]
    headers = _bearer(user)
    for image_ref in (
        "https://127.0.0.1/foto.jpg",
        "https://192.168.0.8/foto.jpg",
        "https://localhost/foto.jpg",
    ):
        rejected = api.post(
            f"/actors/{actor_id}/products",
            headers=headers,
            json={
                "name": "Mel",
                "description": "Mel de exemplo",
                "category": "mel",
                "image_ref": image_ref,
            },
        )
        assert rejected.status_code == 422
        assert image_ref not in rejected.text
        assert MARKER not in rejected.text

    accepted = api.post(
        f"/actors/{actor_id}/products",
        headers=headers,
        json={
            "name": "Mel",
            "description": "Mel de exemplo",
            "category": "mel",
            "image_ref": "https://example.com/mel.jpg",
        },
    )
    assert accepted.status_code == 201
    assert accepted.json()["image_ref"] == "https://example.com/mel.jpg"


def test_status_events_follow_the_effective_transitions(api, db_session):
    user = _user(db_session)
    actor_id = _actor(api, user)["id"]
    product_id = _product(api, user, actor_id)["id"]
    offer_id = _offer(api, user, actor_id, product_id)
    assert _events(db_session, offer_id) == []

    before = datetime.now(timezone.utc) - timedelta(seconds=2)
    _transition(api, user, actor_id, offer_id, "publish")
    _transition(api, user, actor_id, offer_id, "suspend")
    _transition(api, user, actor_id, offer_id, "publish")
    _transition(api, user, actor_id, offer_id, "withdraw")
    after = datetime.now(timezone.utc) + timedelta(seconds=2)

    db_session.expire_all()
    stored = db_session.get(Offer, uuid.UUID(offer_id))
    events = _events(db_session, offer_id)
    assert stored is not None
    assert stored.status is OfferStatus.WITHDRAWN
    assert [event.previous_status for event in events] == [
        OfferStatus.DRAFT,
        OfferStatus.PUBLISHED,
        OfferStatus.SUSPENDED,
        OfferStatus.PUBLISHED,
    ]
    assert [event.new_status for event in events] == [
        OfferStatus.PUBLISHED,
        OfferStatus.SUSPENDED,
        OfferStatus.PUBLISHED,
        OfferStatus.WITHDRAWN,
    ]
    assert events[-1].new_status is stored.status
    for event in events:
        assert event.performed_by_user_id == user.id
        assert event.offer_id == stored.id
        assert before <= event.occurred_at <= after
        assert event.previous_status is not event.new_status


def test_invalid_and_unauthorized_transitions_do_not_record(api, db_session):
    user = _user(db_session)
    actor_id = _actor(api, user)["id"]
    product_id = _product(api, user, actor_id)["id"]
    offer_id = _offer(api, user, actor_id, product_id)
    path = f"/actors/{actor_id}/offers/{offer_id}/publish"
    published = api.post(path, headers=_bearer(user))
    assert published.status_code == 200
    assert "performed_by" not in published.text
    assert "previous_status" not in published.text

    repeated = api.post(path, headers=_bearer(user))
    assert repeated.status_code == 422

    reader = _user(db_session)
    db_session.add(
        UserActorAccess(
            user_id=reader.id,
            actor_id=uuid.UUID(actor_id),
            access_level=AccessLevel.READ,
            status=AccessStatus.ACTIVE,
        )
    )
    db_session.flush()
    forbidden = api.post(path, headers=_bearer(reader))
    assert forbidden.status_code == 404

    db_session.expire_all()
    events = _events(db_session, offer_id)
    assert len(events) == 1
    assert events[0].previous_status is OfferStatus.DRAFT
    assert events[0].new_status is OfferStatus.PUBLISHED
    assert events[0].performed_by_user_id == user.id


def test_failed_publish_rolls_back_the_event(api, db_session, monkeypatch):
    user = _user(db_session)
    actor_id = _actor(api, user)["id"]
    product_id = _product(api, user, actor_id)["id"]
    offer_id = _offer(api, user, actor_id, product_id)

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
    stored = db_session.get(Offer, uuid.UUID(offer_id))
    assert stored is not None
    assert stored.status is OfferStatus.DRAFT
    assert _events(db_session, offer_id) == []


def test_concurrent_publishes_leave_one_compatible_event(migrated_database):
    user_id, actor_id, offer_id = _commit_draft()
    try:
        outcome = _overlap(
            lambda session: _publish(session, user_id, actor_id, offer_id),
            lambda session: _publish(session, user_id, actor_id, offer_id),
        )
        assert outcome["holder_error"] is None, outcome["holder_error"]
        assert isinstance(outcome["waiter_error"], OfferRejected)
        evidence = outcome["evidence"]
        assert evidence["blocked"] is True, evidence
        with Session(engine) as session:
            stored = session.get(Offer, offer_id)
            events = list(
                session.scalars(
                    select(OfferStatusEvent)
                    .where(OfferStatusEvent.offer_id == offer_id)
                    .order_by(OfferStatusEvent.occurred_at, OfferStatusEvent.id)
                )
            )
        assert stored is not None
        assert stored.status is OfferStatus.PUBLISHED
        assert len(events) == 1
        assert events[0].previous_status is OfferStatus.DRAFT
        assert events[0].new_status is stored.status
        assert events[0].performed_by_user_id == user_id
    finally:
        _wipe(user_id, actor_id)


def test_migration_preserves_the_offer_and_invents_no_event():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    name = f"kaivita_i82_{uuid.uuid4().hex[:12]}"
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
        _alembic(environment, "upgrade", "0007_coverage_and_image_rights")
        _plant_offer(target)
        _alembic(environment, "upgrade", "0008_offer_status_events")
        upgraded = _migration_state(target)
        assert upgraded["version"] == "0008_offer_status_events"
        assert upgraded["offer_status"] == "published"
        assert upgraded["events"] == 0
        assert upgraded["events_table"] is True

        _alembic(environment, "downgrade", "0007_coverage_and_image_rights")
        restored = _migration_state(target)
        assert restored["version"] == "0007_coverage_and_image_rights"
        assert restored["offer_status"] == "published"
        assert restored["events_table"] is False

        _alembic(environment, "upgrade", "0008_offer_status_events")
        again = _migration_state(target)
        assert again["version"] == "0008_offer_status_events"
        assert again["offer_status"] == "published"
        assert again["events"] == 0
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


def _record(args: tuple) -> "logging.LogRecord":
    import logging

    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=args,
        exc_info=None,
    )


def _user(session: Session) -> User:
    user = create_active_user(session, f"i82-{uuid.uuid4().hex[:12]}@example.com", PASSWORD)
    session.flush()
    return user


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_access_token(user.id)}"}


def _actor(api, user: User) -> dict:
    created = api.post(
        "/actors",
        headers=_bearer(user),
        json={
            "kind": "person",
            "display_name": "Produtor Exemplo",
            "general_location": "Inhambane",
            "roles": ["producer"],
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _product(api, user: User, actor_id: str) -> dict:
    created = api.post(
        f"/actors/{actor_id}/products",
        headers=_bearer(user),
        json={"name": "Mel", "description": "Mel de exemplo", "category": "mel"},
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


def _events(session: Session, offer_id: str) -> list[OfferStatusEvent]:
    session.expire_all()
    return list(
        session.scalars(
            select(OfferStatusEvent)
            .where(OfferStatusEvent.offer_id == uuid.UUID(offer_id))
            .order_by(OfferStatusEvent.occurred_at, OfferStatusEvent.id)
        )
    )


def _commit_draft() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with Session(engine) as session:
        user = create_active_user(session, f"i82-concorrencia-{uuid.uuid4().hex[:8]}@example.com", PASSWORD)
        session.flush()
        actor, _roles = create_represented_actor(
            session,
            user,
            ActorKind.PERSON,
            "Concorrência",
            "Beira",
            [RoleCode.PRODUCER],
        )
        product = create_product(session, actor, "Milho", "Milho de exemplo", "milho", None)
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
        session.commit()
        return user.id, actor.id, offer.id


def _publish(session: Session, user_id: uuid.UUID, actor_id: uuid.UUID, offer_id: uuid.UUID) -> str:
    actor = session.get(Actor, actor_id)
    offer = session.get(Offer, offer_id)
    assert actor is not None and offer is not None
    publish_offer(session, actor, offer, user_id)
    return offer.status.value


def _wipe(user_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    with Session(engine) as session:
        offer_ids = list(
            session.scalars(select(Offer.id).where(Offer.owner_actor_id == actor_id))
        )
        if offer_ids:
            session.execute(delete(OfferStatusEvent).where(OfferStatusEvent.offer_id.in_(offer_ids)))
            session.execute(delete(Offer).where(Offer.id.in_(offer_ids)))
        session.execute(text("DELETE FROM products WHERE owner_actor_id = :actor_id"), {"actor_id": actor_id})
        session.execute(text("DELETE FROM actor_roles WHERE actor_id = :actor_id"), {"actor_id": actor_id})
        session.execute(text("DELETE FROM user_actor_access WHERE actor_id = :actor_id"), {"actor_id": actor_id})
        session.execute(text("DELETE FROM actors WHERE id = :actor_id"), {"actor_id": actor_id})
        session.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
        session.commit()


def _overlap(holder, waiter) -> dict:
    ready = threading.Event()
    release = threading.Event()
    entered = threading.Event()
    box: dict = {"pids": {}}
    holder_thread = threading.Thread(target=_run_holder, args=(holder, ready, release, box))
    waiter_thread = threading.Thread(target=_run_waiter, args=(waiter, ready, entered, box))
    holder_thread.start()
    waiter_thread.start()
    evidence = {"blocked": False}
    try:
        if not ready.wait(POLL_SECONDS):
            raise TimeoutError("A primeira transacção não segurou o bloqueio.")
        if not entered.wait(POLL_SECONDS):
            raise TimeoutError("A segunda transacção não chegou a pedir o bloqueio.")
        evidence = _await_blocked(box["pids"]["waiter"], box["pids"]["holder"])
    finally:
        release.set()
        holder_thread.join(20)
        waiter_thread.join(20)
    return {
        "holder_error": box.get("holder_error"),
        "waiter_error": box.get("waiter_error"),
        "evidence": evidence,
    }


def _run_holder(holder, ready, release, box) -> None:
    session = Session(engine)
    try:
        box["pids"]["holder"] = int(session.scalar(text("SELECT pg_backend_pid()")))
        box["holder_result"] = holder(session)
        ready.set()
        if not release.wait(POLL_SECONDS + 2):
            raise TimeoutError("A primeira transacção não foi libertada.")
        session.commit()
    except Exception as exc:
        box["holder_error"] = exc
        session.rollback()
        ready.set()
    finally:
        session.close()


def _run_waiter(waiter, ready, entered, box) -> None:
    if not ready.wait(POLL_SECONDS + 2):
        box["waiter_error"] = TimeoutError("A primeira transacção não ficou pronta.")
        entered.set()
        return
    session = Session(engine)
    try:
        box["pids"]["waiter"] = int(session.scalar(text("SELECT pg_backend_pid()")))
        session.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        entered.set()
        box["waiter_result"] = waiter(session)
        session.commit()
    except Exception as exc:
        box["waiter_error"] = exc
        session.rollback()
    finally:
        entered.set()
        session.close()


def _await_blocked(waiter_pid: int, holder_pid: int) -> dict:
    deadline = time.monotonic() + POLL_SECONDS
    last: dict = {"blocked": False}
    while time.monotonic() < deadline:
        last = _blocking_view(waiter_pid, holder_pid)
        holder_has_offer = any(lock["relname"] == "offers" for lock in last["holder_locks"])
        if holder_pid in last["blockers"] and holder_has_offer and last["wait_event_type"] == "Lock":
            last["blocked"] = True
            return last
        time.sleep(0.05)
    last["blocked"] = False
    return last


def _blocking_view(waiter_pid: int, holder_pid: int) -> dict:
    with Session(engine) as session:
        activity = session.execute(
            text(
                """
                SELECT pg_blocking_pids(:waiter) AS blockers, wait_event_type
                FROM pg_stat_activity
                WHERE pid = :waiter
                """
            ),
            {"waiter": waiter_pid},
        ).one()
        held = session.execute(
            text(
                """
                SELECT pg_class.relname AS relname
                FROM pg_locks
                JOIN pg_class ON pg_class.oid = pg_locks.relation
                WHERE pg_locks.pid = :holder
                  AND pg_locks.granted
                  AND pg_class.relname = 'offers'
                """
            ),
            {"holder": holder_pid},
        ).mappings().all()
    blockers = activity.blockers
    if isinstance(blockers, str):
        inner = blockers.strip("{}")
        parsed = [] if inner == "" else [int(part) for part in inner.split(",")]
    else:
        parsed = [] if blockers is None else [int(part) for part in blockers]
    return {
        "blockers": parsed,
        "wait_event_type": activity.wait_event_type,
        "holder_locks": [{"relname": row["relname"]} for row in held],
    }


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


def _plant_offer(target: str) -> None:
    planted = create_engine(target)
    with planted.begin() as connection:
        actor_id = connection.execute(
            text(
                """
                INSERT INTO actors (kind, display_name, general_location, status)
                VALUES ('person', 'Produtor histórico', 'Inhambane', 'active')
                RETURNING id
                """
            )
        ).scalar_one()
        product_id = connection.execute(
            text(
                """
                INSERT INTO products (owner_actor_id, name, description, category, status)
                VALUES (:actor_id, 'Milho histórico', 'Descrição', 'milho', 'active')
                RETURNING id
                """
            ),
            {"actor_id": actor_id},
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO offers (
                    product_id, owner_actor_id, price, currency, quantity, unit,
                    availability, status
                )
                VALUES (
                    :product_id, :actor_id, 12.00, 'MZN', 2.00, 'kg',
                    'available', 'published'
                )
                """
            ),
            {"product_id": product_id, "actor_id": actor_id},
        )
    planted.dispose()


def _migration_state(target: str) -> dict:
    inspected = create_engine(target)
    with inspected.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        offer_status = connection.execute(text("SELECT status FROM offers")).scalar_one()
        events_table = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'offer_status_events'
                )
                """
            )
        ).scalar_one()
        events = 0
        if events_table:
            events = connection.execute(text("SELECT count(*) FROM offer_status_events")).scalar_one()
    inspected.dispose()
    return {
        "version": version,
        "offer_status": offer_status,
        "events_table": events_table,
        "events": events,
    }
