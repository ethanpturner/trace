## Context

Finding approval is the second of the two structural human checkpoints
(`docs/architecture/decision-log.md` DEC-005, `docs/architecture/current-architecture.md`
section 8). It occurs after consolidation and before report generation, and it ships inside the
Findings component rather than alongside the report. The checkpoint machinery — the pause, the
resume, and the `ReviewerDecision` object — is built upstream for context approval and is reused
here rather than rebuilt. This issue wires the finding checkpoint into that machinery and implements
the reviewer dispositions.

## Scope

- Register the finding checkpoint with the shared checkpoint machinery, using the pause and resume
  semantics fixed in DX-07 and the configurability decision fixed in DX-01. The checkpoint is a
  property of the workflow graph, not a runtime conditional over a configuration field.
- Implement the eleven reviewer actions of `docs/architecture/agent-design.md` section 18: approve,
  reject, edit, change severity, merge, defer, request more analysis, convert to question, convert to
  documentation gap, add reviewer rationale, add remediation guidance. Conversions call the existing
  reclassification helpers and merges call the existing merge operation.
- Each action produces a `ReviewerDecision` (data-model section 25) carrying disposition,
  `prior_value`, `updated_value`, rationale, reviewer identifier and workflow run identifier.
  Reviewer edits do not silently overwrite generated content (data-model section 2.5); the
  representation follows DX-16.
- `ReviewDisposition` (data-model section 4.6) lists seven values and does not include `merge`,
  while agent-design section 18 lists merging as a reviewer action. Resolve this in the same change:
  either add the value to the data model or record a merge as `edit` under a stated convention.
  State which was chosen and why in the pull request and in the model docstring.
- Reviewer identity under DEC-004 is a local single-user string. There is no authentication, no role
  and no tenancy. Establish the convention for populating `reviewer_id`, `created_by` and
  `approved_by`, and record it.
- Severity changes are recorded per the ownership decision in DX-11.
- Raise and resolve, within this issue, whether a blocking `Question` produced during evidence
  validation constitutes a pause point. `Question.blocking` is documented as "whether workflow should
  pause" (data-model section 22) while DEC-005 declares two structural checkpoints. Either blocking
  questions surface at this checkpoint rather than pausing the pipeline earlier, or the field's
  description is wrong. Decide, implement, and correct the document that is inaccurate.
- Human-review timeout behaves as `current-architecture.md` section 11 specifies: pause, preserve
  state, resume when the reviewer responds. It is not a failure condition.
- The interface follows DX-17.

## Acceptance criteria

- [ ] The workflow does not advance from consolidation to report generation without a recorded
      `ReviewerDecision` for every provisional finding.
- [ ] A run interrupted at the checkpoint resumes at the same point with no loss of provisional
      findings, documentation gaps, questions or decisions.
- [ ] Each of the eleven reviewer actions produces a `ReviewerDecision` with disposition, prior
      value, updated value and workflow run identifier.
- [ ] A reviewer edit preserves the generated value in `prior_value`; the original is recoverable.
- [ ] A merge performed by the reviewer produces the same merge record shape as an automated merge.
- [ ] The `ReviewDisposition` gap is resolved, and `docs/architecture/data-model.md` section 4.6 and
      `docs/architecture/agent-design.md` section 18 no longer disagree.
- [ ] The blocking-question question is resolved, implemented, and the inaccurate document corrected.
- [ ] No authentication, role, permission or multi-user construct is introduced (DEC-004).
- [ ] An assessment in which the reviewer approves nothing passes the checkpoint successfully and
      proceeds to report generation with an empty approved set. Approving nothing is a valid outcome.
- [ ] The checkpoint makes no model call; a test asserts this.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The checkpoint machinery itself, the pause and resume implementation, and the `ReviewerDecision`
  model, all delivered upstream for context approval.
- The context-approval checkpoint.
- The approved-finding gate and rejected-candidate retention, which is a separate issue.
- A web interface.

## References

- `docs/architecture/current-architecture.md` — section 5.12, section 8, section 11
  ("Human-review timeout")
- `docs/architecture/agent-design.md` — section 4, section 18, section 27
- `docs/architecture/data-model.md` — section 2.5, section 4.6, section 21, section 22, section 25,
  section 26, section 31
- `docs/architecture/decision-log.md` — DEC-004, DEC-005, DEC-006
- `docs/product/design-principles.md` — section 5, section 16, section 18
- `docs/product/roadmap.md` — Stage 4, "Human finding review"
