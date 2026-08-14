# The duration ceiling stops counting reviewer time

## What changed

One line in the orchestrator, closing #396. `run()` measured the duration ceiling from
`WorkflowRun.started_at` — set once when the run first began and never reset by a pause or a
resume — so the ceiling was spending its budget on wall-clock time that included the human review
at a checkpoint. With the default ceiling of an hour, any `trace resume` more than an hour after
the run began stopped on its first step with `maximum_workflow_duration`, which contradicted
DEC-017's own words: pausing is stopping, waiting costs nothing, there is no timeout.

The measurement base is now the orchestrator loop's entry — the start of the current process's
active segment. Since DEC-017 makes a resume a new process, each segment gets the full ceiling,
and the ceiling does what `limits.py` always said it was for: bounding a run that is stuck, not
one that waited for a person.

## Why per-segment rather than cumulative

The alternative was accumulating active time across segments on the run row, which needs a
persisted field, a data-model change, and pause-time bookkeeping — to defend against a run that
is slow in aggregate but never stuck in any segment, which is not the failure the ceiling exists
to catch. The stuck-run detector is per-segment by nature. No decision-log entry: this restores
documented behavior rather than choosing new behavior.

The new test is the one the audit noted was missing: a ledger whose run row started hours ago —
exactly what a resume after a long review looks like — runs to its stop point instead of failing
on the first step.

## Open next

The audit backlog's remaining code items are on the checkpoint-1 surface (#399 wiring the three
unreachable reviewer actions, #400 the dead sixth trigger) and the evaluation milestone M11
(#403, #404, #405). The two doc sweeps (#410, #411) are ready whenever a docs pass fits.
