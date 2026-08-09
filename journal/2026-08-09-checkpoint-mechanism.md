# 2026-08-09 — Pausing by exiting

Closes #28 as DEC-017. The fifth M0 decision, and the one that mostly followed from decisions
already made rather than needing its own argument.

## The shape was already determined

DEC-016 rejected a framework checkpointer, so resume is a database read. DEC-012 established that
answering a checkpoint without a human present and removing the checkpoint are different things,
and only the second is an ablation. `data-model.md` section 31 already specified
`pending_human_review` with a checkpoint type and object identifiers, and `WorkflowRun` already had
`status: paused` and `current_node`.

Put together, those leave one mechanism standing: **the run persists itself and the process
exits.** Nothing is held in memory across a human review, so a paused run is a complete record on
disk, and resuming is a separate invocation that loads it.

I spent longer than I should have looking for the decision in this, before noticing that the prior
decisions had made it and what remained was writing it down precisely.

## What the alternative would have cost

The thing a local single-user application invites is a blocking prompt inside one long-running
process. It is the obvious simplest option and it fails three ways that matter.

It cannot survive process exit, and this is an application a reviewer steps away from — reviewing
fifty findings would be bounded by the terminal staying open.

It is unscriptable, so evaluation runs would have to bypass the checkpoint. That would quietly undo
DEC-012: the distinction between answering non-interactively and removing the node only exists if
answering non-interactively is possible. A blocking prompt collapses them, and the collapse would
not announce itself — it would look like a reasonable test affordance.

And it puts the decision in memory rather than in a `ReviewerDecision` row. Section 2.5 requires
reviewer actions to be recorded, and reviewer acceptance and edit rates are primary evaluation
metrics. A decision that exists only as a keystroke is not measurable.

So the decision records that reviewer decisions reach the workflow through **one** writer
regardless of origin — interactive command, web form, or evaluation harness replaying recorded
decisions all produce identical rows. Replay is the same path with a different caller, not a
special case.

## Two things fell out

**`checkpoint_reference` is now vestigial.** Its description is "persistence reference"; it existed
to hold a framework checkpoint id, and DEC-016 removed the framework. `current_node` says where the
run stopped and `pending_human_review` says what it is waiting for. Removed, following the
precedent DEC-012 set with the two configuration booleans — a field whose referent no longer exists
is not harmless, because someone will find a use for it and that use will not be the documented
one.

**The human-review timeout stopped being a failure mode.** `current-architecture.md` section 11
lists it among the errors, with the response "pause the workflow, preserve state, resume when the
reviewer responds." Under persist-and-exit that is not an error at all — it is the normal state of
a paused run, which can wait indefinitely because waiting costs nothing when nothing is resident.
The entry is rewritten from a failure mode to a description of ordinary operation.

That is the second time this week a decision made a documented problem disappear rather than
solving it. DEC-015 did the same by making normalization line-preserving so the original-versus-
normalized ambiguity could not arise. It seems worth noticing as a pattern: the better decisions
here have removed the conditions for a class of bug rather than handling the bug.

## The friction I am least comfortable with

The completion condition is that **every** object named in `pending_human_review` has a decision. A
reviewer with fifty provisional findings decides fifty times; there is no supported "approve the
rest as-is."

That is deliberate — those decisions are the evaluation data, and a bulk-approve would produce
fifty identical rows carrying no signal, which is worse than useless because it would look like
signal. But it will feel like friction in the demo, and I do not have a good answer for the case
where a reviewer genuinely agrees with everything.

## Open next

DEC-017 leaves four questions, two of which are near-term: where reviewer identity comes from under
DEC-004, which has no authentication, and whether resume should verify the pending objects are
unchanged since the pause.

DX-16 (#34), how reviewer edits are represented on the object, is now the adjacent decision — this
one settled that decisions are recorded, not how an edit changes the thing it edits. DX-17 (#35),
CLI versus web, is deliberately untouched: the review package is derived rather than stored so the
mechanism does not presuppose an interface.
