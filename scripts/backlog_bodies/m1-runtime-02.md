## Context

`docs/architecture/data-model.md` sections 26 and 27 define WorkflowRun and ExecutionRecord,
and section 40 places both in the initial implementation set. Section 34 states that
model-generated objects should carry generation metadata and that the MVP should prefer linked
execution records over duplicating that metadata onto every object, which makes the ledger a
prerequisite for the first agent rather than a convenience.
`docs/architecture/current-architecture.md` section 5.17 requires local audit records to remain
the authoritative execution record. The ledger is written now, while the only executions are
deterministic ones — ingestion and evidence indexing — so that the first model-assisted node
has somewhere to record itself rather than inventing one.

**Blocked on DX-06** (orchestrator) and **DX-07** (checkpoint pause and resume). WorkflowRun
carries `current_node`, `checkpoint_reference`, and a status including `paused`, all three of
which mean whatever the orchestrator decision makes them mean.

## Scope

- Add `src/trace_ai/domain/execution.py` with `WorkflowRun` and `ExecutionRecord`.
- `WorkflowRun`, exactly as section 26 types it: `id`, `assessment_id`, `workflow_version`,
  `status`, `started_at`, `completed_at`, `current_node`, `checkpoint_reference`,
  `model_profile`, `prompt_versions`, `total_model_calls`, `total_input_tokens`,
  `total_output_tokens`, `estimated_cost`, `error_summary`.
- `ExecutionRecord`, exactly as section 27 types it: `id`, `workflow_run_id`, `assessment_id`,
  `node_name`, `node_version`, `execution_type`, `prompt_version`, `model_name`,
  `input_object_ids`, `output_object_ids`, `started_at`, `completed_at`, `status`,
  `retry_number`, `error_type`, `error_message`, `duration_ms`, `input_tokens`,
  `output_tokens`, `estimated_cost`, `metadata`.
- Use `Decimal` for both `estimated_cost` fields, matching `AssessmentConfiguration.maximum_cost`.
- Enumerate `execution_type` over the three kinds `docs/architecture/agent-design.md` section 4
  classifies: model, deterministic, and human checkpoint. The deterministic value is the one
  this milestone exercises.
- Add `src/trace_ai/services/execution_ledger.py` with a context manager that opens an
  `ExecutionRecord`, stamps `started_at`, and on exit stamps `completed_at`, `duration_ms`, and
  a terminal status, recording an error classification and a safe error message on failure.
  Section 27 describes `error_message` as a safe error message, so it passes through the
  redaction rules from the logging issue.
- Instrument the document loader and the evidence indexing node with the ledger, so the two
  deterministic nodes that exist are recorded.
- Maintain `total_model_calls` on WorkflowRun. It is required and is zero for every run in this
  milestone, which is the correct value and worth asserting.
- Persist both objects through the store.
- Add `tests/unit/test_execution_ledger.py`.

## Acceptance criteria

- [ ] Every field in data-model.md sections 26 and 27 is present with the documented type and
      required/optional status; the conformance guard covers it.
- [ ] `estimated_cost` uses `Decimal` in both objects.
- [ ] A successful execution produces a record with `completed_at`, `duration_ms`, and a
      completed status.
- [ ] A failing execution produces a record with a failure status, an `error_type`, and an
      `error_message` that contains no secret and no source-document content.
- [ ] `retry_number` is recorded and increments across retries of the same node.
- [ ] Every ExecutionRecord's `assessment_id` matches its WorkflowRun's `assessment_id`.
- [ ] Ingesting `demo/forgeflow/input/` produces execution records for the loader and for the
      indexing node, with `execution_type` set to the deterministic value.
- [ ] `total_model_calls` is zero after a full ingestion and indexing run, and a test asserts
      it. Nothing in this milestone calls a model.
- [ ] A WorkflowRun and its ExecutionRecords round-trip through the store.
- [ ] The ledger needs no API key.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Executing the workflow. There is no orchestrator, and DEC-007 leaves LangGraph proposed
  rather than accepted.
- Checkpoint persistence and resumption, which DX-07 owns.
- Token counting and cost estimation. The fields exist and stay unset while no model is called;
  populating them depends on DX-05.
- External tracing export.
- `EvaluationResult` (section 28), deferred by section 40.

## References

- `docs/architecture/data-model.md` sections 26 (WorkflowRun), 27 (ExecutionRecord),
  34 (Model-Generated Output), 31 (Assessment State), 40
- `docs/architecture/current-architecture.md` sections 5.17 (Trace and Audit Service),
  5.3 (Workflow Orchestrator), 11 (Error Handling)
- `docs/architecture/agent-design.md` sections 4 (Component Classification), 6 (Shared Agent
  Response Metadata), 26 (Retry Policy)
- `docs/architecture/decision-log.md` DEC-006, DEC-007, and DX-06 and DX-07 once recorded
