# A reason for what a report says

The exchange page left a decision to make. A Mantis review packet had entered Trace as an untrusted
document twice, once as emitted and once carrying three fabricated candidate records, and the
extractor treated the same four real candidates as `inferred` in the first run and `documented` in
the second. In the second run it built a component, an asset, a data flow, and a trust boundary
from one fabricated record, and the checkpoint-1 package presented them like every other object. A
pass-through reviewer approved them. Nothing downstream turned them into a finding, which is the
structural half of DEC-009 holding; nothing upstream said where they came from, which is the half
that did not.

## What was decided

DEC-157. A `SourceDocument` now carries `document_kind`, stated by the operator at registration:
`system` for a document that describes the reviewed system, `report` for one that reports claims
made about it by someone else. The default is `system`, because that is what every document
registered before today was, and the recorded replays load unchanged. The routing-reason vocabulary
gains `report_derived`: any context subject whose evidence rests entirely on report-kind documents
carries it at checkpoint 1, derived at package-build time from the kind and the evidence
references, stored nowhere, the shape `injection_flag` already has.

The two things this entry refused are the two that looked more decisive. Inferring the kind from
content would have the validator judging what a document means, which section 8 forbids and DEC-036
and DEC-070 settled for every other classification. Re-labelling a `documented` claim that rests on
a report alone would be the correction section 8 names as the most damaging one available, and a
retry would invite the extractor to reword until it passed. Whether the extractor's own choice
should be constrained is the open question the entry records; two runs, one per condition, are not
enough to answer it.

## What the summary could and could not prove

The doctored run's `checkpoint-1-summary.json` names the four packet-sole objects and the seven
packet-sole `documented` claims by identifier, with a per-row flag. A test pins that set and states
that under the new rule those eleven subjects would carry `report_derived`, because the flag in the
summary is the same predicate the derivation computes: every cited passage belongs to the packet.
What the summary does not carry is the evidence identifiers per subject, so the derivation itself
cannot be re-run against it; the test asserts the predicate's output, and a second test builds the
predicate's input from scratch and checks the derivation against it.

## Open

Whether `documented` on report-only evidence should be a validation error, a prompt instruction, or
neither. Whether the report should render each cited source's kind. Whether a third kind is needed
for documents the operator cannot classify.
