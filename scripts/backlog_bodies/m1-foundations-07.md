## Context

`docs/architecture/data-model.md` section 35 proposes SQLite for structured assessment data
and the local filesystem for artifacts, with the database holding references and content
hashes for the files. `docs/architecture/current-architecture.md` section 5.15 lists what the
assessment store holds. `docs/product/roadmap.md` Stage 1 makes "Structured objects can be
persisted and retrieved" an exit criterion, and the same stage requires that no model call be
needed to verify the foundation. Persistence is also what makes the identifier scheme
meaningful: section 2.1 lists resuming interrupted workflows and comparing evaluation runs
among the reasons identifiers exist.

**Blocked on DX-04** (persistence approach and schema versioning). DX-04 settles which
objects live in SQLite versus version-controlled YAML or JSON (data-model.md open question
13), how object revisions are stored (open question 9), and how migrations are handled during
early development (open question 17). Do not begin until it is recorded.

## Scope

- Add `src/trace_ai/infrastructure/database/store.py` implementing the approach DX-04 decides.
- Provide a repository interface per persisted object rather than one general-purpose table
  accessor, so that the assessment-data boundary is expressible: every read and write is
  scoped by `assessment_id`.
- Implement persistence for the objects this milestone produces: `Assessment`,
  `AssessmentConfiguration` (as part of its assessment), `SourceDocument`, and
  `EvidenceReference`. Leave the remaining objects in data-model.md section 40's priority list
  to later milestones.
- Store references and content hashes for filesystem artifacts rather than file bodies, per
  section 35.
- Implement schema versioning as DX-04 decides, including a recorded schema version that a
  later migration can read.
- Validate on the way in and on the way out. Section 33 requires validation when input enters
  the application and before objects are persisted, and a row that no longer parses into its
  model must fail loudly rather than return a partially populated object.
- Use the local database file path from the artifact store's root, so a single assessment's
  data is co-located and deletable.
- Add `tests/unit/test_store.py`, using `tmp_path` and an on-disk database rather than
  `:memory:`, so the file-path behavior is exercised.

## Acceptance criteria

- [ ] An `Assessment` round-trips: persisted and re-read, it compares equal to the original,
      including `Decimal` fields, timezone-aware timestamps, and `tags`.
- [ ] A `SourceDocument` and an `EvidenceReference` round-trip, with their `assessment_id`
      preserved.
- [ ] A read scoped to assessment A never returns a row belonging to assessment B, asserted
      for every implemented repository. This is `current-architecture.md` section 12's
      assessment-data boundary.
- [ ] Writing an object whose `assessment_id` does not match the repository's scope raises.
- [ ] A stored row that fails to validate on read raises a named error rather than returning a
      partial object (section 33: validation errors are not silently discarded).
- [ ] The recorded schema version is readable from a fresh database and from an existing one.
- [ ] Two assessments in the same database do not share identifiers or overwrite each other.
- [ ] The store needs no API key and no network; tests run under a bare `uv run pytest`.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Workflow checkpointing and resumable runs. `current-architecture.md` section 5.15 lists
  workflow checkpoints among the store's contents, but the checkpoint format depends on the
  orchestrator, which is DX-06, and on pause-and-resume, which is DX-07.
- An ORM choice beyond what DX-04 decides. `current-architecture.md` section 14 records the
  ORM or database layer as "To be determined".
- Migrations against real data. Nothing has been persisted yet.
- Export packaging (`data-model.md` section 37) and retention (section 36).

## References

- `docs/architecture/data-model.md` sections 35 (Data Persistence), 33 (Schema Validation),
  2.1 (Stable identifiers), 39 questions 9, 13, and 17, 40
- `docs/architecture/current-architecture.md` sections 5.15 (Assessment Store),
  12 (Security Boundaries), 14 (Proposed Technology Stack)
- `docs/product/roadmap.md`, Stage 1, "Persistence" and "Exit criteria"
- `docs/architecture/decision-log.md` DEC-004, DEC-006, and DX-04 once recorded
