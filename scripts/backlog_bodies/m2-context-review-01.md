## Context

Checkpoint 1 exists to stop incorrect extracted context from corrupting every later stage. `docs/architecture/current-architecture.md` section 8 states its purpose directly: prevent downstream analysis from being built on incorrect architecture assumptions, capture missing business and technical context, and demonstrate the importance of human validation. `agent-design.md` section 9 states the workflow rule without qualification — threat analysis does not begin until the required context checkpoint is approved. The shared checkpoint machinery provides pause, resume, and the review package builder; this issue supplies the context-specific content and the approval gate.

## Scope

`src/trace_ai/application/context_review.py`:

- Configure the shared checkpoint node for `context_review`, so the run pauses after context validation and before any threat work.
- Assemble the context review package from the validated objects and the validation results: proposed components, actors, assets, data flows, and trust boundaries grouped by type; each claim with its status, confidence, and evidence excerpts; the human-review triggers that fired; and the open questions ordered with blocking ones first.
- Present evidence with each claim. `data-model.md` section 2.2 requires conclusions to link to specific source locations, and a reviewer cannot confirm a claim without seeing the passage it rests on. Excerpts are marked as quoted untrusted source content, so a reviewer reading the ForgeFlow injection fixture sees it framed as data.
- Distinguish, in the package, what is documented from what is inferred, assumed, or unknown. `current-architecture.md` section 5.5 states that the system does not silently convert an interpretation into a confirmed fact, and the checkpoint is where that distinction earns its keep.
- Approve and reject actions: approval sets `approved_at` and `approved_by` on the current `SystemContext`; rejection returns the run to extraction through the re-extraction path. Both write `ReviewerDecision` records.
- The advance guard. The run cannot proceed to threat analysis while `SystemContext.is_approved` is false. Per DX-01 this is a code path with no configuration input; the guard is expressed so that disabling it is unrepresentable rather than merely discouraged.
- Refusal conditions: approval is refused while a blocking question is open or a blocking validation error is outstanding, with a message naming what is outstanding.

## Acceptance criteria

- [ ] The run pauses at `context_review` after context validation and does not execute any threat-analysis transition while paused.
- [ ] The review package contains every context object type produced by the extractor, each claim's status and confidence, and the evidence excerpts supporting documented and inferred claims.
- [ ] Source excerpts in the package are marked as quoted untrusted content.
- [ ] The package separates documented claims from inferred, assumed, and unknown ones, and a test asserts the grouping.
- [ ] The package lists the human-review triggers that fired, with the objects that caused each.
- [ ] Open questions appear with blocking ones first.
- [ ] Approval sets `approved_at` and `approved_by` and writes a `ReviewerDecision` with disposition `approve`.
- [ ] Approval is refused while a blocking question is open, with a message naming the question.
- [ ] Approval is refused while a blocking validation error is outstanding, with a message naming the error.
- [ ] A test asserts that no configuration value, environment variable, or function argument causes the run to advance past an unapproved checkpoint, and the test docstring cites DEC-005 and DX-01.
- [ ] All tests run offline with no API key present.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Editing, adding objects, answering questions, and revision creation, which the reviewer-edit issue covers.
- The command-line surface, which is a separate issue.
- Any web interface. `docs/product/roadmap.md` section 9 says not to begin with the web interface.
- The finding checkpoint, which belongs to M4 though it reuses the same machinery.
- Measuring whether the checkpoint improves results, which `docs/product/roadmap.md` places in Stage 5.

## References

- `docs/architecture/decision-log.md` DEC-005, DEC-006, DEC-009
- `docs/architecture/current-architecture.md` section 5.5 (Context Extraction — Output discipline), section 5.6 (Context Review), section 8 (Checkpoint 1: Context approval)
- `docs/architecture/agent-design.md` section 7 (Human-review triggers), section 8 (Context Validation Node — Outputs), section 9 (Human Context Review)
- `docs/architecture/data-model.md` section 2.2 (Evidence must be addressable), section 9 (SystemContext), section 22 (Question), section 25 (ReviewerDecision), section 31 (Assessment State)
- `docs/product/roadmap.md` Stage 2 "Human context review", "Exit criteria"
