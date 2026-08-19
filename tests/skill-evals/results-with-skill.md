# Routed-skill evidence

These are deterministic review notes, not model scores or evidence of a live CI evaluation. Each section records the decision a reviewer should see after the matching prompt is routed through the aiogram engineering skill and its referenced bundle material.

## fsm-linear-flow

The routed answer selects an aiogram `StatesGroup` for the linear registration flow, makes each answer transition explicit, and validates before advancing. It includes a cancellation handler that clears persisted FSM context instead of leaving partial data in a module-level mapping.

## scenes-isolated-flow

The answer recognizes that entry, exit, and back navigation justify a scene-oriented flow rather than only flat state flags. It scopes journey data to the update context and storage key, explains cleanup on exit, and avoids shared per-process user state.

## dialog-widget-ui

The dialog reference changes the UI decision from manual keyboards to dialog windows and widgets. Toggle and pagination state live in the dialog model; callbacks are handled through the framework interaction path, which keeps the settings screen coherent after redraws.

## mini-app-launch-security

The routed answer uses a WebApp launch mechanism but separates it from authentication. It sends `initData` to the backend, validates its Telegram hash and freshness server-side, then derives the user identity from the verified payload rather than client JavaScript fields.

## callback-authorization

The result treats callback data as an identifier, reloads the report, and authorizes the pressing user before an approval mutation. It also performs an idempotent state transition so stale or repeated button presses receive a safe, explainable response.

## payment-lifecycle

The payment guidance places business fulfillment after `successful_payment`, while pre-checkout is answered promptly as a validation gate. A persisted provider charge identifier or equivalent unique key makes subscription activation safe when Telegram retries delivery.

## webhook-secret

The deployment-aware response configures Telegram's secret token and rejects requests whose secret-token header does not match. It keeps the HTTPS endpoint focused on updates, separates operational acknowledgment from unauthenticated traffic, and avoids emitting credentials in logs.

## background-jobs

The routed solution commits the order before durable follow-up work is made available to a worker, using an outbox or queue boundary where the work matters. Notification and report workers have idempotency keys, retries, and failure visibility instead of relying only on in-process background tasks.

## testing-strategy

The testing reference produces layered tests: pure policy tests, handler/storage integration tests, and assertions on outgoing bot effects. It explicitly covers an unauthorized callback, duplicate successful-payment delivery, and the UI response a user can observe.

## production-uow-observability

The production answer makes order mutation and an outbox record atomic in one unit of work, then lets a retryable worker handle external effects. It adds correlation identifiers to structured logs, metrics for outcomes and retries, and trace context across the asynchronous boundary, making failures diagnosable.
