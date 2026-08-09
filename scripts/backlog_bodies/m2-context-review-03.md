## Context

`docs/product/roadmap.md` Stage 1 names the initial commands and Stage 2 states that the first review experience may be command-line based or use simple structured files; section 9 says not to begin with the web interface. `docs/architecture/current-architecture.md` section 5.1 also wants a command-line interface for development, automated testing, repeatable evaluation, and demo recovery if the web interface fails. The current entry point in `src/trace_ai/__init__.py` prints the environment, the log level, and which credentials are configured, and nothing else. DX-17 settles the interface question; this issue builds the command-line surface for the context slice.

## Scope

Extend the `trace` entry point with the context-slice commands from `docs/product/roadmap.md` Stage 1:

- `trace context extract` — run the extraction node and the validation node for an assessment and stop at the checkpoint.
- `trace context show` — render the review package: components, actors, assets, data flows, trust boundaries, and claims with status, confidence, and evidence excerpts; the human-review triggers that fired; and open questions with blocking ones first.
- `trace context review` — apply the reviewer actions. Support a structured-file round trip as well as flags, since `docs/product/roadmap.md` Stage 2 permits either and a file round trip is the practical way to edit many claims.
- `trace context approve` — approve the baseline, refusing with a named reason when a blocking question or a blocking validation error remains.
- `trace assessment status` — show the current phase, whether a checkpoint is pending, and the counters from `WorkflowRun`.

Constraints on the surface:

- No command prints a secret. `src/trace_ai/config.py` holds provider credentials as `SecretStr`, and the existing `main()` prints only whether each is configured; that discipline continues.
- Source excerpts printed by `trace context show` are marked as quoted untrusted source content, so a reviewer reading the ForgeFlow injection fixture sees it framed as data rather than as guidance.
- Exit codes are meaningful. A refused approval exits non-zero, so the command is usable from an evaluation script without parsing output.
- Argument parsing stays in the standard library unless a dependency is justified; `pyproject.toml` declares no command-line framework.
- Help text follows the corpus prose register.

## Acceptance criteria

- [ ] `trace context extract`, `trace context show`, `trace context review`, `trace context approve`, and `trace assessment status` exist and are covered by tests in `tests/unit/`, following the conventions in `tests/unit/test_entrypoint.py`.
- [ ] `trace context show` renders every context object type in the review package and marks source excerpts as untrusted quoted content.
- [ ] `trace context review` round-trips a structured file: exporting, editing, and reapplying produces the same `ReviewerDecision` records as the equivalent flags.
- [ ] `trace context approve` exits non-zero and names the reason when a blocking question or validation error remains.
- [ ] `trace context approve` exits zero and sets `approved_at` and `approved_by` when the baseline is clean.
- [ ] No command prints a secret value, asserted against populated fake settings.
- [ ] Running `trace context show` on the ForgeFlow fixture displays the injected block from `demo/forgeflow/input/sample-repository-notes.md` as quoted source content, not as instructions.
- [ ] `trace assessment status` reports the pending checkpoint type when a run is paused.
- [ ] Help output for every command matches the corpus prose register: flat declarative, no marketing language, no emoji.
- [ ] All tests run offline with no API key present.
- [ ] `uv run mypy` passes strict over the new modules.

## Out of scope

- A web interface. `docs/product/roadmap.md` Stage 5 covers the demonstration interface.
- Commands for threats, mappings, findings, or reports.
- `trace assessment create` and `trace source add`, which belong to the M1 surface.
- Rich terminal rendering libraries, unless a decision records why one is needed.

## References

- `docs/product/roadmap.md` Stage 1 "Basic application entry point", Stage 2 "Human context review", section 9 (Near-Term Sequence)
- `docs/architecture/current-architecture.md` section 5.1 (User Interface — Initial implementation choice), section 12 (Security Boundaries)
- `docs/architecture/agent-design.md` section 9 (Human Context Review — Reviewer actions)
- `docs/architecture/data-model.md` section 25 (ReviewerDecision), section 26 (WorkflowRun), section 31 (Assessment State)
- `src/trace_ai/__init__.py`, `src/trace_ai/config.py`
- `tests/unit/test_entrypoint.py`
- `demo/forgeflow/input/sample-repository-notes.md`
