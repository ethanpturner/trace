# Recorded run for the contradictory-docs scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording exercises the scenario's finding path — extraction, threat, an unmet
mapping, a supporting evidence assessment, and the approved finding — which is what the
harness scores as `false_negative_rate`. The documentation gap, question, and rejection in
`../expected/` document the complete expected output; a richer recording or a live run
produces the gap as well. The finding is the scored headline and matches its truth entry
exactly.
