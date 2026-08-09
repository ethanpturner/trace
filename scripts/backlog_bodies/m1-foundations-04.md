## Context

`docs/architecture/data-model.md` is authoritative for field names and types, and its objects
are specified as Markdown tables with the columns `| Field | Type | Required | Description |`.
`tests/unit/test_requirements_catalog.py` already demonstrates the pattern for holding
hand-maintained data to that document: it encodes section 17's field lists as frozensets and
fails when the catalog drifts. The same drift is available to the Pydantic models, in both
directions — a field renamed in the document and not in the code, or a field added to the code
that the document never sanctioned. A guard that reads the document directly catches both,
and it is the cheapest way to keep "data-model.md is authoritative" true rather than
aspirational.

## Scope

- Add `tests/unit/test_data_model_conformance.py`.
- Parse the field tables out of `docs/architecture/data-model.md`, keyed by section number and
  object name. The tables are uniform: a header row, a separator row, and one row per field
  with name, type, `Yes`/`No`, and description.
- For each implemented domain object, assert that its Pydantic field set equals the document's
  field set for that section, and that each field's required/optional status matches the
  document's `Required` column.
- Maintain an explicit registry mapping section number to implemented model, so that an
  unimplemented object is skipped deliberately rather than by accident. Objects deferred by
  section 40 (Critique, EvidenceAssessment, PromptDefinition, RequirementsCatalog,
  EvaluationResult) are listed as deferred, not silently absent.
- Assert that every enum in `src/trace_ai/domain/enums.py` matches the value list in its
  section 4 subsection, replacing the ad-hoc literal assertions written alongside the enums.
- Fail with a message that names the section, the object, and the specific field, in the style
  the requirements-catalog test uses.

## Acceptance criteria

- [ ] The parser extracts the field table for data-model.md section 5 (Assessment), 6
      (AssessmentConfiguration), 7 (SourceDocument), and 8 (EvidenceReference), and the row
      counts match the document.
- [ ] Adding a field to a model that the document does not list fails the test.
- [ ] Renaming a field in the document without renaming it in the model fails the test.
- [ ] Changing a field from `No` to `Yes` in the document without making it required in the
      model fails the test.
- [ ] The registry lists every section between 5 and 31 as implemented, deferred, or
      not-yet-in-scope, so no object falls out of view.
- [ ] The test names the section number in every failure message.
- [ ] The test reads the document from `PROJECT_ROOT` and needs no API key; it runs under a
      bare `uv run pytest`.
- [ ] `uv run mypy` passes strict, which for tests means the parser is typed even though
      `disallow_untyped_defs` is relaxed for `tests.*`.

## Out of scope

- Validating types beyond required/optional. The document's `Type` column mixes model names,
  primitives, and prose (`map[string, any]`, `list[string]`, `AssessmentConfiguration`), and
  parsing it into Python types would encode a mapping the document does not define.
- Generating models from the document. The models stay hand-written; this is a guard, not a
  code generator.
- Checking `docs/architecture/agent-design.md` or `docs/architecture/current-architecture.md`,
  which contain no field tables.

## References

- `docs/architecture/data-model.md` sections 5, 6, 7, 8, 4.1–4.7, 38 (Deferred Objects),
  40 (Initial Implementation Priority)
- `tests/unit/test_requirements_catalog.py` (the pattern this extends)
- `docs/architecture/decision-log.md` DEC-006
- `CLAUDE.md`, "Requirements catalog" (data-model.md section 17 is authoritative)
