# Results with skill — recorded treatment run

Independent treatment run collected 2026-08-19 after reading `SKILL.md` and only its routed resources.

## fsm-linear-flow

Use native FSM: this is a short linear form, not a dialog stack. Define `Registration.name`, `Registration.email`, and `Registration.age`. `/register` clears any abandoned registration, enters `name`, and prompts the user. Each state-specific handler normalizes and validates its answer before calling `state.update_data(...)` and advancing: require a bounded nonblank name, parse and normalize an email with an application validator, and parse an age within the supported range. On invalid input, explain the constraint and remain in the same state.

Register one `/cancel` handler that matches every registration state. It should acknowledge cancellation, remove any reply keyboard, and call `state.clear()`; it should also respond harmlessly when no flow is active. After the third valid answer, copy the collected values into a registration service, persist the user in one durable transaction, then clear FSM state. Do not treat FSM data as the user record. Use shared persistent `BaseStorage` in production, plus event isolation for simultaneous updates to the same user/chat key; reserve `MemoryStorage` for tests and local development.

## scenes-isolated-flow

Use native aiogram Scenes because onboarding needs lifecycle hooks and history; note that Scenes are experimental in aiogram 3.30. Model welcome, profile, and preferences as isolated scenes. The entry command enters the welcome scene and initializes fresh scene data; each accepted answer is validated and stored through the scene wizard before moving forward. Provide a Back action that calls scene history navigation, and an Exit/Cancel action that leaves the scene, clears transient onboarding data, and returns to a known safe menu. On successful exit, persist the completed profile through a service and transaction.

Configure the dispatcher with persistent shared FSM storage and event isolation. Choose an FSM key strategy that includes bot, chat, and user identity so two people in a group—or the same person in two chats—do not share state. Never keep answers in module globals, class attributes, or a singleton scene object. Any durable draft should carry an owner ID and be checked on every load. Entry should reset stale/superseded sessions rather than revive them. Test independent chat/user keys concurrently, Back after every step, cancellation from every scene, restart recovery, and same-key racing updates.

## dialog-widget-ui

Use aiogram-dialog 2.6.0 with a `SettingsSG` and two windows: `settings` and `confirm`. The settings window can contain a `Checkbox` for the boolean preference, a server-backed `Select` inside a `ScrollingGroup` for paginated choices, and a `Button` that switches to confirmation. Store only staged UI values and the requested page in `DialogManager.dialog_data`; the getter should be read-only, load the current account/settings, clamp the page to server-derived bounds, and return render data.

Toggle and selection callbacks should acknowledge promptly, parse IDs defensively, reload allowed options server-side, and check `callback.from_user.id` against the account. The confirm callback writes through a settings service in one transaction, preferably checking a settings version so an old screen cannot overwrite newer changes, then calls `manager.done()`. Back returns without committing; repeated or out-of-range paging renders the same bounded page.

Start `/settings` with `StartMode.RESET_STACK`. Include the command router and dialog before `setup_dialogs(dp)`, use persistent shared storage in production, and centrally recover `UnknownIntent`/`UnknownState` by logging, acknowledging the callback, and resetting to the safe settings window.

## mini-app-launch-security

Launch the account dashboard from an inline `InlineKeyboardButton(web_app=WebAppInfo(url=MINI_APP_URL))`; the HTTPS URL locates the app but does not authenticate it. The frontend should send the raw `Telegram.WebApp.initData` to the backend. Do not use a reply-keyboard `sendData` result, `initDataUnsafe`, or a client-provided user ID as identity.

At the backend, one validator should parse the query string strictly, reject duplicate or missing fields, remove `hash`, sort the remaining `key=value` lines, and compute the documented HMAC using a secret derived from the bot token with `WebAppData`. Compare hashes with `hmac.compare_digest`. Reject malformed, tampered, future-dated, or older-than-policy `auth_date` before any account lookup. Keep the bot token server-side and never log the token or raw init data.

Only after validation should the backend parse the signed `user`, map its Telegram ID to a server-side account, establish a short-lived session bound to that identity, and authorize every dashboard request against stored ownership, role, and entitlement data. TLS, secure cookie settings, rate limits, and normal CSRF controls complement this boundary; none replaces Telegram signature validation.

## callback-authorization

Encode only a compact `report_id` and rendered `version` in typed callback data; neither is proof of permission or freshness. The callback handler should acknowledge all outcomes promptly, parse both fields defensively, then load the report and the actor’s moderator membership from durable storage using `callback.from_user.id`. Deny malformed, missing, cross-tenant, ordinary-user, expired, already-decided, or version-mismatched requests with a neutral alert.

For an allowed moderator, execute approval in one transaction. Lock the report row or use a conditional update such as “pending and version equals rendered version,” re-check authorization inside that boundary, advance it to approved, increment its version, and write an audit record with actor and correlation ID. A uniqueness constraint or idempotency key should make a replay return the recorded outcome instead of approving twice. If the conditional write affects no row, treat the button as stale and refresh or remove its keyboard.

Do not trust a role, status, owner, or signature-shaped value embedded in callback data. Log safe identifiers and the decision, not report content. Unexpected database errors should roll back and reach centralized error handling rather than being converted into a successful callback.

## payment-lifecycle

For an in-Telegram digital subscription, use Telegram Stars (`currency="XTR"`) and no provider token, subject to a current policy check before release. Create a durable pending order from the server-selected plan and price; put only its opaque public reference in the invoice payload.

