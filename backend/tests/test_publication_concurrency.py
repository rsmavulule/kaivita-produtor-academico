"""Disputa efectiva do bloqueio da linha do contacto.

As duas transacções ficam abertas ao mesmo tempo. A primeira segura o
bloqueio adquirido pela operação real. A segunda só é libertada depois
de ``pg_blocking_pids`` mostrar que está à espera dessa primeira.
Uma terceira sessão lê o estado final. O intervalo entre leituras não
substitui essa evidência.
"""

import os
import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.contacts import (
    ContactStatus,
    ContactVisibility,
    PublicContact,
    deactivate_contact,
    update_contact,
)
from app.db import engine
from app.identity import Actor
from app.offers import AvailabilityStatus, create_offer, publish_offer
from app.products import create_product
from app.public_offers import public_offer_contacts
from app.publication import (
    INACTIVE_DISCLOSURE,
    STALE_REVISION,
    AuthorizationConflict,
    PublicationAuthorization,
    RevocationReason,
    grant_authorization,
    revoke_authorization,
)
from test_publication import OTHER_PHONE, PHONE, _commit_contact, _commit_grant, _commit_revoke, _wipe

BACKEND_ROOT = Path(__file__).resolve().parents[1]
POLL_SECONDS = 6.0
LOCK_TIMEOUT = "12s"


@pytest.fixture(scope="module")
def migrated_database():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Defina RUN_DB_TESTS=1 para contactar um PostgreSQL real.")

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")


def test_grant_holds_the_lock_and_the_update_revokes_afterwards(migrated_database):
    user_id, actor_id, contact_id, offer_id = _plant("concessao-primeiro")
    try:
        outcome = _overlap(
            lambda session: _grant(session, actor_id, contact_id, user_id, 1),
            lambda session: _change(session, actor_id, contact_id, user_id),
        )
        _assert_blocked(outcome)
        assert outcome["waiter_error"] is None
        final = _snapshot(contact_id, offer_id)
        assert outcome["holder_result"]["created"] is True
        assert final["revision"] == 2
        assert final["value"] == OTHER_PHONE
        assert final["visibility"] is ContactVisibility.PRIVATE
        assert final["current"] == 0
        assert len(final["rows"]) == 1
        assert final["rows"][0]["reason"] is RevocationReason.CONTACT_CHANGED
        assert final["rows"][0]["revoked_by"] == user_id
        assert final["rows"][0]["revoked_at"] == outcome["waiter_result"]["revoked_at"]
        assert final["public"] == []
    finally:
        _wipe(user_id, actor_id)


def test_update_holds_the_lock_and_the_old_revision_is_refused(migrated_database):
    user_id, actor_id, contact_id, offer_id = _plant("alteracao-primeiro")
    try:
        outcome = _overlap(
            lambda session: _change(session, actor_id, contact_id, user_id),
            lambda session: _grant(session, actor_id, contact_id, user_id, 1),
        )
        _assert_blocked(outcome)
        assert isinstance(outcome["waiter_error"], AuthorizationConflict)
        assert outcome["waiter_error"].detail == STALE_REVISION
        final = _snapshot(contact_id, offer_id)
        assert final["revision"] == 2
        assert final["value"] == OTHER_PHONE
        assert final["visibility"] is ContactVisibility.PRIVATE
        assert final["rows"] == []
        assert final["current"] == 0
        assert final["public"] == []
    finally:
        _wipe(user_id, actor_id)


def test_grant_holds_the_lock_and_deactivation_revokes_afterwards(migrated_database):
    user_id, actor_id, contact_id, offer_id = _plant("desactiva-depois")
    try:
        outcome = _overlap(
            lambda session: _grant(session, actor_id, contact_id, user_id, 1),
            lambda session: _deactivate(session, actor_id, contact_id, user_id),
        )
        _assert_blocked(outcome)
        assert outcome["waiter_error"] is None
        final = _snapshot(contact_id, offer_id)
        assert final["status"] is ContactStatus.INACTIVE
        assert final["visibility"] is ContactVisibility.PRIVATE
        assert final["revision"] == 1
        assert final["current"] == 0
        assert len(final["rows"]) == 1
        assert final["rows"][0]["reason"] is RevocationReason.CONTACT_DEACTIVATED
        assert final["rows"][0]["revoked_by"] == user_id
        assert final["public"] == []
    finally:
        _wipe(user_id, actor_id)


