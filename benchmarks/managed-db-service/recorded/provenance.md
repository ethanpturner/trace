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

## Re-authored for the IaC parser (#525, DEC-113)

The scenario gained `input/terraform-db.tf.json`, a Terraform JSON declaration of the managed
database with `storage_encrypted: true` and `publicly_accessible: false` stated. The IaC
parser seeds one component and two documented claims from it before the recorded extraction
converts, which shifts the component and claim allocation: the agent's components moved from
`cmp-001`/`cmp-002` to `cmp-002`/`cmp-003` and its claims from `ctx-001..004` to
`ctx-003..006`, and every recorded reference moved with them. `decisions-context.yaml` gained
approvals for the parser's component and both claims — the declared encryption is now
machine-documented evidence beside the prose, which is the scenario's inherited-encryption
point restated by a declaration. Per-prefix counters keep every other identifier stable; the
replay completes with the same expected outcomes.
