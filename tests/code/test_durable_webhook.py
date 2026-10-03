from __future__ import annotations

import asyncio
from contextlib import suppress
import importlib.util
import json
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from aiogram import Bot, Dispatcher
import pytest
import pytest_asyncio


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = (
    REPOSITORY_ROOT
    / "skill"
    / "aiogram-bot-engineering"
    / "examples"
    / "durable_webhook.py"
)
SECRET_TOKEN = "test_secret-token_123"
PAYLOAD_MARKER = "sensitive-webhook-payload"
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


def make_payload(update_id: int = 1, *, text: str = PAYLOAD_MARKER) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 1_791_020_800,
            "chat": {"id": 42, "type": "private"},
            "from": {"id": 7, "is_bot": False, "first_name": "Test"},
            "text": text,
        },
    }


def make_http_request(
    *,
    payload: object | None = None,
    headers: dict[str, str] | None = None,
) -> SimpleNamespace:
    request_headers = {SECRET_HEADER: SECRET_TOKEN} if headers is None else headers
    return SimpleNamespace(
        headers=request_headers,
        json=AsyncMock(return_value=make_payload() if payload is None else payload),
    )


def import_durable_webhook(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module_name = "aiogram_bot_engineering_durable_webhook_example"
    spec = importlib.util.spec_from_file_location(module_name, EXAMPLE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


class FakeInbox:
    def __init__(self) -> None:
        self.records: dict[tuple[int, int], dict[str, Any]] = {}
        self.calls: list[tuple[int, int, dict[str, Any]]] = []
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.block = False
        self.error: Exception | None = None
        self.active_accepts = 0

    async def accept(
        self,
        *,
        bot_id: int,
        update_id: int,
        payload: dict[str, Any],
    ) -> None:
        self.calls.append((bot_id, update_id, payload.copy()))
        self.active_accepts += 1
        self.entered.set()
        try:
            if self.error is not None:
                raise self.error
            if self.block:
                await self.release.wait()
            self.records.setdefault((bot_id, update_id), payload.copy())
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        finally:
            self.active_accepts -= 1


@pytest.fixture
def inbox() -> FakeInbox:
    return FakeInbox()


@pytest_asyncio.fixture
async def bot_and_dispatcher():
    bot = Bot("42:TEST")
    dispatcher = Dispatcher()
    try:
        yield bot, dispatcher
    finally:
        await bot.session.close()
        await dispatcher.storage.close()


@pytest.fixture
def example(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    return import_durable_webhook(monkeypatch)


@pytest.fixture
def handler_factory(example: ModuleType, bot_and_dispatcher, inbox: FakeInbox):
    bot, dispatcher = bot_and_dispatcher

    def build_handler(
        *,
        acceptance_timeout: float = 10.0,
        secret_token: str = SECRET_TOKEN,
        handler_inbox: FakeInbox | None = None,
        handler_bot: Bot | None = None,
    ):
        return example.DurableWebhookRequestHandler(
            dispatcher=dispatcher,
            bot=bot if handler_bot is None else handler_bot,
            inbox=inbox if handler_inbox is None else handler_inbox,
            secret_token=secret_token,
            acceptance_timeout=acceptance_timeout,
        )

    return build_handler


@pytest.fixture
def handler(handler_factory):
    return handler_factory()


@pytest.fixture
def http_request() -> SimpleNamespace:
    return make_http_request()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {SECRET_HEADER: "wrong-ascii-secret"},
        {SECRET_HEADER: "é"},
        {SECRET_HEADER: "\udce9"},
        {SECRET_HEADER: ""},
        {SECRET_HEADER: "has spaces"},
        {SECRET_HEADER: "x" * 257},
    ],
    ids=["missing", "wrong", "non-ascii", "surrogate", "empty", "spaces", "too-long"],
)
async def test_invalid_secret_rejected_before_parsing(
    handler,
    http_request: SimpleNamespace,
    inbox: FakeInbox,
    headers: dict[str, str],
) -> None:
    http_request.headers = headers

    response = await handler.handle(http_request)

    assert response.status == 401
    http_request.json.assert_not_awaited()
    assert inbox.calls == []


@pytest.mark.asyncio
async def test_success_waits_for_committed_inbox(
    handler_factory,
    http_request: SimpleNamespace,
    inbox: FakeInbox,
) -> None:
    inbox.block = True
    handler = handler_factory()
    response_task: asyncio.Task | None = None
    try:
        response_task = asyncio.create_task(handler.handle(http_request))
        await asyncio.wait_for(inbox.entered.wait(), timeout=1.0)
        assert not response_task.done()
        assert inbox.records == {}

        inbox.release.set()
        response = await asyncio.wait_for(response_task, timeout=1.0)

        assert response.status == 200
        assert inbox.records[(42, 1)] == make_payload()
    finally:
        if response_task is not None:
            if not response_task.done():
                response_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await response_task


@pytest.mark.asyncio
async def test_inbox_failure_is_not_acknowledged(
    handler,
    http_request: SimpleNamespace,
    inbox: FakeInbox,
    example: ModuleType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    inbox.error = RuntimeError(f"{SECRET_TOKEN} 42:TEST {PAYLOAD_MARKER}")
    caplog.set_level(logging.ERROR, logger=example.__name__)

    response = await handler.handle(http_request)

    assert response.status == 503
    assert inbox.records == {}
    assert SECRET_TOKEN not in caplog.text
    assert "42:TEST" not in caplog.text
    assert PAYLOAD_MARKER not in caplog.text


@pytest.mark.asyncio
async def test_acceptance_timeout_is_not_acknowledged(handler_factory, http_request, inbox) -> None:
    inbox.block = True
    handler = handler_factory(acceptance_timeout=0.01)

    response = await handler.handle(http_request)

    assert response.status == 503
    await asyncio.wait_for(inbox.cancelled.wait(), timeout=1.0)
    assert inbox.records == {}
    assert inbox.active_accepts == 0


@pytest.mark.asyncio
async def test_request_cancellation_propagates(handler, http_request, inbox) -> None:
    inbox.block = True
    request_task = asyncio.create_task(handler.handle(http_request))
    try:
        await asyncio.wait_for(inbox.entered.wait(), timeout=1.0)
        request_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request_task

        await asyncio.wait_for(inbox.cancelled.wait(), timeout=1.0)
        assert inbox.records == {}
        assert inbox.active_accepts == 0
    finally:
        if not request_task.done():
            request_task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await request_task


@pytest.mark.asyncio
async def test_duplicate_update_uses_same_inbox_key(handler, inbox) -> None:
    first = await handler.handle(make_http_request())
    second = await handler.handle(make_http_request())

    assert first.status == second.status == 200
    assert set(inbox.records) == {(42, 1)}
    assert [call[:2] for call in inbox.calls] == [(42, 1), (42, 1)]


@pytest.mark.asyncio
async def test_update_ids_are_scoped_by_bot(
    handler_factory,
    inbox: FakeInbox,
    bot_and_dispatcher,
) -> None:
    bot_43 = Bot("43:TEST")
    handler_42 = handler_factory()
    handler_43 = handler_factory(handler_bot=bot_43)
    payload = make_payload(update_id=7)
    try:
        response_42 = await handler_42.handle(make_http_request(payload=payload))
        response_43 = await handler_43.handle(make_http_request(payload=payload))
    finally:
        await bot_43.session.close()

    assert response_42.status == response_43.status == 200
    assert set(inbox.records) == {(42, 7), (43, 7)}
    assert inbox.records[(42, 7)] == inbox.records[(43, 7)] == payload


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_input", ["json", "unicode", "missing-update-id", "non-object"])
async def test_invalid_json_or_update_is_rejected(
    handler,
    http_request: SimpleNamespace,
    inbox: FakeInbox,
    invalid_input: str,
) -> None:
    if invalid_input == "json":
        http_request.json.side_effect = json.JSONDecodeError("bad json", "{", 0)
    elif invalid_input == "unicode":
        http_request.json.side_effect = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")
    elif invalid_input == "missing-update-id":
        http_request.json.return_value = {"message": {}}
    else:
        http_request.json.return_value = []

    response = await handler.handle(http_request)

    assert response.status == 400
    assert inbox.calls == []


@pytest.mark.asyncio
async def test_http_path_never_dispatches(
    handler,
    http_request: SimpleNamespace,
    bot_and_dispatcher,
) -> None:
    _, dispatcher = bot_and_dispatcher
    dispatcher.feed_webhook_update = AsyncMock()
    dispatcher.feed_update = AsyncMock()
    dispatcher.feed_raw_update = AsyncMock()

    response = await handler.handle(http_request)

    assert response.status == 200
    dispatcher.feed_webhook_update.assert_not_awaited()
    dispatcher.feed_update.assert_not_awaited()
    dispatcher.feed_raw_update.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
async def test_acceptance_timeout_configuration_rejects_nonpositive_or_nonfinite(
    handler_factory,
    timeout: float,
) -> None:
    with pytest.raises(ValueError, match="acceptance_timeout"):
        handler_factory(acceptance_timeout=timeout)


def test_acceptance_timeout_configuration_accepts_positive_finite_default(handler) -> None:
    assert handler.acceptance_timeout == 10.0
    assert handler.handle_in_background is False


@pytest.mark.parametrize("secret_token", ["", "has spaces", "ё", "x" * 257])
def test_constructor_rejects_invalid_secret_token(handler_factory, secret_token: str) -> None:
    with pytest.raises(ValueError, match="secret_token"):
        handler_factory(secret_token=secret_token)