def test_deactivation_holds_the_lock_and_the_grant_is_refused(migrated_database):
    user_id, actor_id, contact_id, offer_id = _plant("desactiva-primeiro")
    try:
        outcome = _overlap(
            lambda session: _deactivate(session, actor_id, contact_id, user_id),
            lambda session: _grant(session, actor_id, contact_id, user_id, 1),
        )
        _assert_blocked(outcome)
        assert isinstance(outcome["waiter_error"], AuthorizationConflict)
        assert outcome["waiter_error"].detail == INACTIVE_DISCLOSURE
        final = _snapshot(contact_id, offer_id)
        assert final["status"] is ContactStatus.INACTIVE
        assert final["visibility"] is ContactVisibility.PRIVATE
        assert final["rows"] == []
        assert final["current"] == 0
        assert final["public"] == []
    finally:
        _wipe(user_id, actor_id)


def test_revoke_holds_the_lock_and_the_update_keeps_that_revocation(migrated_database):
    user_id, actor_id, contact_id, offer_id = _plant("revoga-primeiro")
    try:
        authorization_id = _commit_grant(user_id, actor_id, contact_id)
        outcome = _overlap(
            lambda session: _revoke(session, actor_id, contact_id, authorization_id, user_id),
            lambda session: _change(session, actor_id, contact_id, user_id),
        )
        _assert_blocked(outcome)
        assert outcome["waiter_error"] is None
        final = _snapshot(contact_id, offer_id)
        assert final["revision"] == 2
        assert final["visibility"] is ContactVisibility.PRIVATE
        assert final["current"] == 0
        assert len(final["rows"]) == 1
        row = final["rows"][0]
        assert row["id"] == authorization_id
        assert row["reason"] is RevocationReason.MANUAL
        assert row["revoked_by"] == user_id
        assert row["revoked_at"] == outcome["holder_result"]["revoked_at"]
        assert final["public"] == []
    finally:
        _wipe(user_id, actor_id)


def test_update_holds_the_lock_and_the_later_revoke_does_not_rewrite_it(migrated_database):
    user_id, actor_id, contact_id, offer_id = _plant("altera-revoga")
    try:
        authorization_id = _commit_grant(user_id, actor_id, contact_id)
        outcome = _overlap(
            lambda session: _change(session, actor_id, contact_id, user_id),
            lambda session: _revoke(session, actor_id, contact_id, authorization_id, user_id),
        )
        _assert_blocked(outcome)
        assert outcome["waiter_error"] is None
        final = _snapshot(contact_id, offer_id)
        assert final["revision"] == 2
        assert final["visibility"] is ContactVisibility.PRIVATE
        assert final["current"] == 0
        assert len(final["rows"]) == 1
        row = final["rows"][0]
        assert row["reason"] is RevocationReason.CONTACT_CHANGED
        assert row["revoked_by"] == user_id
        assert row["revoked_at"] == outcome["holder_result"]["revoked_at"]
        assert final["public"] == []
    finally:
        _wipe(user_id, actor_id)


def test_repeated_grant_holds_the_lock_and_does_not_create_another_row(migrated_database):
    user_id, actor_id, contact_id, offer_id = _plant("repetida-primeiro")
    try:
        authorization_id = _commit_grant(user_id, actor_id, contact_id)
        before = _snapshot(contact_id, offer_id)
        outcome = _overlap(
            lambda session: _grant(session, actor_id, contact_id, user_id, 1),
            lambda session: _revoke(session, actor_id, contact_id, authorization_id, user_id),
        )
        _assert_blocked(outcome)
        assert outcome["waiter_error"] is None
        assert outcome["holder_result"]["created"] is False
        assert outcome["holder_result"]["id"] == authorization_id
        final = _snapshot(contact_id, offer_id)
        assert len(final["rows"]) == 1
        assert final["current"] == 0
        assert final["rows"][0]["id"] == authorization_id
        assert final["rows"][0]["granted_at"] == before["rows"][0]["granted_at"]
        assert final["rows"][0]["granted_by"] == user_id
        assert final["rows"][0]["reason"] is RevocationReason.MANUAL
        assert final["visibility"] is ContactVisibility.PRIVATE
        assert final["public"] == []
    finally:
        _wipe(user_id, actor_id)


