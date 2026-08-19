# Assertion-level evaluation summary

Protocol: composite evaluator `evaluator-20260820-composite-r7` scored the assertions recorded in
[`assertion-results.json`](assertion-results.json), using
[`retrieval-trace.json`](retrieval-trace.json) exclusively for retrieval and
exact case-output excerpts for application and gap evidence.
[`run-manifest.json`](run-manifest.json) records task identities, context rules,
the base skill commit, exact working-bundle hash, limitations, and artifact
hashes. The original ten treatment cases use a shared-batch self-report; the two
presentation cases use isolated-runner self-reports against frozen bundle
SHA-256 `cf25cd24f78fc85cf4698caaeb8d54281752afb2ee91e3c5af516546ead2b150`.
None is platform-signed, so a retrieval pass establishes recorded path
availability, not an independently attested read event.

| Case | Control | Treatment | Delta | Honest gap assessment |
|---|---:|---:|---:|---|
| fsm-linear-flow | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs explicitly covered the three content assertions. |
| scenes-isolated-flow | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs covered scene lifecycle, isolation, and durable non-global state. |
| dialog-widget-ui | 3/4 | 4/4 | +1 | Only the control retrieval assertion failed; both outputs used dialog-managed widgets and callbacks rather than an ad-hoc widget protocol. |
| native-presentation-anti-slop | 1/8 | 8/8 | +7 | The control had a usable hierarchy, but no complete brief/spec/state contract, stable navigation, or coherent semantic icon system. |
| custom-emoji-capability-selection | 0/5 | 5/5 | +5 | The control avoided invented IDs but misstated channel capability and omitted licensing, provenance, coherence locking, and deterministic fallbacks. |
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

## native-presentation-anti-slop

The control scored 1/8 and the treatment scored 8/8, a seven-point behavioral improvement rather than a retrieval-only difference. The final treatment supplied a complete PresentationBrief, ScreenSpec, explicit decisions for all six canonical states, stable edit-in-place navigation, semantic icon tokens under one pack lock, a decorative-only banner policy, and fallback-safe labels.

## custom-emoji-capability-selection

The control scored 0/5 and the treatment scored 5/5. The treatment correctly separated owner-Premium and channel capabilities, required licensed provenance and verified IDs, kept unresolved registry entries disabled, and made the model choose semantic tokens while deterministic code performs coherent pack-first resolution and fallbacks.

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

The aggregate scores are control 31/53 and treatment 53/53. The original ten engineering cases contribute a ten-point retrieval-only delta; the two new presentation and custom-emoji cases contribute twelve additional points through stricter routing, application, and gap assertions. The exact deployed model revision was not exposed, and all retrieval paths remain runner self-reports, so the evidence demonstrates the recorded bundle's behavior without claiming platform-signed or byte-for-byte reproducibility.
