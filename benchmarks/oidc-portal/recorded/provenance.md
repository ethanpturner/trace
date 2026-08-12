# Recorded run for the oidc-portal scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording exercises the zero-finding path the scenario exists for: a successful
assessment that approves no findings (DEC-013). The delegated-authentication conclusions a
generic review most often asserts here — the local-password-policy false-positive class in
`../expected/expected-rejections.yaml` — are recorded as suppressed on the mappings: the
req-AUTH-001 mapping is satisfied by the documented delegation with the password-policy
conclusion suppressed by the catalog's `common_false_positives` entry, and the req-AUTH-002
mapping is not applicable under the requirement's own `non_applicable_conditions` entry. The
one expected documentation gap (req-NET-001) comes from an unverified mapping whose evidence
assessment recommends a gap: the reachability restriction is stated, its enforcement is not.
The finding review concludes over an empty candidate set, and the report carries the
`lim-empty-findings` limitation the assembler requires of a zero-finding run.