def test_revoke_holds_the_lock_and_the_following_grant_is_a_new_row(migrated_database):
    user_id, actor_id, contact_id, offer_id = _plant("nova-depois")
    try:
        authorization_id = _commit_grant(user_id, actor_id, contact_id)
        outcome = _overlap(
            lambda session: _revoke(session, actor_id, contact_id, authorization_id, user_id),
            lambda session: _grant(session, actor_id, contact_id, user_id, 1),
        )
        _assert_blocked(outcome)
        assert outcome["waiter_error"] is None
        assert outcome["waiter_result"]["created"] is True
        assert outcome["waiter_result"]["id"] != authorization_id
        final = _snapshot(contact_id, offer_id)
        assert len(final["rows"]) == 2
        assert final["current"] == 1
        original = next(row for row in final["rows"] if row["id"] == authorization_id)
        current = next(row for row in final["rows"] if row["revoked_at"] is None)
        assert original["reason"] is RevocationReason.MANUAL
        assert original["revoked_at"] == outcome["holder_result"]["revoked_at"]
        assert original["revoked_by"] == user_id
        assert current["id"] == outcome["waiter_result"]["id"]
        assert current["granted_by"] == user_id
        assert final["visibility"] is ContactVisibility.PUBLIC
        assert final["public"] == [("phone", PHONE)]
    finally:
        _wipe(user_id, actor_id)


def test_revoking_the_old_row_does_not_hide_the_later_grant(migrated_database):
    user_id, actor_id, contact_id, offer_id = _plant("antiga-nao-mexe")
    try:
        original_id = _commit_grant(user_id, actor_id, contact_id)
        _commit_revoke(user_id, actor_id, contact_id, original_id)
        later_id = _commit_grant(user_id, actor_id, contact_id)
        before = _snapshot(contact_id, offer_id)
        original = next(row for row in before["rows"] if row["id"] == original_id)
        outcome = _overlap(
            lambda session: _revoke(session, actor_id, contact_id, original_id, user_id),
            lambda session: _grant(session, actor_id, contact_id, user_id, 1),
        )
        _assert_blocked(outcome)
        assert outcome["waiter_error"] is None
        assert outcome["holder_result"]["revoked_at"] == original["revoked_at"]
        assert outcome["holder_result"]["reason"] is RevocationReason.MANUAL
        assert outcome["waiter_result"]["created"] is False
        assert outcome["waiter_result"]["id"] == later_id
        final = _snapshot(contact_id, offer_id)
        assert final["current"] == 1
        kept = next(row for row in final["rows"] if row["id"] == original_id)
        current = next(row for row in final["rows"] if row["id"] == later_id)
        assert kept["revoked_at"] == original["revoked_at"]
        assert kept["revoked_by"] == original["revoked_by"]
        assert kept["reason"] == original["reason"]
        assert current["revoked_at"] is None
        assert final["visibility"] is ContactVisibility.PUBLIC
        assert final["public"] == [("phone", PHONE)]
    finally:
        _wipe(user_id, actor_id)


