## Context

`docs/architecture/data-model.md` section 40 names Assessment and AssessmentConfiguration as
the first two objects to implement, and sections 5 and 6 are authoritative for their fields
and types. The Assessment is the parent of every other object in the model — sixteen objects
carry an `assessment_id` — so the loader and the evidence model both wait on it.
`docs/architecture/current-architecture.md` section 12 names the assessment-data boundary:
data from one assessment must not contaminate another.

**DX-01 is resolved.** DEC-012 removed `require_context_review` and `require_finding_review`
from AssessmentConfiguration. The checkpoints are workflow-graph nodes, not runtime
conditionals, so this object carries no setting that governs them and must not acquire one.

**Still blocked on DX-05** (model provider and abstraction), which determines what
`model_profile` may contain before a provider is selected. It is a required field, so it
cannot be implemented by guessing.

## Scope

- Add `src/trace_ai/domain/assessment.py` with `Assessment` and `AssessmentConfiguration`,
  both deriving from `DomainModel`.
- `AssessmentConfiguration`, exactly as data-model.md section 6 types it: `model_profile`
  (required), `threat_methodology` (required), `maximum_model_calls` (optional),
  `maximum_cost` (optional, `Decimal`), `maximum_retries_per_node` (required),
  `retain_debug_artifacts` (required), `enable_external_tracing` (required),
  `evidence_threshold` (required).
- `Assessment`, exactly as section 5 types it: `id`, `name`, `description`, `status`
  (`ObjectStatus`), `created_at`, `updated_at`, `created_by`, `architecture_version`,
  `data_model_version`, `workflow_version`, `requirements_catalog_version`, `configuration`,
  `active_workflow_run_id`, `final_report_path`, `tags`.
- Record in the class docstring that this object deliberately carries no checkpoint setting,
  citing DEC-012, so a later reader adding one finds the reasoning first. `extra="forbid"`
  makes a reintroduced field fail validation rather than pass silently.
- Use `Decimal` for `maximum_cost`, not `float`. Section 6 types it `decimal`, section 27
  types `estimated_cost` the same way, and a cost limit compared through binary floating point
  is wrong exactly at the boundary where it matters.
- Set `maximum_retries_per_node` to default to 2, matching the default retry policy in
  `docs/architecture/agent-design.md` section 26.
- Apply whatever DX-05 decides for `model_profile`, and record in the field docstring that it
  does not select a provider or a model.
- Add a `new_assessment(...)` factory that stamps `id`, `created_at`, `updated_at`, and the
  three required version fields, so no caller assembles them by hand.
- Add `tests/unit/test_assessment.py`.

## Acceptance criteria

- [ ] Every field in data-model.md sections 5 and 6 is present with the documented type and
      required/optional status. The data-model conformance guard covers this; a failure there
      is a failure here.
- [ ] A field not listed in sections 5 or 6 is rejected.
- [ ] `AssessmentConfiguration` has no `require_context_review` or `require_finding_review`
      field, and a test asserts that constructing one with either is rejected, with a
      docstring naming DEC-005 and DEC-012. The checkpoints are not configurable, so the
      absence is the behaviour under test.
- [ ] `maximum_cost` accepts `Decimal("5.00")` and preserves it exactly; a test asserts the
      value does not pass through `float`.
- [ ] `status` accepts only `ObjectStatus` members.
- [ ] `updated_at` is not earlier than `created_at`.
- [ ] `created_at` and `updated_at` are timezone-aware.
- [ ] The example values in data-model.md section 5 (`asm-001`, `status: pending_review`,
      `architecture_version: "0.1"`, three tags) and section 6 construct successfully as
      written.
- [ ] Constructing an `Assessment` requires no environment variable, no `.env`, and no
      network.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Persisting an Assessment or looking one up. That is the assessment service issue.
- `SystemContext` (section 9) and the context objects, which belong to the context-extraction
  milestone.
- Severity calculation, evidence thresholds, and anything `evidence_threshold` will later
  govern; DX-08 owns that.
- Assessment deletion and retention (section 36).

## References

- `docs/architecture/data-model.md` sections 5 (Assessment), 6 (AssessmentConfiguration),
  4.1 (ObjectStatus), 27 (`estimated_cost` type precedent), 40
- `docs/architecture/decision-log.md` DEC-004, DEC-005, DEC-006, and DX-01 and DX-05 once
  recorded
- `docs/architecture/agent-design.md` section 26 (Retry Policy)
- `docs/architecture/current-architecture.md` sections 8 (Human-in-the-Loop Checkpoints), 12
- `docs/product/roadmap.md`, Stage 1, "Core application models"
