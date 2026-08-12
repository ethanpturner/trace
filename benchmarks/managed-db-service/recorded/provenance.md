# Recorded run for the managed-db-service scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording exercises the zero-finding path through the inherited-control route: the
encryption-detail false-positive class in `../expected/expected-rejections.yaml`. The
req-DATA-001 mapping proposes the platform's encryption as an inherited control, concludes
satisfied on the documented at-rest and transport encryption, and records the at-rest and
application-cryptography conclusions as suppressed by the catalog's `common_false_positives`
entry. The one expected documentation gap (req-DATA-002) comes from an unverified mapping
whose evidence assessment recommends a gap: the documents establish that confidential metrics
are persisted and say nothing about retention. The metrics-API authentication claim in
REJ-MD-03 is not mapped at all — no passage addresses it, and an unverified mapping would
manufacture a second gap the truth set does not expect. The finding review concludes over an
empty candidate set, and the report carries the `lim-empty-findings` limitation the assembler
requires of a zero-finding run.
