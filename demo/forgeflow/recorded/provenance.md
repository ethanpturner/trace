# The recorded ForgeFlow run

This directory holds one complete offline run of the pipeline: eight model responses, the
reviewer decisions for both checkpoints, and the content hash of the report the run renders.
`uv run python scripts/replay_forgeflow.py` replays it end to end with no provider, no key, and
no network, and exits non-zero if the report's bytes stop matching `report-hash.txt`.
`tests/unit/test_forgeflow_replay.py` runs the same replay in the default suite.

## What this recording is, and is not

The responses are authored offline against the `offline-fake` profile and the deterministic
model — they were not captured from a provider call. They are shaped exactly as recordings are
consumed (one JSON file per model call, schema inferred structurally, replayed in order), so a
live capture can replace them file for file without changing the replayer. The run is a
representative slice of the ForgeFlow scenario — two threats, one finding, one documentation
gap — not the benchmark truth run; scoring against `demo/forgeflow/expected/` is the evaluation
harness's work (DEC-073), not this recording's.

The reviewer decisions reach the workflow through the same writers an interactive session uses
(DEC-017): `decisions-context.yaml` is an exported review file applied verbatim, and
`decisions-findings.yaml` drives the same severity and approval functions the CLI calls. Both
checkpoints execute and their gates hold; replay is not an ablation (DEC-012).

## Version pins

| Pin | Value |
|---|---|
| Model profile | `offline-fake` (provider `fake`, model `deterministic-fake`) |
| Workflow version | `0.1` |
| Requirements catalog | `0.1` |
| Report template | `report-v1` |
| Generation timestamp | `2026-08-11T12:00:00+00:00` (pinned in `scripts/replay_forgeflow.py`) |

The report carries exactly one timestamp, and the replayer pins it; everything else the run
writes is deterministic, which is what makes the pinned hash a claim worth checking.

## Files, in consumption order

| File | Consumed by |
|---|---|
| `01-context-extraction.json` | the Context Extraction agent's one call |
| `decisions-context.yaml` | checkpoint 1, applied through the review-file writer |
| `02-threat-analysis.json` | the Threat Analysis agent's one call |
| `03-mapping-thr-001.json`, `04-mapping-thr-002.json` | one mapping call per threat |
| `05-evidence-validation.json` | the Evidence Validation agent's one call |
| `06-critical-review-thr-001.json`, `07-critical-review-thr-002.json` | one critic call per threat; both found nothing to challenge |
| `decisions-findings.yaml` | checkpoint 2: severity assigned, the finding approved |
| `08-report-sections.json` | the Report Generation agent's one call |
| `report-hash.txt` | the pinned content hash of the rendered report |
