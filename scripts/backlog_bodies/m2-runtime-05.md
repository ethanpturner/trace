## Context

DEC-005 makes two human checkpoints structural: context approval and finding approval. `docs/architecture/current-architecture.md` section 8 places the first after context extraction and before threat analysis, and `agent-design.md` section 9 states the rule unconditionally — threat analysis does not begin until the context checkpoint is approved. No pause mechanism exists. DX-07 settles how a run pauses and resumes and DX-01 settles the configurability question raised by `AssessmentConfiguration.require_context_review`, which `data-model.md` section 6 makes a required boolean while `README.md` and `CLAUDE.md` state the checkpoints are not configurable. This issue builds the machinery both checkpoints share, so the M4 finding checkpoint reuses it rather than reimplementing it.

## Scope

`src/trace_ai/workflow/checkpoint/`:

- A checkpoint node satisfying the node protocol, parameterised by checkpoint type. `data-model.md` section 31 names `context_review` as a `checkpoint_type` on `pending_human_review`; the finding checkpoint is the second value.
- Pause: the run transitions to paused, `pending_human_review` is populated with the checkpoint type and the object identifiers awaiting decision, and the state is persisted per DX-04. `WorkflowRun.status` becomes `paused` and `WorkflowRun.checkpoint_reference` is given the meaning DX-07 records, since `data-model.md` section 26 leaves it an undefined string.
- Resume from a persisted paused run after the process has exited. This is a local single-user application (DEC-004), so the process is not running while the reviewer reads. Resumption locates the paused run by assessment, restores state, and continues at the transition the table permits.
- A review package builder: the reviewer-facing bundle assembled from validated objects, the validation results, and the triggers that fired. `agent-design.md` section 8 names the human-review package as an output of the Context Validation node, and section 7 lists the triggers that require reviewer involvement. The builder is generic over object type so the finding checkpoint reuses it.
- Decision recording: a session that applies reviewer dispositions and writes `ReviewerDecision` records, capturing `prior_value` before each edit. The disposition vocabulary is `data-model.md` section 4.6.
- The advance guard. The workflow cannot leave a checkpoint until the checkpoint's approval condition holds. Per DX-01 this is a code path with no configuration input; whatever DX-01 records about `require_context_review` is expressed at the type level, so that disabling the checkpoint is not merely discouraged but unrepresentable.
- Human-review timeout handling per `current-architecture.md` section 11: pause, preserve state, resume when the reviewer responds. A checkpoint waiting on a reviewer is not a failure.

## Acceptance criteria

- [ ] A checkpoint node satisfies the node protocol and is parameterised by checkpoint type, with `context_review` implemented and the finding type reserved.
- [ ] Pausing sets `WorkflowRun.status` to `paused`, populates `pending_human_review` with the checkpoint type and the pending object identifiers, and persists the state.
- [ ] A run paused, with the process exited and restarted, resumes from the persisted state and continues at a permitted transition.
- [ ] `WorkflowRun.checkpoint_reference` carries the meaning DX-07 defines, and a test asserts the value round-trips through persistence.
- [ ] The review package builder produces a bundle containing the objects awaiting decision, the validation results, and the fired triggers, and a test constructs one for a non-context object type to prove it is generic.
- [ ] Applying a disposition writes a `ReviewerDecision` with `prior_value` captured before the edit.
- [ ] A test asserts that no configuration value, environment variable, or function argument causes the run to advance past an unapproved checkpoint, and the test docstring cites DEC-005 and DX-01.
- [ ] A checkpoint awaiting a reviewer records no error and consumes no retry budget.
- [ ] Resuming a run does not restart completed nodes; a test asserts the execution ledger gains no duplicate records for work already done.
- [ ] All tests run offline with no API key present.
- [ ] `uv run mypy` passes strict.

## Out of scope

- The context-specific content of checkpoint 1, which the context review issues cover.
- The finding checkpoint's content, which belongs to M4.
- Any reviewer interface. The command-line surface is a separate issue and the web interface is deferred by `docs/product/roadmap.md` section 9.
- Deciding the pause mechanism or the configurability question, which are DX-07 and DX-01.
- Evaluation of checkpoint value, such as the context-review-enabled comparison in `docs/product/roadmap.md` section 2, which belongs to Stage 5.

## References

- `docs/architecture/decision-log.md` DEC-004, DEC-005, DEC-006, DEC-007
- `docs/architecture/current-architecture.md` section 5.3 (Workflow Orchestrator), section 8 (Human-in-the-Loop Checkpoints), section 11 (Error Handling — Human-review timeout)
- `docs/architecture/agent-design.md` section 7 (Human-review triggers), section 8 (Context Validation Node — Outputs), section 9 (Human Context Review — Workflow rule), section 18 (Human Finding Review)
- `docs/architecture/data-model.md` section 4.6 (ReviewDisposition), section 6 (AssessmentConfiguration), section 25 (ReviewerDecision), section 26 (WorkflowRun), section 31 (Assessment State — `pending_human_review`)
- `README.md` ("Not an autonomous security authority"), `CLAUDE.md` ("Binding design constraints")
