# The retry ceiling becomes operative, and the retry count becomes true

## What changed

The audit's retry-accounting pair, delivered as one change and recorded as DEC-084. #397: the
configuration's `maximum_retries_per_node` now governs the attempt loops — `Budget.retry_policy()`
derives the policy from the configured value, `resolve_retry_policy` gives it precedence in all
six agent nodes, and configuring zero retries now produces exactly one attempt where it previously
produced three whatever the configuration said. #398: `ExecutionRecord.retry_number` is now the
retries the execution consumed, set by the attempt loop as it runs, on success and failure paths
alike — so the evaluation's retries metric sums a measurement instead of a constant zero.

`Budget.check_retry` and `LimitKind.RETRIES` are gone. They were the dead half of a
twice-declared enforcement that fired nowhere.

## The two decisions worth recording

**Where the retries ceiling lives.** Section 27 says the orchestrator enforces five ceilings, and
the letter of that put `check_retry` on the budget — where it sat uncalled, because a retry
decision happens between a classified failure and the next attempt, inside the node, where the
orchestrator never stands. The repair keeps the *value* in the one budget the orchestrator owns
and moves the *check* to the only place a retry decision exists. A run stopped by exhausted
retries is classified by the failing attempt's error class with the attempt count, which is
section 26's semantics — "retries exceeded" was never the right stop reason, and removing the
unused `LimitKind` member says so structurally.

**One record per execution, not per attempt.** The orchestrator's docstring claimed a record per
model attempt; the corpus's field table says "retry count". Per-attempt records would have moved
model-call accounting, the counters, and the drift-checked evaluation pages for no reader's
benefit — the per-attempt story is already told by the `attempt_N` metadata and the preserved
outputs under `traces/`. So the record stays one per node execution and its `retry_number` says
how many retries it took, which is the reading the field table always supported. The drift checks
and the pinned replay passing untouched confirmed the choice: no committed feed moved.

## Mechanics

`Execution` gained a mutable `retry_number` the loop sets (`attempts - 1` at each attempt's
start), because the count is only known at exit and the record is written when the execution
closes. The six nodes changed identically: an optional policy field deferring to the budget, and
one line in the attempt closure.

## Open next

From the audit backlog, #396 (the duration ceiling counting paused time) is the remaining runtime
bug, and it touches the same orchestrator/ledger seam this change just visited. #399 and #400
remain on the checkpoint-1 surface.
