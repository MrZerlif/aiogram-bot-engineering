---
name: aiogram-bot-engineering
description: Use when designing, implementing, reviewing, or deploying Python aiogram Telegram bots with native UI presentation, dialogs, custom emoji, Rich Messages, Mini Apps, payments, or webhooks.
---

# Aiogram Bot Engineering

Start by inspecting the existing project, dependency versions, and user constraints. Preserve a coherent architecture unless restructuring is requested. Classify the request, then load only the smallest relevant set below; combine references only when the request genuinely crosses boundaries.

Compatibility baseline: Python 3.10+, aiogram 3.30.0, aiogram-dialog 2.6.0, and Telegram Bot API 10.2. These are dated compatibility targets, not a claim of latest versions. For another version or a latest-version request, verify the official documentation before writing version-sensitive code.

| Request | Read |
| --- | --- |
| Routers, Dispatcher, configuration, middleware, FSM, storage, or polling decisions | [architecture](references/architecture.md) |
| Native FSM or Scenes, multi-window menus, wizards, dynamic lists, pagination, or styled-button mechanics | [dialogs and UI](references/dialogs-and-ui.md) |
| Native screen composition, cover art, action hierarchy, concise copy, screen states, accessibility, or emoji-slop review | [presentation and UX](references/presentation-and-ux.md) |
| Custom emoji capability, sourcing and licenses, semantic registry, deterministic selection, owned sets, or fallbacks | [custom emoji system](references/custom-emoji-system.md) |
| Structured native Rich Messages, media bindings, custom emoji, or streaming drafts | [rich messages](references/rich-messages.md) |
| Server-side Mini App `initData` validation or launch boundary | [Mini Apps](references/mini-apps.md) |
| Telegram Stars, physical/offline payments, external checkout, or fulfillment | [payments](references/payments.md) |
| aiohttp webhooks, polling/webhook operation, shutdown, logging, or production rollout | [deployment](references/deployment.md) |
| Handler, router, FSM, webhook, Mini App, or payment tests | [testing](references/testing.md) |
| PostgreSQL, idempotency, queues, rate limits, observability, or production reliability | [production engineering](references/production-engineering.md) |
| A complete aiogram-dialog example | [full dialog example](examples/dialog-bot.py) |

For a styled native interface, read presentation guidance first. If the output
includes an inline or reply keyboard, also read dialogs and UI for the native
mechanics even when the request is primarily visual. If the request mentions
emoji or icons, or the proposed design uses them, also read the custom emoji
system and output semantic tokens before rendered assets. An attractive screen
is a coherent hierarchy, not an emoji quota.

Prefer native aiogram APIs. Use a handler/native keyboard for one action or
screen, native FSM for short linear input, experimental Scenes for an isolated
flow that needs lifecycle or history, aiogram-dialog for widget-driven UI,
pagination, dialog stacks, or nested flows, and a Mini App for a complex
browser UI. Do not mix frameworks or use raw Bot API HTTP calls. Keep Mini App
frontend and MTProto work outside this skill's implementation boundary.

Treat tokens as secrets from environment variables or a secret manager. Verify Mini App identity and authorization server-side. Treat callback data as an identifier: fetch referenced objects and authorize actions server-side. Log unexpected exceptions and let centralized error handling receive them. Use persistent production FSM/session storage. Fulfill payments idempotently only after confirmed success. Never imply live deployment, payment-provider mutation, or other external action without authorization.
At a webhook boundary, reject an invalid secret before dispatch, return success
only after the authenticated update reaches the chosen acceptance boundary, and
never log the secret header or bot token. For payments, persist the stable
Telegram charge identifier and any nonempty provider identifier under the
appropriate uniqueness constraints.

Run tests proportional to the change before claiming completion.
