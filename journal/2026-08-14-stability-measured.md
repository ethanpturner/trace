# Stability is a number now

## What changed

Issue #330 closed: the DEC-077 protocol has run live for the first time. Five completed
`claude-opus-5` runs of unsigned-webhooks — identical input, checkpoints decided by the
protocol's named default policy, 182 defaulted decisions disclosed — plus three failed attempts,
counted rather than hidden. The committed summary (`docs/eval/live-stability.json`) renders on
the scorecard as a live-stability section and flips the comparison table's Trace stability cell
from "not measured" to the measured truth.

The headline is the honest one: **the scenario's single expected finding matched in 2 of 5
runs.** Cost $6.92 ± $3.28 per run; runtime 41 ± 15 minutes; 15.4 ± 6.4 model calls; 584k ±
284k tokens. Evidence coverage was 100% in every run and no run produced a spurious finding —
the DEC-009 discipline held under variance — but *which* defensible conclusions a run reaches
moves substantially between runs. That is the documented, named weakness of LLM threat-modeling
tools, measured on our own system and reported without a gate, exactly as DEC-077 reasons:
the moment a variance number gates something, it stops being honest.

## What the protocol's failures taught

The first session lost three of five runs to one mechanical slip: the model wrote
`authentication: 'none'` where the documents are silent, and the validation node correctly
refused the DEC-009 violation — but the default policy had no hands to make the edit any
interactive reviewer would. Two fixes: the extract prompt now teaches that `none` is an
assertion ("absence of a statement is not a statement of absence"), and the default policy
performs exactly that one mechanical relabel, through the same reviewer-edit path a person
uses, counted among the defaulted decisions. The top-up session ran three for three.

The harness also gained its live mode — the stability path had never actually been runnable:
it demanded a recording for a condition that cannot have one while refusing offline replay.
Live runs now skip recordings, tolerate per-run failures as data, and the summary artifact is
read by the page builders the way the history file is: committed, never regenerated, because a
drift check cannot re-run a $35 protocol.

## Spend

This measurement cost roughly $45 across the two sessions (including the three failed runs'
partial spend). Today's total live spend, with the flagship capture, is about $75 — every
tranche disclosed in a provenance file or the summary artifact.

## Open

#331 (prompt comparison) and #332 (model comparison) are the remaining M11 measurements; the
live harness mode built here is most of what they need.
