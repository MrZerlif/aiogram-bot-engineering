# Baseline without skill — recorded control run

Run `control-20260819-r1`, produced by `/root/eval_baseline_run` on
2026-08-19. The runner received the ten prompt texts directly and confirmed it
did not read the repository skill, rubrics, tests, README, result artifacts, or
web content. The exact deployed model revision was not exposed. See
[`run-manifest.json`](run-manifest.json) for the recorded protocol and hashes.

## fsm-linear-flow

Model the conversation as a `StatesGroup` with `name`, `email`, and `confirmation` states. The `/register` handler clears any abandoned registration, initializes fresh FSM data, sets `name`, and renders the first prompt. Each state gets its own handler: normalize and validate the name, validate the email syntactically and against any product rules, then accept only an explicit confirm or restart choice. Invalid input must leave the state unchanged and return a specific correction message. Store normalized values in `FSMContext`, not module-level variables.

Register a `/cancel` and cancel-button handler that applies while any registration state is active. It should clear the FSM data, remove or replace obsolete keyboards, and acknowledge callback queries. On confirmation, revalidate the complete payload and persist it atomically before clearing state; if persistence fails, retain enough state to retry and show a recoverable error. Also handle unexpected text and old callback buttons without advancing. Test every valid transition, each validation failure, cancellation from all three states, duplicate confirmation, and simultaneous registrations by different users.

## scenes-isolated-flow

Represent onboarding as a scene or wizard with explicit entry, step, back, completion, and exit handlers. Entry should initialize a fresh, namespaced data object and render the first view. Each forward transition validates the current answer before saving it; back navigation moves to the previous step while preserving already entered values and re-renders them for editing. Completion writes the final model atomically, while cancel and exit clear transient scene data and remove obsolete controls.

Isolation depends on storage keys, not merely on scene code. Configure FSM storage so the key includes at least bot, chat, and user identifiers; this is especially important in group chats where several users share one chat. Use Redis or another durable FSM backend in a multi-process deployment, with an appropriate TTL, and never store current-user data in globals or singleton scene objects. If two updates for one user can execute concurrently, serialize them or use a version check. Tests should interleave two users in one chat and one user in two chats, verify back/exit behavior, restart the application mid-flow, and assert that no answers cross storage keys.

## dialog-widget-ui

Build one `Dialog` window whose getter returns persisted settings plus the current page. Use a `Checkbox` for the boolean setting, a paginated `ScrollingGroup` or paged `Select` for the list, navigation controls, and a `Button` for confirmation. Give every widget a stable, unique ID. The checkbox callback updates only dialog-local draft data and re-renders; page navigation changes the dialog page without mutating the saved settings. The getter should derive checked state and visible rows from the draft so the UI remains deterministic after every callback.

The confirm callback must validate the complete draft and save it in a transaction, then show success or close the dialog. Keep persistent settings in the database and temporary edits in `dialog_data`; do not use process-global state. Treat callbacks as untrusted: verify the acting user owns the dialog, reject unavailable item IDs, and make confirmation idempotent so double taps do not duplicate side effects. A cancel action should discard the draft. Test initial rendering, toggle on/off, first/middle/last page boundaries, empty lists, persistence failures, double confirmation, and reopening the dialog from stored values.

## mini-app-launch-security

Send an inline keyboard button containing `WebAppInfo` with an HTTPS dashboard URL. The Mini App should pass Telegram’s initialization data to its backend immediately. On the server, validate the `initData` signature according to Telegram’s HMAC procedure using the bot token, compare the computed hash in constant time, reject an old `auth_date`, and optionally track a nonce or data hash briefly to reduce replay. Parse the user identity only after successful validation; never accept a user ID, role, or account ID merely because JavaScript supplied it.

After validation, issue a short-lived application session scoped to that Telegram user. Use secure, `HttpOnly`, `SameSite` cookies with CSRF protection, or a short-lived bearer token kept in memory. Every dashboard endpoint must authorize access to the requested account independently. Keep the bot token exclusively server-side, enforce HTTPS through the proxy and application, restrict CORS to the Mini App origin, rate-limit authentication, and avoid logging raw initialization data or credentials. Test modified fields, invalid hashes, expired data, replay, cross-account requests, and a legitimate launch on both Telegram clients and browser-like test clients.

## callback-authorization

Encode only a report identifier and expected version in a structured callback payload; do not encode “is moderator” or approval state as trusted facts. When clicked, always answer the callback promptly, then obtain the actor’s moderator status from an authoritative source such as current chat membership or the application role table. Hiding the button from ordinary users improves UX but is not authorization. Reject unauthorized actors with a neutral alert and record the attempt without exposing sensitive report details.

Load the report in a transaction using a row lock or conditional update such as `WHERE status = 'pending' AND version = :expected`. If no row changes, the button is stale, the report is missing, or another moderator already acted; return an “already handled” response and refresh the message. On success, record approver, timestamp, and the new version, commit, and then edit the UI. Use an idempotency key based on report and action so duplicate deliveries are harmless. Test ordinary users, removed moderators, forged payloads, malformed IDs, old versions, two simultaneous moderators, duplicate updates, and failures between database commit and message editing.

