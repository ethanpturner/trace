# The recorded ForgeFlow run

This directory holds one complete run of the pipeline, captured live from `claude-opus-5`
(profile `primary-development`) on 2026-08-14: every model response the run consumed, the
reviewer decisions for both checkpoints, and the content hash of the report the run renders.
`uv run python scripts/replay_forgeflow.py` replays it end to end with no provider, no key, and
no network, and exits non-zero if the report's bytes stop matching `report-hash.txt`.
`tests/unit/test_forgeflow_replay.py` runs the same replay in the default suite.

## What this recording is

The responses were captured from live provider calls by `scripts/capture_forgeflow.py` (#324;
since generalized into `trace capture`, #482, and the script removed):
a recording wrapper behind the model seam wrote each successful response, in consumption order,
shaped exactly as `load_recorded_responses` reads them back. The reviewer decisions were authored
against what the live run actually produced — sixteen components, fifteen threats, five candidate
findings — with the scenario's `expected/reviewer-notes.md` as the judgment guide. The run is
scored against `demo/forgeflow/expected/` by the evaluation harness (DEC-073), and the scorecard
carries the honest result: strong context and mapping accuracy, one rejected candidate, and none
of the truth set's three expected findings matched — the run found real, defensible weaknesses
that are not the ones the truth set names.

**Retries are part of the recording.** Four calls failed schema validation live and were retried
with the validator's feedback; the failed responses are recorded in their consumed positions, so
a replay reproduces the retries exactly, within the default retry budget. One reviewer decision
is a rejection (fnd-003), taken on DEC-009 grounds: the run proposed a finding whose enforcement
evidence was silence, and the reviewer routed it back toward the gap the run had also raised.

The capture session spent roughly $30 of provider budget in total, including attempts that were
discarded along the way (truncations, grammar rejections, and validation failures — each one a
live-run defect fixed in the same change set). No per-call price is pinned here: the profile's
published rates and the execution ledger are the accounting surfaces.

The reviewer decisions reach the workflow through the same writers an interactive session uses
(DEC-017): `decisions-context.yaml` is an exported review file applied verbatim, and
`decisions-findings.yaml` drives the same severity, approval, and rejection functions the CLI
calls. Both checkpoints execute and their gates hold; replay is not an ablation (DEC-012).

## Version pins

| Pin | Value |
|---|---|
| Model profile | `primary-development` (provider `anthropic`, model `claude-opus-5`) |
| Captured | 2026-08-14, by `scripts/capture_forgeflow.py` (now `trace capture`, #482) |
| Workflow version | `0.1` |
| Requirements catalog | `0.1` |
| Report template | `report-v1` |
| Generation timestamp | `2026-08-14T12:00:00+00:00` (pinned in `scripts/replay_forgeflow.py`) |

The report carries exactly one timestamp, and the replayer pins it; everything else the run
writes is deterministic, which is what makes the pinned hash a claim worth checking.

## Files, in consumption order

The numbered files are consumed strictly in sorted order, one per model call including retried
calls; the replayer derives the list from the directory. The first file answers the context
extraction call, the last answers report generation, and everything between belongs to the
reasoning segment: one threat-analysis response, one mapping response per threat (plus recorded
failed attempts where the live run retried), one evidence-validation response, and one critique
response per threat. `decisions-context.yaml` is applied at checkpoint 1, `decisions-findings.yaml`
at checkpoint 2, and `report-hash.txt` pins the rendered report.
