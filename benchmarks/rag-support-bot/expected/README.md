# Relay Answers expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material Trace
reads is `../input/`.

## Purpose

The AI-system-retrieval scenario (#489, DEC-098): a RAG support assistant documented well in
most respects — a governed, reviewed corpus write path; delimited prompt context; identifier
stripping toward the provider — with one affirmatively documented weakness and one genuine
silence. It exists to make the 0.2 catalog's retrieval-augmentation requirements measurable:

- `expected-findings.yaml` — FND-RSB-01, the cross-workspace retrieval finding (req-RAG-002).
  The overview states relevance alone selects passages from one shared index: a documented
  absence, which is what makes this a finding rather than a DEC-009 violation.
- `expected-documentation-gaps.yaml` — GAP-RSB-01 (req-RAG-003): deletion propagation to the
  index is unstated either way.
- `expected-questions.yaml` — Q-RSB-01, the gap's paired question.
- `expected-rejections.yaml` — the two false positives a naive pass commits here: prompt
  injection reported over documented fencing (req-AI-001), and an ungoverned write path
  claimed against a documented one (req-RAG-001).
- `evaluation-contract.yaml` — matching policy; authored against catalog 0.2.
- `reviewer-notes.md` — the judgment guide used when authoring the recorded decisions.

Every file is authored; the recorded run under `../recorded/` replays offline against it.
