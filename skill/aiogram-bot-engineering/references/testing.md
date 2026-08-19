# Testing an aiogram bot

Test the smallest boundary that can expose the behavior. The official aiogram
testing guidance uses direct handler calls for local behavior and
`Dispatcher.feed_raw_update()` for the routing pipeline. Neither requires long
polling, a real bot token, nor a Telegram network call.

## Handler and dispatcher tests

Handlers are ordinary async callables. For behavior inside a handler, call it
directly with an `AsyncMock` event and assert the observable result. Mock only
the Telegram-facing event or an external dependency; keep application services
and validation real where practical.

```python
from unittest.mock import AsyncMock

import pytest


async def echo_handler(message) -> None:
    await message.answer(message.text)


@pytest.mark.asyncio
async def test_echo_handler_answers_with_the_message_text() -> None:
    message = AsyncMock(text="hello")

    await echo_handler(message)

    message.answer.assert_awaited_once_with("hello")
```

Use `Dispatcher.feed_raw_update()` when the result depends on router selection,
filters, middleware, or dependency injection. Provide an in-memory raw update,
a test-only `Bot("42:TEST")`, and explicit dependencies in the call. Do not
start polling and do not let the test perform a Telegram API request.

```python
import time

import pytest
from aiogram import Bot, Dispatcher, F


@pytest.mark.asyncio
async def test_ping_reaches_the_filtered_handler() -> None:
    dispatcher = Dispatcher()

    @dispatcher.message(F.text == "ping")
    async def ping_handler() -> str:
        return "pong"

    result = await dispatcher.feed_raw_update(
        bot=Bot("42:TEST"),
        update={
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "text": "ping",
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 42, "is_bot": False, "first_name": "Test"},
            },
        },
    )

    assert result == "pong"
```

## State and hostile inputs

Exercise FSM transitions with the configured test storage: assert the initial
state, saved data, next state, reset, and behavior after storage recreation.
For concurrent updates to the same FSM key, use a barrier or controlled fake
repository to prove that the configured event isolation permits only one state
transition; also test independent users or chats can proceed concurrently.

Treat every callback payload as hostile. Test malformed `CallbackData` parsing
and a syntactically valid identifier for a missing object, wrong owner, and
wrong permission. The handler must load the object server-side and authorize
the actor; parsed fields only select the lookup.

For Mini Apps, test `initData` validation at its server boundary: missing,
malformed, signature-tampered, expired, and future-dated values must all be
rejected before any business action. A valid signature alone is insufficient:
test the Telegram user against the server-side ownership or permission policy.

Webhook tests must send an invalid or missing secret header to the request
handler and assert rejection before dispatcher invocation. Separately feed a
valid update through the normal path; do not test secret comparison by calling
an unrelated helper in isolation.

## Payments and test discipline

Feed the same successful-payment update twice and assert fulfillment happens
once, with the transaction identifier recorded atomically with the entitlement.
Also cover replayed events after a simulated restart and a payment whose stored
order, payer, currency, or amount no longer matches. Test the database
transaction outcome, not only a mocked `fulfill` call.

Keep test configuration separate from deployment secrets. Use fake tokens,
local storage, controlled clocks, and test-only dependencies. Unit and routing
tests must not have credentials capable of contacting Telegram or any payment
provider. For persistence, queue, and migration concerns, see
[production engineering](production-engineering.md).

See the [official aiogram testing documentation](https://docs.aiogram.dev/en/latest/dispatcher/testing.html)
for the current `feed_raw_update()` examples and API details.
