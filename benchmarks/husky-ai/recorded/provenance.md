# Recorded run for the husky-ai scenario

Captured live from `claude-opus-5` on 2026-08-18 through `trace capture` (DEC-091), replacing
the authored offline recording file for file — the second live-captured scenario after the
flagship. Version pins: profile primary-development, workflow 0.1, catalog 0.1, report template
report-v1, generation timestamp 2026-08-11T12:00:00+00:00 (the capture's pinned stamp). One JSON
envelope per consumed model call, real usage on every envelope: 30 responses, 28 replay calls
(the report attempt pair occupies two consumed positions), $17.58. The capture's run-row total
was $26.83 over 45 calls — the difference is the interruption tax: seven critique responses a
killed session bought and never persisted (pruned from the promoted sequence after the
execution records identified them; the replay round-trip verified byte-for-byte against the
pinned hash afterwards), plus provider-overload attempts that produced nothing. Recorded here
rather than rounded away.

## The capture was interrupted four ways, and the recording survived them

This capture rode through a silent process death mid-mappings, a provider 529-overload window
that consumed a retry budget, an external kill mid-critique that orphaned the workflow run at
`running` (repaired through the execution ledger's own `complete` API; issue #613 records the
missing surface), and two capture-flow defects it surfaced and fixed: a resumed reason stage
re-applied context decisions (#484's resume fix), and `--from-recorded`'s fresh-root assumption
does not hold for an advanced data root. Every staged envelope survived every interruption; the
superseded ones are pruned above, and nothing in the promoted sequence was paid for twice.

## Reviewer decisions

Checkpoint 1 approved all 47 extracted objects as extracted — the extraction carried no
false-shaped transport labels — and answered the one blocking question (the model-blob writer
contradiction, obs-001) without inventing facts: both documented statements stand, the effective
writer set is undetermined, and the ambiguity is analysis input. Checkpoint 2 approved four of
eight candidates (fnd-005 high — the tampered-artifact code-execution path; fnd-001, fnd-006,
fnd-007 medium) and rejected four with recorded rationales: two as same-lens duplicates, two on
DEC-009 grounds — undetermined reachability and input-validation postures are the questions the
run itself asked (qst-002, qst-011), not findings.

## What this recording measures against the truth set

The truth set (`expected/`) was authored against the offline recording and expects findings on
`req-SECRET-001` and `req-AUTH-002`. The live run's approved findings sit under
`req-ADMIN-001`, `req-CICD-001`, and `req-LOG-002` — so the structural matcher scores this
recording as missed expectations beside spurious findings, the same shape as the flagship's
0-of-3 (DEC-116). Whether that is the evidence-assessment funnel again or genuine lens
divergence is what the `evidence_assessment_coverage` metric in this recording's replay is for.
The score is the measurement, not a defect in the recording.

The `baselines/` directory retains the authored offline baseline recordings; live baselines
remain with the keyed steps (DEC-100) and are budget-parked with the rest of the #484 sweep.
