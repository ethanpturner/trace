# Recorded run for the missing-docs scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording exercises the explicit missing-documentation path: a one-page note that makes
three requirements applicable and answers none of them. All three mappings are unverified,
every evidence assessment recommends a documentation gap, and consolidation produces the
three expected gaps and nothing else. Zero findings by design (DEC-009): a run that produces
any finding from this input has invented a fact the note does not contain. The finding review
concludes over an empty candidate set, and the report carries the `lim-empty-findings`
limitation.
