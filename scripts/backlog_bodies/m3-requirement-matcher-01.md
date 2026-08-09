## Context

`requirements/` holds 23 requirements across 11 category files plus a manifest.
`requirements/README.md` states that no product code reads it and that
`tests/unit/test_requirements_catalog.py` checks only that it is well-formed. DEC-010
records that `content_hash`, required on `RequirementsCatalog` by `docs/architecture/data-model.md`
section 30, is deliberately omitted "until a loader exists to compute it." This issue
builds that loader and makes the catalog the first version-controlled data the application
reads. It precedes every other requirement-matcher and control-mapper issue in M3.

## Scope

- Add `src/trace_ai/domain/models/requirement.py` with a `Requirement` Pydantic model
  matching `docs/architecture/data-model.md` section 17 exactly. Required: `id`,
  `catalog_version`, `title`, `statement`, `rationale`, `category`, `status`. Optional:
  `applicable_technologies`, `applicable_conditions`, `non_applicable_conditions`,
  `acceptable_implementations`, `evidence_expectations`, `common_false_positives`,
  `default_severity`, `source_frameworks`, `supersedes_id`. Unknown fields are a
  validation error, matching the existing `test_has_no_unknown_fields`.
- Add `src/trace_ai/domain/models/requirements_catalog.py` with a `RequirementsCatalog`
  model per section 30.
- Add `src/trace_ai/services/requirements/loader.py`. It discovers the version directory
  from `catalog.yaml`, loads every category file, validates each requirement, and asserts
  manifest and file agreement in both directions.
- Compute `content_hash` per the DX-20 decision. State in the loader docstring exactly
  what input the hash covers, because a hash over an unstated input is not verifiable.
- Refactor `tests/unit/test_requirements_catalog.py` to validate through the loader where
  that does not weaken a check. Retain every check it makes today: schema conformance,
  the `req-` identifier prefix, manifest agreement, and citation format against the
  adopted framework list. The citation-format check has no Pydantic equivalent and must
  survive the refactor unchanged in strictness.
- Update `requirements/README.md` and the DEC-010 entry to reflect that a loader now
  exists and that the `content_hash` open question is closed.

## Acceptance criteria

- [ ] All 23 requirements in `requirements/0.1/` load and validate.
- [ ] A requirement carrying a field outside the section 17 set fails to load, with a
      message naming the field and pointing at `docs/architecture/data-model.md` section 17.
- [ ] `default_severity` accepts only the section 4.5 vocabulary. `status` accepts only
      `draft`, `active`, `retired`.
- [ ] Manifest and file disagreement in either direction is an error that names the
      identifiers on each side.
- [ ] `content_hash` is computed per DX-20, is stable across runs, and changes when any
      requirement changes. The loader docstring states what is hashed.
- [ ] The citation-format check survives the refactor and still rejects a citation naming
      a framework the catalog has not adopted.
- [ ] The loader reads the catalog version recorded on the assessment rather than whatever
      directory happens to sort last, so a later catalog version cannot silently change an
      in-flight assessment.
- [ ] `uv run pytest` passes with no network access and no provider API key.
- [ ] `uv run mypy` passes in strict mode.
- [ ] `requirements/README.md` no longer states that no product code reads the catalog.

## Out of scope

- Any change to requirement content. This issue reads the catalog; it does not edit it.
- Adding fields to `Requirement`. `requirements/README.md` is explicit that extending the
  object is a design change requiring a decision-log entry, and DEC-011 is the worked
  example of that process.
- Introducing a controlled vocabulary for `applicable_conditions`. That omission is
  deliberate per `docs/architecture/data-model.md` section 39 question 5 and
  `requirements/README.md`, and answering it by accident here is the failure to avoid.
- Candidate selection and payload assembly, which follow in later requirement-matcher
  issues.

## References

- `docs/architecture/data-model.md` section 17 (Requirement — Fields; Note on
  common_false_positives), section 30 (RequirementsCatalog), section 4.5 (Severity),
  section 33 (Schema Validation), section 40 (Initial Implementation Priority item 12)
- `docs/architecture/decision-log.md` DEC-010, including its third open question
- `requirements/README.md` — *Layout*, *How to read a requirement*, *Validation*,
  *`content_hash`*, *Version 0.1*
- `requirements/catalog.yaml`; `requirements/0.1/*.yaml`
- `tests/unit/test_requirements_catalog.py`
