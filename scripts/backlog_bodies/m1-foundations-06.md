## Context

`docs/architecture/current-architecture.md` section 5.16 specifies a controlled local
directory as the MVP artifact store, with an assessment-specific structure that avoids mixing
data between assessments, and gives the layout `data/assessments/assessment-001/{sources,
normalized, outputs, traces, evaluation}`. `docs/architecture/data-model.md` section 35 splits
storage: original and normalized documents live on the filesystem, and the database stores
references and content hashes. Section 12 of current-architecture.md names the assessment-data
boundary as a trust boundary in its own right. The loader cannot register a document until
there is somewhere defined to put it, and where that is must not be a decision each caller
makes.

## Scope

- Add `src/trace_ai/infrastructure/filesystem/artifact_store.py` with an `ArtifactStore`
  rooted at a configurable directory, defaulting to `PROJECT_ROOT / "data"`.
- Implement the per-assessment layout under `assessments/<assessment_id>/`: `sources/`,
  `normalized/`, `outputs/`, `traces/`, `evaluation/`, created on demand.
- Implement `store_source(filename, content) -> Path` and `store_normalized(...)`, returning
  the written paths that populate `SourceDocument.original_path` and
  `SourceDocument.normalized_path`.
- Bind a store instance to one assessment identifier. Every path it resolves is under that
  assessment's directory, and a request naming another assessment raises.
- Reject any filename that escapes the assessment directory. `SourceDocument.filename` is the
  original filename and is caller-supplied, so a `..` component, an absolute path, or a
  symlink whose target resolves outside the root must raise before anything is written.
- Reuse the content-hash helper from the identifiers and hashing issue rather than hashing
  here; hashing lives in one place.
- Use `pathlib` throughout. The `PTH` ruff rules are enabled and `os.path` will not pass lint.
- Add a settings field for the artifact root if one is warranted, together with its
  `.env.example` line. `tests/unit/test_config.py::test_env_example_matches_settings_fields`
  fails if `Settings` and `.env.example` drift apart.
- Add `tests/unit/test_artifact_store.py`, using `tmp_path` throughout.

## Acceptance criteria

- [ ] The directory layout matches `current-architecture.md` section 5.16 exactly, including
      all five subdirectories.
- [ ] `store_source` with `filename="../../../etc/passwd"` raises and writes nothing outside
      the assessment root. Asserted separately for `..` traversal, for an absolute path, and
      for a symlink resolving outside the root.
- [ ] Two assessments storing the same filename do not collide or overwrite each other.
- [ ] A store bound to one assessment cannot read or write a path belonging to another. This
      is the assessment-data boundary from `current-architecture.md` section 12 and is
      asserted directly rather than implied by the path construction.
- [ ] Stored content is byte-identical to the input. Section 5.4 requires preserving original
      content, and a normalization applied at write time would destroy the property the
      evidence model depends on.
- [ ] Storing the same content twice yields the same content hash.
- [ ] Every test writes under `tmp_path`; no test writes into the repository or into `data/`.
- [ ] `uv run mypy` passes strict; the `S` and `PTH` ruff rule sets pass with no `noqa`.

## Out of scope

- SQLite and the structured assessment store.
- Normalization, segmentation, and evidence indexing.
- Report and trace writing; the directories exist, but nothing in this milestone fills
  `outputs/`, `traces/`, or `evaluation/`.
- Assessment deletion and retention (`data-model.md` section 36) and export packaging
  (section 37).

## References

- `docs/architecture/current-architecture.md` sections 5.16 (Artifact Store),
  5.15 (Assessment Store), 5.4 (Document Ingestion), 12 (Security Boundaries)
- `docs/architecture/data-model.md` sections 35 (Data Persistence), 7 (`original_path`,
  `normalized_path`, `content_hash`)
- `docs/product/roadmap.md`, Stage 1, "Persistence"
- `pyproject.toml` (`[tool.ruff.lint] select` includes `S` and `PTH`)
