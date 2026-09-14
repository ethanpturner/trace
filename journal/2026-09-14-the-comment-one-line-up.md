# The comment one line up

Closing #696, the evidence threshold rendered into every report and enforced nowhere. The fix took
an hour; understanding what was actually broken took most of it, and the issue's own framing was
half wrong.

## What was not broken

DEC-013's rules are enforced, and thoroughly. `outcome_for` is total over all thirty cells of the
satisfaction-by-validation cross product, with a test that checks no cell produces a finding from
silence rather than checking the rows somebody remembered. DEC-046 splits the four `unmet`
conditions across two nodes because `EvidenceAssessment` does not exist when the first one runs,
and records the downgrade rather than performing it silently. `Finding` refuses a validation status
no cell would reach. `FINDING_VALIDATION_STATUSES` is derived from the table rather than restated,
with a comment saying a hardcoded set "would be the second opinion this module exists to prevent".

That is a lot of machinery, all of it working, none of it reading
`AssessmentConfiguration.evidence_threshold`.

## What was

The field selected nothing. One implemented table, one branch, and a required configuration value
that named which branch you wanted — with no code anywhere to honour the answer. The report then
printed the field.

So the line was true by coincidence. The default is `direct-or-confirmed`, the implemented table is
`direct-or-confirmed`, and they matched. Set the field to `permissive`, which the model accepted as
a valid value, and the report would have said `permissive` while the pipeline applied the strict
table. The document whose entire job is provenance would have named a policy that did not run.

## The part that stings

The comment immediately above that line, about the model profile, is this exact lesson, written out
in full:

> The run's profile, not the configured default: `versions` is assembled by the caller that ran,
> and the two differ whenever a run overrides the configuration — every offline replay does. A
> report claiming a profile nobody used is a provenance error in the one document that exists to
> carry provenance.

The next line down renders `assessment.configuration.evidence_threshold.value`. Somebody solved
this problem, wrote down why it mattered, and did not look one line further. That is not
carelessness so much as the shape of the defect: each claim reads fine on its own, and only the
block read together shows one line contradicting the comment above it.

## What replaced it

The name is now read off the table. DEC-013's distinguishing sentence is its own — "`unverified`
never produces a finding under `direct-or-confirmed`" — so `evidence_policy_name` asks the table
whether silence can reach a finding, and answers `permissive` or `direct-or-confirmed` accordingly.
`APPLIED_EVIDENCE_POLICY` is that applied to the real table, and the report renders it.

It takes the table as an argument rather than reading the module global, which is the whole point:
both names are reachable, and the negative test hands it a relaxed table and gets `permissive`
back. A constant computed inline would have been the third instance this week of a value that
cannot come out otherwise.

`permissive` itself is gone rather than implemented. It existed to measure "what a review without
an evidence threshold would report", as the baseline for the evaluation plan's comparison — and the
baselines that were actually built are prompt-shaped arms, scored in `comparison.md`, with
`permissive` appearing in no evaluation page at all. Implementing it now would mean building the
route by which a low-confidence finding rests on absence, which is the output DEC-009 exists to
suppress, to serve a comparison that was met another way five weeks ago.

## Blast radius

None. The ForgeFlow replay reproduces byte-for-byte, because the rendered string is identical —
only its source changed. No stored payload carried the field, so removing a required field needed
no migration. One test moved, the conformance anchor pinning section 6 at nine rows, which is that
anchor doing its job.

## What this says about the sweep

Three of the six defects in this class have now been in the report renderer or its inputs. That is
where a claim gets made to a reader, so it is where an unbacked claim does the most damage, and it
is worth treating the renderer as the highest-risk surface in the tree rather than as presentation.

The next pass the audit named is the threat model's Enforced rows, each paired with the test that
would fail if the enforcement were removed. This finding is the argument for it: the enforcement
existed, the claim about it did not match, and nothing connected the two.
