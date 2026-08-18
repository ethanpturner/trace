# Recorded run for the nightly-reconciler scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1,
requirements catalog 0.3, org-controls catalog 0.2, report template report-v1.

## Scope

This recording exercises the org-controls path end to end (#568, DEC-122). The parser
verifies `input/workspace-org-controls.yaml` against org-controls catalog 0.2 and seeds two
documented claims — `secrets-vault` and `managed-db-encryption`, each carrying its statement,
mechanism, and DEC-122 references — before the recorded extraction converts, so the agent's
claims sit at `ctx-003..006` behind the parser's `ctx-001..002`. Both parser claims are
approved at checkpoint 1 through the recorded decisions.

The zero-finding outcome is the scenario's point: the req-SECRET-001 mapping is satisfied
with the unmanaged-credential conclusion suppressed by the asserted secrets-vault control,
and the req-DATA-001 mapping is satisfied with the unencrypted-at-rest conclusion suppressed
by the asserted managed-db-encryption control — both suppressions resting on organizational
facts with catalog provenance rather than on requirements-catalog entries. The one expected
documentation gap (req-NET-001) comes from an unverified mapping whose evidence assessment
recommends a gap: the billing database's reachability restriction is stated, its enforcement
is not. The finding review concludes over an empty candidate set, and the report carries the
`lim-empty-findings` limitation the assembler requires of a zero-finding run.

Live baselines await the keyed capture step (DEC-100); none are authored here.