The `pre_checkout_query` handler must reload that order and, within Telegram’s 10-second window, verify pending/payable status, payer policy, currency, and total amount. Approval is not fulfillment. On every `successful_payment`, reload and validate the same contract again, then run `fulfill_paid_order_once` in one database transaction: insert the `telegram_payment_charge_id` under a unique constraint, record the paid/fulfilled transition, and grant the subscription atomically. A duplicate or replay after restart returns the existing result. The provider charge ID is nullable for Stars.

Make out-of-order handling state-based: a success event may complete a valid pending order even if the local pre-checkout update was missed, while a later pre-checkout for an already paid order is rejected. Process renewal, cancellation, refund, reversal, and dispute events using their stable identifiers and idempotent transitions. Reconcile charges against entitlements and send mismatches to investigation rather than granting ad hoc access.

## webhook-secret

Run exactly one delivery mode and expose a stable HTTPS aiohttp endpoint using aiogram’s `SimpleRequestHandler` and `setup_application`. Generate the Telegram webhook secret once in a trusted administrative context with `secrets.token_urlsafe(32)`, store it in an environment variable or secret manager, and reject blank, placeholder, malformed, or weak values during startup. It is separate from `BOT_TOKEN` and must not be generated anew on every restart.

Pass that same secret as `secret_token` both to `SimpleRequestHandler` and `bot.set_webhook(...)`, together with `dispatcher.resolve_used_update_types()`. The handler verifies Telegram’s secret header on each request before dispatch, so missing or random values cannot invoke handlers. TLS termination, a narrow webhook path, request-size limits, and edge rate limiting are useful additional controls, not substitutes for the header.

Do not start polling in this deployment. Keep liveness separate from readiness; readiness should remain false until the database, persistent FSM store, and any essential queue are usable. On shutdown, stop intake, drain bounded in-flight work, and close the bot session and pools. Test missing/invalid headers at the actual request handler and assert the dispatcher was never called.

## background-jobs

Keep the successful-order handler transactional and short. In the same database transaction that marks the order fulfilled, insert durable outbox rows for “send notifications” and “generate report,” keyed uniquely by order, job type, and relevant version. Commit, acknowledge the update, and let an outbox publisher deliver those records to a persistent queue. Do not use untracked `asyncio.create_task()`; a process crash between commit and scheduling would lose work.

Workers should use bounded concurrency and acknowledge a queue message only after its durable result is recorded. Make each operation idempotent: notification delivery records prevent duplicates, while report generation writes a stable artifact/status for the same job key. Classify failures as transient, permanent, or cancellation; retry only transient failures with bounded exponential backoff and jitter. Move exhausted or malformed jobs to a dead-letter store with alerts and a documented replay path.

Propagate the incoming correlation ID through the order transaction, outbox row, queue message, logs, and traces. Track queue depth, oldest-job age, retries, failures, and completion latency. During shutdown, stop intake, mark readiness false, let workers drain for a bounded period, and leave unacknowledged work available for recovery on restart.

## testing-strategy

Use three layers. First, call handlers/services directly with `AsyncMock` Telegram events for local behavior. For callbacks, cover malformed data, missing report/order, ordinary user, wrong tenant/owner, stale version/session, already-completed state, and a valid moderator. Assert the object is fetched and authorization is server-side, callbacks are acknowledged, and the authorized conditional transition/audit happens once.

Second, use `Dispatcher.feed_raw_update()` with a fake bot token to verify router filters, middleware injection, and callback routing without polling or network calls. Exercise the dialog getter, toggle staging, confirm/cancel, Back, stack reset, stale-intent recovery, first/last/out-of-range pages, repeated navigation, and isolation between two users/chats.

Third, run repository-level integration tests against disposable storage. Validate pre-checkout rejection for wrong payer, state, currency, or total. Feed the same successful-payment event twice, then replay it after recreating dispatcher/storage; assert one unique charge, one entitlement, and the same recorded result. Include success arriving without the locally observed pre-checkout update and contract-mismatch incidents.

Use controlled clocks, fake credentials, deterministic queue workers, and concurrency barriers. Assert committed database outcomes—not only mocked calls—and ensure no test can contact Telegram or a payment provider.

## production-uow-observability

Keep the handler thin. Middleware should attach a correlation ID and inject a Unit of Work backed by a bounded PostgreSQL pool. Inside one transaction, parse the order reference, load/lock the order, authorize the Telegram actor from server-side data, verify pending state and expected version, and claim a durable idempotency key. Then mark the order confirmed, append an audit record, and insert outbox jobs for downstream work before one explicit commit.

Repositories participate in the Unit of Work and never commit independently. Expected rejection performs no mutation; unexpected failure rolls back, releases the connection in `finally`, logs context, and is re-raised to centralized error handling. A replay returns the previously stored outcome. Retry only classified transient database failures, with bounded backoff and jitter, by rerunning the whole transaction and re-reading state; never retry authorization or business conflicts blindly.

Emit structured logs containing correlation ID, update ID, safe user/order identifiers, attempt, outcome, latency, and idempotency-conflict status while redacting tokens, secrets, payment details, and personal content. Create trace spans around update handling, authorization/query, transaction/commit, outbox publishing, and worker execution. Export latency/error/retry/idempotency and queue-depth/age metrics, with alerts for sustained failures, dead letters, and readiness loss.
