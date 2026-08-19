# Results with skill — recorded treatment run

Run `treatment-20260819-r3`, produced by `/root/eval_treatment_round3` on
2026-08-19 after the gap-driven skill revision. The runner received the ten
prompt texts directly, read `SKILL.md` and a shared batch of its routed
resources, and confirmed it did not read eval rubrics, tests, README, prior
results, git history, or web content. The exact deployed model revision was not
exposed. See [`retrieval-trace.json`](retrieval-trace.json) for the self-reported
read set and [`run-manifest.json`](run-manifest.json) for protocol and hashes.

## fsm-linear-flow

Use a native aiogram FSM because this is a short linear form. Define a `Registration` `StatesGroup` with `name`, `email`, and `age` states, and put its handlers in a feature `Router`. Each handler should normalize and validate only the answer for its current state: reject a blank or oversized name, parse and validate the email, and parse age with explicit bounds. On invalid input, answer with a specific correction and leave the state unchanged. On valid input, save the normalized value with `FSMContext.update_data()` and advance with `set_state()`.

Register a `/cancel` handler, plus a cancel callback if buttons are shown, so it matches every registration state. It should acknowledge callbacks, clear the FSM, and return a neutral confirmation; cancellation must not create a user record. At the final step, read all state data, persist the registration through a service/repository transaction, and clear state only after success. Use persistent production FSM storage and event isolation, not module-level dictionaries, so restarts and concurrent answers do not corrupt progress.

## scenes-isolated-flow

Model onboarding as an aiogram Scene because it needs an isolated lifecycle and navigation history, while noting that Scenes are experimental in aiogram 3.30.0. Give entry, profile, and review steps explicit scene states. An entry hook may initialize onboarding metadata; navigation should use the scene wizard’s `goto()` and `back()` operations rather than encoding the current screen in callback data. An exit hook should perform bounded cleanup, while successful completion should call the application service first and then leave the scene. A cancel action should be available in every step.

Store draft answers only in the user’s `FSMContext` through a persistent `BaseStorage`. Configure the storage key strategy so the intended user/chat pair owns the session, and never keep drafts in a mutable global, router singleton, or shared getter. Durable profile and authorization data still belong in the database. On every callback, treat identifiers as untrusted, acknowledge denied or malformed input, and reject stale scene history by resetting to a known entry state. Add same-user concurrency isolation and verify separately that two users and two chats cannot observe one another’s drafts.

## dialog-widget-ui

Use aiogram-dialog 2.6.0 because the screen is widget-driven and paginated. Define a `SettingsSG` state and a `Dialog` containing a `Window` with a `Checkbox` or toggle control, a bounded `ScrollingGroup`/pager for the settings list, and a confirm `Button`. Include the dialog router before calling `setup_dialogs(dp)`, and start this top-level screen with `StartMode.RESET_STACK` when a fresh settings session is intended.

The getter should be read-only: load the authenticated user’s current settings, clamp the requested page to the server-derived last page, and return render data. Toggle callbacks may update `dialog_data` as a draft, but they must not trust a setting name or value supplied by callback data. Confirm should reload the allowed settings server-side, authorize the actor, validate the draft, and persist all changes atomically through a service. Only then should it call `done()` or render success. A cancel/back action should discard the draft. Acknowledge callbacks on success, denial, and malformed input, and route stale dialog intents through centralized recovery to a safe window.

## mini-app-launch-security

Launch the dashboard from an inline `WebAppInfo` button, which supports the signed `initData` flow. The URL only locates the Mini App; it is not proof of identity. The frontend should send the raw `Telegram.WebApp.initData` to the HTTPS backend. One server-side validator should parse it strictly, reject duplicate or missing fields, remove `hash`, sort the remaining `key=value` lines, and verify the documented HMAC using a secret derived from the bot token. Use `hmac.compare_digest`, enforce an application-chosen short maximum age, and reject both expired and future `auth_date` values.

Only after validation should the backend parse the validated `user` JSON and use that Telegram ID to find an application account. Bind a server session to that identity and authorize every dashboard operation against server-side account, role, and ownership data. Never accept `initDataUnsafe`, a client-provided user ID, role, price, or account ID as authority. Keep the bot token server-side, redact `initData` and secrets from logs, apply normal session expiry and rotation, and reject malformed requests before any account lookup or business action.

## callback-authorization

Use a native inline keyboard for this single action. Encode only a compact action plus `report_id` and, if useful, an expected report version in typed `CallbackData`; do not encode the moderator role, approval state, or trusted snapshot. The callback handler should parse defensively, load the report from durable storage, resolve the actor’s current moderator permission server-side, and check that the report is still pending and the version belongs to the displayed action.

Perform approval in one transaction with a conditional update or row lock. The invariant should require both “actor is authorized” and “status is pending”; a uniqueness/idempotency key should make a retried callback return the existing outcome rather than approve twice. A missing report, ordinary user, revoked moderator, mismatched version, or already-resolved report is denied without mutation. Acknowledge every callback promptly: use a concise alert for malformed, unauthorized, or stale buttons, and edit the message/remove the button only after the transaction commits. Record safe audit fields such as report ID, actor ID, decision, and correlation ID, but never treat Telegram callback payloads as authorization evidence.

