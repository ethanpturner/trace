## Context

`docs/architecture/data-model.md` section 19 calls `ControlMapping` "one of the most
important objects in Trace because it prevents the application from jumping directly from
a requirement to a finding." Section 18 defines `Control`. Both sit in the initial
implementation priority at section 40, items 13 and 14.

One thing is undefined across the whole corpus: no document says which node creates
`Control` objects. Context Extraction identifies "Existing controls"
(`docs/architecture/agent-design.md` section 7), the Mapping Agent outputs "New or refined
Control objects" (section 12), and Mapping Validation must "Confirm control identifiers
exist" (section 13). `Control` is also the only one of these objects with no
`generated_by` field, so its provenance is currently unrecordable. That ownership question
is decided and recorded inside this issue.

## Scope

- Add `src/trace_ai/domain/models/control.py` with a `Control` model per section 18.
  Promote the prose value lists to closed enumerations: `ControlType` as `implemented`,
  `inherited`, `compensating`, `planned`, `recommended`; `ImplementationStatus` as
  `implemented`, `partially_implemented`, `claimed`, `unknown`, `absent`,
  `not_applicable`. Reuse `ValidationStatus` from section 4.7.
- Add `src/trace_ai/domain/models/control_mapping.py` with a `ControlMapping` model per
  section 19. Promote its value lists to closed enumerations: `ApplicabilityStatus` as
  `applicable`, `conditionally_applicable`, `not_applicable`, `unknown`;
  `SatisfactionStatus` as `satisfied`, `partially_satisfied`, `unverified`, `unmet`,
  `not_applicable`.
- Represent `inheritance_scope` per the DX-15 decision rather than leaving it a free
  string.
- Add `ControlProposal` and `ControlMappingProposal` variants omitting every
  application-owned field, following the pattern set by the threat proposal schema.
- Make `applicability_reason` required and non-empty. Section 12 makes "Requirements are
  applied without an applicability rationale" a failure condition, and section 13 requires
  the validation node to enforce rationales.
- Decide and record control ownership: which node creates a `Control`, how a control
  claimed during context extraction becomes a `Control` row, and whether `Control` needs a
  `generated_by` field. Adding a field to a data-model object is a design change requiring
  a decision-log entry; DEC-011 is the worked example of that process, and
  `docs/architecture/data-model.md` section 18 is updated if the answer is yes.

## Acceptance criteria

- [ ] `ControlMapping` accepts the section 19 field set and rejects any applicability or
      satisfaction value outside the enumerated sets.
- [ ] `applicability_reason` is required and rejects empty or whitespace-only text.
- [ ] `ControlMappingProposal` rejects a payload containing `id`, `assessment_id`,
      `generated_by`, or `reviewer_status`.
- [ ] A mapping with `satisfaction_status: satisfied` and an empty `evidence_ids` is
      rejected at the model level. Section 12 makes "Unverified controls are marked
      implemented" a failure condition, and the schema enforces the structural half of it.
- [ ] A `Control` with `implementation_status: implemented` and empty `evidence_ids` is
      likewise rejected.
- [ ] A `Control` with `control_type: inherited` carries an inheritance scope in the DX-15
      representation, and a test asserts that an inherited control with unstated scope is
      distinguishable from one with documented scope rather than collapsing to the same
      value.
- [ ] A test asserts that `satisfaction_status: unverified` with empty `evidence_ids` is
      valid. Absence of evidence is the expected resolution under DEC-009 and must not be
      a schema error.
- [ ] A decision-log entry records which node creates `Control` objects and how a
      context-extracted control claim becomes one.
- [ ] If `generated_by` is added to `Control`, the same entry records it as a data-model
      change and `docs/architecture/data-model.md` section 18 is updated to match.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The evidence threshold separating `unverified`, `unmet`, and `satisfied`. DX-08 decides
  it; this issue enforces structure only.
- The mapping agent and the mapping validation node.
- `Finding`, which is created by Finding Consolidation in M4.
- Enterprise control inheritance catalogs, deferred by `docs/product/roadmap.md` under
  Later Stage.

## References

- `docs/architecture/data-model.md` section 18 (Control — Fields; Control-type values;
  Implementation-status values), section 19 (ControlMapping — Fields; Applicability-status
  values; Satisfaction-status values; Important rule), section 4.7 (ValidationStatus),
  section 39 question 6, section 40 (Initial Implementation Priority items 13–14)
- `docs/architecture/agent-design.md` section 7 (Context Extraction — Responsibilities),
  section 12 (Mapping Agent — Outputs; Prohibited operations; Failure conditions),
  section 13 (Mapping Validation Node)
- `docs/architecture/decision-log.md` DEC-006, DEC-009, DEC-011
- `demo/forgeflow/forgeflow-scenario.md` section 12 (Existing and Inherited Controls)
