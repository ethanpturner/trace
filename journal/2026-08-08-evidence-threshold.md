# 2026-08-08 — The threshold, and what it says about the benchmark

Closes #26 as DEC-013. This is the decision the project's central claim rests on, and it
turned out to be less a matter of choosing a policy than of noticing that the data model had
already made the choice.

## The rule was already in the schema

`AssessmentConfiguration.evidence_threshold` was required, its only value was an example
string, and the question was recorded as open in three places at once: `data-model.md`
question 15, `current-architecture.md` question 7, and DEC-009's own open questions. Until it
was answered, the Finding and DocumentationGap distinction was enforced by prompt wording,
which design principle 7 says is not enforcement.

What resolved it was a property the data model already has. An `EvidenceReference` requires
non-empty `quoted_text` drawn from a real source location, and section 8 forbids changing it
after creation. **There is no way to construct an evidence reference that expresses the
absence of a passage.** So requiring evidence for `unmet` is sufficient, on its own and
mechanically, to prevent concluding absence from silence. No agent has to understand DEC-009
for DEC-009 to hold.

That is a much better position than a graduated scoring rule, which was the alternative I
started drafting. A threshold that has to be tuned is a threshold that can be tuned wrongly,
and `data-model.md` section 4.5 already warns against elaborate algorithms before the core
workflow is validated. The argument applies with more force here, because this rule decides
whether the project's claim about false positives holds.

It also gave `EvidenceStrength` its first consumer. The M1 research had flagged it as defined
and carried by no object. Condition 2 of the `unmet` rule — that at least one cited reference
describes absence or inadequacy directly, or contradicts a claim of existence — is exactly
the judgment that type expresses.

## Two values, not a scale

`direct-or-confirmed` is the default and the only value permitted for an authoritative
assessment. `permissive` is reachable only from the evaluation harness and marks the run
non-authoritative, following the pattern DEC-012 set for the checkpoint ablation.

`permissive` earns its place rather than existing for symmetry. The evaluation plan's baseline
comparison needs to show what a review without an evidence threshold reports, and that
baseline is precisely a permissive threshold. The false positives Trace avoids are only
demonstrable if the system can be made to produce them on demand.

I also narrowed DEC-009. It lists a low-confidence candidate finding among the classifications
available when documentation is missing; under the default threshold that classification is
now unreachable, and remains defined only under `permissive`. A low-confidence finding built
on absence is the output DEC-009 exists to suppress, so making it unreachable by default is
the stronger reading of the decision rather than a departure from it. The entry says so
explicitly, because narrowing an accepted decision quietly would be the wrong way to do it.

## The part that was not expected

Working the rule through the ForgeFlow scenario, as the issue required, produced a
disagreement with the scenario.

**FND-001, webhook replay protection, cannot be a finding on the documented evidence.**

Section 19 lists it as an expected finding and requires evidence that delivery identifiers are
not tracked. The documents do not establish that. `github-integration.md` section 6 says only
that incoming requests are validated before processing, which is the section 15.1 ambiguity
rather than a statement about replay. `operations-guide.md` section 3 shows a delivery
identifier carried in the job payload and says nothing about deduplication. And
`architecture-overview.md` section 26 lists webhook replay handling under Known Documentation
Gaps, stating those details are maintained elsewhere or require further clarification.

The only direct evidence is a document saying the topic is undocumented. Treating that as
evidence of absence is the exact failure DEC-009 names — and section 26's own wording
describes the inherited-or-elsewhere case that DEC-009 exists to protect. Under DEC-013 this
resolves to `unverified`, and therefore to a documentation gap and a question.

I did not bend the rule to fit the fixture. Given the choice between a rule that produces the
scenario's expected answer and a rule that is consistent with DEC-009, the second is the one
worth having; a benchmark that can only be passed by violating the project's central
constraint is measuring the wrong thing.

There is a detail worth sitting with. Removing FND-001 from the expected findings leaves
**three** — which is the count `structured-system-input.yaml` declared before #18 relocated
it. The count that #39 was filed to treat as disputed may have been right, and the scenario
document's list of four may be the error. That is now recorded on both #39 and #86 rather
than resolved here, because it is a benchmark question.

If it holds, it is the better benchmark anyway. Declining to conclude from a self-declared
documentation gap is precisely the behaviour a generic review gets wrong, and testing it is
worth more than one additional finding.

## The maintenance cost is now visible

DEC-012 invalidated one downstream issue. DEC-013 touched sixteen.

Most only carried a `blocked_by` edge, which GitHub resolves on its own once the blocker
closes, so those needed nothing. Twelve needed a comment because their implementation now has
a rule to follow, and two — the benchmark issues — needed the FND-001 conflict recorded
against them.

That is the shape of the remaining M0 work. Each decision closes one issue and changes the
meaning of between one and sixteen others, and the changed ones are not always obvious from
the dependency graph: #86 is not blocked by #26 in the manifest, but DEC-013's worked example
is the most consequential thing that has happened to it. Checking dependents is part of
closing a decision, and the dependency edges are a starting point rather than the answer.

## Open next

DEC-013 leaves four questions open, deliberately. Whether a documentation gap on a
high-impact requirement is itself reportable is DEC-009's second open question and is
untouched. Where evidence strength is recorded is a small schema question that #89 will hit.
Whether the `unmet` downgrade should be visible to the reviewer as an event belongs with the
checkpoint work. And whether `permissive` belongs on the assessment configuration at all, or
should be a harness parameter like the checkpoint ablation, is the same question DEC-012
answered one way and this decision answered the other — worth reconciling before either is
implemented.

That last one is the most likely place this decision is wrong.
