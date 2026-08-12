# Kiosk Sync Service expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material
Trace reads is `../input/`.

## Purpose

The explicit missing-documentation scenario (roadmap Stage 5; evaluation-plan.md section 6,
scenario 6): a one-page note that establishes what the system does — customer order records
moving from kiosks to a stored service — and almost nothing about its protections. The
graded behaviour is DEC-009's: silence resolves to documentation gaps and paired questions,
never to findings. `expected-findings.yaml` is empty by design, and the rejections name the
three invented-fact claims a generic review most often produces from an input like this.

## What is here

| File | Status |
| --- | --- |
| `evaluation-contract.yaml` | The grading policy. Declares no counts (DEC-028). |
| `expected-findings.yaml` | Authored (#328) — empty by design. |
| `expected-documentation-gaps.yaml` | Authored (#328) — the three gaps silence resolves to. |
| `expected-questions.yaml` | Authored (#328) — one paired question per gap. |
| `expected-rejections.yaml` | Authored (#328) — the invented-fact claims. |
| `reviewer-notes.md` | The checkpoint guidance for whoever plays the reviewer. |

The scenario carries a recording (`../recorded/`, #328), so `trace evaluate missing-docs`
replays it offline and scores it against these files.
