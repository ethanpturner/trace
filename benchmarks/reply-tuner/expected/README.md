# Reply Tuner — expected outputs

The truth set for the fine-tuning scenario (#531, DEC-114). Nothing in this directory is
supplied to Trace during an assessment; a benchmark that hands the system under test its own
answer key measures nothing.

The scenario exists to exercise the fine-tuning requirement pack (catalog 0.3,
`req-TRAIN-001..003`) in all three of its shapes at once: a documented negative that is a
finding (unminimized customer transcripts train the model), a silence that is a gap (artifact
lineage), and a documented control whose absence a generic review asserts anyway (the governed
write path, recorded as a suppressed conclusion on its satisfied mapping).

## What is here

- `evaluation-contract.yaml` — the grading policy (DEC-027), declaring no counts (DEC-028).
- `expected-findings.yaml` / `expected-documentation-gaps.yaml` — the outcome-side truth the
  harness scores (DEC-073), each entry citing the passage it rests on.
- `expected-questions.yaml` / `expected-rejections.yaml` — none authored and the three claims
  a correct assessment does not make, each rejection naming its mechanism.
- `reviewer-notes.md` — the judgement calls and what is deliberately not authored.
