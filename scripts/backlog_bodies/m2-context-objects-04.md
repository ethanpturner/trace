## Context

`SystemContext` is the approved architecture baseline every later stage is designed to reason from — `docs/architecture/current-architecture.md` section 5.6 states that threat analysis should reason from the approved context baseline rather than repeatedly reinterpreting all source documents. It holds identifier lists rather than embedded objects, and it carries `approved_at`, `approved_by`, and an integer `version`, which are the fields that make the DEC-005 checkpoint observable in data rather than only in control flow (`docs/architecture/data-model.md` section 9).

## Scope

- `src/trace_ai/domain/models/system_context.py` — `SystemContext` with the section 9 field list: `assessment_id`, `system_name`, `system_purpose`, `business_criticality`, `environment`, `deployment_model`, `data_classifications`, `context_claim_ids`, `component_ids`, `asset_ids`, `data_flow_ids`, `trust_boundary_ids`, `approved_at`, `approved_by`, `version`. If the Actor decision in the architecture-objects issue retains Actor, `actor_ids` is added here and the data-model change is recorded.
- Resolve and document the identity question. Section 9 gives `SystemContext` no `id` field and no `status`, unlike every other object in sections 10 through 15. It is therefore keyed by `(assessment_id, version)`. State that in the module docstring and align it with the persistence and schema-versioning scheme settled in DX-04.
- `is_approved`, a derived property that is true when both `approved_at` and `approved_by` are set. Downstream gating reads this property, never a configuration flag; DX-01 settles the configurability question and this property is the shape that decision takes in code.
- `validate_against(objects)`, the referential-integrity helper the Context Validation node calls: every identifier in the lists resolves to a real object of the matching type, and every `DataFlow.source_component_id`, `destination_component_id`, and `crosses_trust_boundary_ids` entry appears in this context's own lists.
- A `next_version()` constructor producing the successor revision, so revision creation has one implementation rather than being reassembled at each call site. Whether a reviewer edit uses it is DX-16's decision; this issue provides the mechanism.

## Acceptance criteria

- [ ] `SystemContext`'s field set matches `data-model.md` section 9 exactly, with a test that fails on drift.
- [ ] `version` is a required integer and the first extracted context is version 1.
- [ ] `approved_at` and `approved_by` are optional, and `is_approved` is false when either is absent.
- [ ] `validate_against` reports every dangling identifier by list name and value rather than raising on the first one.
- [ ] A data flow whose source component is absent from `component_ids` is reported as an error.
- [ ] A trust boundary referenced by `DataFlow.crosses_trust_boundary_ids` but absent from `trust_boundary_ids` is reported as an error.
- [ ] The `(assessment_id, version)` key is stated in the module docstring and matches the DX-04 persistence scheme.
- [ ] `next_version()` returns a context with `version` incremented and `approved_at` and `approved_by` cleared, so a successor revision cannot inherit an approval it never received.
- [ ] Round-tripping a `SystemContext` through JSON preserves list ordering.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Deciding whether a reviewer edit creates a new revision or mutates the current one. That is `data-model.md` section 39 open question 10 and is settled in DX-16.
- Persisting the object, which belongs to the M1 persistence issue.
- Threat, control, mapping, and finding identifier lists. `data-model.md` section 31 keeps those on the workflow state rather than on `SystemContext`.
- The approval action itself, which belongs to the context review issues.

## References

- `docs/architecture/data-model.md` section 9 (SystemContext), section 31 (Assessment State), section 39 open question 10
- `docs/architecture/current-architecture.md` section 5.6 (Context Review), section 8 (Checkpoint 1: Context approval)
- `docs/architecture/agent-design.md` section 9 (Human Context Review — Output; Workflow rule)
- `docs/architecture/decision-log.md` DEC-005, DEC-006
