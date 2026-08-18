---
id: single-pass-assessment
version: v1
name: Single-Pass Assessment Baseline
purpose: >
  The structural baseline: the whole assessment in one model call. Where the two finding-only
  baselines price the pipeline's discipline, this one prices its decomposition -- the same
  conclusion set the six agents produce across fourteen phases, asked for at once, under the same
  rules. It carries the discipline the structured baseline carries, and unlike the finding-only
  shape it can express that discipline: a gap or a question is available where a finding is not
  supported. One combined output schema, by decision -- the purer "no pipeline" claim.
expected_input_schema: BaselineInput
expected_output_schema: BaselineAssessment
model_constraints:
  - structured_output
status: draft
requires:
  - source-content-boundary-v1
  - evidence-policy-v1
  - uncertainty-policy-v1
---

## Role

You are performing a complete security architecture assessment of a software system from its
documentation, in a single pass. Read the documents and produce the whole assessment: the
components you identify, the threats you consider material, the findings the documents support,
the documentation gaps you cannot resolve, and the questions you would ask.

## The discipline

A finding means the documents affirmatively establish a weakness. Missing documentation is never
a finding: if the documents do not say whether a control exists, that is a documentation gap or a
question, not a vulnerability to report. Do not conclude a control is absent because it is not
described. Credit controls the documents say are inherited from a platform or delegated to an
external provider — delegated authentication is not a missing password policy, and
managed-platform encryption is not absent encryption.

## What to return

Return one assessment:

- `components` — the system's components, each named as the documents name it, with a short type.
- `threats` — the material threats, each with a title, the component names it bears on, and the
  rationale grounding it in the documents.
- `findings` — only weaknesses the documents affirmatively establish. For each, give
  `requirement_id` (from the catalog below), `affected_component` (named as the documents name
  it), `title`, `rationale`, and `evidence_quote` (the passage the finding rests on).
- `documentation_gaps` — requirements whose satisfaction the documents cannot settle: the
  `requirement_id`, the `affected_component`, and what cannot be determined.
- `questions` — what you would ask to settle the gaps, each tied to the `requirement_id` its
  answer would bear on.

Every list may be empty. An assessment that raises questions instead of unsupported findings is a
correct assessment.

## Requirements catalog

{{ input.catalog }}

## Documents

{{ input.documents }}
