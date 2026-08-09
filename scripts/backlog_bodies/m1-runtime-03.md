## Context

`docs/product/roadmap.md` Stage 1 calls for a simple CLI before the full interface and names
initial commands: `trace assessment create`, `trace source add`, `trace context extract`,
`trace context show`, `trace assessment status`. `docs/architecture/current-architecture.md`
section 5.1 records a local web application as the preferred MVP interface with a CLI for
development, automated testing, repeatable evaluation, and demo recovery, and states that the
interface should call application services rather than contain analysis logic. A `trace`
command already exists: `pyproject.toml` maps it to `trace_ai:main`, which prints the
environment, the log level, and which credentials are configured. This issue turns that
placeholder into the subcommand surface for the parts of the system this milestone builds.

**Blocked on DX-17** (CLI versus web interface), which settles whether the CLI is the primary
interface or a development affordance, and therefore how much it is expected to carry.

## Scope

- Add `src/trace_ai/cli.py` and route `trace_ai:main` through it, preserving the current
  no-argument behavior so `uv run trace` still reports environment, log level, and configured
  credentials.
- Use `argparse` from the standard library. No CLI framework is declared in `pyproject.toml`,
  and adding one is a dependency decision that this issue does not need to make.
- Implement the subcommands whose services exist after this milestone:
  - `trace assessment create --name ... [--description ...] [--tag ...]`
  - `trace assessment list`
  - `trace assessment status <assessment-id>`
  - `trace source add <assessment-id> <path>` — accepts a file or a directory
  - `trace source list <assessment-id>`
  - `trace evidence list <assessment-id> [--source <source-id>]`
  - `trace evidence show <evidence-id> --assessment <assessment-id>`
- Do not implement `trace context extract` or `trace context show`. Both require the Context
  Extraction Agent, which does not exist; a stub command that prints an error is worse than an
  absent one.
- Every command calls a service. The CLI parses arguments, formats output, and sets an exit
  code; it contains no ingestion, indexing, or analysis logic.
- Print source-derived text only where the user asked for it — `evidence show` — and never as
  incidental output of another command.
- Return a non-zero exit code on failure, with a message rather than a traceback for the errors
  the services raise by name: unknown assessment, unsupported format, path outside the
  assessment directory.
- Add `tests/unit/test_cli.py`, driving the parser directly and asserting on captured output.

## Acceptance criteria

- [ ] `uv run trace` with no arguments behaves as it does today, and the existing assertions in
      `tests/unit/test_entrypoint.py` still pass.
- [ ] `trace assessment create --name X` prints the new assessment identifier and persists it,
      so a following `trace assessment list` shows it.
- [ ] `trace source add <id> demo/forgeflow/input` registers all eight documents and reports
      the count.
- [ ] `trace source add` with an unsupported extension exits non-zero with a message naming the
      four supported formats, and prints no traceback.
- [ ] `trace assessment status` reports the assessment status and the source-document and
      evidence-reference counts.
- [ ] `trace evidence show` prints the identifier, the source filename, the location, and the
      quoted text.
- [ ] An unknown identifier exits non-zero with a message, not a traceback.
- [ ] No command prints a provider key, and no command prints an absolute filesystem path from
      the artifact store.
- [ ] No command requires an API key; every command in this surface runs without one.
- [ ] `trace context extract` and `trace context show` are absent rather than stubbed.
- [ ] `uv run mypy` passes strict over `src/trace_ai/cli.py`.

## Out of scope

- A web interface. `docs/product/roadmap.md` Stage 1 says do not begin with it, and Stage 5
  scopes the demonstration interface.
- Context extraction and every later workflow phase.
- Interactive human review. DEC-005's two checkpoints are structural, and their interface
  depends on DX-07 and DX-17.
- Shell completion, colored output, and progress display.
- Packaging or distribution changes beyond the existing `[project.scripts]` entry.

## References

- `docs/product/roadmap.md`, Stage 1, "Basic application entry point" and "Exit criteria";
  Stage 5, "Demonstration interface"
- `docs/architecture/current-architecture.md` sections 5.1 (User Interface),
  5.2 (Application Service), 12 ("Browser-to-application boundary")
- `docs/architecture/decision-log.md` DEC-004, DEC-005, and DX-17 once recorded
- `pyproject.toml` (`[project.scripts] trace = "trace_ai:main"`)
- `src/trace_ai/__init__.py`, `tests/unit/test_entrypoint.py`
