# Recorded run for the invoice-agent scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording exercises the full outcome truth set: five threats, three unmet mappings whose
supported evidence becomes the three expected findings (req-AI-001, req-AI-002, req-LOG-001),
and two unverified mappings whose evidence assessments recommend a documentation gap, which
consolidation builds as the two expected gaps (req-SECRET-001, req-AUTHZ-001). The expected
questions pair with the gaps in `../expected/` and are not produced here: the clarifying
question metric is reserved, and the gap route asserts the least. Every citation resolves to
an evidence reference the input document actually mints; the unmet mappings address the
catalog's `common_false_positives` entries by name, which the mapping validation checks
structurally (DEC-025).
