## Context

Only approved findings may appear in the final findings section
(`docs/architecture/agent-design.md` section 18, "Workflow rule"), and an approved finding is held
to a higher bar than a provisional one: reviewer approval, supported or partially supported
evidence, a clear distinction from a documentation gap, and actionable remediation or acceptance
criteria (`docs/architecture/data-model.md` section 21). Rejected candidates are preserved for
evaluation without being displayed as results
(`docs/product/design-principles.md` section 9). This issue makes both of those properties
deterministic rather than conventional.

## Scope

- A deterministic approval gate that runs on every transition of a `Finding` to `approved` and
  enforces the four conditions in data-model section 21, against the evidence threshold fixed in
  DX-08.
- Where a reviewer approves a finding that fails one of the conditions, the override is explicit: the
  gate refuses the silent path, and the reviewer supplies a rationale that is stored on the
  `ReviewerDecision`. An override is recorded, never inferred.
- A finding whose `validation_status` is `unsupported` or `contradicted` cannot reach `approved`
  without such an override.
- A finding that would be indistinguishable from a documentation gap cannot reach `approved`. This is
  the last enforcement point for the DEC-009 boundary before the conclusion becomes official.
- Rejected, deferred and superseded candidates are retained with their reasons and are queryable for
  evaluation, and are excluded from every approved-set query.
- A single authoritative accessor for the approved set, used by report generation, rendering and
  evaluation, so that no consumer assembles its own idea of what was approved.
- `Assessment.status` transitions to reflect that the finding checkpoint is complete.

## Acceptance criteria

- [ ] A finding lacking a linked `ReviewerDecision` cannot be persisted with status `approved`.
- [ ] A finding with `validation_status` of `unsupported` or `contradicted` is refused approval
      unless an override rationale is supplied; both paths are tested.
- [ ] Every override is recorded on the `ReviewerDecision` and is retrievable afterwards.
- [ ] A finding without a recommendation or acceptance criteria is refused approval.
- [ ] Rejected and deferred candidates are retained, carry their reason, and are absent from the
      approved-set accessor.
- [ ] The approved-set accessor is the only path used by report generation, rendering and
      evaluation; a test asserts that each consumer calls it rather than querying findings directly.
- [ ] An assessment in which nothing is approved returns an empty approved set and completes
      successfully. Zero approved findings is a valid terminal state.
- [ ] The gate makes no model call.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The reviewer interface and the dispositions themselves.
- Report content and formatting.
- Metrics computed over acceptance and rejection, which the evaluation component owns.

## References

- `docs/architecture/data-model.md` — section 4.1, section 4.7, section 5, section 21
  ("An approved finding should generally require"), section 25
- `docs/architecture/agent-design.md` — section 18 ("Workflow rule"), section 19 ("Inputs")
- `docs/architecture/current-architecture.md` — section 5.12, section 8, section 12
  ("Generated-output boundary")
- `docs/architecture/decision-log.md` — DEC-005, DEC-009
- `docs/product/design-principles.md` — section 7, section 9, section 16
- `docs/product/roadmap.md` — Stage 4, "Exit criteria"
