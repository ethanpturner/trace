# nightly-reconciler expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material Trace
reads is `../input/`.

## Provenance

An original small architecture authored for this project to exercise the org-controls
assertion (#568, DEC-122; design-principles section 19). It is fictional and clean-room; no
confidential or employer-derived material appears, and the organization named by the asserted
controls is the fictional operator of org-controls catalog 0.2. The input documents are what a
team would supply; the expected outputs here are derived from them against requirements
catalog 0.3 and org-controls catalog 0.2, and are never shown to the system. See
`reviewer-notes.md` for the construction method and self-agreement check.

## What is here

- `evaluation-contract.yaml` — the grading policy (DEC-027), declaring no counts (DEC-028).
- `expected-findings.yaml` / `expected-documentation-gaps.yaml` — the outcome-side truth the
  harness scores (DEC-073), each entry citing the passage it rests on.
- `expected-questions.yaml` / `expected-rejections.yaml` — the clarifying questions and the
  claims a correct assessment does not make; both rejections name the
  `organizational_control` mechanism (DEC-122) and the asserted org-controls entry.
- `expected-control-mappings.yaml` — the mapping-step truth, carrying the two expected
  suppressions that rest on asserted organizational facts.
- `reviewer-notes.md` — the judgement calls and what is deliberately not authored.
