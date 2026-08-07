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

# 5. Evaluation Dataset

Every benchmark scenario should be stored in version control.

Each scenario should contain:

scenario/

README.md

architecture.md

requirements.json

expected-context.yaml

expected-threats.yaml

expected-findings.yaml

review-notes.md

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

This creates a history of improvement.

# 18. Future Research

Potential future evaluations include:

- Comparing multiple reasoning strategies
- Evaluating chain-of-thought alternatives without storing reasoning
- Measuring reviewer time savings
- Comparing expert reviewers with Trace-assisted reviewers
- Measuring consistency across multiple runs
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
