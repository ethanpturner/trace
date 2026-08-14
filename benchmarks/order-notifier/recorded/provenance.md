# Recorded run for the order-notifier scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording exercises duplicate collapse (DEC-052). One threat carries two mappings to
req-WEBHOOK-001 — the same conclusion drawn once from each supplied document — and
consolidation builds two provisional findings from them. They share a threat and a
requirement, so dedup merges them: the survivor carries the union of both documents'
evidence, the merged finding is retained with `duplicate_of_id`, and a merge record
persists. Exactly one finding reaches the checkpoint and is approved, and the scorecard's
`duplicate_finding_rate` is non-zero for this scenario by design. The replay-handling
silence resolves to the one expected gap.
