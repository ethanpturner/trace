# Trace — Evaluation Plan

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Evaluation Plan Version:** 0.2

**Status:** Accepted

**Last Updated:** 2026-08-18

The 0.2 revision (DEC-131) reconciles this plan with the system that shipped and measured
itself under it: the section 9 rubric is struck by decision, section 5's file rule admits the
instrument classes DEC-110 and DEC-119 added beside it, and section 19 strikes the questions
later decisions answered. What a section states in the present indicative runs today.

# 1. Purpose

The purpose of this document is to define how Trace will be evaluated as it evolves.

Trace is not intended to produce impressive demonstrations through carefully selected prompts.

Instead, improvements should be measured through repeatable evaluation using controlled assessment scenarios and objective metrics whenever practical.

The evaluation framework exists to answer one question:

**Is Trace producing better security assessments over time?**

# 2. Evaluation Goals

The evaluation process should determine whether changes improve:

- Context understanding
- Threat quality
- Requirement applicability
- False-positive reduction
- Evidence quality
- Explainability
- Human reviewer experience
- Cost
- Runtime
- Workflow reliability

A new prompt, workflow, or model should only be considered an improvement if evaluation demonstrates measurable benefit.

# 3. Guiding Principles

## Repeatable

The same assessment should produce comparable results across versions.

## Versioned

Every evaluation should record:

- Architecture version
- Workflow version
- Prompt versions
- Requirements catalog version
- Model
- Model configuration

## Evidence-based

Claims about improvement should be supported by metrics rather than anecdotes.

## Human-centered

The goal is not simply generating more findings.

The goal is producing findings that experienced security reviewers would keep.

## Cost-aware

Higher quality is valuable only if it is practical.

A 2% quality improvement may not justify a 5x increase in runtime or cost.

# 4. Evaluation Pipeline

Scenario

↓

Assessment

↓

Workflow Execution

↓

Structured Output

↓

Reviewer Assessment

↓

Metrics

↓

Historical Comparison

DEC-073 fixes how this pipeline executes: the harness reads the scenario registry and drives
the ordinary pipeline as a caller of `AssessmentService` — recorded model responses through the
replay adapter, recorded reviewer decisions replayed at both checkpoints, ablations applied
harness-side as non-authoritative run construction. `EvaluationResult` objects persist with the
assessment as the authoritative home; a derived, regenerable metrics feed keyed by scenario,
condition, and commit serves the scorecard and CI. Run comparison is per-item — matched,
missed, spurious, changed — through the DEC-056 matcher and DEC-066 fingerprints. Scenario
conditions (`clean`, `ambiguous`, `adversarial`, `missing_evidence`) are DEC-075's; the
baseline protocol is DEC-074's; stability measurement is DEC-077's.

# 5. Evaluation Dataset

Every benchmark scenario is stored in version control. The layout is fixed by DEC-027.

Each scenario directory has two subdirectories: `input/` holds the material supplied to Trace, and
`expected/` holds the truth set. **Nothing under `expected/` is ever supplied to Trace during an
assessment.** A benchmark that hands the system under test its own answer key measures nothing.

```
<scenario>/
  input/                            documents and structured system input
  expected/
    expected-context.yaml
    expected-threats.yaml
    expected-control-mappings.yaml
    expected-findings.yaml
    expected-questions.yaml
    expected-documentation-gaps.yaml
    expected-observations.yaml
    expected-rejections.yaml
    expected-duplicates.yaml
    annotations/second/             the independent second set, once a pass exists
    reviewer-notes.md
    evaluation-contract.yaml
    README.md
```

**The expected file list is derived, not enumerated, and the rule has three classes** (the 0.1
rule had one; DEC-110 flagged that its file fell outside it rather than silently widening it,
and the 0.2 revision is that widening, decided):

1. **Graded object classes** — one `expected-*.yaml` per domain object type the pipeline
   produces and the benchmark grades, plus `expected-rejections.yaml` for the negative set:
   claims a correct assessment should decline to make. Adding an object type to `data-model.md`
   adds a file class here by construction. A scenario carries the files for what it grades; an
   absent graded class means the scenario does not grade that type and yields no metric —
   unmeasured, never zero.
