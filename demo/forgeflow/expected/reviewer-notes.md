# ForgeFlow reviewer notes

The judgement calls behind the outcome-side truth set — what was decided, what is legitimately
borderline, and why. `forgeflow-scenario.md` sections 19 through 22 are the source; DEC-027,
DEC-028, DEC-029, and DEC-030 govern the shape. Nothing in this directory is supplied to Trace
during an assessment.

## The webhook replay call is the scenario's centre of gravity

The complete scenario truth (section 13.1) is that replay protection genuinely is missing. The
supplied documents do not establish it: the only direct statement is `architecture-overview.md`
section 26 listing "Webhook replay handling" under its own *Known Documentation Gaps*. A truth
set that expected FND-001 as a finding would grade the DEC-009 failure — concluding absence from
silence — as correct, so DEC-029 reclassified it as GAP-004 with Q-02 as its load-bearing paired
question, and REJ-11 records the wrong conclusion. This is the one item where a well-reasoned
generic review and a correct Trace assessment must disagree.

## FND-003 versus GAP-004: the deliberate contrast

Both subjects appear in `architecture-overview.md` section 26. FND-003 is a finding and GAP-004
is not, because FND-003 rests on an affirmative statement — `operations-guide.md` states a 30-day
retention target while `product-overview.md` describes the same artifacts as temporary data
deleted after analysis — and GAP-004 rests on a statement that a topic is undocumented. Silence
and a positive statement fall on opposite sides of the DEC-009 line, and having both in one
scenario is deliberate: a matcher that cannot tell them apart fails the scenario's point.

## FND-002 and FND-004 stay separate, and merging them is not an error

Section 19's consolidation test is whether the remediation and impact are substantially related.
Related and not the same: FND-002 needs a human approval gate before external publication,
FND-004 needs isolation of untrusted repository content from model instructions, and either can
be fixed without the other. The truth set records the finer decomposition because a matcher can
collapse two entries onto one runtime finding and cannot split one entry across two. A run that
merges them into one well-reasoned finding is defensible and is not scored as an error (DEC-029).

## Severity guidance is not graded output

DEC-030 assigns severity at checkpoint 2, by the reviewer, so the pipeline emits nothing to score
severities against. The `severity_guidance` values exist to keep whoever plays the reviewer
consistent between benchmark runs — FND-002's "medium-or-high" is genuinely repository-dependent,
and either assignment is within guidance.

## Borderline items, recorded as borderline

- **Administrative job retry reusing stored artifacts** (scenario 13.4) is a genuine weakness in
  the complete scenario and is *not* an expected finding: the supplied documents do not establish
  the retry path's data source affirmatively enough to clear DEC-013's evidence conditions. It is
  covered by GAP-002's administrative-access questions and the retention finding's exposure
  argument. A run that raises a question about retry data flow is doing well, not deviating.
- **GAP-001 versus Q-03/Q-04**: provider-side data handling produces both a gap and questions.
  That is not double counting — the gap records what the documentation cannot establish, the
  questions ask for the specific answers that would change mappings (section 16's split, applied
  by `agent-design.md` section 16's reclassification rules).
- **Question selection has a rule, not a count** (section 20): questions are prioritised by their
  ability to change findings. The ten enumerated in `expected-questions.yaml` are the candidates;
  a run is not penalised for ordering within priority bands.

## What is deliberately not here

No counts are declared anywhere in this directory (DEC-028) — the expected set *is* what each
file enumerates. And no expected finding rests on the absence of documentation;
`tests/unit/test_benchmark_outcome_truth.py` holds that with a test named for DEC-009.
