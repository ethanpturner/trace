# 2026-08-12 — The approval verb lands, and phase fourteen stays a marker (#350, DEC-082)

First M13 delivery, and the day's seventh issue. The assessment lifecycle's final verb had no
driver: `AssessmentService.approve()` had no caller in `src/`, its docstring still claimed
`WorkflowRun` did not exist, phase fourteen declared no node, and a completed run left its
assessment in `draft` forever.

## The decision (DEC-082)

The interesting part was a genuine corpus contradiction. DEC-031's transition table assigns
`draft → approved` to "the terminal node"; the implementation deliberately left phase
fourteen empty, and the driver test asserted a completed run leaves `draft`, annotated
"approval is a person's verb, not a run's". Nothing resolved the disagreement because nothing
exercised the edge at all.

DEC-082 sides with the implementation, with the argument the table lacked: checkpoint 2
approves *findings*, and the report is generated and rendered afterwards. `approved` means
"the conclusions are the reviewer's" — and the conclusions a customer reads are the rendered
document, which nobody has confirmed reading at the moment the run completes. A terminal node
cannot make that judgment; a person can.

DEC-031's stated fear — "a user-settable `approved` is a checkpoint bypass with extra steps"
— is answered by making the verb self-guarding rather than by withholding it. The service
refuses unless the assessment carries a rendered report, the run *named by the report's
filename* completed, and that run is authoritative. No report exists without passing both
structural checkpoints, so the earliest moment the verb can succeed is after every gate
DEC-031 protects has already held. `run_is_authoritative` stopped being caller-supplied for
the same reason: the run exists now, and a boolean the caller asserts is a bypass one keyword
away.

Binding the sign-off to the report's run rather than the latest run was a small deliberate
choice: a later failed revision run does not block approving the earlier finished
deliverable, and the reviewer holding the report is the right judge of whether it should.

## What changed

`trace assessment approve` on the surface (the DEC-032 surface test now pins six assessment
subcommands); the guarded service verb with `AssessmentNotApprovableError` naming each
refusal; the driver's end-to-end test now completes a real run, asserts `draft`, and then
approves through the service; CLAUDE.md's "a person may only archive" is corrected to the
amended rule.

## Open next

M13's remaining two: #352 (the interface-surface decision, which unblocks #276) and #351
(the full finding-review action set). The M11 live-run trio still waits on authorization.
