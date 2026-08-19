# Assertion-level evaluation summary

Protocol: evaluator `evaluator-20260819-r4` scored the assertions recorded in
[`assertion-results.json`](assertion-results.json), using
[`retrieval-trace.json`](retrieval-trace.json) exclusively for retrieval and
exact case-output excerpts for application and gap evidence.
[`run-manifest.json`](run-manifest.json) records task identities, context rules,
the exact skill commit, limitations, and artifact hashes. The treatment trace
is shared-batch/self-reported, not per-case platform-signed, so a treatment
retrieval pass means the expected references were present in the shared ordered
context and does not establish an independent read event for that case.

| Case | Control | Treatment | Delta | Honest gap assessment |
|---|---:|---:|---:|---|
| fsm-linear-flow | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs explicitly covered the three content assertions. |
| scenes-isolated-flow | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs covered scene lifecycle, isolation, and durable non-global state. |
| dialog-widget-ui | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs used dialog-managed widgets and callbacks rather than an ad-hoc widget protocol. |
| mini-app-launch-security | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs required server-side init-data validation before identity trust. |
| callback-authorization | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs made authorization server-side and stale actions idempotent. |
| payment-lifecycle | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs deferred fulfillment to successful payment and deduplicated charges. |
| webhook-secret | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs authenticated a narrow HTTPS webhook and protected secrets. |
| background-jobs | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs used durable outbox/worker boundaries instead of an in-memory-only guarantee. |
| testing-strategy | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs exercised adverse updates, duplicate payments, bot responses, and storage effects. |
| production-uow-observability | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs coupled the mutation and outbox and supplied recovery diagnostics. |

## fsm-linear-flow

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly used a `StatesGroup`, state-wide cancellation, and non-global FSM storage; the one-point difference comes solely from the empty control retrieval trace.

## scenes-isolated-flow

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly selected scene-style navigation, keyed data to user/chat context, and paired persistent storage with a prohibition on shared mutable state; only retrieval differed.

## dialog-widget-ui

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly used dialog windows and managed toggle, pagination, and confirm widgets, with callbacks operating through dialog-local state; the treatment alone has trace support for the expected references.

## mini-app-launch-security

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly launched with `WebAppInfo`, forwarded signed initialization data, validated it server-side, and rejected client-origin identity as authority; the delta is retrieval-only.

## callback-authorization

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly reloaded server state, checked current moderator authority, kept trusted role data out of callback payloads, and handled stale or repeated actions without a second mutation.

## payment-lifecycle

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly answered pre-checkout promptly, fulfilled only after `successful_payment`, and used stable charge identifiers for idempotency; only the trace-backed retrieval assertion differs.

## webhook-secret

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly required HTTPS, a configured and verified secret token, authenticated acceptance before success, and secret-safe logging; the control has no recorded retrieval paths.

## background-jobs

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly used a transactional outbox, idempotent workers, retries, restart recovery, and observable dead-letter handling, so the measured difference is not a content-assertion gain.

## testing-strategy

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly separated test boundaries and exercised unauthorized callbacks, duplicate payment delivery, real update handling, bot acknowledgements, and persistence effects.

## production-uow-observability

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly made the state transition and outbox atomic and supplied correlation data, structured errors, metrics, trace propagation, and retry/recovery behavior.

## Overall findings

The aggregate scores are control 30/40 and treatment 40/40. All ten points of measured delta come from retrieval: application and gap evidence is 30/30 in each condition, while control retrieval is 0/10 and treatment retrieval is 10/10 under the shared-batch trace rule. The exact deployed model revision was not exposed to this evaluator, and the treatment trace provenance limits claims to shared-context availability rather than per-case retrieval events.
