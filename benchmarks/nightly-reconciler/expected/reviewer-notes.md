# Nightly Reconciler reviewer notes

## Construction method

An original small architecture authored for this project (design-principles section 19), built
to exercise the org-controls assertion (#568, DEC-122) cleanly: a system whose documents are
silent about credential custody and database encryption, both of which the organization
provides. The truth set derives from `input/system-overview.md`, the workspace assertion in
`input/workspace-org-controls.yaml`, and org-controls catalog 0.2, and nothing else. Both
rejections cite the asserted control by `(name, catalog version)`; the `organizational_control`
mechanism is DEC-122's addition to the negative-expectation vocabulary, beside the
requirements-catalog mechanisms the earlier scenarios use.

Single annotator (the project author). In place of inter-annotator agreement, the set was
re-derived from the inputs after an interval without consulting the first pass; the two
rejections, the empty finding set, and GAP-NR-01 were reproduced with the same requirements.
No count is declared (DEC-028).

## Why zero findings is the correct output

The two conclusions a generic review reaches here — unmanaged credentials, unencrypted billing
data — each rest on a silence the organization's asserted controls answer: the credential is
provisioned through the standard workload deployment (the secrets-vault control's condition),
and the database is the platform's managed relational service (the managed-db-encryption
control's condition). An organizational control asserts existence only (DEC-115); whether this
system inherits it was the assessment's ordinary work, decided at checkpoint 1 where the
reviewer approved both parser-seeded claims. GAP-NR-01 is the one genuinely undetermined item:
the reachability restriction is stated, its enforcement is not.

## The distinction this scenario adds

oidc-portal's suppressions rest on requirements-catalog entries (`common_false_positives`,
`non_applicable_conditions`); managed-db-service's rest on the catalog's phrasing discipline.
This scenario's suppressions rest on *asserted organizational facts* verified against the
central org-controls catalog — the third mechanism, and the one the roadmap's section 10 claim
("approved organizational context prevents a false conclusion") is measured by.

## Deliberately not authored

`expected-context.yaml` and `expected-threats.yaml` are not authored for this scenario. The
harness scores findings, gaps, questions, and mappings; those are authored here. Live
baselines await the keyed capture step (DEC-100). Stating the omission keeps it a decision.
