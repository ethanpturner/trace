# The call count stops reading yesterday's row

## What changed

#388, the last pre-audit bug on the board. The `model_call_count`, `estimated_cost`, and
`token_usage` metrics read `WorkflowRun`'s totals — a snapshot written at the last pause — while
the evaluation node computes them inside the final segment, before `complete()` writes the
closing counters. The final segment's calls were invisible: invoice-agent read 13 of its 14
recorded calls, and oidc-portal read 1 of 8, because a zero-finding run never pauses at the
finding checkpoint and everything after context approval is one long uncounted segment.

The metrics now read `ExecutionLedger.counters()` — the computation `complete()` and `pause()`
already share, over the records the run wrote. That keeps one implementation, which is the
property the ledger's own docstring asks for: computed from what was written, never a parallel
tally that can drift. All three snapshot reads were fixed together; the issue named the call
count, but cost and tokens had the same segment-start staleness and would have under-reported
the first live run — the measurement #330 exists to take.

## The regression pin

The test derives its expectation from the recording itself — the count of response files the
scenario supplies — so authoring a new scenario cannot silently diverge from the test, and pins
oidc-portal, the worst case observed: 8 recorded responses, 8 counted, where the stale row said 1.

The committed pages do not move: the drift checks pass untouched, because the scorecard renders
cost (zero offline either way) and the corrected values live in the regenerable runtime feeds.
The fix matters most for the live run, where the cost cell will finally be the run's whole cost.