2. **Instrument annotations** — files an evaluation instrument defines and reads, grading the
   instrument's question rather than a pipeline object: `expected-duplicates.yaml` (DEC-110's
   authored duplicate pairs behind `duplicate_miss_rate`) and `annotations/second/` with its
   `adjudication.md` (DEC-112 and DEC-119 — the independent second annotation set and the
   adjudication record, present once a second annotator's pass exists).
3. **Scenario apparatus** — `evaluation-contract.yaml`, `reviewer-notes.md`, and `README.md`:
   the contract, the authoring rationale, and the directory's own guide. None is graded.

The listing above is what those rules produce under the current object model and instruments,
not an independent specification; where the two disagree, the rules govern and the listing is
stale. `tests/unit/test_evaluation_plan_conformance.py` holds the committed truth-set
directories to these classes, so a file class no rule admits fails there instead of accreting
silently.

`expected-observations.yaml` covers both `SourceObservation` kinds defined in DEC-021 —
contradictions and injection attempts — because they are one object type.

`evaluation-contract.yaml` holds the scenario's `benchmark_version` and the `catalog_version` its
expected outputs were authored against. **It declares no expected-output counts** (DEC-028). The
expected set is the enumerated content of the files above; a count is derived from a file when a
report needs one and is stored nowhere. A declared count that can disagree with its own enumeration
is a second source of truth, and a count used as a target is a finding quota, which section 20
rejects.

There is no per-scenario requirements file. The whole requirements catalog reaches the mapping step
on every call (DEC-024), so a scenario-scoped requirement list could only narrow what the pipeline
sees. A scenario pins `catalog_version` instead, and expected control mappings reference catalog
identifiers directly.

Scenarios are discovered from `benchmarks/scenarios.yaml`, never by scanning directories. ForgeFlow
lives at `demo/forgeflow/` because it is the demo as well as the first benchmark scenario;
scenarios two onward live under `benchmarks/`. Both use the layout above, and the registry is what
makes two locations safe.

The expected outputs evolve as understanding improves, through DEC-119's adjudication rule: a
disagreement the truth-set owner agrees with changes `expected/` in an ordinary,
separately-committed edit that moves the benchmark going forward and never rewrites a recorded
agreement statistic.

# 6. Initial Benchmark Scenarios

Fifteen scenarios are registered in `benchmarks/scenarios.yaml` — the authoritative list — and
every registered scenario is fully authored and replays offline. The sketch below is the 0.1
plan's; every row has at least one realized scenario, and the registry, not this section,
governs what exists.

The original sketch — the MVP should contain approximately 8–12 carefully designed scenarios:

### Scenario 1

Simple Web Application

Purpose:

Baseline extraction accuracy.

### Scenario 2

OIDC Authentication

Purpose:

Ensure delegated authentication does not generate password-policy findings.

### Scenario 3

Managed Database

Purpose:

Validate inherited encryption controls.

### Scenario 4

Unsigned Webhooks

Purpose:

Generate a legitimate finding.

### Scenario 5

Contradictory Documentation

Purpose:

Generate clarifying questions.

### Scenario 6

Missing Documentation

Purpose:

Generate documentation gaps instead of vulnerabilities.

### Scenario 7

Prompt Injection

Purpose:

Ensure embedded instructions are ignored.

### Scenario 8

AI Integration

Purpose:

Evaluate AI-specific threat generation.

### Scenario 9

Third-Party SaaS

Purpose:

Validate inherited controls.

### Scenario 10

Large Complex Architecture

Purpose:

Measure scalability.

# 7. Evaluation Categories

Evaluation occurs across multiple dimensions.

## Context Extraction

Measures:

- Component accuracy
- Asset accuracy
- Data-flow accuracy
- Trust-boundary accuracy
- Missing-object rate
- Unsupported claim rate

## Threat Generation

Measures:

- Relevant threats
- Duplicate threats
- Generic threats
- Threat coverage
- Threat specificity

## Requirement Mapping

Measures:

- Correct applicability
- Incorrect applicability
- Inherited control recognition
- False requirement assignments

## Evidence Validation

Measures:

- Supported findings
- Unsupported findings
- Contradictions detected
- Evidence citation quality

## Final Findings

Measures:

- Accepted findings
- Rejected findings
- Edited findings
- Duplicate findings
- False positives
- False negatives

## Reports

Measures:

- Readability
- Consistency
- Unsupported statements
- Reviewer edits

## Workflow

Measures:

- Runtime
- Model calls
- Token usage
- Cost
- Retry count
- Failure rate

# 8. Primary Metrics

The following metrics are computed deterministically from persisted objects on every evaluation
(`services/evaluation/metrics.py`; DEC-056 fixes the matching rule). Later decisions added
metrics beside them without displacing them: `evidence_assessment_coverage` (DEC-116),
`severity_concordance` (#507), `duplicate_miss_rate` (DEC-110), and the checkpoint review-time
seconds (DEC-117). The scorecard is the surface; nothing gates on any of them.

## Context Accuracy

Definition:

Percentage of architectural objects correctly extracted.

Goal:

Higher.

## Evidence Coverage

Definition:

Percentage of findings supported by evidence references.

Goal:

100%.

## Reviewer Acceptance Rate

Definition:

Approved findings / proposed findings.

Goal:

Higher.

## Reviewer Edit Rate

Definition:

Edited findings / approved findings.

Goal:

Lower.

## False Positive Rate

Definition:

Rejected findings / proposed findings.

Goal:

Lower.

This is one of the primary success metrics.

## False Negative Rate

Definition:

Known expected findings not generated.

Goal:

Lower.

## Documentation Gap Recall

Definition:

Expected gap requirements reached by at least one produced gap, over the expected set. The
0.1 draft called this "documentation gap precision — percentage of documentation gaps
correctly classified", and the shipped metric denominated it on production instead:
matching produced gaps over produced gaps. DEC-147 retired that shape. An expected-gap file
is a must-include list, not an enumeration of every gap a correct run may produce — the whole
catalog reaches the mapping step (DEC-024), so silence on any of its requirements can support
a gap, while the truth sets author one to four. A gap declines to assert, so an unexpected one
may simply be true, and the claims a correct assessment does not make are the negative set's
(`expected-rejections.yaml`).

Goal:

Higher.

## Documentation Gaps Produced

Definition:

The count of documentation gaps a run produced, reported as a count and never as a ratio
against the expected set.

Goal:

None. This is an observation, not a target — a gap volume is only interpretable beside the
document set that produced it, and a target would be a quota, which section 20 rejects.

## Clarifying Question Usefulness

Definition:

Matched expected questions over the expected set, through the DEC-056 matcher; paired
questions are excluded from the denominator. The 0.1 draft called this a reviewer rating; the
shipped metric is computed against the authored truth set.

Goal:

Higher.

## Duplicate Rate

Goal:

Lower.

## Unsupported Claim Rate

Goal:

Lower.

## Execution Time

Goal:

Lower.

## Estimated Cost

Goal:

Lower.

# 9. Human Review Rubric

**Struck by decision (DEC-131, this revision).** The 0.1 plan proposed seven reviewer-scored
categories — context accuracy, threat quality, finding usefulness, false positives, evidence
quality, report quality, overall confidence — each 1 to 5 on every evaluation. It was never
implemented, and no decision had deferred it; unimplemented-and-undeferred is the one state
this corpus does not tolerate, so the revision decides it.

Five of the seven are measured deterministically against authored truth sets today — context
accuracy, threat coverage, the finding match sets and false-negative rate, the
reviewer-decision rates that carry false positives, and evidence coverage with the
unsupported-claim rate — and a 1-to-5 re-score of a computed number is a weaker duplicate of
it. The two genuinely subjective categories would be scored by the truth sets' own author, and
DEC-112 already declined that shape: self-agreement is not a statistic. When an independent
scorer exists, the judgment arrives item-anchored through DEC-119's annotation pass and
adjudication record rather than as a seven-row average; arithmetic over judgments is the shape
section 20 warns against.

Qualitative comments land where they always have: `reviewer-notes.md` in the truth set, and
`annotations/second/adjudication.md` once a second pass exists. Reviewer time, the one review
quantity a rule can hold, is DEC-117's instrument and gates nothing.

# 10. Benchmark Fixture Design

Each fixture should intentionally include:

- Correct documentation
- Missing documentation
- Contradictory documentation
- Inherited controls
- Irrelevant information
- Ambiguous wording

Some fixtures should include:

- Prompt injection
- Incorrect assumptions
- Conflicting architecture diagrams

This ensures Trace is tested under realistic conditions.

## Editing an authored expectation

A truth set is the ruler. It may be edited **only** on an argument from the scenario's own inputs,
its own documentation, or its own internal consistency. A run's output is never an argument for
changing an expectation — an expectation exists to be disagreed with, and one edited toward a run
has stopped measuring anything (DEC-149).

Before changing an expectation, classify the divergence:

| Class | What it is | Where it is fixed |
|---|---|---|
| 1. Instrument definition | the metric's denominator, shape, or population is wrong | the metric and its definition here (DEC-147) |
| 2. Matcher classification | the comparison misreads a correct result | `matching.py`, mirrored into `baselines.py` (DEC-148) |
| 3. Truth-set inconsistency | the expectation contradicts itself, its scenario's docs, or its inputs | the truth set — **the only class an edit answers** (DEC-133) |
| 4. Pipeline divergence | the run reached the substance in another layer, or concluded differently | the pipeline, or recorded as measured |
| 5. Run-to-run variance | identical inputs produce the outcome only sometimes | repeated measurement (DEC-077); edit nothing |

A divergence is presumed class 4 or class 5 until the truth set is shown wrong on its own terms.
Classes 4 and 5 cannot be separated on a single run: reply-tuner's expected finding was measured at
three of five runs on identical inputs, so one run disagreeing with an expectation establishes
nothing about the expectation. A named mechanism is a hypothesis about class 4, not a separation
from class 5.

When an edit does clear that bar, it lands separately committed, with its justification in the
commit that makes it and the superseded figures retained rather than replaced (DEC-143).

# 11. Regression Tests

Every important bug should become a permanent regression test.

Examples:

A previous version:

- Generated password-policy findings for OIDC.

Create fixture.

Never allow regression.

Previous version:

Ignored inherited encryption.

Create fixture.

Never regress.

Previous version:

Hallucinated missing MFA.

Create fixture.

Never regress.

# 12. Prompt Evaluation

Every prompt change should answer:

Did quality improve?

Possible evaluation:

Prompt V1

↓

Scenario Set

↓

Metrics

↓

Prompt V2

↓

Same Scenario Set

↓

Compare

Only keep changes that improve overall performance.

First executed 2026-08-20 (#331): the `validate-evidence` v1/v2 pair, both arms on the same
gateway model with the run diff landing per scenario — the record is
`docs/eval/prompt-comparison-331.md`, and the verdict kept v2.

# 13. Model Evaluation

Different models should be compared using the same benchmark scenarios.

Comparison dimensions include:

- Accuracy
- Cost
- Runtime
- Structured output reliability
- Reviewer preference

Do not switch models based solely on subjective impressions.

# 14. Workflow Evaluation

Workflow changes should be evaluated independently.

The baseline comparison protocol is DEC-074's: the prompt baselines run through the same
seam with versioned, hashed prompts, emit schema-forced output, and are scored by the same
parallel matchers; they receive the same source documents and the requirements catalog, with
input-choice ties resolved against Trace. The external comparable is scored in the portfolio
write-up, not in-repo. The single-agent-versus-multi-agent row is DEC-126's
`baseline-single-pass`: the whole assessment in one call, one combined schema, run as a
non-authoritative harness condition; its live pair rides the keyed capture step.

Examples:

Single agent

vs

Multi-agent

Critic enabled

vs

Critic disabled

Evidence validation

vs

No evidence validation

Human checkpoint

vs

No checkpoint

This helps determine whether architectural complexity actually improves outcomes.

## How these comparisons are run

Each comparison is an experiment on the architecture, not a setting on an assessment. The
ablation is applied by the evaluation harness. No assessment configuration disables a
component, and DEC-012 removed the two fields that previously appeared to.

A run that ablates a component is recorded as non-authoritative and names the ablation it
applied. This matters most for the checkpoint comparison: ablating a human checkpoint
produces findings that no reviewer approved, which is precisely the output DEC-005 exists
to keep out of an assessment. Marking it at the point of production is more reliable than
inferring it afterwards.

The checkpoint comparison is the only one of these that removes human review, and it should
not be confused with running an evaluation unattended. Ordinary evaluation replays recorded
reviewer decisions: the checkpoint node executes, the gate holds, and a ReviewerDecision is
written, so reviewer acceptance and edit rates remain measurable. Replay is not an ablation
and needs no switch.

# 15. Success Criteria

The MVP is considered successful if it can consistently demonstrate:

- High reviewer acceptance
- Low false positives
- Evidence-backed findings
- Reliable workflow execution
- Explainable outputs
- Useful clarifying questions

without excessive runtime or cost.

# 16. Dashboard Metrics

The scorecard computes these today (DEC-076; per-scenario precision, recall, and F1 with
cross-version trends per #535): finding counts and match sets, questions, documentation gaps,
evidence coverage, cost, runtime, tokens, and model calls, rendered from the committed runs by
`scripts/build_scorecard.py` and held against a fresh offline sweep in CI. Absent measurements
render as a dash, never zero (DEC-092). Cross-version viewing is the retained history
(DEC-081, `docs/eval/history.jsonl`) and the release record (`docs/eval/releases.md`, #524).

# 17. Longitudinal Tracking

Every release should record:

Version

Date

Major changes

Evaluation summary

Known regressions

Outstanding issues

This creates a history of improvement. The record exists as `docs/eval/releases.md` (#524):
sections are authored, the evaluation-summary block is assembled from the committed artifacts
by `scripts/build_release_record.py`, and `tests/unit/test_release_record.py` holds every
section to this shape and every git tag to a section.

# 18. Future Research

Potential future evaluations include:

- Comparing multiple reasoning strategies
- Evaluating chain-of-thought alternatives without storing reasoning
- Measuring reviewer time savings
- Comparing expert reviewers with Trace-assisted reviewers
- ~~Measuring consistency across multiple runs~~ Moved from research to protocol by DEC-077:
  n live runs with replay-matched decisions, per-item agreement sets retained, gating nothing
- Benchmarking against traditional threat-model templates

# 19. Open Questions

1. ~~How should "expected findings" be established?~~ Answered: authored by one person against
   the input documents alone, with reliability measured by an independent second annotation set
   (DEC-112, DEC-119).
2. ~~Should reviewers score independently?~~ Answered: independence is the second set's whole
   value; the annotator reads `input/` and nothing else (DEC-112, DEC-119).
3. ~~How should disagreement between reviewers be handled?~~ Answered by DEC-119's adjudication
   rule: the second set is immutable, the first stays authoritative, and each disagreement is
   recorded as agree, hold, or out of scope.
4. How many benchmark scenarios are enough?
5. ~~Should benchmarks include intentionally malicious documentation?~~ Answered: yes — the
   adversarial condition runs poisoned-document variants across five payload classes, scored on
   detection and injected-instruction compliance (DEC-075).
6. How should business context be evaluated?
7. ~~Should Trace benchmark itself against commercial tools?~~ Answered: the in-repo baselines
   are DEC-074's prompt baselines and DEC-126's single-pass condition; the external comparable
   is scored in the portfolio write-up, not in-repo (DEC-074).
8. Which metrics best predict reviewer trust?
9. ~~When should evaluation block a release?~~ Answered: never, as decided repeatedly — the
   coverage baseline, the stability protocol, the agreement instrument, and the review-time
   instrument all report and gate nothing (DEC-063, DEC-077, DEC-112, DEC-117).
10. How should benchmark scenarios evolve over time?

# 20. Core Evaluation Philosophy

Trace should not optimize for producing the largest number of findings.

It should optimize for producing the **smallest set of defensible, evidence-backed findings that an experienced security reviewer would approve.**

That philosophy should guide every future prompt, workflow change, and architectural decision.
