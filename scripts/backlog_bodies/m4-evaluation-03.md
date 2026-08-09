## Context

`docs/architecture/evaluation-plan.md` section 7 lists Reports as its own evaluation category with
four measures: readability, consistency, unsupported statements and reviewer edits. Two of those are
computable and two are human judgements. Section 9 defines a seven-category reviewer rubric scored
one to five with qualitative comments. `docs/product/design-principles.md` section 15 warns against
scores that look precise without improving judgement, so the computed and the judged measures are
recorded distinctly rather than blended into one number.

## Scope

- Computed report metrics, drawn from the report consistency validator and the render:
  `unsupported_claim_count`, report-only invented findings which must be zero, approved-finding
  coverage in the rendered document, and severity inconsistency count between prose and objects.
- Reviewer rubric capture: the seven categories of evaluation-plan section 9 — context accuracy,
  threat quality, finding usefulness, false positives, evidence quality, report quality and overall
  confidence — each scored one to five, plus free-text qualitative comments.
- Rubric scores are stored as `EvaluationResult` rows with `evaluator_type` of `reviewer` and an
  `evaluation_method` naming the rubric version, so a reviewer judgement is never mistaken for a
  computed measure.
- Readability and report quality are recorded, not inferred. No heuristic readability score is
  computed and presented as if it were measured.
- A per-run evaluation summary covering the counts listed in `docs/product/roadmap.md` Stage 5 that
  are available at this point: findings proposed, approved, rejected and edited; questions generated;
  documentation gaps; evidence coverage; false positives; false negatives; model calls; tokens;
  estimated cost; execution time; failures and retries.
- The summary is written to the assessment's evaluation directory, separately from the report.

## Acceptance criteria

- [ ] `unsupported_claim_count` for the report is computed from the validator's output and stored as
      an `EvaluationResult`.
- [ ] Report-only invented findings is computed and is zero for a report that passes validation.
- [ ] Rubric scores are storable, retrievable, constrained to the range one to five, and carry
      `evaluator_type` of `reviewer`.
- [ ] No computed readability score is produced or displayed; a test asserts that report quality and
      readability values originate only from reviewer input.
- [ ] The evaluation summary is generated for a completed run and contains every available count.
- [ ] An assessment with zero approved findings produces a complete summary with zero counts and no
      error, and the report metrics record that the report correctly contained no findings.
- [ ] The summary is written outside the user-facing report directory.
- [ ] Computation makes no model call on the default path.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Finding-quality metrics, delivered separately.
- Baseline comparison against a generic prompt, roadmap Stage 5.
- Dashboards and cross-version views, evaluation-plan sections 16 and 17.
- Reviewer time-savings measurement, evaluation-plan section 18.

## References

- `docs/architecture/evaluation-plan.md` — section 7 ("Reports"), section 8, section 9, section 16,
  section 20
- `docs/architecture/agent-design.md` — section 21, section 32 (Report Generation scorecard)
- `docs/architecture/data-model.md` — section 28
- `docs/architecture/current-architecture.md` — section 5.14
- `docs/product/design-principles.md` — section 10, section 15
- `docs/product/roadmap.md` — Stage 4, Stage 5 ("Evaluation reporting")
