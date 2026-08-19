# Production engineering for aiogram bots

This reference covers the operational boundaries that sit below handlers. Keep
feature behavior small and move durable work behind explicit repositories and
services; do not turn a router into a database, queue, or retry framework.

## Durable state and transactions

Use PostgreSQL repositories for durable orders, users, entitlements, and audit
records. Create a Unit of Work for one request or one update, inject it into
the handling path, and give it an explicit commit/rollback boundary. Repository
methods participate in that one transaction; they do not independently commit.
On expected rejection, roll back or make no mutation; on an unexpected error,
roll back, log the correlation context, and let centralized error handling see
the failure. Acquire connections from a bounded pool, release them in `finally`,
and close the pool only after intake has stopped and active work has drained.

Schema migrations are deployed artifacts, reviewed and applied in order. Test
both upgrade and rollback/recovery plans against representative data; do not
alter production tables from a handler at runtime. The FSM store is transient
conversation state, not a substitute for these durable records.

Protect an FSM key from concurrent updates with event isolation, and test the
same-user/same-chat race. For business writes, use transaction isolation,
row/advisory locking where the invariant requires it, and database uniqueness
constraints. Those controls complement each other: FSM isolation protects the
conversation path, while the database protects durable invariants across
processes.

## Idempotency, throughput, and background work

Every externally triggered write—not just a payment—needs an idempotency or
deduplication key with a durable uniqueness constraint. Record the key and the
state transition in the same transaction; a retry returns the earlier outcome
instead of repeating a side effect. Use separate keys and policies for updates,
commands, webhooks, imports, and provider events.

Apply per-user, per-chat, and global rate limits before expensive work. Bound
concurrent update and outbound-job work with semaphores or worker capacity, and
use queues to create backpressure instead of accumulating unbounded tasks in
memory. Reject, defer, or shed overload according to an explicit product
policy, with a safe retry response where applicable.

Put slow or retryable work in a queue-backed background job. Write the domain
change and a durable outbox record in one transaction; a publisher later emits
that record, so a process crash cannot lose a committed side effect. Classify
errors as permanent, transient, or cancellation. Retry only transient failures
with bounded exponential backoff and jitter, honor cancellation during shutdown,
and move exhausted or malformed jobs to a poison/dead-letter store with alerts
and a replay procedure.

## Sessions, observability, and operations

For any session-like record, enforce TTL, version, and owner checks on every
use. Reject stale, superseded, or cross-user records, then reset safely to a
known initial state; never revive an old action from callback data alone.

Emit structured logs with a correlation ID that follows the incoming update,
database operation, and queued job. Include safe identifiers and decision
outcomes, but redact bot tokens, webhook secrets, `initData`, payment details,
and personal content. Export metrics for intake, latency, error classes, queue
depth/age, retries, and idempotency conflicts; add traces around update, query,
and job boundaries. Persist trace context in outbox or queue metadata and
propagate it into worker spans, so background processing is linked to the
originating update rather than starting an unrelated trace. Alert on sustained
error rates, failed readiness, growing dead letters, migration failure, and
queue latency that breaches the service objective.

Build a small Docker image with a non-root runtime user and only the runtime
dependencies. On shutdown, stop accepting new updates, mark readiness false,
allow bounded in-flight work to finish or cancel it safely, flush the outbox as
the shutdown policy permits, then close bot sessions, workers, and database
connections. Liveness means the process can make progress; readiness becomes
true only after required dependencies are usable, not merely after the port is
open. See [deployment](deployment.md) for polling and webhook wiring.

CI should gate each change with the skill contract linter, focused and full
tests, type checking, and executable examples. Keep production credentials out
of CI logs and run any integration environment with isolated, disposable
resources.
