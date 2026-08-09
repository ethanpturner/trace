## Context

The Report Generation agent's prohibited operations — no new findings, no severity changes, no
unsupported facts, no removed limitations, no assumptions presented as confirmed, no questions
presented as vulnerabilities — are stated in `docs/architecture/agent-design.md` section 19 and
guaranteed by nothing. `docs/product/design-principles.md` section 7 is explicit that a rule whose
violation makes the system behave incorrectly belongs outside the prompt. `docs/product/roadmap.md`
Stage 4 sets report-only invented findings at zero as an evaluation target, which requires something
that can measure it.

## Scope

- A deterministic validator that runs between generation and rendering, and again over the rendered
  document, and blocks the workflow on violation.
- Checks over `ReportSections`:
  - Every finding identifier, title and severity label mentioned corresponds to an approved
    `Finding`, and severity words in prose match the object's `severity`.
  - No finding-shaped claim exists without a corresponding approved object. Implement this
    conservatively against the approved title and identifier set rather than as a semantic
    judgement, and document in the module docstring what the check does and does not catch.
  - Every limitation and assumption recorded on an approved finding or on the assessment appears in
    the report.
  - Open `Question` objects appear in the questions section and never in the findings section.
  - `DocumentationGap` objects are described as gaps and never as confirmed weaknesses. This is the
    DEC-009 boundary surviving into the output, and it is the last place it can be enforced.
  - Quoted evidence text is unaltered.
- Checks over the rendered document: the approved-finding count matches, no rejected finding
  identifier appears, and severity values are consistent with the objects.
- On violation the node fails, preserves the offending output as a debug artifact, and routes to
  retry or human review per `docs/architecture/current-architecture.md` section 11 and agent-design
  section 26. It never repairs the prose silently.
- An unsupported-statement count exposed in a form the evaluation component can consume.
- The validator uses no model.

## Acceptance criteria

- [ ] A section set naming a finding absent from the approved set fails validation.
- [ ] A section set stating a severity that differs from the approved `Finding.severity` fails
      validation.
- [ ] A section set that omits a recorded limitation fails validation.
- [ ] A section set describing a `DocumentationGap` as a confirmed weakness fails validation, in a
      regression test named for DEC-009.
- [ ] A section set presenting an open question as a vulnerability fails validation.
- [ ] A section set that alters quoted evidence text fails validation.
- [ ] Validation failures preserve the offending output and do not rewrite it.
- [ ] With zero approved findings, a report using the template's empty-findings wording passes
      validation and produces no violation. An empty findings section is correct output, not a
      defect.
- [ ] The unsupported-statement count is emitted in a form the evaluation component consumes.
- [ ] The validator makes no model call; a test asserts this.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Readability, which is a reviewer rubric score rather than a computed value
  (`docs/architecture/evaluation-plan.md` section 9).
- Semantic fact-checking of prose against source documents. The validator checks consistency with
  approved objects, not truth.
- A model-based evaluator. Agent-design section 21 permits one for narrow comparative tasks; this
  validator is deterministic by design.

## References

- `docs/architecture/agent-design.md` — section 19 ("Prohibited operations", "Failure conditions"),
  section 20, section 21, section 26
- `docs/architecture/current-architecture.md` — section 11, section 12
  ("Generated-output boundary")
- `docs/architecture/data-model.md` — section 8, section 21, section 22, section 23, section 33
- `docs/architecture/decision-log.md` — DEC-009
- `docs/architecture/evaluation-plan.md` — section 7 ("Reports"), section 8, section 9
- `docs/product/design-principles.md` — section 7, section 17
- `docs/product/roadmap.md` — Stage 4, "Evaluation targets"
