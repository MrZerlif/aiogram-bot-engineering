# Assertion-level evaluation summary

Protocol: composite evaluator `evaluator-20260820-composite-r8` scored the assertions recorded in
[`assertion-results.json`](assertion-results.json), using
[`retrieval-trace.json`](retrieval-trace.json) exclusively for retrieval and
exact case-output excerpts for application and gap evidence.
[`run-manifest.json`](run-manifest.json) records task identities, context rules,
the base skill commit, exact working-bundle hash, limitations, and artifact
hashes. Eight unaffected engineering cases retain their historical shared-batch
self-report, the native-presentation case retains its prior isolated report, and
the three affected dialog/custom-emoji/webhook cases use one fresh shared-batch
report against frozen bundle SHA-256
`03b1002d0efd7c878fd189ff74bc101db078ff62848473d56cde91f23bde4ba2`.
None is platform-signed, so a retrieval pass establishes recorded path
availability, not an independently attested read event.

| Case | Control | Treatment | Delta | Honest gap assessment |
|---|---:|---:|---:|---|
| fsm-linear-flow | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs explicitly covered the three content assertions. |
| scenes-isolated-flow | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs covered scene lifecycle, isolation, and durable non-global state. |
| dialog-widget-ui | 1/5 | 5/5 | +4 | The control supplied managed widgets, but did not make ownership exclusive or complete stale recovery with both exceptions and `ShowMode.SEND`. |
| native-presentation-anti-slop | 1/8 | 8/8 | +7 | The control had a usable hierarchy, but no complete brief/spec/state contract, stable navigation, or coherent semantic icon system. |
| custom-emoji-capability-selection | 0/7 | 7/7 | +7 | The control avoided invented IDs but missed channel capability, licensing/provenance, coherence locking, bundled offline validation, and the full rejection gate. |
| mini-app-launch-security | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs required server-side init-data validation before identity trust. |
| callback-authorization | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs made authorization server-side and stale actions idempotent. |
| payment-lifecycle | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs deferred fulfillment to successful payment and deduplicated charges. |
| webhook-secret | 1/5 | 5/5 | +4 | The control authenticated and durably stored updates, but omitted the explicit aiogram background-ack setting, 55-second caveat, per-bot polling bound, and complete shutdown distinction. |
| background-jobs | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs used durable outbox/worker boundaries instead of an in-memory-only guarantee. |
| testing-strategy | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs exercised adverse updates, duplicate payments, bot responses, and storage effects. |
| production-uow-observability | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs coupled the mutation and outbox and supplied recovery diagnostics. |

## fsm-linear-flow

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly used a `StatesGroup`, state-wide cancellation, and non-global FSM storage; the one-point difference comes solely from the empty control retrieval trace.

## scenes-isolated-flow

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly selected scene-style navigation, keyed data to user/chat context, and paired persistent storage with a prohibition on shared mutable state; only retrieval differed.

## dialog-widget-ui

The control scored 1/5 and the treatment scored 5/5. Both used dialog-managed widgets, but only the treatment explicitly gave `aiogram-dialog` exclusive ownership of the flow and centrally recovered both `UnknownIntent` and `UnknownState` with callback acknowledgement, `RESET_STACK`, and `ShowMode.SEND`.

## native-presentation-anti-slop

The control scored 1/8 and the treatment scored 8/8, a seven-point behavioral improvement rather than a retrieval-only difference. The final treatment supplied a complete PresentationBrief, ScreenSpec, explicit decisions for all six canonical states, stable edit-in-place navigation, semantic icon tokens under one pack lock, a decorative-only banner policy, and fallback-safe labels.

## custom-emoji-capability-selection

The control scored 0/7 and the treatment scored 7/7. The treatment correctly separated owner-Premium and channel capabilities, required licensed provenance and verified IDs, used the bundled Draft 2020-12 schema plus semantic validator, kept unresolved records disabled, and made the model choose semantic tokens while deterministic code performs coherent pack-first resolution and fallbacks.

## mini-app-launch-security

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly launched with `WebAppInfo`, forwarded signed initialization data, validated it server-side, and rejected client-origin identity as authority; the delta is retrieval-only.

## callback-authorization

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly reloaded server state, checked current moderator authority, kept trusted role data out of callback payloads, and handled stale or repeated actions without a second mutation.

## payment-lifecycle

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly answered pre-checkout promptly, fulfilled only after `successful_payment`, and used stable charge identifiers for idempotency; only the trace-backed retrieval assertion differs.

## webhook-secret

The control scored 1/5 and the treatment scored 5/5. Both authenticated HTTPS traffic, but only the treatment set `handle_in_background=False`, preserved a committed inbox/outbox boundary within aiogram's roughly 55-second wait, declared a positive downstream-sized per-bot polling bound, and separated that cap from graceful draining and durability.

## background-jobs

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly used a transactional outbox, idempotent workers, retries, restart recovery, and observable dead-letter handling, so the measured difference is not a content-assertion gain.

## testing-strategy

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly separated test boundaries and exercised unauthorized callbacks, duplicate payment delivery, real update handling, bot acknowledgements, and persistence effects.

## production-uow-observability

The control scored 3/4 and the treatment scored 4/4. Both answers explicitly made the state transition and outbox atomic and supplied correlation data, structured errors, metrics, trace propagation, and retry/recovery behavior.

## Overall findings

The aggregate scores are control 27/57 and treatment 57/57. Eight unaffected engineering cases contribute an eight-point retrieval-only delta; the prior native-presentation case contributes seven points, and the three freshly rerun dialog/custom-emoji/webhook cases contribute fifteen points through stricter routing, application, and gap assertions. The exact deployed model revision was not exposed, and all retrieval paths remain runner self-reports, so the evidence demonstrates the recorded bundle's behavior without claiming platform-signed or byte-for-byte reproducibility.
