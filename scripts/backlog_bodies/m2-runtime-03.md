## Context

Trace is designed as a fixed pipeline with explicit permitted transitions, not a free-form agent conversation. `docs/architecture/agent-design.md` section 27 requires the orchestrator to enforce maximum node executions, maximum model calls, maximum retries, maximum cost, maximum workflow duration, and explicit permitted transitions, and states that no agent may invoke itself or another agent without workflow control. DX-06 settles the orchestrator question, including whether DEC-007's LangGraph proposal is accepted; this issue builds what DX-06 records. Nothing in `src/` currently executes a workflow node.

## Scope

`src/trace_ai/workflow/`:

- A node protocol with defined inputs and outputs, covering the three execution types in `data-model.md` section 27: model, deterministic, and human checkpoint. `agent-design.md` section 4 classifies every pipeline component into those types, and the protocol accommodates all three so a checkpoint is a node rather than a special case.
- A permitted-transition table expressing the pipeline in `agent-design.md` section 3 and `README.md`. Transitions are declared data, not implied by call order, so an attempted transition outside the table fails rather than proceeding.
- Workflow state per `data-model.md` section 31: `assessment_id`, `workflow_run_id`, `status`, `current_phase`, `next_action`, the identifier lists, `pending_human_review`, `execution_limits`, and `errors`. Section 31's state-design rule is binding — full source documents, full prompt transcripts, and every generated object stay out of the state payload. The state holds identifiers and routing information; objects live in persistence and are retrieved when needed. The schema follows the shape DX-06 and DX-04 record.
- Execution limits enforced before each node execution and before each model call: `maximum_model_calls`, `maximum_cost`, and `maximum_retries_per_node` from `AssessmentConfiguration` (`data-model.md` section 6), plus a maximum node-execution count and a maximum workflow duration from `agent-design.md` section 27. Exceeding a limit stops the run with a classified error; it does not silently continue or silently truncate.
- An execution ledger writer producing one `ExecutionRecord` per node execution and per retry, with `node_name`, `node_version`, `execution_type`, `prompt_version`, `model_name`, `input_object_ids`, `output_object_ids`, timings, `status`, `retry_number`, `error_type`, `error_message`, tokens, and estimated cost (`data-model.md` section 27), and updating the `WorkflowRun` counters in section 26. If the M1 execution-ledger issue already provides the models, this issue provides the writer that populates them from node results.
- Loop prevention: a node cannot enqueue itself, and a node cannot invoke another node directly. Routing belongs to the orchestrator (`agent-design.md` section 27).

## Acceptance criteria

- [ ] A node protocol exists covering model, deterministic, and human-checkpoint execution types, and a test implements one of each against it.
- [ ] The permitted-transition table is declared data, and a transition absent from the table is refused with a message naming the attempted source and destination.
- [ ] The workflow state schema matches the field list in `data-model.md` section 31.
- [ ] A test asserts the state payload contains no source document text and no prompt text, citing the section 31 state-design rule.
- [ ] A run configured with `maximum_model_calls` of zero stops before any model call.
- [ ] A run that would exceed `maximum_cost` stops before the call that would exceed it, not after.
- [ ] Exceeding the maximum node-execution count or the maximum workflow duration stops the run with a classified error.
- [ ] One `ExecutionRecord` is written per node execution and per retry, with `retry_number` incrementing.
- [ ] `WorkflowRun.total_model_calls` equals the number of model calls made, and the token and cost counters accumulate across nodes.
- [ ] A node attempting to invoke another node directly fails a test that asserts routing is the orchestrator's alone.
- [ ] All tests run under a bare `uv run pytest` with no API key present, using the deterministic model fake.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Choosing the orchestration framework, which is DX-06.
- Pausing and resuming at a checkpoint, which is the next runtime issue.
- The error taxonomy and retry policy, which is a separate runtime issue; this issue enforces the limits and records the outcomes that policy routes on.
- Any node's analytical content. Context extraction and context validation are separate issues.
- The second checkpoint, finding approval, whose content belongs to M4 though it reuses this machinery.

## References

- `docs/architecture/agent-design.md` section 3 (Workflow Overview), section 4 (Component Classification), section 27 (Loop Prevention)
- `docs/architecture/current-architecture.md` section 5.3 (Workflow Orchestrator), section 7 (Workflow State)
- `docs/architecture/data-model.md` section 6 (AssessmentConfiguration), section 26 (WorkflowRun), section 27 (ExecutionRecord), section 31 (Assessment State)
- `docs/architecture/decision-log.md` DEC-006, DEC-007
- `README.md` ("Pipeline", "Safety properties")
