# Mini App backend boundary

This reference covers the bot and backend boundary for a Telegram Mini App.
Frontend SDK calls, UI, and browser-side state are out of scope for this
workflow; use another workflow for them. Treat every browser-supplied value,
including `user` and its `id`, as untrusted until the backend validates it.

## Launch flows

The launch URL identifies the application; it is not authentication. Choose the
flow by the launch surface rather than assuming every Mini App has the same
return path.

### Reply keyboard: `sendData` to the bot

A reply `KeyboardButton` can return a small result directly to the bot with
`Telegram.WebApp.sendData`. Telegram delivers it as `message.web_app_data`.
This flow does **not** make a signed `initData` or identity claim available for
the bot to trust: treat the returned data as untrusted action input and do not
use it to authenticate a backend session.

```python
from aiogram import F, Router
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo

reply_launch_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Choose dates", web_app=WebAppInfo(url=MINI_APP_URL))]
    ],
    resize_keyboard=True,
)

router = Router()


@router.message(F.web_app_data)
async def receive_reply_keyboard_result(message: Message) -> None:
    payload = message.web_app_data.data
    # Validate the expected action data before using it; it is not initData.
    await message.answer(f"Received {len(payload)} bytes of selection data.")
```

The frontend calls `Telegram.WebApp.sendData(payload)`. It is available only to
Mini Apps launched from a reply keyboard button, and Telegram closes the Mini
App after sending the service message.

### Inline, menu, main, or direct launch: validate `initData` at the backend

For an inline button, menu button, Main Mini App, or direct launch, the
frontend sends the raw `Telegram.WebApp.initData` to the backend over the
application's transport. The backend validates its HMAC and age, then parses
the validated identity and performs authorization for the requested operation.
Do not use `initDataUnsafe`, a frontend-provided user id, or a launch URL as a
substitute for this validation.

Use an inline button as the canonical signed-`initData`-compatible launch
surface:

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

signed_init_data_launch = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Open account", web_app=WebAppInfo(url=MINI_APP_URL))]
    ]
)
```

## Canonical `initData` validation

Implement one server-side validator with the documented shape
`validate_init_data(init_data: str, bot_token: str, max_age: timedelta) -> dict[str, str]`.
It must reject missing, malformed, tampered, or expired input. Do not accept a
client-provided user or id as a substitute for this check.
Missing, malformed, tampered, and expired requests are rejected before any
identity lookup or authorization.

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from urllib.parse import parse_qsl


def validate_init_data(
    init_data: str, bot_token: str, max_age: timedelta
) -> dict[str, str]:
    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("duplicate initData field")
        values[key] = value

    # Remove hash before constructing the sorted data_check_string.
    received_hash = values.pop("hash", None)
    if not received_hash:
        raise ValueError("missing hash")
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    expected_hash = hmac.new(
        secret, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("invalid hash")

    try:
        auth_date = datetime.fromtimestamp(int(values["auth_date"]), tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid auth_date") from exc
    now = datetime.now(timezone.utc)
    if auth_date > now or now - auth_date > max_age:
        raise ValueError("expired initData")
    return values
```

`parse_qsl` preserves the query-string interpretation used for the signed
data. Remove `hash`, sort the remaining `key=value` lines, and join them with
newlines to form `data_check_string`. Derive the secret with
`hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()`, then
compare the calculated and received hashes with `hmac.compare_digest`.

Select `max_age` as an application policy (a short `timedelta` appropriate to
the sensitivity of the action) rather than hard-coding a universal lifetime.
Reject future timestamps as well as stale `auth_date` values. The bot token is
a server secret: never send it to the Mini App or log it with the request.

## Identity and authorization follow validation

After cryptographic validation, parse the validated `user` JSON and use its
validated Telegram id only as an identity claim. Fetch the server-side account,
order, or entitlement, then authorize the requested operation there. Never
trust a client-supplied `user`, `id`, price, role, order, or entitlement merely
because it appears in the Mini App request. Bind an application session to the
validated identity and perform authorization for each protected action. This
identity-validation flow applies to the signed-`initData` launch surfaces above,
not to a reply-keyboard `sendData` result.

An identity field is untrusted before validation; server-side authorization is
required after validation and remains separate from authentication.

For the authoritative format and security notes, see Telegram's
[Mini Apps `initData` validation guide](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).
