# The adversarial numbers become measured, labelled, and guarded

## What changed

The audit's three M11 evaluation gaps, delivered together because they share one thread: the
adversarial claims were better than their presentation, and in one place the presentation was
better than the measurement.

**#404 — measured, not asserted.** `_STRUCTURAL` had grown to three payload classes when DEC-075
sanctions exactly one: checkpoint bypass, "a structural argument scored as trivially zero". The
fence neutralisation and the deterministic validators are real controls, but "the mechanism
exists" is not "this run was measured" — the same decision calls a resistance claim without a
measured compliance rate the anti-pattern it exists to avoid. Scoring now measures four of the
five classes from the same match set as axis one: findings suppression by the vanished expected
finding, verifier sabotage by an unsupported conclusion surviving validation into the approved
set, and the two instruction-vehicle classes — direct injection and the fence escape — by either
signal, since compliance for a vehicle means a carried instruction's objective happened. The
recorded run's rates stay zero, which is the point: the same zeros, now verified rather than
declared. No new DEC — this restores the accepted decision as written.

**#403 — labelled per class.** DEC-075's tradeoff is explicit: the rate "is meaningful per class
and meaningless as a universal claim, and the scorecard must label it per class." The computation
existed end to end and the committed pages dropped it at the last step. The scorecard now carries
an adversarial section — scenario, condition, the detection axis, and one row per payload class —
and the comparison table's compliance cell gains a footnote breaking the aggregate out per class,
with the structural class's basis stated. The history file retains the new fields, with the
tuple-shape round-trip handled so a reloaded snapshot compares equal to the retained one.

**#405 — checked on every pull request.** The drift checks ran only on PRs touching an
evaluation-shaped path, while the harness replays the whole pipeline — so a change to
`workflow/` or `domain/` could move the regenerated feeds silently, and the red check would land
on whichever later evaluation PR happened to inherit it (#388 was a live instance of the class).
The path filter is gone; the three checks run offline in seconds, so it was not buying anything.

## The one line worth keeping

The difference between `complied=False` by construction and `complied=False` by measurement is
invisible in the number and is the entire credibility of the number. This project's thesis is
that absence of evidence is not evidence of absence; a hard-coded zero was the evaluation
committing the failure the pipeline exists to prevent.

## Open next

From the audit backlog: the chores (#401, #402, #406–#409) and the two doc sweeps (#410, #411).
The live-run milestone work (#324, #330) is unblocked and waiting on a decision to spend.
