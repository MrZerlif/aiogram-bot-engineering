# Deploying an aiogram bot

Use one update-delivery mode per bot deployment. Keep `BOT_TOKEN` and the
webhook `SECRET_TOKEN` and `WEBHOOK_URL` in environment variables or a secret
manager; never place secret values in source control.

## Polling

Polling is appropriate for local development and straightforward operations.
Run `Dispatcher.start_polling` under a process supervisor, pass the bot to it,
and use `allowed_updates` based on the update types the dispatcher actually
handles. Before enabling polling, remove any configured webhook for that bot.

```python
from aiogram import Bot, Dispatcher


async def run_polling(
    bot: Bot,
    dispatcher: Dispatcher,
    *,
    max_concurrent_updates: int,
) -> None:
    if max_concurrent_updates <= 0:
        raise ValueError("max_concurrent_updates must be positive")
    await bot.delete_webhook(drop_pending_updates=False)
    await dispatcher.start_polling(
        bot,
        allowed_updates=dispatcher.resolve_used_update_types(),
        handle_as_tasks=True,
        tasks_concurrency_limit=max_concurrent_updates,
    )
```

Size the positive limit to the database pool, queue, outbound limits, and
handler cost. With `handle_as_tasks=True`, `tasks_concurrency_limit` is per bot;
multiple bots multiply the possible work. A deliberately sequential deployment
may instead set `handle_as_tasks=False`. A concurrency cap prevents task growth
but does not itself drain update tasks. Own the shutdown policy: stop intake,
track and drain bounded in-flight work or make cancellation safe, then close
database pools and bot sessions.

## Webhook

Webhook delivery requires a stable HTTPS endpoint. Use aiogram's official
aiohttp integration instead of making raw Telegram HTTP requests. Register the
webhook with `allowed_updates` and the same `secret_token` that the request
handler validates. The `secret_token` is a separate secret from the bot token.

Generate that webhook secret once in a trusted server-side administration
context with Python's CSPRNG, for example `secrets.token_urlsafe(32)`. Its
43-character URL-safe output has 256 bits of entropy and fits Telegram's
`secret_token` character set (`A-Z`, `a-z`, `0-9`, `_`, `-`) and 1–256 character
limit. Store the generated value in an environment variable or secret manager;
never generate a replacement on every process start. Blank, placeholder, or
weak values must be rejected during configuration loading. This startup check
does not authenticate requests: `SimpleRequestHandler` remains the per-request
secret-header verifier.

```python
import os
import re
from urllib.parse import urlsplit

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from durable_webhook import DurableInbox, DurableWebhookRequestHandler

WEBHOOK_PATH = "/telegram/webhook"

def load_webhook_url() -> str:
    url = os.environ.get("WEBHOOK_URL", "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("WEBHOOK_URL must be an absolute HTTPS URL")
    return url


def load_webhook_secret() -> str:
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if (
        len(secret) < 43
        or not re.fullmatch(r"[A-Za-z0-9_-]{43,256}", secret)
        or secret.casefold() in {"change-me", "example-secret", "placeholder"}
    ):
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET is blank, placeholder, or weak")
    return secret


WEBHOOK_URL = load_webhook_url()
SECRET_TOKEN = load_webhook_secret()


async def start_webhook(
    bot: Bot,
    dispatcher: Dispatcher,
    inbox: DurableInbox,
) -> web.Application:
    app = web.Application()
    handler = DurableWebhookRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        inbox=inbox,
        secret_token=SECRET_TOKEN,
    )
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dispatcher, bot=bot)

    await bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=SECRET_TOKEN,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )
    return app
```

`SimpleRequestHandler` and `setup_application` connect aiogram lifecycle hooks
to aiohttp so startup and shutdown are coordinated. Configure the web server to
stop accepting new work, allow in-flight work to finish, and close application
resources for a graceful shutdown.

When using the ordinary handler directly, disable its immediate background
acknowledgement:

```python
SimpleRequestHandler(
    dispatcher=dispatcher,
    bot=bot,
    handle_in_background=False,
    secret_token=SECRET_TOKEN,
)
```

This setting only makes aiohttp await `feed_webhook_update`. Aiogram's webhook
dispatcher waits about 55 seconds and then may return while unfinished work
continues in memory. The flag alone does not create durable acceptance.

The copied `examples/durable_webhook.py` module must be importable as
`durable_webhook`. Its `DurableWebhookRequestHandler` inherits the
`SimpleRequestHandler` secret-header verifier, request routing, and shutdown
hook, while overriding the aiogram 3.30.0 private `_handle_request` extension
point to validate the update and await `inbox.accept`. The project supplies the
durable inbox adapter and a worker; this example does not contain a fake or
in-memory production adapter.

The adapter must commit atomically under the unique `(bot_id, update_id)` key
and return only after that record is committed or a committed duplicate is
confirmed. A worker reads committed rows, calls
`dispatcher.feed_raw_update(bot, update=payload)`, marks each row processed
after success, and retries processing failures under the application's durable
retry policy. Do not dispatch business work in the HTTP handler.

The handler returns `200` only after inbox acceptance. A timeout or storage
failure returns `503`; cancellation propagates so Telegram can retry. A timeout
can have an ambiguous commit outcome, so a redelivery must use the same key and
the adapter must make that retry idempotent. Worker retries and idempotency for
external effects are still required; this example does not provide exactly-once
business effects.

Reject a missing or invalid secret header before parsing or dispatching the
update, and never return a successful acknowledgement for a rejected request.
Return success only after the authenticated update has been accepted by the
chosen processing boundary; if business work continues asynchronously, make
that boundary durable before acknowledging when loss is unacceptable. Log safe
request and correlation metadata, but never log `BOT_TOKEN`, the webhook secret
or its header value, or an unredacted update body.

Do not run polling alongside this webhook: the modes are mutually exclusive.
Expose liveness separately from readiness: liveness answers whether the process
needs restarting, while readiness stays false until required dependencies (for
example, database, FSM storage, and an essential queue) are configured and
usable. Do not report ready merely because the HTTP server has started. Inspect
`await bot.get_webhook_info()` (the `Bot.get_webhook_info` API) when diagnosing
webhook URL, pending updates, or the last delivery error. Treat those results
as diagnostics, not a substitute for application logs and alerting.
