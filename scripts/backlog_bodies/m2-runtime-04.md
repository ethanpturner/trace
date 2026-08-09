## Context

The workflow is designed to distinguish an output that failed to parse from an analysis that genuinely cannot be concluded. `docs/architecture/agent-design.md` section 26 draws that line explicitly: retry on invalid structured output, missing required fields, invalid identifiers, schema mismatch, recoverable provider timeout, and rate limits; do not retry on missing source information, genuine ambiguity, contradictory evidence, unknown control status, low confidence, or a requirement that cannot be evaluated. Those conditions produce questions or human review, not repeated model calls. Getting this wrong spends money to no purpose and, worse, invites an agent to fabricate an answer on the third attempt.

## Scope

`src/trace_ai/workflow/errors.py` and `src/trace_ai/workflow/retry.py`:

- An error taxonomy with the retryable classes from `agent-design.md` section 26 — `schema_validation_failure`, `transient_provider_failure`, `missing_required_relationship` — and the non-retryable analysis conditions — `insufficient_evidence`, `unresolved_contradiction`, `reviewer_input_required`. The vocabulary is closed, so a new class is a deliberate addition rather than a free-text string appearing in a log.
- The failure classes from `current-architecture.md` section 11 mapped onto that taxonomy: validation failure, model-service failure, insufficient evidence, human-review timeout, and unexpected application failure. Section 11 gives each a required response, and insufficient evidence is explicitly not a technical execution failure.
- A retry policy bounded by `AssessmentConfiguration.maximum_retries_per_node`, default 2 (`data-model.md` section 6), consuming the taxonomy rather than exception types.
- Validation feedback on retry. `data-model.md` section 33 requires the workflow to preserve the invalid output for debugging, return validation feedback to the generating node when appropriate, retry within configured limits, and stop or request human review if valid output cannot be produced. The retry path implements all four; the invalid output is written to the assessment's debug artifact directory and referenced from the `ExecutionRecord`.
- Bounded exponential backoff for provider failures, per `current-architecture.md` section 11, with a ceiling so a provider outage cannot consume the workflow duration limit silently.
- A terminal path. When retries are exhausted, the run stops with a classified error recorded on `WorkflowRun.error_summary` and the most recent valid checkpoint preserved, per `current-architecture.md` section 11 Unexpected application failure.
- `error_type` and `error_message` on `ExecutionRecord` populated from the taxonomy, and `error_message` is safe — no prompt text, no source excerpt, no credential.

## Acceptance criteria

- [ ] The error taxonomy is a closed vocabulary containing the six classes named in `agent-design.md` section 26.
- [ ] Each failure class in `current-architecture.md` section 11 maps to exactly one taxonomy member, and a test asserts the mapping is total.
- [ ] A schema validation failure retries at most `maximum_retries_per_node` times and then stops with a classified error.
- [ ] An insufficient-evidence condition produces no retry, and the test docstring cites `agent-design.md` section 26 Non-retryable analysis conditions.
- [ ] An unresolved contradiction produces no retry.
- [ ] The invalid output from a failed attempt is written to the assessment's debug artifact directory and referenced from the `ExecutionRecord`.
- [ ] Validation feedback from a failed attempt reaches the next attempt, and a test asserts the second attempt's input differs from the first.
- [ ] Backoff for provider failures is bounded, and a test asserts the ceiling is respected.
- [ ] Exhausted retries record a classified error on `WorkflowRun.error_summary` and leave the last valid checkpoint intact.
- [ ] `ExecutionRecord.error_message` contains no prompt text, no source excerpt, and no credential; a test asserts this against a failure constructed with all three present in the attempt.
- [ ] All tests run offline against the deterministic model fake.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Node execution and transitions, which the workflow-runtime issue provides.
- Deciding what counts as sufficient evidence, which is DX-08 and applies at the finding stage rather than here.
- Human-review timeout handling beyond pausing and preserving state, which the checkpoint issue covers.
- Retry behaviour for agents other than context extraction, though the policy is shared.

## References

- `docs/architecture/agent-design.md` section 26 (Retry Policy), section 7 (Context Extraction Agent — Retry behavior), section 27 (Loop Prevention)
- `docs/architecture/current-architecture.md` section 11 (Error Handling)
- `docs/architecture/data-model.md` section 6 (AssessmentConfiguration — `maximum_retries_per_node`), section 26 (WorkflowRun — `error_summary`), section 27 (ExecutionRecord — `error_type`, `error_message`), section 33 (Schema Validation)
- `docs/architecture/decision-log.md` DEC-009
