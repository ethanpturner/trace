# unsigned-webhooks expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material Trace
reads is `../input/`.

## Provenance

An original small architecture authored for this project to exercise a documented-absent webhook signature check
(design-principles section 19). It is fictional and clean-room; no confidential or
employer-derived material appears. The input documents are what a team would supply; the
expected outputs here are derived from them against catalog 0.1 and are never shown to the
system. See `reviewer-notes.md` for the construction method and self-agreement check.

## What is here

- `evaluation-contract.yaml` — the grading policy (DEC-027), declaring no counts (DEC-028).
- `expected-findings.yaml` / `expected-documentation-gaps.yaml` — the outcome-side truth the
  harness scores (DEC-073), each entry citing the passage it rests on.
- `expected-questions.yaml` / `expected-rejections.yaml` — the clarifying questions and the
  claims a correct assessment does not make, each rejection naming its mechanism.
- `reviewer-notes.md` — the judgement calls and what is deliberately not authored.
