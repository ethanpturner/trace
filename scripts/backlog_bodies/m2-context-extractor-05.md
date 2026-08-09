## Context

This is the first of the six model-assisted agents and the first model call anywhere in the codebase. Its contract is fully specified in `docs/architecture/agent-design.md` section 7, including a retry rule that distinguishes a recoverable output failure from genuine analytical uncertainty: retry when the output fails schema validation, but do not retry simply because the source material is incomplete, because incomplete context is designed to produce questions. `docs/product/roadmap.md` Stage 2 makes this the first meaningful product milestone.

## Scope

`src/trace_ai/workflow/nodes/context_extraction.py`, satisfying the node protocol:

1. Build the input package and load the composed prompt through the registry.
2. Call the model seam requesting a `ContextExtractionProposal`, using the generation settings for the assessment's model profile.
3. On schema failure, route through the workflow retry policy: preserve the raw invalid output, return validation feedback to the next attempt, and stop after `AssessmentConfiguration.maximum_retries_per_node`.
4. On success, convert the proposal into domain objects with application-allocated identifiers and hand them to the Context Validation node.
5. Write one `ExecutionRecord` per attempt through the execution ledger, with `node_name`, `node_version`, `execution_type` of model, `prompt_version`, `model_name`, `input_object_ids`, `output_object_ids`, timings, `status`, `retry_number`, tokens, and estimated cost.
6. Set `generated_by` on produced objects to `context-extraction-v1`, per `agent-design.md` section 33.
7. Check execution limits before each call, so a run that would exceed `maximum_model_calls` or `maximum_cost` stops before spending rather than after.
8. Produce the first `SystemContext` at version 1, unapproved, with `approved_at` and `approved_by` unset.

The node produces a context and stops. It does not approve anything, and it cannot: the checkpoint that follows is structural.

`agent-design.md` section 38 open question 1 asks whether context extraction requires one agent or separate extraction and architecture-normalization stages. This issue implements one node, consistent with the six-agent cap in section 36; splitting it into two model-assisted stages would be a design change requiring a decision-log entry, and normalization deterministic work belongs in the validation node.

## Acceptance criteria

- [ ] The node produces `SystemContext` version 1 plus the proposed context objects, all with application-allocated identifiers.
- [ ] `generated_by` on every produced object is `context-extraction-v1`.
- [ ] A stubbed schema failure retries at most `maximum_retries_per_node` times and then stops with a classified error, without discarding the invalid output.
- [ ] The invalid raw output is written to the assessment's debug artifact directory and referenced from the `ExecutionRecord`.
- [ ] A stubbed response representing incomplete source material produces questions and triggers no retry; the test docstring cites `agent-design.md` section 7 Retry behavior.
- [ ] One `ExecutionRecord` exists per attempt, with `retry_number` incrementing and `execution_type` of model.
- [ ] `WorkflowRun.total_model_calls` equals the number of attempts, and the token and cost counters are populated.
- [ ] A configured `maximum_model_calls` of zero stops the node before any call.
- [ ] A test asserts every produced object has a non-approved status and that `SystemContext.approved_at` and `approved_by` are unset.
- [ ] The node runs against the ForgeFlow input documents using the deterministic model fake and produces a well-formed context.
- [ ] Every test runs under a bare `uv run pytest` with no API key present and makes no network call.
- [ ] `uv run mypy` passes strict.

## Out of scope

- The deterministic post-checks, which the Context Validation node provides. This node calls the validator; it does not implement it.
- The human checkpoint and any reviewer action.
- Re-extraction after reviewer correction, which the context review issues route back to this node.
- Any live-provider run, which belongs behind the `integration` or `evaluation` marker.
- Splitting extraction into two model-assisted stages, which would need a decision-log entry against the six-agent cap.

## References

- `docs/architecture/agent-design.md` section 5 (Shared Agent Contract), section 7 (Context Extraction Agent), section 23 (Retrieval Design), section 26 (Retry Policy), section 33 (Agent Versioning), section 36 (MVP Agent Set), section 38 open question 1
- `docs/architecture/data-model.md` section 6 (AssessmentConfiguration), section 26 (WorkflowRun), section 27 (ExecutionRecord), section 33 (Schema Validation), section 34 (Model-Generated Output)
- `docs/architecture/current-architecture.md` section 5.5 (Context Extraction), section 11 (Error Handling)
- `docs/product/roadmap.md` Stage 2 "Context Extraction Agent", "Exit criteria"
- `docs/architecture/decision-log.md` DEC-005, DEC-006, DEC-009
