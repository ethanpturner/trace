## Context

`docs/architecture/data-model.md` section 4 defines seven shared enumerated types that every
later domain object refers to by name. Section 33 states that the implementation should use
Pydantic models for domain validation, and DEC-006 makes schema-validated structured objects
the authoritative workflow state. Nothing in `src/trace_ai/` defines a domain object today, so
the shared types and the common model configuration land first and every other object in this
milestone imports them.

## Scope

- Add `src/trace_ai/domain/enums.py` with one `StrEnum` per shared type, carrying exactly the
  members data-model.md section 4 lists and no others:
  - `ObjectStatus`: `draft`, `candidate`, `pending_review`, `approved`, `rejected`,
    `superseded`, `archived` (section 4.1)
  - `ConfidenceLevel`: `low`, `medium`, `high` (section 4.2)
  - `EvidenceStrength`: `direct`, `indirect`, `contextual`, `contradictory` (section 4.3)
  - `SourceOrigin`: `uploaded_document`, `structured_input`, `user_response`,
    `requirements_catalog`, `system_generated`, `reviewer_edit`, `external_tool` (section 4.4)
  - `Severity`: `informational`, `low`, `medium`, `high`, `critical`, `unassigned` (section 4.5)
  - `ReviewDisposition`: `approve`, `reject`, `edit`, `defer`, `request_more_analysis`,
    `convert_to_question`, `convert_to_documentation_gap` (section 4.6)
  - `ValidationStatus`: `supported`, `partially_supported`, `unsupported`, `contradicted`,
    `requires_confirmation`, `not_evaluated` (section 4.7)
- Add `src/trace_ai/domain/base.py` with a `DomainModel(BaseModel)` base carrying one
  `model_config`: `extra="forbid"`, `frozen=True`, `validate_assignment=True`,
  `str_strip_whitespace=True`.
  `extra="forbid"` is the mechanism by which an agent-proposed object carrying an invented
  field fails validation instead of silently passing it downstream. Agents propose objects;
  the application validates and persists them, so the rejection has to happen in the schema.
- Add a UTC-aware timestamp helper (`now()`) used by every object with `created_at` or
  `updated_at`, so no naive datetime enters the model.
- Add `tests/unit/test_domain_enums.py` and `tests/unit/test_domain_base.py`.

## Acceptance criteria

- [ ] Each enum's member set is asserted literally against the list in data-model.md section
      4. A member added or removed in the document without updating the code fails the test.
- [ ] Enum values are the exact lowercase snake_case strings the document uses, so a
      serialized object round-trips into the corpus vocabulary.
- [ ] `DomainModel` rejects an unknown field with a `ValidationError`.
- [ ] `DomainModel` instances are immutable; assigning to an attribute raises.
- [ ] `now()` returns a timezone-aware datetime.
- [ ] No module under `src/trace_ai/domain/` imports `anthropic`, `openai`, `langchain`,
      `langgraph`, or `instructor`. A test asserts this. Those packages are declared in
      `pyproject.toml` and imported nowhere, and their presence is not a decision.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Any concrete domain object. Assessment, SourceDocument, and EvidenceReference are separate
  issues.
- `ContextClaim` status values (data-model.md section 10). That vocabulary is declared on
  `ContextClaim` rather than in section 4, and belongs to the context-extraction milestone.
- Identifier types and content hashing.
- Persistence and serialization.

## References

- `docs/architecture/data-model.md` sections 4.1–4.7 (Shared Types), 33 (Schema Validation),
  40 (Initial Implementation Priority)
- `docs/architecture/decision-log.md` DEC-006
- `docs/architecture/agent-design.md` sections 2.2, 2.5
- `docs/architecture/current-architecture.md` section 14 (Proposed Technology Stack)
