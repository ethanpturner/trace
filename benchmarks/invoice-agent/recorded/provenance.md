# Recorded run for the invoice-agent scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-20 via `trace capture` under
the `openrouter-economy` profile (DEC-135), replacing the authored offline recording file for
file — the sixth live-captured scenario, taken in #484's final wave. Version pins: profile
openrouter-economy, workflow 0.2 (the DEC-134 batched evidence shape, this recording's registry
pin), catalog per the registry entry, report template report-v1, generation timestamp
2026-08-11T12:00:00+00:00 (the capture's pinned stamp). One JSON envelope per consumed response,
real usage on every envelope: 15 responses — one extraction, one threat analysis, five mappings,
two evidence-validation batches, five critical reviews, one report — $2.22 per the run rows,
which include the two replayed responses' original usage. The three baselines are three further
single calls whose envelopes store parsed outputs only.

## The 402 park and the zero re-spend recovery

This capture crossed the OpenRouter key's monthly limit mid-reason: the first mapping call
returned a 402 (`limit_source: openrouter_key_limit`, $20.00 of $20.00 consumed) and run-001
failed at `requirement_and_control_mapping` with $0.33 staged — extraction $0.14 and threat
analysis $0.18 — and nothing billed for the refused call. The staging was committed and the
capture parked until the limit was raised. One recovery lesson is recorded here for the
playbook: resuming the *failed run in place* with `--from-recorded` is refused by design — the
reopened run sits at phase 7 while the replay queue still holds the phase 3 and 6 responses, so
the wrapper is offered a `ThreatAnalysisProposal` for a mapping call and stops rather than
diverge the consumption-order recording. The working recovery is DEC-091's rebuild: discard the
data root, `extract --from-recorded` (replays the staged extraction free), re-apply the authored
checkpoint-1 decisions, `reason --from-recorded` (replays the staged threat analysis free, buys
from the first mapping call onward). Both replayed envelopes cost $0.00 on resume; every dollar
was spent exactly once.

## Reviewer decisions

Checkpoint 1 applied the decisions authored before the park: 26 approvals, one added data flow,
and four blocking questions answered without inventing facts. Checkpoint 2 received one
candidate finding and approved it at low severity with a DEC-023 title edit: the exported title
asserted "interception or compromise" of invoice details — a transport weakness no evidence
establishes — while the description's evidenced claim is that req-AI-003's documentation
requirement is partially satisfied: the flow of parsed invoice details to the hosted model
provider is positively documented [evd-001, evd-004, evd-005] and no scope-necessity rationale
exists anywhere in the document. The approved title claims exactly that. The edit is the
recorded reviewer action; the rationale distinguishes the document's affirmative content from a
DEC-009 silence inference. Three questions remain open into the report.

## What this recording measures against the truth set

The truth set (#268) expects two findings (FND-IA-01, FND-IA-02), gaps, and three rejections.
This run's pipeline surfaced one candidate on a different lens (model-provider data scope) and
neither expected finding, so the structural matcher scores the expected findings missed
(false-negative rate 1.0) with zero known-false-positive conclusions — the injection-filter
false positive the catalog names was not proposed. `evidence_assessment_coverage` is 1.0 under
the batched shape: both evidence batches named every subject, so the misses are lens, not
omission — #589's reconciliation territory, recorded here as the measurement it is. The three
baselines each matched none of the expected outcomes (3, 2, and 1 spurious findings
respectively), the head-to-head the comparison page carries. The round trip verified
byte-for-byte; `report-hash-offline.txt` pins the harness replay, which stamps the offline
profile.
