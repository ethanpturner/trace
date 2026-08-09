## Context

`docs/architecture/agent-design.md` section 9 lists what a reviewer may do at the context checkpoint: approve, reject, and edit claims, add missing components, correct data flows, confirm assumptions, resolve contradictions, answer questions, add evidence, and request re-extraction. Its outputs are an approved `SystemContext`, updated context objects, `ReviewerDecision` records, answered `Question` objects, and a revised context version. `data-model.md` section 2.5 requires reviewer actions to be recorded rather than silently overwriting generated content, because those edits are the evaluation signal that shows where the workflow was inaccurate.

## Scope

Extend `src/trace_ai/application/context_review.py` with the mutating reviewer actions:

- Edit an existing context object or claim, writing a `ReviewerDecision` with `prior_value` captured before the change and `updated_value` after it.
- Add a component, asset, actor, data flow, or trust boundary the extractor missed, with `source_origin` of `reviewer_edit` (`data-model.md` section 4.4).
- Correct a data flow, subject to the same referential rules the validation node enforces, so a reviewer correction cannot introduce a dangling endpoint.
- Confirm an assumption, moving a claim to status `user_confirmed`. That status sits at the top of the evidence hierarchy in `agent-design.md` section 14, so the transition is recorded rather than inferred.
- Resolve a contradiction, in whatever form DX-14 records, writing the resolution and its rationale rather than silently selecting one side. `demo/forgeflow/forgeflow-scenario.md` section 16 requires that Trace not quietly choose the safer statement.
- Answer a question: set `response`, `response_origin` of `user_response`, `answered_at`, and status `answered`, and clear it from the blocking set.
- Add evidence to a claim, linking an existing `EvidenceReference`. Evidence text is never edited; `data-model.md` section 8 requires corrections to create a new evidence reference.
- Request re-extraction, routed back to the extraction node with the reviewer's rationale carried into the next attempt and counted against the run's execution limits so re-extraction cannot loop unbounded.
- Produce the revised context version. Whether an edit creates a new object revision or updates the current object with decision history follows DX-16; this issue implements that decision consistently across claims and architecture objects, using `SystemContext.next_version()` and `ContextClaim.supersedes_id` as DX-16 directs.

## Acceptance criteria

- [ ] Every reviewer action listed in `agent-design.md` section 9 is supported and produces a `ReviewerDecision`.
- [ ] An edit preserves the prior value; a test asserts the generated value is recoverable from the decision after the object has changed.
- [ ] A reviewer-added object carries `source_origin` of `reviewer_edit`.
- [ ] A reviewer correction that would create a dangling data-flow endpoint is refused with the same error the validation node produces.
- [ ] Confirming a claim sets status `user_confirmed` and records the decision.
- [ ] Resolving a contradiction records the resolution and a rationale, and a test asserts the unselected statement remains retrievable.
- [ ] Answering a blocking question sets `response`, `response_origin` of `user_response`, and `answered_at`, and removes it from the blocking set.
- [ ] Adding evidence links an existing reference and does not modify its `quoted_text`; a test asserts the text is unchanged.
- [ ] Requesting re-extraction routes to the extraction node, carries the rationale into the next attempt, and consumes execution budget.
- [ ] The revision behaviour matches DX-16 and is consistent across claims and architecture objects, asserted by one test per object family.
- [ ] Approving the revised context sets `approved_at` and `approved_by` and leaves the prior revision retrievable.
- [ ] All tests run offline with no API key present.
- [ ] `uv run mypy` passes strict.

## Out of scope

- The command-line surface, which is a separate issue.
- Deciding the reviewer edit representation or the contradiction representation, which are DX-16 and DX-14.
- Reviewer-experience metrics such as correction and edit rates, which belong to the evaluation harness.
- Finding-review edits, which belong to M4.

## References

- `docs/architecture/agent-design.md` section 9 (Human Context Review — Reviewer actions; Output), section 14 (Evidence hierarchy)
- `docs/architecture/data-model.md` section 2.5 (Human actions must be preserved), section 2.6 (Current state and history are separate), section 4.4 (SourceOrigin), section 4.6 (ReviewDisposition), section 8 (EvidenceReference — Validation rules), section 9 (SystemContext), section 10 (ContextClaim), section 22 (Question), section 25 (ReviewerDecision), section 39 open question 10
- `docs/architecture/current-architecture.md` section 5.6 (Context Review), section 5.12 (Human Finding Review)
- `docs/architecture/decision-log.md` DEC-005, DEC-009
- `demo/forgeflow/forgeflow-scenario.md` section 16 (Intentional Contradictions)
- `docs/product/roadmap.md` Stage 2 "Human context review"
