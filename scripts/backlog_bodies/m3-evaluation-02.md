## Context

`docs/architecture/evaluation-plan.md` section 11 requires that every important bug become
a permanent regression test, and names three: password-policy findings generated for OIDC,
ignored inherited encryption, and hallucinated missing MFA. `docs/product/roadmap.md`
section 4 repeats the rule as a cross-cutting workstream. The unusual property of this
project is that its known false positives are known in advance:
`demo/forgeflow/forgeflow-scenario.md` section 14 lists five intentional non-findings and
section 22 lists ten claims Trace should not make, and DEC-011 records
`common_false_positives` entries written specifically to suppress them.

These belong in a suite that runs on every change to a prompt, a requirement, or a mapping
rule, separate from the fixture tests attached to individual agent issues. A false positive
that returns after a prompt edit is the failure mode this project exists to prevent, and
nothing currently catches it.

## Scope

- Add a regression suite under `tests/evaluation/`, which
  `docs/architecture/current-architecture.md` section 15 and the repository layout already
  scaffold as empty.
- One case per intentional non-finding at `demo/forgeflow/forgeflow-scenario.md`
  section 14, and one per rejected claim at section 22. Each case asserts the negative:
  that a specific conclusion is not reached.
- Each case names the mechanism that suppresses it — the requirement identifier and the
  `common_false_positives` entry, or the inherited control, or the
  `non_applicable_conditions` entry. A regression test that passes for an unknown reason
  is not evidence of anything.
- Add the inverse: one case per genuine weakness at scenario section 13, asserting that
  the weakness remains reachable. `journal/2026-08-08-requirements-catalog.md` records
  over-suppression as the failure mode on the other side of DEC-009, and DEC-011 names it
  as the field's main risk. A suite that only asserts negatives will pass on a system that
  finds nothing at all.
- Record the DX-09 suppression trail per case, so a suppressed conclusion is visible as
  suppressed rather than as absent.
- Mark the suite with the `evaluation` marker so `addopts` deselects it by default and a
  bare `uv run pytest` cannot spend money, per `CLAUDE.md` working norms. Provide a
  documented command that runs it.
- Where a case can be evaluated against recorded model output rather than a live call,
  prefer that, so as much of the suite as possible runs without a provider key.

## Acceptance criteria

- [ ] A regression case exists for each of the five intentional non-findings at scenario
      section 14 and each of the ten rejected claims at section 22.
- [ ] Each negative case names the specific suppressing mechanism, and a test asserts that
      mechanism is the reason rather than inferring it from the absent output.
- [ ] A positive case exists for each of the five genuine weaknesses at scenario
      section 13, asserting the weakness remains reachable.
- [ ] The suite fails if a genuine weakness stops being reachable, not only if a false
      positive returns.
- [ ] The three regressions named in `docs/architecture/evaluation-plan.md` section 11 each
      have a case: OIDC password policy, inherited encryption, hallucinated MFA.
- [ ] Suppressions are recorded in the DX-09 representation, so the false-negative
      measurement at `docs/architecture/evaluation-plan.md` section 8 can read them.
- [ ] The suite carries the `evaluation` marker and is deselected by a bare
      `uv run pytest`.
- [ ] The command to run the suite is documented alongside the existing commands.
- [ ] No case asserts a minimum number of findings, threats, or critiques.
      `docs/architecture/evaluation-plan.md` section 20 states the goal is the smallest set
      of defensible conclusions, and a floor on output count would contradict it.
- [ ] `uv run mypy` passes in strict mode; the type checker covers `tests/` already.

## Out of scope

- Metric computation and the evaluation summary report.
  `docs/architecture/agent-design.md` section 21 defines the Evaluation Node and
  `docs/product/roadmap.md` places the summary in Stage 5.
- Baseline comparisons against a single generic prompt, which is Stage 5.
- Scenarios beyond ForgeFlow.
- Reviewer scoring rubrics at `docs/architecture/evaluation-plan.md` section 9, which need
  a reviewer.

## References

- `docs/architecture/evaluation-plan.md` section 8 (False Positive Rate; False Negative
  Rate; Documentation Gap Precision), section 10 (Benchmark Fixture Design), section 11
  (Regression Tests), section 20 (Core Evaluation Philosophy)
- `demo/forgeflow/forgeflow-scenario.md` section 13 (Intentional Genuine Weaknesses),
  section 14 (Intentional Non-Findings), section 22 (Expected Rejected Findings)
- `docs/architecture/decision-log.md` DEC-009, DEC-011 (Tradeoffs — over-suppression risk)
- `journal/2026-08-08-requirements-catalog.md` — *Verification*
- `docs/architecture/agent-design.md` section 31 (Testing Strategy — Regression tests),
  section 21 (Evaluation Node)
- `docs/product/roadmap.md` section 4 (Cross-Cutting Workstreams — Evaluation), Stage 4
  (Evaluation targets)
- `CLAUDE.md`, *Working norms* — the deselected `integration` and `evaluation` markers
