# Recorded run for the translation-gateway scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording exercises the third-party-integration path: two unmet mappings whose
supported evidence becomes the two expected findings — the documented absence of any
retention or secondary-use agreement with the translation provider (req-TPI-001), and the
admittedly over-scoped workspace token (req-AUTHZ-002) — and one unverified mapping whose
assessment recommends a gap for token custody (req-SECRET-001). The boundary the truth set
grades is between the relationship and the provider: nothing in the recording asserts what
the provider does with submitted text, which is unknown and stays out of the findings.
