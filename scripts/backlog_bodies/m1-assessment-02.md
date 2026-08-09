## Context

`docs/architecture/current-architecture.md` section 5.2 assigns the application service
assessment creation, input validation, file registration, and configuration management, and
says it should contain no agent prompts and no substantial security-analysis logic.
`docs/product/roadmap.md` Stage 1 makes "A new assessment can be created" and "Structured
objects can be persisted and retrieved" exit criteria, and lists assessment isolation among
the tests the stage requires. The Assessment model and the persistence layer exist
separately; this issue is the seam between them, and it is where the assessment-data boundary
in section 12 is actually enforced.

## Scope

- Add `src/trace_ai/services/assessment.py` with an `AssessmentService` over the store and the
  artifact store.
- Implement `create(name, description=None, configuration=None, tags=None) -> Assessment`:
  allocate the identifier, stamp the version fields, persist the assessment, and create its
  artifact directory. Creation is one operation; a persisted assessment without its directory,
  or the reverse, is a state the rest of the milestone should not have to handle.
- Implement `get(assessment_id)`, `list()`, and `status(assessment_id)`. `status` returns the
  assessment's `status`, its `active_workflow_run_id`, and counts of its registered source
  documents and evidence references — the information `trace assessment status` needs.
- Implement `update_status(assessment_id, status)` enforcing the `ObjectStatus` transitions
  the MVP uses, and refreshing `updated_at`.
- Return an assessment-scoped handle (store repositories plus artifact store) rather than raw
  identifiers, so that a caller holding one assessment cannot address another by passing a
  different string.
- Reject creation with a duplicate identifier, and reject a lookup for an unknown identifier
  with a named error rather than `None`.
- Add `tests/unit/test_assessment_service.py`.

## Acceptance criteria

- [ ] `create` produces an assessment that `get` returns unchanged, including its
      configuration.
- [ ] `create` leaves the artifact directory present with all five subdirectories.
- [ ] A failure part-way through `create` leaves neither a persisted assessment without a
      directory nor a directory without a persisted assessment. Asserted by injecting a
      failure.
- [ ] `get` for an unknown identifier raises a named error; it does not return `None`.
- [ ] Two assessments created in the same store are independent: source documents and evidence
      references registered under one are not visible from the other, and neither can read the
      other's artifact directory. This is the assessment-data boundary from
      `current-architecture.md` section 12 and is asserted directly.
- [ ] `status` reports source-document and evidence-reference counts that match what was
      registered.
- [ ] `update_status` refreshes `updated_at` and rejects a value outside `ObjectStatus`.
- [ ] The service makes no model call and needs no API key.
- [ ] `uv run mypy` passes strict.

## Out of scope

- A CLI. The CLI issue calls this service.
- Starting a workflow run. `active_workflow_run_id` is read and written but nothing sets it
  until the execution ledger exists.
- Deleting an assessment and its artifacts (`data-model.md` section 36).
- Multi-user concerns. DEC-004 makes the MVP local and single-user, with no RBAC.

## References

- `docs/architecture/current-architecture.md` sections 5.2 (Application Service),
  5.15, 5.16, 12 (Security Boundaries)
- `docs/architecture/data-model.md` sections 5 (Assessment), 4.1 (ObjectStatus),
  35 (Data Persistence)
- `docs/architecture/decision-log.md` DEC-004
- `docs/product/roadmap.md`, Stage 1, "Test foundation" and "Exit criteria"
