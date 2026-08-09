## Context

`src/trace_ai/` currently contains `config.py` and `__init__.py`, and nothing else. Every
issue in this milestone adds a module, and without an agreed layout each one places its
module by taste. `docs/architecture/current-architecture.md` section 15 proposes an initial
organization and states that the important boundary is that domain models, workflow logic,
prompts, infrastructure, and user-interface code remain reasonably separated. This issue
creates that skeleton once, so that later issues add files rather than argue about
directories.

## Scope

- Create the package skeleton under `src/trace_ai/`, each directory carrying an
  `__init__.py`:
  - `domain/` — Pydantic domain objects and shared types
  - `services/ingestion/` — document loading, normalization, segmentation
  - `services/evidence/` — evidence indexing and retrieval
  - `infrastructure/filesystem/` — the artifact store
  - `infrastructure/database/` — the assessment store
- Adapt section 15's proposed tree to the real package name. The document says `src/trace/`;
  the import package is `trace_ai`, because `trace` shadows a stdlib module.
- Do not create `api/`, `application/`, `workflow/`, `reporting/`, or `evaluation/`. Section
  15 proposes them, but nothing in this milestone puts a file in them, and an empty package
  reads as a commitment that has not been made.
- Record the layout and the domain/services/infrastructure boundary in a short section of
  `README.md` or in `src/trace_ai/domain/__init__.py`'s docstring, whichever matches the
  existing documentation practice.
- Establish the test-module naming convention. `tests/unit/` is flat today
  (`test_config.py`, `test_entrypoint.py`, `test_requirements_catalog.py`, `test_smoke.py`);
  keep it flat and name modules after the unit under test.
- Confirm the new packages are covered by the existing tooling: `[tool.mypy] files` already
  lists `src`, and `[tool.coverage.run] source` already lists `src`, so no configuration
  change should be needed. Verify rather than assume.

## Acceptance criteria

- [ ] Every directory listed above exists and contains an `__init__.py` with a one-line
      docstring stating what belongs in it.
- [ ] `uv run mypy` passes strict over the new packages with no configuration change.
- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass.
- [ ] `uv run pytest` passes.
- [ ] `import trace_ai.domain`, `import trace_ai.services.ingestion`,
      `import trace_ai.services.evidence`, `import trace_ai.infrastructure.filesystem`, and
      `import trace_ai.infrastructure.database` all succeed.
- [ ] No new runtime dependency is added to `pyproject.toml`.
- [ ] No module under `src/trace_ai/domain/` imports from `src/trace_ai/services/` or
      `src/trace_ai/infrastructure/`. A test asserts the direction of that dependency, because
      it is the boundary section 15 names and it erodes quietly.

## Out of scope

- Any domain object, service, or infrastructure implementation. This issue creates the
  skeleton only.
- A web or API layer. `docs/architecture/current-architecture.md` section 5.1 prefers a local
  web application eventually; `docs/product/roadmap.md` Stage 1 says do not begin with the
  web interface.
- Restructuring `config.py`, which stays at the package root because it is process-wide
  configuration rather than domain, service, or infrastructure code.

## References

- `docs/architecture/current-architecture.md` sections 15 (Repository Structure), 5.1, 5.2
- `docs/product/roadmap.md`, Stage 1, "Repository"
- `pyproject.toml` (`[tool.uv.build-backend] module-name`, `[tool.mypy] files`)
