# Order Notifier expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material
Trace reads is `../input/`.

## Purpose

The duplicate-threats scenario (roadmap Stage 5): two documents — an integration guide and
incident-review notes — affirmatively describe the same unsigned callback intake on the
same endpoint. A correct assessment draws the conclusion from each source and reports the
weakness once: the provisional duplicates share a threat and a requirement, so DEC-052
merges them deterministically, retains the merged finding with `duplicate_of_id`, and
persists a merge record. The scorecard's `duplicate_finding_rate` is non-zero for this
scenario by design, and exactly one finding is approved.

## What is here

| File | Status |
| --- | --- |
| `evaluation-contract.yaml` | The grading policy. Declares no counts (DEC-028). |
| `expected-findings.yaml` | Authored (#328) — one finding, stated twice in the inputs. |
| `expected-documentation-gaps.yaml` | Authored (#328) — the replay-handling gap. |
| `expected-questions.yaml` | Authored (#328). |
| `expected-rejections.yaml` | Authored (#328) — double-reporting is the graded failure. |
| `reviewer-notes.md` | The checkpoint guidance for whoever plays the reviewer. |

The scenario carries a recording (`../recorded/`, #328), so `trace evaluate order-notifier`
replays it offline and scores it against these files.
