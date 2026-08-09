## Context

The Evaluation node is primarily deterministic and measures workflow quality, cost and behaviour
(`docs/architecture/agent-design.md` section 21).
`docs/architecture/evaluation-plan.md` section 8 defines the primary metrics and
`docs/product/roadmap.md` Stage 4 sets numeric targets: approximately 100 percent finding evidence
coverage, and zero known false-positive regressions. None of these can be reported today because
nothing computes them. This issue adds the result object and the finding-quality metrics; report
metrics and the reviewer rubric follow separately.

## Scope

- The `EvaluationResult` model per `docs/architecture/data-model.md` section 28, promoted from the
  deferred group of section 40, with the promotion recorded in that section.
- Deterministic computation, per workflow run, of the finding-quality metrics:
  `finding_evidence_coverage`, `reviewer_acceptance_rate`, `reviewer_rejection_rate`,
  `reviewer_edit_rate`, `duplicate_finding_rate`, false-positive rate as rejected over proposed,
  false-negative rate as expected findings not produced, and `documentation_gap_precision`.
- Acceptance, rejection and edit rates derive from `ReviewerDecision` records rather than from
  finding status alone, so that an edit followed by an approval counts as both.
- False negatives and gap precision are computed against the authored ForgeFlow expected files.
- A documented matching rule for pairing produced objects with expected objects. Start structural:
  match on requirement, threat and affected component rather than on title wording. Record the rule
  in the module docstring, because the metric means nothing without it.
- Where a model-based comparison is used at all, it is labelled a model-generated judgement rather
  than ground truth (agent-design section 21) and it sits behind the `evaluation` pytest marker.
- Workflow measures already available from `WorkflowRun` and `ExecutionRecord`: execution duration,
  model-call count, token counts, estimated cost and node failure rate.
- Results are written to the assessment's evaluation directory, separately from the user-facing
  report (`docs/architecture/current-architecture.md` section 5.14 and section 5.16).

## Acceptance criteria

- [ ] `EvaluationResult` exists per data-model section 28, and section 40 records the promotion.
- [ ] Every metric above is computed from persisted objects with no model call on the default path.
- [ ] `finding_evidence_coverage` is 100 percent for a run in which every approved finding cites
      resolvable evidence, and below 100 percent when one does not; both cases are tested.
- [ ] Acceptance, rejection and edit rates are derived from `ReviewerDecision` records, and a test
      covers a finding that was edited and then approved.
- [ ] False-negative rate is computed against `expected-findings.yaml`, and the matching rule is
      documented in the module docstring.
- [ ] An assessment producing zero findings yields a valid metric set rather than a division error,
      an exception or a reported failure. Zero findings is a successful outcome and the metrics say
      so.
- [ ] Evaluation output is written outside the user-facing report directory.
- [ ] Any model-based comparative evaluator is labelled model-generated and is gated behind the
      `evaluation` marker, which remains deselected by default.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Report-quality metrics and the reviewer rubric, which follow separately.
- Context, threat and requirement-mapping accuracy metrics, owned by the components that produce
  those objects.
- Baseline comparison against a generic single-pass prompt, and the eight to twelve scenario suite.
  Both are roadmap Stage 5.
- Dashboards and longitudinal tracking, evaluation-plan sections 16 and 17.

## References

- `docs/architecture/evaluation-plan.md` — section 3, section 7 ("Final Findings"), section 8,
  section 20
- `docs/architecture/agent-design.md` — section 21, section 32
- `docs/architecture/data-model.md` — section 25, section 26, section 27, section 28, section 40
- `docs/architecture/current-architecture.md` — section 5.14, section 5.16
- `docs/product/roadmap.md` — Stage 4 ("Evaluation targets"), Stage 5
- `docs/product/design-principles.md` — section 9, section 10
