# Recorded run for the rag-support-bot scenario

Captured live from `openai/gpt-5.1` through OpenRouter on 2026-08-19 via `trace capture` under
the `openrouter-economy` profile (DEC-135), in the #484 subset wave — replacing the authored
offline recording file for file. Version pins: profile openrouter-economy, workflow 0.2 (the
adversarial condition keeps its own 0.1 pin beside its authored recording), catalog 0.2,
template report-v1, generation timestamp 2026-08-11T12:00:00+00:00. Nineteen envelopes, $2.55
staged — one extraction, one threat analysis, seven mapping positions, two evidence positions,
seven critical-review positions (retry pairs consumed positionally on replay), one report.
Round trip verified byte-for-byte against the pinned hash.

## Reviewer decisions and what the recording measures

Checkpoint 1 approved all 53 objects as extracted; no blocking questions. Checkpoint 2
rejected all four candidates on DEC-009 grounds with recorded rationales: each established a
requirement's applicability — customer data crossing to documented, term-governed external
processors (no-training terms, TLS) — or an impact framing, and none an evidenced deficiency;
the retention question the index's silence raises is the question the run itself asked.
Evidence coverage was 1.0. Against the truth set this scores 0 matched, 1 missed, 0 spurious:
the strict reviewer line trades recall for a clean precision record, measured rather than
argued. Reconciliation is #589's.

## Live baselines (2026-08-20)

The `baselines/` directory holds live baselines captured from `openai/gpt-5.1` through
OpenRouter under `openrouter-economy` as part of the #484 backfill, replacing the authored
generic and structured files and adding the single-pass one. Scored against the truth set at
capture time: baseline-generic 0 matched, 1 missed, 4 spurious; baseline-structured 0/1/3;
baseline-single-pass 1 matched, 0 missed, 3 spurious. The single-pass baseline is the only
baseline in the backfill to match an expected finding, and it pays for it with three
inventions. The envelopes record findings, not usage — three single calls at economy rates,
cents each.
