"""O commit fica visível antes da linha de estado HTTP."""

import asyncio

import pytest
from starlette.requests import Request

from app.db import SESSION_SCOPE_KEY, CommitBeforeResponse, get_session


def test_commit_precedes_the_status_line():
    events: list[str] = []

    class OpenSession:
        def in_transaction(self) -> bool:
            return True

        def commit(self) -> None:
            events.append("commit")

    async def application(scope, receive, send):
        scope[SESSION_SCOPE_KEY] = OpenSession()
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"{}", "more_body": False})

    async def observe(message):
        if message["type"] == "http.response.start":
            events.append("start")

    asyncio.run(CommitBeforeResponse(application)({"type": "http"}, _receive, observe))
    assert events == ["commit", "start"]


def test_a_request_without_a_session_still_responds():
    events: list[str] = []

    async def application(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}", "more_body": False})

    async def observe(message):
        if message["type"] == "http.response.start":
            events.append("start")

    asyncio.run(CommitBeforeResponse(application)({"type": "http"}, _receive, observe))
    assert events == ["start"]


def test_a_failed_commit_does_not_send_the_status_line():
    sent: list[str] = []

    class BrokenSession:
        def in_transaction(self) -> bool:
            return True

        def commit(self) -> None:
            raise RuntimeError("commit falhou")

    async def application(scope, receive, send):
        scope[SESSION_SCOPE_KEY] = BrokenSession()
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"{}", "more_body": False})

    async def observe(message):
        sent.append(message["type"])

    with pytest.raises(RuntimeError, match="commit falhou"):
        asyncio.run(
            CommitBeforeResponse(application)({"type": "http"}, _receive, observe)
        )
    assert sent == []


def test_the_generator_commits_once_when_the_response_was_not_confirmed(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr("app.db.Session", _session_type(events, open_transaction=True))
    generator = get_session(_request())

    next(generator)
    with pytest.raises(StopIteration):
        next(generator)

    assert events == ["open", "commit", "close"]


def test_the_generator_does_not_commit_again_after_the_middleware(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr("app.db.Session", _session_type(events, open_transaction=False))
    generator = get_session(_request())

    next(generator)
    with pytest.raises(StopIteration):
        next(generator)

    assert events == ["open", "close"]


def test_a_failed_request_rolls_back_and_closes_the_session(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr("app.db.Session", _session_type(events, open_transaction=True))
    request = _request()
    generator = get_session(request)
    next(generator)

    with pytest.raises(RuntimeError, match="falha do pedido"):
        generator.throw(RuntimeError("falha do pedido"))

    assert events == ["open", "rollback", "close"]
    assert SESSION_SCOPE_KEY not in request.scope


def _session_type(events: list[str], *, open_transaction: bool):
    class FakeSession:
        def __init__(self, bind) -> None:
            self._open = open_transaction
            events.append("open")

        def in_transaction(self) -> bool:
            return self._open

        def commit(self) -> None:
            events.append("commit")
            self._open = False

        def rollback(self) -> None:
            events.append("rollback")
            self._open = False

        def close(self) -> None:
            events.append("close")

    return FakeSession


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 9),
            "server": ("test", 80),
        }
    )


async def _receive():
    return {"type": "http.disconnect"}
