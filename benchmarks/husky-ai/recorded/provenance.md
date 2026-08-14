# Recorded run for the husky-ai scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording carries all nine threats of the OWASP-derived truth set and exercises the full
outcome truth: two unmet mappings whose supported evidence becomes the two expected findings
(req-SECRET-001 on the API-key storage placement, req-AUTH-002 on the password-only
experimental boundary), and two unverified mappings whose evidence assessments recommend a
documentation gap (req-CICD-001, req-TPI-002). Six of the nine threats map to no requirement
and produce no output — the source list is threat truth, not finding truth, and most of its
entries rest on preconditions the documents leave open. The unmet mappings address the
catalog's `common_false_positives` entries by name (DEC-025), and the security notes'
completeness statement is extracted as a documented claim because FND-HA-01's
documented-negative reading rests on it.