## payment-lifecycle

Create a pending order before sending the invoice and place an opaque, unique order reference in the invoice payload. In the `pre_checkout_query` handler, reload that order and verify product, price, currency, buyer eligibility, and pending status; answer within Telegram’s deadline. Do not grant access at pre-checkout, because it is only permission to attempt payment. Fulfillment begins from `successful_payment`, after verifying its invoice payload and monetary fields against the stored order.

Process payment in a database transaction with a lock or conditional state transition. Store both Telegram and provider charge IDs under unique constraints, mark the order paid once, extend the subscription deterministically, and insert an outbox event in the same transaction. Duplicate successful-payment updates then return the existing result. If payment arrives without a recorded pre-checkout event, reconcile it from the trusted invoice payload rather than discarding paid money; if events arrive late, state transitions must never move a paid order backward. Workers consume the outbox idempotently for receipts and notifications. Test duplicate and reordered updates, concurrent handlers, amount mismatch, declined checkout, crash after commit, subscription extension rules, refunds, and reconciliation of ambiguous payments.

## webhook-secret

Expose a single POST endpoint behind a TLS-terminating reverse proxy and configure `setWebhook` with a high-entropy `secret_token`. For every request, compare Telegram’s secret-token header to the configured value before parsing or dispatching the update, using a constant-time comparison where practical. Missing or incorrect secrets should receive an immediate 401 or 403 and must never reach bot middleware. Keep the secret in a secret manager, separate from the bot token, and support rotation by updating Telegram and the deployment deliberately.

Use HTTPS with valid certificates, restrict the endpoint to POST and the expected content type, cap body size and request duration, and apply conservative rate limits. A random URL path and Telegram IP allowlisting can add defense in depth, but neither replaces the secret header; IP rules must account for trusted-proxy configuration so clients cannot spoof forwarding headers. Return success quickly after safely accepting an authenticated update, while durable processing handles longer work. Log authentication failures without logging secrets or full update bodies. Test absent, incorrect, and correct headers, oversized and malformed bodies, proxy header spoofing, duplicate updates, and behavior during secret rotation.

## background-jobs

Use a transactional outbox. In the same database transaction that changes the order to `paid`, insert separate durable jobs for customer notification and report generation, each with a stable idempotency key such as `order_id + job_type`. The update handler commits this small transaction and responds; it does not render reports or call slow downstream services. A dispatcher publishes committed outbox rows to a durable broker, or workers can lease rows directly from the database with `SKIP LOCKED` semantics.

Workers acknowledge a job only after its side effect is complete. They should use bounded exponential backoff with jitter, lease expiry for crashed workers, maximum attempts, and a dead-letter state with alerting. Notification delivery records and generated-report records need unique constraints so redelivery cannot send or create twice; store reports in durable object storage and save their location atomically. Propagate order, update, job, and trace identifiers into job metadata. On restart, expired leases and unpublished outbox rows are picked up again. Test crashes before and after each commit, duplicate delivery, transient Telegram/storage failures, poison jobs, concurrent workers, shutdown while processing, and replay from the dead-letter queue.

## testing-strategy

Split tests by boundary. Unit-test callback payload encoding/decoding, order state transitions, amount checks, authorization decisions, and keyboard construction with table-driven cases. Handler tests should feed synthetic callback and payment updates through the dispatcher with a fake bot session, then assert callback acknowledgements, message edits, alerts, and database effects. Include malformed and forged callback data, an ordinary user, an active moderator, a moderator whose role was revoked, a missing order, and a stale order version.

Run integration tests against the real database engine used in production so transactions, unique constraints, locks, and rollback behavior are exercised. Deliver the same successful-payment update repeatedly and out of order relative to pre-checkout; assert one charge record, one fulfillment transition, and one outbox event. Race two approval or payment handlers and verify only one wins. For UI behavior, assert semantic properties of the keyboard—button text, callback payload, enabled actions, pagination boundaries, and the refreshed state—rather than brittle serialized snapshots alone. Add tests for Telegram API failures after commit, worker retry/restart, unauthorized audit logs, and property-based fuzzing of callback bytes and state-event sequences.

## production-uow-observability

Make the handler an orchestration layer around a unit of work. Parse and validate the callback, authenticate the actor, then begin a transaction and load the order with a row lock or optimistic version. Apply a domain transition that only permits `pending -> confirmed`, write the confirmation and audit record, and insert an outbox event in the same commit. A unique idempotency key derived from the update/action ensures retries return the previously committed result. Call Telegram to refresh the message after commit; failures there must not roll back the order and can be retried from the outbox.

Retry only classified transient failures such as serialization conflicts, deadlocks, timeouts, and rate limits, using bounded exponential backoff with jitter. Do not retry validation, authorization, or invariant failures. Emit structured logs containing update, callback, order, actor, attempt, state transition, duration, and outcome fields, while excluding secrets and payment data. Start a trace span at update receipt and propagate its context into database and outbox-worker spans; record retry and external-call events. Metrics should cover latency, outcomes, retries, conflicts, outbox lag, and dead letters. Test commit ambiguity, concurrent confirmations, duplicate updates, post-commit API failure, log redaction, and trace-context propagation.
