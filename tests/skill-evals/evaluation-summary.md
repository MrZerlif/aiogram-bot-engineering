# Behavioral evaluation assessment

Protocol note (2026-08-19): This is an independent final-round rubric judgment of the two recorded behavioral outputs, not a CI result or model benchmark. Every retrieval, application, and gap assertion was scored all-or-nothing from explicit output only.

| Case | Control | Treatment | Delta/remaining gap |
|---|---:|---:|---|
| fsm-linear-flow | 4/4 | 4/4 | +0; none |
| scenes-isolated-flow | 3/4 | 4/4 | +1; none |
| dialog-widget-ui | 4/4 | 4/4 | +0; none |
| mini-app-launch-security | 4/4 | 4/4 | +0; none |
| callback-authorization | 4/4 | 4/4 | +0; none |
| payment-lifecycle | 4/4 | 4/4 | +0; none |
| webhook-secret | 4/4 | 4/4 | +0; none |
| background-jobs | 3/4 | 4/4 | +1; none |
| testing-strategy | 4/4 | 4/4 | +0; none |
| production-uow-observability | 4/4 | 4/4 | +0; none |

## fsm-linear-flow

Both outputs explicitly choose a `StatesGroup`, define one state per awaited answer, and install cancellation across every registration state with FSM clearing. Both also reject module-level progress storage, so each satisfies all four assertions.

## scenes-isolated-flow

The control covers scene lifecycle, back behavior, user/chat isolation, durable storage, and rejection of shared globals, but it does not explicitly distinguish a Scene from a simple FSM by identifying navigation history as the selection criterion; its retrieval assertion therefore fails. The treatment gives that explicit lifecycle-and-history rationale and also covers entry, exit, back navigation, scoped persistent state, and rejection of shared mutable storage.

## dialog-widget-ui

Both outputs explicitly select aiogram-dialog, define a `Dialog`/`Window`, and use widgets plus dialog-local draft data for toggle, pagination, and confirmation behavior. Their widget-owned callback designs avoid the manual single-message and ad-hoc per-widget parsing approach, satisfying the remaining application and gap assertions.

## mini-app-launch-security

Both outputs launch through `WebAppInfo`, forward raw `initData` to an HTTPS backend, and require server-side HMAC validation before deriving identity. Each explicitly rejects client-supplied identity or URL-based authentication, so both satisfy all assertions.

## callback-authorization

Both outputs keep callback data to identifiers/versioning, load the report and current actor authority server-side before mutation, and make stale or repeated approval idempotent. They explicitly reject button visibility, embedded role data, and callback payloads as authorization evidence.

## payment-lifecycle

Both outputs distinguish pre-checkout validation from fulfillment and grant access only after `successful_payment`. Each persists stable Telegram and provider charge identifiers when available, makes replay idempotent, and explicitly rules out fulfillment at pre-checkout.

## webhook-secret

Both outputs route to an HTTPS webhook design, configure and verify Telegram's secret-token header before dispatch, and keep the endpoint narrow. They acknowledge only an authenticated accepted update and explicitly reject unauthenticated invocation and secret/token logging.

## background-jobs

The control explicitly uses an atomic transactional outbox, durable workers, retries, deduplication, and observable dead-letter handling, so it satisfies retrieval and both application assertions. It never explicitly rejects fire-and-forget `asyncio.create_task` as the sole business-critical guarantee, while the treatment does so directly and therefore earns the fourth point.

## testing-strategy

Both outputs separate small decision/handler tests from dispatcher and transactional-storage integration tests, and both exercise unauthorized callbacks, duplicate successful payments, and asserted bot responses. Their negative payload cases and semantic UI assertions also rule out a source-snapshot-only or happy-path-only strategy.

## production-uow-observability

Both outputs make the order mutation and outbox event atomic inside a unit of work, then specify bounded retries, correlation fields, structured failure diagnostics, metrics, and worker trace propagation. Those explicit recovery and diagnostic boundaries reject a best-effort sequence of writes, bot sends, and prints, satisfying all four assertions.

## Overall findings

The control satisfies 38/40 assertions (95%), while the treatment satisfies 40/40 (100%), for a +2 assertion improvement. The treatment has no remaining rubric gaps; its measurable gains are the explicit Scene-versus-simple-FSM routing rationale and the direct rejection of `asyncio.create_task` as the only durability mechanism.

