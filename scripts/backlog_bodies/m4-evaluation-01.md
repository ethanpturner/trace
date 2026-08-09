## Context

`demo/forgeflow/expected/` contains only a `.gitkeep`. Without an authored truth set, nothing can
measure whether a finding set is correct, and the false-negative rate and documentation-gap precision
defined in `docs/architecture/evaluation-plan.md` section 8 cannot be computed at all. The scenario
document already states the intended truth in prose
(`demo/forgeflow/forgeflow-scenario.md` sections 19 through 22); this issue turns the outcome-side
portion of it into structured fixtures. The benchmark directory layout and the resolved expected
counts are fixed by DX-18, and the evaluation contract currently embedded in the input fixture is
removed separately.

## Scope

- Author, under `demo/forgeflow/expected/` and in the layout fixed by DX-18:
  - `expected-findings.yaml`, from `forgeflow-scenario.md` section 19. Each entry records the
    expected severity, the evidence the scenario says must be established before the item becomes a
    finding, and which input documents supply that evidence.
  - `expected-documentation-gaps.yaml`, from section 21.
  - `expected-questions.yaml`, from section 20, each with priority and what answering it would
    change.
  - `expected-rejections.yaml`, from section 22, each recording why the claim is unsupported and
    which scenario fact contradicts it.
  - `reviewer-notes.md`, recording the judgement calls, including which items are legitimately
    borderline and why.
- Each expected object conforms to the corresponding data-model shape: section 21 for findings,
  section 22 for questions, section 23 for documentation gaps.
- A test validating the expected files, in the style of
  `tests/unit/test_requirements_catalog.py`: structure and convention, not judgement.
- No expected finding rests on the absence of documentation. Where the scenario's intended weakness
  depends on evidence that the input documents do not supply, it belongs in
  `expected-questions.yaml` or `expected-documentation-gaps.yaml` instead, and the reviewer notes
  say so.
- The expected files are never supplied to Trace during an assessment
  (`forgeflow-scenario.md` section 25). A test asserts that no loader path reads from
  `demo/forgeflow/expected/`.

## Acceptance criteria

- [ ] The five files exist under `demo/forgeflow/expected/` in the DX-18 layout and are valid YAML
      or Markdown as appropriate.
- [ ] A unit test validates each expected file against the corresponding data-model shape and fails
      with the offending entry named.
- [ ] Every expected finding names the evidence that must be established for it.
- [ ] No expected finding rests solely on the absence of documentation; a test named for DEC-009
      asserts this over the fixture data.
- [ ] Every expected rejection names the scenario fact that contradicts it.
- [ ] Expected finding, question and documentation-gap counts agree with the counts resolved in
      DX-18, and a test asserts the agreement rather than leaving it to review.
- [ ] A test asserts that nothing under `demo/forgeflow/expected/` is read by an assessment run.
- [ ] `uv run pytest` passes with no provider credential configured. These are unit tests over static
      data.
- [ ] `uv run mypy` passes in strict mode over the new test module.

## Out of scope

- `expected-context.yaml`, `expected-threats.yaml` and `expected-control-mappings.yaml`, owned by the
  context, threat and control-mapping components.
- Removing the evaluation contract from `demo/forgeflow/input/structured-system-input.yaml`, tracked
  as a separate defect.
- The eight to twelve additional benchmark scenarios of evaluation-plan section 6 and roadmap
  Stage 5.

## References

- `demo/forgeflow/forgeflow-scenario.md` — section 2, section 13, section 14, section 19,
  section 20, section 21, section 22, section 25, section 28
- `docs/architecture/evaluation-plan.md` — section 5, section 10, section 19 question 1
- `docs/architecture/data-model.md` — section 21, section 22, section 23
- `docs/architecture/decision-log.md` — DEC-009, DEC-010
- `docs/product/design-principles.md` — section 9, section 10
- `tests/unit/test_requirements_catalog.py` — the established pattern for validating hand-maintained
  fixture data
