# The sweep closed: fifteen of fifteen live, the control arm real, and what the money bought

The #484 live sweep finished today. Every registered scenario now carries a live-captured
recording that replays offline, every scenario has its three live baselines beside it, and the
comparison that carries the project's thesis is live-versus-live for the first time. Eight
scenarios were captured across three waves (contradictory-docs, invoice-agent,
managed-db-service; order-notifier, nightly-reconciler, parcel-platform; reply-tuner,
translation-gateway), live baselines were backfilled for the five scenarios captured earlier,
and the corpus prose that said "the other thirteen recordings are authored" stopped being true
and was corrected in the same commits that made it false.

## What the measurements say

Precision is the pipeline's differential, measured rather than asserted: zero spurious findings
across all thirteen sweep captures, against 45 for the generic baseline over the same fifteen
scenarios — seventeen of them on oidc-portal's zero-finding truth set alone. Two findings
matched exactly with severity concordance (reply-tuner's training-data finding, parcel-platform's
admin-path finding, both approved at high with DEC-023 title edits narrowing exported claims to
the evidenced deficiency). Both zero-finding scenarios completed their intended paths.
`evidence_assessment_coverage` read 1.0 on every sweep capture — the DEC-134 batching fix is now
measured working on thirteen live runs, and the pre-batching funnel failure narrows to the two
opus captures that diagnosed it.

Recall is the measured weakness, and the sweep bought the diagnosis, not just the number. The
misses are lens divergences with coverage 1.0: expected findings surfacing as questions or gaps
instead of candidates (order-notifier's unsigned intake, parcel-platform's notification logging),
the DEC-066 fingerprint splitting a substantively matched finding on component-name string
inequality (translation-gateway), and — the sharpest single observation of the sweep —
contradictory-docs' checkpoint-1 contradiction resolution failing to reach the downstream
lenses, which re-asked the resolved question three times and filed the subject as a gap. That
last one is a pipeline-shape defect, filed as its own issue. The gap layer over-mints where gaps
are expected (11 against 1, 17 against 2). All of it is #589's reconciliation material and is
recorded scenario by scenario in provenance.

One honest row cuts the other way: on order-notifier, all three one-call baselines matched the
finding the pipeline missed. The comparison exists to measure that difference too.

## What the operations taught

The run-operability bundle shipped yesterday earned its place the same day. The key's monthly
credit limit — not an outage — stopped the first wave at 402s; the parked captures preserved
every staged response and resumed for zero re-spend once the limit was raised, exactly the
posture the response journal was built to prove. `trace runs status` and the DEC-138 narration
located every stall and death from outside the process. The DEC-091 rebuild recovered two
harness-side process kills on parcel-platform, replaying up to 26 staged envelopes free each
time. Fork self-wake after backgrounded stages proved unreliable; a coordinator watchdog on a
25-minute cadence plus targeted pings became the working protocol, and each silent gap cost
minutes of wall clock and nothing else.

Sweep economics, final: roughly $27 for eight full captures, twenty-four wave baselines, and
fifteen backfill baselines, against the ~$63 authorized — the per-scenario median held near
$3.30, with parcel-platform's large architecture the outlier at $7.70. Total corpus cost for
all thirteen gateway captures across all sessions: ~$50.

## Open next

- #589 truth-set reconciliation, now carrying the sweep's full evidence: the lens divergences,
  the fingerprint splits, the gap over-minting, and the component-name matching question the
  baselines raise.
- The checkpoint-1 propagation defect (new issue) and #588's re-capture of forgeflow and
  husky-ai under the batched shape.
- DEC-077 stability protocol on the sweep model (new issue) — variance is the differentiating
  honest number and it still describes one scenario on the old model.
- #601 scorecard v3: the stratified readout the pooled numbers now visibly need, unblocked at
  last. Then #574's public benchmark package, shipping with these numbers inside.
