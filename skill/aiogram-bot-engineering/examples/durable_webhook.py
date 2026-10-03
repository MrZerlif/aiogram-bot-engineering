"""Durable webhook acceptance boundary for aiogram 3.30.0."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from typing import Any, Protocol

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from pydantic import ValidationError


logger = logging.getLogger(__name__)


class DurableInbox(Protocol):
    """Project adapter for durable webhook acceptance.

    ``accept`` returns only after an atomic durable commit, or after confirming
    that a committed record already exists for the unique ``(bot_id,
    update_id)`` key. A duplicate may succeed only for an already committed
    record. Cancellation must be cooperative. If the commit outcome is
    ambiguous, an idempotent retry with the same key must be safe. An
    in-memory implementation does not satisfy this production contract.
    """

    async def accept(
        self,
        *,
        bot_id: int,
        update_id: int,
        payload: dict[str, Any],
    ) -> None:
        """Durably record one raw Telegram update before returning."""


class DurableWebhookRequestHandler(SimpleRequestHandler):
    """Acknowledge only after the project-owned durable inbox accepts an update.

    This overrides ``SimpleRequestHandler._handle_request``, a private
    extension point verified against aiogram 3.30.0. The inherited ``handle``
    method retains request routing and compares secrets after header validation.
    """

    def __init__(
        self,
        dispatcher: Dispatcher,
        bot: Bot,
        *,
        inbox: DurableInbox,
        secret_token: str,
        acceptance_timeout: float = 10.0,
    ) -> None:
        if not math.isfinite(acceptance_timeout) or acceptance_timeout <= 0:
            raise ValueError("acceptance_timeout must be positive and finite")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret_token):
            raise ValueError("secret_token must contain 1-256 URL-safe ASCII characters")

        self.inbox = inbox
        self.acceptance_timeout = acceptance_timeout
        super().__init__(
            dispatcher=dispatcher,
            bot=bot,
            handle_in_background=False,
            secret_token=secret_token,
        )

    def verify_secret(self, telegram_secret_token: str, bot: Bot) -> bool:
        """Reject malformed headers before the constant-time secret comparison."""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", telegram_secret_token):
            return False
        return super().verify_secret(telegram_secret_token, bot)

    async def _handle_request(self, bot: Bot, request: web.Request) -> web.Response:
        try:
            raw_payload = await request.json(loads=bot.session.json_loads)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return web.Response(status=400)

        if not isinstance(raw_payload, dict):
            return web.Response(status=400)

        try:
            update = Update.model_validate(raw_payload, context={"bot": bot})
        except ValidationError:
            return web.Response(status=400)

        bot_id = bot.id
        update_id = update.update_id
        try:
            await asyncio.wait_for(
                self.inbox.accept(
                    bot_id=bot_id,
                    update_id=update_id,
                    payload=raw_payload,
                ),
                timeout=self.acceptance_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Durable webhook acceptance timed out for bot_id=%s update_id=%s",
                bot_id,
                update_id,
            )
            return web.Response(status=503)
        except Exception as error:
            logger.error(
                "Durable webhook acceptance failed for bot_id=%s update_id=%s error_type=%s",
                bot_id,
                update_id,
                type(error).__name__,
            )
            return web.Response(status=503)

        return web.Response(status=200)
