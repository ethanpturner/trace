## Context

Reviewer edits, approvals, and rejections are data, not side effects. `docs/architecture/data-model.md` section 2.5 states that reviewer actions should be recorded rather than silently overwriting generated content, because they support auditability, evaluation, and workflow tuning. `ReviewerDecision` (section 25) is the object that records them. Both structural checkpoints produce these records — context approval in M2 and finding approval in M4 — so the model is shared rather than owned by either.

## Scope

- `src/trace_ai/domain/models/reviewer_decision.py` — `ReviewerDecision` with the section 25 field list: `id`, `assessment_id`, `subject_type`, `subject_id`, `disposition`, `prior_value`, `updated_value`, `rationale`, `reviewer_id`, `created_at`, `workflow_run_id`.
- `ReviewDisposition` with exactly the seven values in section 4.6: `approve`, `reject`, `edit`, `defer`, `request_more_analysis`, `convert_to_question`, `convert_to_documentation_gap`.
- Identifiers use the `dec-` prefix from section 2.1, allocated under the DX-02 scheme.
- `prior_value` and `updated_value` are string-keyed mappings of JSON-compatible values, typed concretely so `mypy --strict` passes. Section 25 types them `map[string, any]`.
- A validator tying the disposition to the payload: `edit` requires both `prior_value` and `updated_value`; `approve` and `reject` require neither. A recorded edit that cannot say what changed is not an audit record.
- A constructor helper that captures `prior_value` from a domain object before an edit is applied, so the capture is not left to each call site and cannot be forgotten after the object has already been mutated.
- Resolve one vocabulary gap. `agent-design.md` section 9 lists "Request re-extraction" among the reviewer actions at the context checkpoint, and section 4.6 has no matching disposition; `request_more_analysis` is the nearest fit. Either map re-extraction onto `request_more_analysis` and record the mapping in the module docstring, or extend the vocabulary with a decision-log entry. Do not add a value silently — section 4.6 is authoritative.
- The representation of an edit — a new object revision against an in-place update carrying decision history — follows DX-16. This issue models the record; DX-16 governs what the record accompanies.

## Acceptance criteria

- [ ] `ReviewerDecision`'s field set matches `data-model.md` section 25 exactly, with a test that fails on drift.
- [ ] `ReviewDisposition` has exactly the seven values in section 4.6, and a test asserts the members.
- [ ] An `edit` decision without `prior_value` or without `updated_value` raises a validation error.
- [ ] The prior-value capture helper records the generated state before the edit, and a test asserts the generated value is recoverable from the decision after the object has changed.
- [ ] `prior_value` and `updated_value` have concrete JSON-compatible types and `uv run mypy` passes strict.
- [ ] The re-extraction mapping is either implemented against `request_more_analysis` and documented, or the vocabulary is extended with a decision-log entry.
- [ ] `subject_type` accepts any context object type produced in this milestone, and a test covers a decision against a claim, a component, and a system context.
- [ ] A decision round-trips through JSON with `prior_value` and `updated_value` intact.

## Out of scope

- Recording decisions during a review session, which belongs to the checkpoint machinery and the context review issues.
- Finding-review dispositions specific to M4, though the same model serves them.
- Evaluation metrics derived from decisions, such as reviewer acceptance and edit rates. `docs/architecture/evaluation-plan.md` section 8 places those in the evaluation harness.
- Deciding whether an edit produces a new object version, which is DX-16.

## References

- `docs/architecture/data-model.md` section 2.1 (Stable identifiers), section 2.5 (Human actions must be preserved), section 2.6 (Current state and history are separate), section 4.6 (ReviewDisposition), section 25 (ReviewerDecision), section 39 open question 10
- `docs/architecture/agent-design.md` section 9 (Human Context Review — Reviewer actions; Output), section 18 (Human Finding Review — Reviewer actions)
- `docs/architecture/current-architecture.md` section 5.12 (Human Finding Review)
- `docs/architecture/decision-log.md` DEC-005
