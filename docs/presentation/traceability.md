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
| 21 | A finding walks back to evidence, source context, and the execution trace | The lineage chain (`docs/architecture/data-model.md` section 32) rendered at `trace view` `/asm-001/lineage/fnd-001`; every approved finding's evidence resolves to a stored, hashed excerpt (`docs/eval/comparison.md`: 100%, 17/17 findings) |
| 22 | ForgeFlow: a fictional AI code-review platform, eight documents, one carrying a deliberate prompt-injection payload | `demo/forgeflow/input/` (8 files); the payload is `sample-repository-notes.md`; fictional provenance is stated in README's scope and disclosure section |
| 22 | fnd-003 was proposed by the model and rejected by the reviewer because it rested on silence | `demo/forgeflow/recorded/decisions-findings.yaml`; demo script beat 7; DEC-009 |
| 23 | The demo replays offline from committed fixtures, no provider key | `docs/product/demo-script.md`; the recording was captured from a live claude-opus-5 run on 2026-08-14 and replays byte-for-byte (`demo/forgeflow/recorded/provenance.md`, 38 recorded responses) |
| 23 | The demo sequence and recovery plan | The eight steps are `demo/forgeflow/speaker-notes.md`; the beat table, timings, and recovery artifacts are `docs/product/demo-script.md` — the second acceptance criterion, held by matching the slide notes to those files verbatim in [deck.md](deck.md) |

## Measured numbers available to the Trace segment

The draft deck quotes no measured number in slides 19–23. If a number is added, it comes from
this table and nowhere else; each is committed and regenerated offline.

| Number | Value | Source |
|---|---|---|
| Evidence-linked approved findings | 100% (17/17) | `docs/eval/comparison.md` |
| Injected-instruction compliance | 0% across 5 payload classes | `docs/eval/comparison.md`; per-class basis in DEC-075 |
| Spurious findings | Trace 4 over 12 scenarios; generic baseline 5 over 4 scenarios; structured baseline 0 over 4 | `docs/eval/comparison.md` |
| Live-run cost and time | $6.92 ± $3.28; 2433 s mean (~41 minutes) per unsigned-webhooks run, n=5 | `docs/eval/comparison.md` (DEC-077) |
| Run-to-run stability | expected finding matched in 2 of 5 live runs | `docs/eval/comparison.md` |
| The ablation's one mover | removing evidence validation raises the false-negative rate to 100% on 7 of 12 scenarios; critical review and context approval move no metric on these recordings | `docs/eval/ablation.md` |
| ForgeFlow walkthrough counts | 8 documents, 16 components, 63 claims (14 unknown), 131 review subjects, 5 candidate findings, 4 approved, 1 rejected, 26 questions | `docs/product/demo-script.md`, replayed by `scripts/replay_forgeflow.py` |
| The flagship honest number | the live run matched none of the 3 authored expected findings and approved 4 defensible ones the truth set does not name | `docs/product/demo-script.md` beat 10; `docs/eval/comparison.md` |

## Corrections applied to the draft

- Slide 22's SYSTEM / QUESTION / FINDING placeholders read "[fill in]" in the draft; deck.md
  resolves them to ForgeFlow, the evidence question, and fnd-003.
- Slide 23's draft targeted 6–8 minutes; the committed walkthrough runs about 8:30 with the
  closer and 7:30 without the command-line asides, so deck.md says 7–9 minutes and names the cut.
- Slide 23's draft said "have a recorded backup and screenshots available"; deck.md names the
  committed recovery artifacts instead of leaving them implied.
