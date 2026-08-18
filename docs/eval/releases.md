# Release record

The longitudinal record evaluation-plan section 17 specifies: every release records its
version, date, major changes, evaluation summary, known regressions, and outstanding issues.
Sections are authored, newest first. The evaluation-summary block inside each section is
generated from the committed artifacts by `scripts/build_release_record.py` and rewritten in
place between its markers — the numbers a release claims are the numbers the artifacts hold,
and `--check` fails on drift. `tests/unit/test_release_record.py` holds every section to the
section-17 shape and every git tag to a section.

## v0.1 — 2026-08-17

### Major changes

The first release: the complete MVP pipeline. All six model-assisted agents behind
deterministic validation nodes, fourteen orchestrated phases, both structural human
checkpoints, and the rendered sixteen-section report. The evaluation harness replays thirteen
authored benchmark scenarios offline with baselines, ablations, the adversarial condition, and
a CI-checked scorecard; the flagship ForgeFlow recording is a live capture that replays
byte-for-byte. Two provider adapters sit behind the model seam under one conformance contract.
The three delivery waves that assembled this surface are recorded in the journal and the
decision log (through DEC-105).

### Evaluation summary

<!-- evaluation-summary -->
- Retained snapshot 2026-08-14 (git `0f3348e`, catalog 0.1), the latest in `docs/eval/history.jsonl`.
- Pooled over 13 authoritative rows across 12 scenarios: precision 76%, recall 81%, F1 79%.
- Live stability (DEC-077): 5 runs of `unsigned-webhooks` on `primary-development`, 3 failed, mean cost $6.92 per completed run. Everything else replays offline; a dash on the scorecard is unmeasured, never zero.
<!-- /evaluation-summary -->

### Known regressions

None recorded — this is the first entry, so there is no prior release to regress from. The
live-capture caveat carries forward rather than regressing: the flagship live run's approved
findings matched none of the truth set's three expected findings (real weaknesses, wrong
requirement lens; `demo/forgeflow/recorded/provenance.md`).

### Outstanding issues

- The keyed live-measurement track: the eleven-scenario live sweep with live baselines (#484),
  the prompt-version comparison recording (#331), and the model comparison recording (#332).
- The narrated demo video (#353).
- The open round-3 issues at cut time, tracked on the issue list.
