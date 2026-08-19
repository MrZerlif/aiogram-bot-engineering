# Baseline evidence: without the routed skill

These are deterministic review notes, not scores or records of a live model run. They describe the shortcomings a reviewer should observe when an answer lacks the repository skill's routed guidance.

## fsm-linear-flow

An unguided answer often treats registration as a chain of broad message handlers and tracks the current step in a process-local dictionary. It may omit validation transitions and a cancellation route that clears saved state. That design conflates users, fails after a restart, and makes the next expected input ambiguous.

## scenes-isolated-flow

Without the architecture guidance, a navigation-heavy onboarding flow is commonly flattened into a few FSM flags. Entry, back, and exit behavior are improvised in handlers, while collected data is held in shared memory. The result neither defines scene boundaries nor demonstrates user-and-chat isolation.

## dialog-widget-ui

The baseline tends to hand-build inline keyboards, encode widget state in callback strings, and edit messages manually. It does not identify the dialog layer as the appropriate UI abstraction, so pagination and toggles become duplicated callback parsing with fragile state restoration.

## mini-app-launch-security

An answer without Mini App guidance may show a WebApp button but trust a `user_id` sent by JavaScript. It can confuse launching the WebView with authenticating its backend calls, leaving no server-side check of Telegram init data before the dashboard is authorized.

## callback-authorization

The naive design assumes a visible moderator button is enough protection. It may put the role or approval decision in callback data and mutate the report directly, without reloading it, authorizing the actor on the server, or handling a second click after the report is already resolved.

## payment-lifecycle

The baseline frequently treats invoice delivery or pre-checkout approval as payment confirmation. It leaves fulfillment outside a durable idempotency boundary, so a retried successful-payment update can grant the subscription twice or a delayed update can be mishandled.

## webhook-secret

An unguided deployment answer exposes a generic POST endpoint and assumes HTTPS is sufficient. It does not configure and validate Telegram's webhook secret token, distinguish rejected traffic, or note that credentials and secret headers must stay out of logs.

## background-jobs

The default suggestion is to call `asyncio.create_task` after the order handler returns. That keeps the handler responsive but does not make notification or report generation durable, retryable, or observable; a process restart loses work silently.

## testing-strategy

Without the testing reference, an answer usually says to "add unit tests" without giving update-level cases. It misses unauthorized callbacks, duplicate payment updates, and assertions about the bot's observable replies, so behavior at the framework boundary remains unproven.

## production-uow-observability

The baseline describes sequential database writes and bot calls with a few print statements. It lacks an atomic unit-of-work/outbox decision, correlation data, metrics, traces, and a way to understand or recover failed side effects after retries.
