## Context

`Question` is the DEC-009 outlet. When the documentation cannot settle whether a control exists, the correct output is a question, not a finding — `docs/architecture/decision-log.md` DEC-009 names an open question first among the permitted classifications, and `docs/architecture/data-model.md` section 22 defines the object. The Context Extraction Agent is designed to emit questions rather than retry when source material is incomplete (`agent-design.md` section 7 Retry behavior: "Incomplete context should produce questions"). Questions are also the mechanism by which the ForgeFlow ambiguities reach a reviewer rather than becoming asserted weaknesses.

## Scope

- `src/trace_ai/domain/models/question.py` — `Question` with the section 22 field list: `id`, `assessment_id`, `question`, `rationale`, `related_object_type`, `related_object_id`, `priority`, `blocking`, `response`, `response_origin`, `answered_at`, `status`, `generated_by`.
- `QuestionStatus` with the three values in section 22: `open`, `answered`, `dismissed`.
- Identifiers use the `qst-` prefix from section 2.1, allocated under the DX-02 scheme.
- `blocking` is required, not defaulted. Whether the workflow pauses for a question is a property of the question, and a default would let an unset field decide it.
- `priority` uses the `low`, `medium`, `high` vocabulary in section 22.
- A validator enforcing the answered state: `status == answered` requires `response`, `response_origin`, and `answered_at` to be set together. A half-answered question is worse than an open one, because it reads as resolved.
- `response_origin` is a `SourceOrigin` (section 4.4); a reviewer answer uses `user_response`.
- An ordering helper returning open questions with blocking ones first and then by priority, used by the review package in the checkpoint machinery and by `trace context show`. `demo/forgeflow/forgeflow-scenario.md` section 20 states that questions should be prioritized by their ability to change findings, so the ordering is a product property rather than a display detail.

## Acceptance criteria

- [ ] `Question`'s field set matches `data-model.md` section 22 exactly, with a test that fails on drift.
- [ ] `blocking` is required; constructing a question without it raises a validation error.
- [ ] `status` accepts exactly `open`, `answered`, and `dismissed`.
- [ ] Setting `status` to `answered` without `response`, `response_origin`, or `answered_at` raises a validation error naming the missing fields.
- [ ] A question answered by a reviewer carries `response_origin` of `user_response`.
- [ ] The ordering helper returns blocking questions ahead of non-blocking ones, and orders within each group by priority.
- [ ] A test constructs the ten questions listed in `demo/forgeflow/forgeflow-scenario.md` section 20 and asserts they are all well formed, so the model is exercised against the shape the demo expects.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Generating questions. The Context Extraction Agent proposes them; this issue only models them.
- Answering questions through a reviewer interface, which belongs to the context review issues.
- Question usefulness scoring. `docs/architecture/evaluation-plan.md` section 8 places clarifying-question usefulness in the evaluation harness, which is a later stage.
- `DocumentationGap`, which is a different object with a different meaning (`data-model.md` section 23).

## References

- `docs/architecture/data-model.md` section 2.1 (Stable identifiers), section 4.4 (SourceOrigin), section 22 (Question), section 23 (DocumentationGap — Important distinction)
- `docs/architecture/agent-design.md` section 7 (Outputs; Retry behavior), section 26 (Retry Policy — Non-retryable analysis conditions)
- `docs/architecture/decision-log.md` DEC-009
- `docs/architecture/current-architecture.md` section 2.1 (Evidence over assumptions)
- `demo/forgeflow/forgeflow-scenario.md` section 15 (Intentional Ambiguities), section 20 (Expected Questions)
