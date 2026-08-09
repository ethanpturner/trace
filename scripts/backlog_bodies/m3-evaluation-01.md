## Context

`demo/forgeflow/expected/` and `benchmarks/` contain only `.gitkeep`.
`demo/forgeflow/forgeflow-scenario.md` section 25 names eight truth files and none exist.
Every acceptance criterion in M3 that asks whether an agent produced the right answer
depends on ground truth that has not been written. `docs/architecture/evaluation-plan.md`
section 5 defines the per-scenario layout, and section 19 question 1 asks how expected
findings should be established. DX-18 settles the benchmark layout and the ForgeFlow
expected counts, so this issue authors content against that decision rather than making it.

## Scope

Author the truth files that M3 exercises, in the layout DX-18 fixes:

- `expected-threats.yaml`, derived from `demo/forgeflow/forgeflow-scenario.md` section 18's
  ten expected high-value threats. Section 18 states that exact wording need not match, so
  the file records the scenario elements a threat must contain — affected component,
  affected asset, precondition, impact — rather than prose to string-match.
- `expected-control-mappings.yaml`. For each expected threat, record the requirement
  identifiers that should be `applicable`, those that should be `not_applicable` with the
  condition that excludes them, and the expected `satisfaction_status` under the DX-08
  rules. Every intentional non-finding in scenario section 14 appears here as an explicit
  negative expectation, keyed to the `common_false_positives` entry that suppresses it.
- `expected-questions.yaml`, from scenario section 20's ten expected questions, which are
  the correct output for the section 15 ambiguities.
- `expected-rejections.yaml`, from scenario section 22's ten claims Trace should not make.

Also:

- Add a loader and shape test for the truth files, on the same reasoning as
  `tests/unit/test_requirements_catalog.py`: hand-maintained data with no reader drifts
  silently.
- Reference catalog requirement identifiers rather than restating requirement text.
  Restating would fork the catalog, and DEC-010's first open question asks exactly this
  about the evaluation plan's per-scenario `requirements.json`.

## Acceptance criteria

- [ ] The four expected-output files exist under the path DX-18 fixes, with the names
      DX-18 fixes.
- [ ] `expected-threats.yaml` covers all ten threats in scenario section 18, each
      recording affected components, affected assets, preconditions, and impact, and none
      recording prose intended to be matched literally.
- [ ] `expected-control-mappings.yaml` records an expected negative for each of the five
      non-findings in scenario section 14, each naming the requirement and the specific
      `common_false_positives` entry that suppresses it.
- [ ] Each of the five genuine weaknesses in scenario section 13 has at least one
      applicable requirement recorded, with the expected satisfaction status and the
      evidence condition required to reach it. Scenario section 13.1 states that condition
      explicitly for the webhook replay case.
- [ ] The webhook authenticity ambiguity at scenario section 15.1 is recorded as an
      expected question and not as an expected finding.
- [ ] Both intentional contradictions at scenario section 16 are recorded as expected
      contradictions, carrying the note from section 16.1 that Trace must not silently
      choose the safer statement.
- [ ] Every requirement reference is a catalog identifier. No requirement text is restated.
- [ ] A shape test validates the truth files and fails on drift.
- [ ] The truth files are not supplied to any agent at assessment time. Scenario
      section 25 states this, and a test asserts that no agent payload assembler reads
      from the expected-output directory.
- [ ] The expected counts match DX-18, and the files record that the finding count is a
      ceiling on defensible conclusions rather than a target to reach.
- [ ] `uv run pytest` passes with no network access and no provider API key.

## Out of scope

- `expected-context.yaml` and `reviewer-notes.md`. Context truth belongs to M2.
- `expected-findings.yaml` and `expected-documentation-gaps.yaml` as consolidated outputs.
  Findings are created by Finding Consolidation in M4. Note them as follow-on work.
- Scenarios beyond ForgeFlow. `docs/architecture/evaluation-plan.md` section 6 wants 8 to
  12 and that is Stage 5.
- Metric computation. The Evaluation Node is `docs/architecture/agent-design.md`
  section 21 and lands later.
- Deciding the layout or the counts. DX-18 owns both.

## References

- `demo/forgeflow/forgeflow-scenario.md` section 13 (Intentional Genuine Weaknesses),
  section 14 (Intentional Non-Findings), section 15 (Intentional Ambiguities), section 16
  (Intentional Contradictions), section 18 (Expected High-Value Threats), section 19
  (Expected Findings), section 20 (Expected Questions), section 21 (Expected Documentation
  Gaps), section 22 (Expected Rejected Findings), section 25 (Benchmark Truth Files)
- `docs/architecture/evaluation-plan.md` section 5 (Evaluation Dataset), section 10
  (Benchmark Fixture Design), section 11 (Regression Tests), section 19 question 1,
  section 20 (Core Evaluation Philosophy)
- `docs/architecture/decision-log.md` DEC-010 first open question, DEC-011
- `demo/forgeflow/input/structured-system-input.yaml` (`evaluation.expected_outputs`)
- `tests/unit/test_requirements_catalog.py` (the pattern for validating hand-maintained
  data)
- `docs/product/roadmap.md` Stage 3 (Exit criteria), Stage 4 (Evaluation targets)
