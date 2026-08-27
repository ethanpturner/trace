# Slide-claim traceability

Issue #356's first acceptance criterion: every slide claim traces to a repository artifact or a
measured number. This file is that check. Slides fall into three classes: **conceptual** — an
argument about the field that makes no claim about this repository and needs no artifact;
**illustrative** — a rhetorical number ("20 plausible findings", "500 things") that is framing,
not measurement, and is delivered as such; and **repository claims** — statements about Trace or
the demo, each traced below. A claim that cannot be traced does not go on a slide.

## Classification

| Slides | Class |
|---|---|
| 1, 3–13, 15, 17–18, 24–31 | Conceptual — no repository claim |
| 2, 32 | Speaker biography and contact — the speaker's to assert |
| 14, 16 | Illustrative numbers — "20 plausible findings" and "500 things" are rhetorical orders of magnitude, spoken as such, measured nowhere and asserted of no tool |
| 19–23 | Repository claims — traced below |

## The repository claims

| Slide | Claim | Where it is true |
|---|---|---|
| 19 | Trace makes the analysis observable rather than replacing the reviewer | The two structural checkpoints (DEC-005) and the reviewer-owned severity (DEC-030); `docs/product/vision.md` states the assist-not-replace position |
| 20 | What happened between input and finding is preserved | The execution ledger (`ExecutionRecord`, `src/trace_ai/domain/execution.py`), failed attempts kept in `traces/`, and the recorded-response replay that reproduces a run byte-for-byte (`scripts/replay_forgeflow.py` against `demo/forgeflow/recorded/report-hash.txt`) |
| 21 | A finding walks back to evidence, source context, and the execution trace | The lineage chain (`docs/architecture/data-model.md` section 32) rendered at `trace view` `/asm-001/lineage/fnd-001`; every approved finding's evidence resolves to a stored, hashed excerpt (`docs/eval/comparison.md`: 100%, 15/15 findings) |
| 22 | ForgeFlow: a fictional AI code-review platform, eight documents, one carrying a deliberate prompt-injection payload | `demo/forgeflow/input/` (8 files); the payload is `sample-repository-notes.md`; fictional provenance is stated in README's scope and disclosure section |
| 22 | fnd-003 was proposed by the model and rejected by the reviewer because it rested on silence | `demo/forgeflow/recorded/decisions-findings.yaml`; demo script beat 7; DEC-009 |
| 23 | The demo replays offline from committed fixtures, no provider key | `docs/product/demo-script.md`; the recording was captured from a live claude-opus-5 run on 2026-08-14 and replays byte-for-byte (`demo/forgeflow/recorded/provenance.md`, 38 recorded responses) |
| 23 | The demo sequence and recovery plan | The eight steps are `demo/forgeflow/speaker-notes.md`; the beat table, timings, and recovery artifacts are `docs/product/demo-script.md` — the second acceptance criterion, held by matching the slide notes to those files verbatim in [deck.md](deck.md) |

## Measured numbers available to the Trace segment

The draft deck quotes no measured number in slides 19–23. If a number is added, it comes from
this table and nowhere else; each is committed and regenerated offline.

| Number | Value | Source |
|---|---|---|
| Evidence-linked approved findings | 100% (15/15), hash-resolved and re-verified on read | `docs/eval/comparison.md` |
| Baseline citations that resolve verbatim | 54% / 43% / 47% (generic / structured / single-pass) — the baselines *do* cite, but under half can be checked automatically (DEC-151) | `docs/eval/citation-fidelity.md` |
| Injected-instruction compliance | 0% across 5 payload classes — **on authored recordings; no model has been run against a poisoned document** (DEC-152) | `docs/eval/comparison.md`; per-class basis in DEC-075 |
| Spurious findings | Trace 2 over its 13 current-shape captures; generic baseline 36 over 15 scenarios (17 on one zero-finding scenario); structured baseline 6 over 15 | `docs/eval/comparison.md` |
| Recall, said in the same breath | Trace matches 2 of 12 reachable expectations; the single-call baseline matches 4. Structure bought precision and cost recall | `docs/eval/scorecard.html` |
| Live-run cost and time | $6.92 ± $3.28; 2433 s mean (~41 minutes) per unsigned-webhooks run, n=5 | `docs/eval/comparison.md` (DEC-077) |
| Run-to-run stability | `missing-docs` 0 spurious in 5 of 5; `reply-tuner` expected finding in 3 of 5; `unsigned-webhooks` in 2 of 5. Not-inventing is stable, producing the right finding is not | `docs/eval/stability-633.md` |
| Authored recordings against live captures | same truth sets and matcher: 78% / 82% when the recordings were written offline, 17% / 13% now that they are live captures | `docs/eval/authored-versus-live.md` (DEC-153) |
| The ablation's one mover | removing evidence validation leaves every mapping unassessed, so the run emits no findings at all — it is structurally required rather than shown to improve findings (DEC-150). Critical review moves no metric in 15 scenarios; context approval moves one | `docs/eval/ablation.md` |
| ForgeFlow walkthrough counts | 8 documents, 16 components, 63 claims (14 unknown), 131 review subjects, 5 candidate findings, 4 approved, 1 rejected, 26 questions | `docs/product/demo-script.md`, replayed by `scripts/replay_forgeflow.py` |
| The flagship honest number | the live run matched none of the 3 authored expected findings and approved 4 defensible ones the truth set does not name | `docs/product/demo-script.md` beat 10; `docs/eval/comparison.md` |

## Corrections applied to the draft

- Slide 22's SYSTEM / QUESTION / FINDING placeholders read "[fill in]" in the draft; deck.md
  resolves them to ForgeFlow, the evidence question, and fnd-003.
- Slide 23's draft targeted 6–8 minutes; the committed walkthrough runs about 8:30 with the
  closer and 7:30 without the command-line asides, so deck.md says 7–9 minutes and names the cut.
- Slide 23's draft said "have a recorded backup and screenshots available"; deck.md names the
  committed recovery artifacts instead of leaving them implied.
