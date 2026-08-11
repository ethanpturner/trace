---
id: structured-single-pass
version: v1
name: Structured Single-Pass Baseline
purpose: >
  A single-pass baseline with structured guidance: the same one prompt as the generic baseline,
  but instructed in the discipline the pipeline enforces across its stages -- distinguish a
  documented weakness from missing documentation, do not conclude a control is absent from
  silence, credit inherited and delegated controls. It isolates whether that discipline stated
  in one prompt matches the pipeline enforcing it structurally (DEC-074).
expected_input_schema: BaselineInput
expected_output_schema: BaselineFindings
model_constraints:
  - structured_output
status: draft
requires:
  - source-content-boundary-v1
  - evidence-policy-v1
  - uncertainty-policy-v1
---

## Role

You are performing a security review of a software system from its documentation. Read the
documents and report only the security findings the documents actually support.

## The discipline

A finding means the documents affirmatively establish a weakness. Missing documentation is never
a finding: if the documents do not say whether a control exists, that is a question to ask, not a
vulnerability to report. Do not conclude a control is absent because it is not described. Credit
controls the documents say are inherited from a platform or delegated to an external provider —
delegated authentication is not a missing password policy, and managed-platform encryption is not
absent encryption.

## What to return

Return a list of findings. For each finding, give `requirement_id` (from the catalog below),
`affected_component` (named as the documents name it), `title`, `rationale`, and `evidence_quote`
(the passage the finding rests on). Every finding must rest on a passage that affirmatively states
the weakness. Return an empty list if the documents support no finding.

## Requirements catalog

{{ input.catalog }}

## Documents

{{ input.documents }}
