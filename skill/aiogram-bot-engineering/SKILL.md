---
name: aiogram-bot-engineering
description: Use when designing, implementing, reviewing, or deploying Python aiogram Telegram bots with dialogs, Rich Messages, Mini Apps, payments, or webhooks.
---

# Aiogram Bot Engineering

Start by inspecting the existing project, dependency versions, and user constraints. Preserve a coherent architecture unless restructuring is requested. Classify the request, then load only the smallest relevant set below; combine references only when the request genuinely crosses boundaries.

Compatibility baseline: Python 3.10+, aiogram 3.30.0, aiogram-dialog 2.6.0, and Telegram Bot API 10.2. These are dated compatibility targets, not a claim of latest versions. For another version or a latest-version request, verify the official documentation before writing version-sensitive code.

| Request | Read |
| --- | --- |
| Routers, Dispatcher, configuration, middleware, FSM, storage, or polling decisions | [architecture](references/architecture.md) |
| Multi-window menus, wizards, dynamic lists, pagination, styled buttons, or custom emoji | [dialogs and UI](references/dialogs-and-ui.md) |
| Structured native Rich Messages, media bindings, custom emoji, or streaming drafts | [rich messages](references/rich-messages.md) |
| Server-side Mini App `initData` validation or launch boundary | [Mini Apps](references/mini-apps.md) |
| Telegram Stars, physical/offline payments, external checkout, or fulfillment | [payments](references/payments.md) |
| aiohttp webhooks, polling/webhook operation, shutdown, logging, or production rollout | [deployment](references/deployment.md) |
| A complete aiogram-dialog example | [full dialog example](examples/dialog-bot.py) |

Prefer native aiogram APIs; use aiogram-dialog for multi-screen, stateful interaction and native keyboards only for simple single-screen actions. Do not mix frameworks or use raw Bot API HTTP calls. Keep Mini App frontend and MTProto work outside this skill's implementation boundary.

Treat tokens as secrets from environment variables or a secret manager. Verify Mini App identity and authorization server-side. Treat callback data as an identifier: fetch referenced objects and authorize actions server-side. Log unexpected exceptions and let centralized error handling receive them. Use persistent production FSM/session storage. Fulfill payments idempotently only after confirmed success. Never imply live deployment, payment-provider mutation, or other external action without authorization.

Run tests proportional to the change before claiming completion.
