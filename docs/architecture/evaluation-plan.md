# Trace — Evaluation Plan

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Evaluation Plan Version:** 0.1

**Status:** Proposed

**Last Updated:** 2026-08-05

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

Every benchmark scenario should be stored in version control. The layout is fixed by DEC-027.

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
    reviewer-notes.md
    evaluation-contract.yaml
```

**The expected file list is derived, not enumerated.** There is one `expected-*.yaml` per domain
object type the pipeline produces and the benchmark grades, plus `expected-rejections.yaml` for the
negative set — claims a correct assessment should decline to make. Adding an object type to
`data-model.md` adds a file here by construction. The list above is what that rule produces under
the current object model, not an independent specification of it; where the two disagree, the rule
governs and the list is stale.

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

The expected outputs should evolve as understanding improves.

# 6. Initial Benchmark Scenarios

The MVP should contain approximately 8–12 carefully designed scenarios.

Examples include:

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

The following metrics will be tracked for every evaluation.

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

## Documentation Gap Precision

Definition:

Percentage of documentation gaps correctly classified.

Goal:

Higher.

## Clarifying Question Usefulness

Reviewer rating.

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

Each evaluation should include reviewer scoring.

Suggested rubric:

| Category | Score |
|---|---|
| Context accuracy | 1–5 |
| Threat quality | 1–5 |
| Finding usefulness | 1–5 |
| False positives | 1–5 |
| Evidence quality | 1–5 |
| Report quality | 1–5 |
| Overall confidence | 1–5 |

Reviewers should also record qualitative comments.

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

The baseline comparison protocol is DEC-074's: the two prompt baselines run through the same
seam with versioned, hashed prompts, emit the same target schemas, and are scored by the same
structural matcher; they receive the same source documents and the requirements catalog, with
input-choice ties resolved against Trace. The external comparable is scored in the portfolio
write-up, not in-repo.

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

Eventually, Trace should automatically calculate:

- Findings proposed
- Findings approved
- Findings rejected
- Questions generated
- Documentation gaps
- Average confidence
- Evidence coverage
- Cost
- Runtime
- Tokens
- Model calls

These metrics should be viewable across versions.

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

1. How should "expected findings" be established?
2. Should reviewers score independently?
3. How should disagreement between reviewers be handled?
4. How many benchmark scenarios are enough?
5. Should benchmarks include intentionally malicious documentation?
6. How should business context be evaluated?
7. Should Trace benchmark itself against commercial tools?
8. Which metrics best predict reviewer trust?
9. When should evaluation block a release?
10. How should benchmark scenarios evolve over time?

# 20. Core Evaluation Philosophy

Trace should not optimize for producing the largest number of findings.

It should optimize for producing the **smallest set of defensible, evidence-backed findings that an experienced security reviewer would approve.**

That philosophy should guide every future prompt, workflow change, and architectural decision.