## payment-lifecycle

Treat an in-Telegram subscription as a digital service and route it through Telegram Stars with `currency="XTR"`, subject to a current policy check before shipping. Create a durable order first with the product, amount, payer/recipient policy, and opaque public reference; the invoice payload should only correlate to that order. In `pre_checkout_query`, reload it and compare status, payer policy, currency, and total, denying invalid requests within Telegram’s documented ten-second window.

Fulfillment belongs only in `successful_payment`, never in pre-checkout or a client return. Reload and revalidate the order, then in one database transaction record the unique `telegram_payment_charge_id`, advance payment state, and grant the subscription. Persist a provider charge ID only when nonempty. Replayed success updates must return the recorded result. Model paid, fulfilled, renewed, canceled, refunded, reversed, and disputed transitions explicitly; key each external event by its stable ID so late or out-of-order events are either applied legally or retained for reconciliation. Publish post-payment work through a transactional outbox. Define the policy for duplicate valid payments and investigate contract mismatches rather than silently granting access.

## webhook-secret

Expose one stable HTTPS webhook and do not run polling for the same bot. Generate a high-entropy secret once in a trusted administration context, store it separately from `BOT_TOKEN` in an environment variable or secret manager, and reject blank, placeholder, malformed, or weak values at startup. Register the webhook with `Bot.set_webhook(..., secret_token=secret, allowed_updates=dp.resolve_used_update_types())`.

Use aiogram’s aiohttp `SimpleRequestHandler` with the same secret and `setup_application` for lifecycle wiring. Its request boundary must reject a missing or invalid Telegram secret header before parsing the body or invoking the dispatcher; rejected traffic must not receive a success acknowledgement. Return success only after an authenticated update reaches the selected acceptance boundary. If work continues asynchronously and loss is unacceptable, that boundary is a committed inbox/outbox or durable queue record, not an in-memory task. Never log the secret header, bot token, or raw update. Keep liveness separate from readiness, require storage/database/queue health for readiness, and stop intake before draining in-flight work and closing resources during shutdown.

## background-jobs

Keep the successful-order handler short by committing the order transition and durable outbox records in the same database transaction. Create separate job records for customer/admin notifications and report generation, each with a stable idempotency key derived from the order and job type. A publisher can move committed outbox entries to a durable queue; acknowledging the update after this durable acceptance point avoids losing work if the process exits immediately afterward.

Workers should claim jobs with bounded concurrency and backpressure. Before each side effect, check or atomically record its deduplication key so redelivery cannot send the same notification or publish the same report twice. Retry only classified transient failures with bounded exponential backoff and jitter. Permanent validation failures and exhausted retries belong in a dead-letter store with alerts, diagnostic context, and a controlled replay procedure. Persist job status rather than relying on `asyncio.create_task`, so restart recovery can resume outstanding work. Propagate the incoming correlation and trace context through outbox metadata, and monitor queue depth, oldest-job age, retry counts, dead letters, and end-to-end completion latency.

## testing-strategy

Test application behavior at the smallest useful boundary. Directly call the callback handler with `AsyncMock` callback events for malformed payloads, missing orders, ordinary users, revoked permissions, wrong ownership, stale versions, repeated clicks, and the authorized transition. Assert both repository state and callback acknowledgement; a denied path must make no mutation. Use `Dispatcher.feed_raw_update()` with a fake token when filters, router selection, middleware, or dependency injection matter, without polling or Telegram network access.

For payments, feed the same successful-payment update twice and assert one charge row and one entitlement in the database transaction. Repeat after recreating storage to simulate restart, and cover success arriving around duplicated/stale UI updates, plus payer, order, currency, and amount mismatches. Controlled clocks and barriers should exercise timeout and concurrent-delivery races. For UI behavior, assert the rendered button identifiers, page clamping, disabled/absent actions for terminal states, safe stale-button alerts, and message edits only after commit. Keep service validation real where practical, use disposable repositories for transactional assertions, and ensure test configuration contains no usable Telegram or provider credentials.

## production-uow-observability

Give the order-confirmation handler an injected Unit of Work containing repositories, an outbox, and one explicit transaction. After defensively parsing the callback, load and lock the order, resolve current authorization server-side, and enforce the expected version and confirmable state. Insert an update/callback idempotency key under a unique constraint in the same transaction as the state transition and outbox event. A duplicate should return the previously recorded outcome; expected denial should not mutate, and unexpected failure should roll back and reach centralized error handling. Acknowledge success only after commit.

Retry transient database failures at the application boundary with bounded backoff and jitter, starting a fresh Unit of Work each attempt. Do not retry authorization or validation failures, and rely on the idempotency constraint to prevent duplicate effects. Emit structured logs with correlation ID, safe order/user identifiers, attempt, decision, duration, and error class while redacting callback contents and secrets. Create trace spans around update handling, authorization/query, transaction commit, outbox publication, and worker processing; persist trace context with the outbox record. Track latency, rollback/error classes, retry counts, idempotency conflicts, outbox age, and confirmation outcomes, with alerts tied to service objectives.
