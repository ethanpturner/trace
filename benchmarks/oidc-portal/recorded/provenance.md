# Recorded run for the oidc-portal scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-19 via `trace capture` under
the `openrouter-economy` profile (DEC-135), in the #484 subset wave — replacing the authored
offline recording file for file. Version pins: profile openrouter-economy, workflow 0.2,
catalog 0.3 (the registry entry's), template report-v1, generation timestamp
2026-08-11T12:00:00+00:00. Fourteen envelopes, $1.84 staged: one extraction, one threat
analysis, five mappings, one evidence batch, five critical reviews, one report.
`report-hash.txt` is pinned from the deterministic double replay (the zero-finding stamp
defect; see the unsigned-webhooks provenance and the DEC-134 amendment).

## Reviewer decisions and what the recording measures

Checkpoint 1 approved all 34 objects — every one traceable — and answered the blocking
question honestly: authentication is thoroughly documented (OIDC, no local accounts, IdP
factor policy) and per-ticket authorization is not documented at all; undetermined, analysis
input. The run completed with zero candidate findings at full evidence coverage
(`evidence_assessment_coverage` 1.0), and against the truth set scores 0 matched, 0 missed,
0 spurious — the zero-finding path met exactly. The five threats' critiques and the
authorization question the run raised are the assessment's real output, which is DEC-013
working as designed.

## Live baselines (2026-08-20)

The `baselines/` directory holds live baselines captured from `openai/gpt-5.1` through
OpenRouter under `openrouter-economy` as part of the #484 backfill, replacing the authored
generic and structured files and adding the single-pass one. Scored against the truth set at
capture time: baseline-generic 0 matched, 0 missed, 17 spurious; baseline-structured 0/0/0;
baseline-single-pass 0/0/0. The generic baseline's seventeen inventions against a zero-finding
truth set are the sharpest precision differential any scenario has recorded; the structured
input alone removes all of them. The envelopes record findings, not usage — three single calls
at economy rates, cents each.
