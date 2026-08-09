## Context

`docs/architecture/current-architecture.md` section 5.16 places the MVP artifact store in a
local directory laid out as `data/assessments/assessment-001/{sources, normalized, outputs,
traces, evaluation}`, and `docs/architecture/data-model.md` section 35 puts original
documents, normalized documents, generated reports, debug artifacts, and exported traces on
the filesystem. `.gitignore` currently covers Python build output, the virtual environment,
tool caches, and `.env`, and says nothing about `data/`. The first run of the loader would
therefore offer every ingested source document to the next commit, including
`demo/forgeflow/input/sample-repository-notes.md`, which carries a deliberate
prompt-injection fixture. Duplicating that into an untracked-then-tracked working directory
is the kind of accident that is trivial to prevent and tedious to unwind.

## Scope

- Add `data/` to `.gitignore`, in its own commented section matching the file's existing
  style.
- Add a `.gitkeep`-style exception only if the artifact store requires the root to exist at
  import time. Prefer creating the directory on demand, so the ignore rule needs no exception.
- Confirm the ignore rule does not shadow anything tracked. `demo/`, `benchmarks/`, and
  `requirements/` hold version-controlled fixtures and data and must remain tracked; the rule
  must be anchored so it matches the repository-root `data/` and not a nested `data/`
  directory under any of them.
- Add a test asserting the rule is present, in `tests/unit/test_repository_hygiene.py` or
  alongside the artifact-store tests, so the line is not dropped in a later edit.

## Acceptance criteria

- [ ] `.gitignore` contains an anchored `data/` rule.
- [ ] `git check-ignore -v data/assessments/asm-001/sources/architecture-overview.md` reports
      the rule as matching.
- [ ] No currently tracked file becomes ignored. Verified by confirming that
      `git status --porcelain` reports no change to tracked files other than `.gitignore`.
- [ ] `demo/`, `benchmarks/`, `requirements/`, and `prompts/` remain tracked.
- [ ] A test asserts the presence of the rule and fails if it is removed.

## Out of scope

- Creating the artifact store or its directory layout.
- Data retention and deletion (`docs/architecture/data-model.md` section 36).
- Ignoring generated reports elsewhere in the tree; reports are written under `data/`.

## References

- `docs/architecture/current-architecture.md` section 5.16 (Artifact Store)
- `docs/architecture/data-model.md` sections 35 (Data Persistence), 36 (Data Retention)
- `.gitignore`
- `demo/forgeflow/input/sample-repository-notes.md`
