# Recorded run for the crypto-wallet scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording exercises the hedged-statement path the scenario exists for: a zero-finding
assessment (DEC-013) in which the source's two unconfirmed assumptions surface as outputs
rather than conclusions. The wallet-file mapping (req-DATA-001, thr-001) is unverified and
its evidence assessment recommends `downgrade_to_question`, so consolidation produces the
wallet-encryption question; the exchange-store mapping (req-DATA-001, thr-002) is unverified
with a `documentation_gap` recommendation, producing the one expected gap, whose requested
evidence carries the TLS re-verification the document itself marks outstanding. The two
hedged statements are extracted as documented claims carrying the document's own
qualification, per the reviewer notes. The finding review concludes over an empty candidate
set, and the report carries the `lim-empty-findings` limitation.
