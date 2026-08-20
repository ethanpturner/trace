# Recorded run for the order-notifier scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-20 via `trace capture` under
the `openrouter-economy` profile (DEC-135), replacing the authored offline recording (#328) file
for file — the Wave B lead of the #484 sweep. Version pins: profile openrouter-economy, workflow
0.2 (the DEC-134 batched evidence shape, this recording's registry pin), catalog per the registry
entry, report template report-v1, generation timestamp the capture's pinned stamp. Fifteen JSON
envelopes, one per consumed response, real usage on every envelope: one extraction, one threat
analysis, four mappings, four evidence-validation batches, four critical reviews, one report.
$2.21 over 14 calls per the run rows; nothing unstaged — no retries, no failed attempts. Model
wall clock roughly 43 minutes.

One checkpoint-1 wedge, recovered at zero re-spend: the extractor set `authentication: none` on
the intake flow, and the validation node refused approval — a flow's transport fields never carry
a false-like (data-model.md section 14); documented absence is the claims' to carry (ctx-005,
ctx-014 both state the unsigned intake affirmatively). The reviewer edit set the flow field to
`unknown`, and the DEC-091 rebuild replayed the staged extraction free. This is the same wedge
the subset wave recorded, now with its second worked example.

## Reviewer decisions

Checkpoint 1 approved all 32 subjects — four components, two actors, two assets, three flows,
one boundary, twenty claims, every one traceable to the two input documents — with the one flow
edit above. Two questions were answered from documentation (signing is not enabled and its
enablement is unscheduled backlog work; the endpoint is reachable by effectively anonymous
internet callers), and three were left open: replay handling (the truth set's expected gap),
channel-API authentication, and the operator question. Checkpoint 2 had no subjects: the run
completed with no candidate findings, so no finding decisions exist and the report stage folded
into the reason stage (the zero-finding completion path, its `GENERATED_AT` pinned).

## What this recording measures against the truth set

The truth set (#328) expects exactly one finding — the unsigned callback intake, documented in
both sources — and grades the DEC-052 duplicate merge. The live run minted mappings against
req-WEBHOOK-001/002 and req-TPI-002 and then dropped every candidate in the evidence-validation
and critique lens: the run's own questions (qst-006 through qst-012) ask for a "formal definition
of req-WEBHOOK-001", "an explicit mapping table", and confirmation of the threat model's
documentation — meta-documentation about the catalog and the analysis, not about the system under
review. The structural matcher scores FND-ON-01 **missed** (`false_negative_rate` 1.0), zero
spurious, `evidence_assessment_coverage` 1.0 — the miss is lens, not omission — and
`duplicate_finding_rate` 0 with no data: no provisional findings were minted, so the merge
machinery the scenario grades never engaged. The two gaps the run did mint are the same
meta-documentation shape and match nothing expected (`documentation_gap_precision` 0). This is
the unsigned-webhooks signature — a documented absence judged unconcludable rather than unmet —
now recorded on the scenario that was built to measure duplicate handling, where it preempts the
measurement. #589's reconciliation territory.

## Baselines, the uncomfortable row

All three live baselines (same day, same model, `recorded/baselines/`) **matched** the expected
finding: baseline-generic 1 matched / 1 spurious, baseline-structured 1/0, baseline-single-pass
1/0. On this scenario the one-call baselines beat the pipeline on recall outright — the pipeline's
evidence bar, not model capability, is what withheld the conclusion. The row stands as measured.

## Round trip

`report-hash.txt` pins the live report (`sha256:255125f4…15cca`); `report-hash-offline.txt` pins
the harness replay (`sha256:ca8061da…348c`), verified "against the scenario's recorded pin" on
two consecutive replays.
