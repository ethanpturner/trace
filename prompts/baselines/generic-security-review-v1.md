---
id: generic-security-review
version: v1
name: Generic Security Review Baseline
purpose: >
  A single-pass baseline: one prompt asking for a security review of the supplied documents,
  with no context model, no evidence validation, no critical review, and no human checkpoint.
  It exists so the pipeline's output can be compared against the simplest thing that produces
  findings from the same documents (DEC-074).
expected_input_schema: BaselineInput
expected_output_schema: BaselineFindings
model_constraints:
  - structured_output
status: draft
requires:
  - source-content-boundary-v1
---

## Role

You are performing a security review of a software system from its documentation. Read the
documents and report the security findings you can identify.

## What to return

Return a list of findings. For each finding, give:

- `requirement_id`: the identifier of the requirement it relates to, chosen from the catalog below.
- `affected_component`: the component it concerns, named as the documents name it.
- `title`: a short statement of the finding.
- `rationale`: why it is a finding.
- `evidence_quote`: the passage from the documents the finding rests on.

Report the findings the documents support. If the documents do not describe a security problem,
return an empty list.

## Requirements catalog

{{ input.catalog }}

## Documents

{{ input.documents }}
