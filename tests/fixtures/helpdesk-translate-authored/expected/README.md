# Helpdesk Translate expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material
Trace reads is `../input/`.

## Purpose

The third-party-integration scenario (roadmap Stage 5; evaluation-plan.md section 6,
scenario 9): a connector sending full customer ticket content to an external translation
SaaS. The graded distinction is between the *relationship* and the *provider*: the
documents affirmatively state that no retention or secondary-use agreement exists and that
the delegated token is over-scoped by convenience — two findings — while what the provider
actually does with submitted text is unknown and must stay out of the findings
(REJ-TG-01). Token custody is the one gap.

## What is here

| File | Status |
| --- | --- |
| `evaluation-contract.yaml` | The grading policy. Declares no counts (DEC-028). |
| `expected-findings.yaml` | Authored (#328) — the missing agreement and the over-scoped token. |
| `expected-documentation-gaps.yaml` | Authored (#328) — token custody. |
| `expected-questions.yaml` | Authored (#328). |
| `expected-rejections.yaml` | Authored (#328) — provider-behaviour claims stay out. |
| `reviewer-notes.md` | The checkpoint guidance for whoever plays the reviewer. |

The scenario carries a recording (`../recorded/`, #328), so `trace evaluate
translation-gateway` replays it offline and scores it against these files.
