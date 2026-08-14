# Parcelworks expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material
Trace reads is `../input/`.

## Purpose

The large-architecture scenario (roadmap Stage 5; evaluation-plan.md section 6, scenario
10): four zones, nineteen components, six actors, thirteen flows in one document. The
graded property is that scale does not change the rules — the size lives in the context,
not the finding count. Two findings rest on affirmative statements (the admin console's
customer sign-in path, the notification templates' body-level logging); the warehouse's
admittedly unwritten retention and the data zone's unstated enforcement are gaps; and the
rejections name the conclusions a nineteen-component surface most invites.

## What is here

| File | Status |
| --- | --- |
| `evaluation-contract.yaml` | The grading policy. Declares no counts (DEC-028). |
| `expected-findings.yaml` | Authored (#328) — two findings; the size is in the context. |
| `expected-documentation-gaps.yaml` | Authored (#328) — retention and enforcement. |
| `expected-questions.yaml` | Authored (#328). |
| `expected-rejections.yaml` | Authored (#328) — the conclusions scale invites. |
| `reviewer-notes.md` | The checkpoint guidance for whoever plays the reviewer. |

The scenario carries a recording (`../recorded/`, #328), so `trace evaluate
parcel-platform` replays it offline and scores it against these files.
