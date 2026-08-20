# Recorded run for the missing-docs scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-19 via `trace capture` under
the `openrouter-economy` profile (DEC-135), in the #484 subset wave — replacing the authored
offline recording file for file. Version pins: profile openrouter-economy, workflow 0.2,
catalog per the registry, template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.
Eighteen envelopes, $2.83 staged — one extraction, one threat analysis, five mappings, four
evidence positions, five critical reviews, two report positions (a retry pair). Hash pinned
from the deterministic double replay (the zero-finding stamp defect; see the DEC-134
amendment).

## Reviewer decisions and what the recording measures

The scenario is the DEC-009 thesis case: a two-paragraph note, everything material
undocumented. Checkpoint 1 approved all 20 objects — the extraction labelled every
undetermined field `unknown` and asserted nothing the note does not say. The run completed
with zero candidate findings at full evidence coverage, scoring 0 matched, 0 missed,
0 spurious against a truth set that expects exactly this: questions and gaps, no findings
manufactured from silence. The central claim's cheapest demonstration, now live-captured.

## Live baselines (2026-08-20)

The `baselines/` directory holds live baselines captured from `openai/gpt-5.1` through
OpenRouter under `openrouter-economy` as part of the #484 backfill. Scored against the truth
set at capture time: all three — generic, structured, single-pass — 0 matched, 0 missed,
0 spurious. On the scenario built around absent documentation, none of the one-call baselines
invents a finding from the silence; the DEC-009 differential this scenario measures shows up
in the gap-versus-finding layer, not the finding counts. The envelopes record findings, not
usage — three single calls at economy rates, cents each.
