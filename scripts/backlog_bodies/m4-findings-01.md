## Context

A Finding means available evidence supports the conclusion that a meaningful security weakness
exists. A `DocumentationGap` means it cannot be determined whether a control exists at all
(`docs/architecture/data-model.md` section 23, "Important distinction"). Collapsing the two is the
failure this project exists to avoid, so the invariant that separates them is enforced in code
rather than in prompt text (`docs/product/design-principles.md` section 7). `DocumentationGap` is
delivered upstream by the Requirement and Control Mapping component; this issue adds the `Finding`
object and the separation invariant that binds the two.

## Scope

- A Pydantic model for `Finding` conforming field for field to `docs/architecture/data-model.md`
  section 21, including every required field: `id`, `assessment_id`, `title`, `summary`,
  `description`, `threat_ids`, `requirement_ids`, `control_mapping_ids`, `affected_component_ids`,
  `affected_asset_ids`, `evidence_ids`, `validation_status`, `severity`, `impact`,
  `recommendation`, `confidence`, `status`, `generated_by`, `created_at`, `updated_at`; and the
  optional `likelihood`, `acceptance_criteria`, `assumptions`, `limitations`, `duplicate_of_id`,
  `reviewer_notes`.
- The `Severity` enum (data-model section 4.5) if it does not already exist. `ObjectStatus`
  (section 4.1), `ConfidenceLevel` (section 4.2) and `ValidationStatus` (section 4.7) are reused
  from upstream rather than redefined.
- Identifier generation follows the scheme fixed in DX-02; the readable prefix is `fnd-`
  (data-model section 2.1).
- The minimum validation rules of data-model section 21 encoded as validators: at least one related
  threat, at least one affected asset or component, at least one applicable requirement or stated
  security expectation, a described security impact, evidence or an explicit low-confidence
  justification, a validation status, and a confidence classification.
- The separation invariant: a `Finding` cannot be constructed whose only support is the absence of
  documentation. The outcome table fixed in DX-08 is the single authority, and the construction path
  consults it rather than reimplementing a second opinion.
- `severity` behaviour follows DX-11. If DX-11 leaves severity to the reviewer, the model accepts
  `unassigned` at construction and the approval gate constrains it later.
- `confidence` follows the model fixed in DX-19.
- `duplicate_of_id` references an existing finding in the same assessment, is not self-referential,
  and does not form a cycle.
- Persistence per DX-04, with retrieval by assessment and by status.

## Acceptance criteria

- [ ] `Finding` exists with every field from `docs/architecture/data-model.md` section 21, with
      matching requiredness and types.
- [ ] A `Finding` missing any of the six minimum-validation-rule elements is rejected with an error
      naming the missing element.
- [ ] A regression test named for DEC-009 constructs the exact failure case — a candidate whose sole
      support is that the documentation does not mention a control — and asserts that it cannot
      become a `Finding`, and that the correct outcome is a `DocumentationGap` or a `Question`.
- [ ] A `Finding` citing an evidence identifier that does not resolve is rejected.
- [ ] `duplicate_of_id` pointing at a nonexistent finding, at itself, or forming a cycle is rejected.
- [ ] `validation_status` accepts only the six values in data-model section 4.7.
- [ ] Round-trip persistence: save, reload, compare equal, including every optional field.
- [ ] Fixture tests derived from `demo/forgeflow/forgeflow-scenario.md` section 22 assert that each
      of the ten listed rejected claims fails the minimum criteria on the evidence available.
- [ ] `uv run pytest` passes with no provider credential configured. This module makes no model call.
- [ ] `uv run mypy` passes in strict mode over the new module and its tests.

## Out of scope

- `DocumentationGap`, delivered by the Requirement and Control Mapping component.
- `EvidenceAssessment`, delivered by the Evidence Validation component.
- Severity assignment logic, which DX-11 settles.
- Deduplication and merging, which are consolidation concerns.
- The review workflow and the approval gate.

## References

- `docs/architecture/data-model.md` — section 2.1, section 4.1, section 4.2, section 4.5,
  section 4.7, section 21, section 23, section 32, section 40
- `docs/architecture/agent-design.md` — section 16 ("Finding creation rule")
- `docs/architecture/current-architecture.md` — section 2.1, section 5.9, section 5.11
- `docs/architecture/decision-log.md` — DEC-006, DEC-009
- `demo/forgeflow/forgeflow-scenario.md` — section 19, section 22
- `docs/product/design-principles.md` — section 7, section 9