def _plant(label: str):
    stamp = uuid.uuid4().hex[:8]
    user_id, actor_id, contact_id = _commit_contact(f"i72-{label}-{stamp}@example.com")
    try:
        with Session(engine) as session:
            actor = session.get(Actor, actor_id)
            product = create_product(
                session,
                actor,
                f"Mel {stamp}",
                "Produto sintetico de concorrencia",
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
            return user_id, actor_id, contact_id, offer.id
    except Exception:
        _wipe(user_id, actor_id)
        raise


def _grant(session, actor_id, contact_id, user_id, revision: int) -> dict:
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
    return {"created": outcome.created, "id": outcome.authorization.id}


def _change(session, actor_id, contact_id, user_id) -> dict:
    actor = session.get(Actor, actor_id)
    contact = update_contact(
        session,
        actor,
        contact_id,
        {"value": OTHER_PHONE},
        operator_id=user_id,
    )
    revoked = session.scalar(
        select(PublicationAuthorization).where(
            PublicationAuthorization.contact_id == contact_id,
            PublicationAuthorization.revoked_at.is_not(None),
        )
    )
    return {
        "revision": contact.revision,
        "revoked_at": None if revoked is None else revoked.revoked_at,
    }


def _deactivate(session, actor_id, contact_id, user_id) -> dict:
    actor = session.get(Actor, actor_id)
    contact = deactivate_contact(session, actor, contact_id, operator_id=user_id)
    return {"status": contact.status}


def _revoke(session, actor_id, contact_id, authorization_id, user_id) -> dict:
    actor = session.get(Actor, actor_id)
    authorization = revoke_authorization(
        session,
        actor,
        contact_id,
        authorization_id,
        user_id,
    )
    return {
        "revoked_at": authorization.revoked_at,
        "reason": authorization.revocation_reason,
    }


def _overlap(holder, waiter) -> dict:
    ready = threading.Event()
    release = threading.Event()
    entered = threading.Event()
    box: dict = {"pids": {}}
    holder_thread = threading.Thread(
        target=_run_holder,
        args=(holder, ready, release, box),
        name="holder",
    )
    waiter_thread = threading.Thread(
        target=_run_waiter,
        args=(waiter, ready, entered, box),
        name="waiter",
    )
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
    assert not holder_thread.is_alive()
    assert not waiter_thread.is_alive()
    return {
        "holder_result": box.get("holder_result"),
        "waiter_result": box.get("waiter_result"),
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
        holder_has_contact = any(
            lock["relname"] == "public_contacts" for lock in last["holder_locks"]
        )
        if holder_pid in last["blockers"] and holder_has_contact and last["wait_event_type"] == "Lock":
            last["blocked"] = True
            last["holder_pid"] = holder_pid
            return last
        time.sleep(0.05)
    last["blocked"] = False
    last["holder_pid"] = holder_pid
    return last


def _blocking_view(waiter_pid: int, holder_pid: int) -> dict:
    with Session(engine) as session:
        activity = session.execute(
            text(
                """
                SELECT pg_blocking_pids(:waiter) AS blockers,
                       wait_event_type,
                       wait_event,
                       state
                FROM pg_stat_activity
                WHERE pid = :waiter
                """
            ),
            {"waiter": waiter_pid},
        ).one()
        waiting = session.execute(
            text(
                """
                SELECT locktype, mode
                FROM pg_locks
                WHERE pid = :waiter
                  AND NOT granted
                """
            ),
            {"waiter": waiter_pid},
        ).mappings().all()
        held = session.execute(
            text(
                """
                SELECT pg_class.relname AS relname,
                       pg_locks.mode AS mode,
                       pg_locks.locktype AS locktype
                FROM pg_locks
                JOIN pg_class ON pg_class.oid = pg_locks.relation
                WHERE pg_locks.pid = :holder
                  AND pg_locks.granted
                  AND pg_class.relname = 'public_contacts'
                """
            ),
            {"holder": holder_pid},
        ).mappings().all()
    return {
        "blockers": _pids(activity.blockers),
        "wait_event_type": activity.wait_event_type,
        "wait_event": activity.wait_event,
        "state": activity.state,
        "waiter_locks": [(row["locktype"], row["mode"]) for row in waiting],
        "holder_locks": [
            {"relname": row["relname"], "mode": row["mode"], "locktype": row["locktype"]}
            for row in held
        ],
    }


def _pids(value) -> list[int]:
    if value is None:
        return []
    if isinstance(value, str):
        inner = value.strip("{}")
        if inner == "":
            return []
        return [int(part) for part in inner.split(",")]
    return [int(part) for part in value]


def _assert_blocked(outcome: dict) -> None:
    assert outcome["holder_error"] is None, outcome["holder_error"]
    evidence = outcome["evidence"]
    assert evidence["blocked"] is True, evidence
    assert evidence["wait_event_type"] == "Lock"
    assert evidence["wait_event"] == "transactionid"
    assert evidence["state"] == "active"
    assert ("transactionid", "ShareLock") in evidence["waiter_locks"]
    assert any(
        lock["relname"] == "public_contacts"
        and lock["mode"] == "RowShareLock"
        and lock["locktype"] == "relation"
        for lock in evidence["holder_locks"]
    )


def _snapshot(contact_id, offer_id) -> dict:
    with Session(engine) as session:
        contact = session.get(PublicContact, contact_id)
        rows = list(
            session.scalars(
                select(PublicationAuthorization)
                .where(PublicationAuthorization.contact_id == contact_id)
                .order_by(
                    PublicationAuthorization.granted_at,
                    PublicationAuthorization.id,
                )
            )
        )
        disclosed = public_offer_contacts(session, offer_id)
        assert contact is not None
        return {
            "value": contact.value,
            "channel": contact.channel,
            "revision": contact.revision,
            "status": contact.status,
            "visibility": contact.visibility,
            "rows": [
                {
                    "id": row.id,
                    "revision": row.contact_revision,
                    "channel": row.channel,
                    "granted_at": row.granted_at,
                    "granted_by": row.granted_by_user_id,
                    "revoked_at": row.revoked_at,
                    "revoked_by": row.revoked_by_user_id,
                    "reason": row.revocation_reason,
                }
                for row in rows
            ],
            "current": sum(row.revoked_at is None for row in rows),
            "public": (
                None
                if disclosed is None
                else [(item.channel, item.value) for item in disclosed]
            ),
        }
