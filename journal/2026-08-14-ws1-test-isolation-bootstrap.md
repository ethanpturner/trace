# WS1: test isolation and process bootstrap

First workstream of a twelve-issue robustness/scalability/extensibility program (#442–#453) that
came out of a three-agent exploration of the codebase. WS1 (#442) is phase 0: it fixes the ways the
test suite and the process did not run in the environment they claimed to, so every later
workstream's tests inherit a clean baseline.

## What changed

**A `tests/conftest.py` now isolates every test.** There was none before, so three duties were
handled per-file or not at all. The autouse fixture (a) points `trace_ai.config.ENV_FILE` at a path
that cannot exist and clears `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`LANGSMITH_API_KEY`, so the local
suite runs in the same no-key environment CI does rather than against whatever the developer has
configured; (b) clears the `get_settings` `lru_cache` before and after each test; (c) snapshots and
restores the root logger's handlers and level, so a test that calls `bootstrap()`/`install()` cannot
strip pytest's capture handler for the tests that follow it. This makes #417 — the test that failed
once a real `.env` existed — structurally impossible rather than machine-dependent. Verified by
running the suite with `ANTHROPIC_API_KEY` exported in the shell.

**`bootstrap()` now runs for every command, not just the banner.** It was called only from
`_banner()` (the no-argument invocation), so `run`, `resume`, and `evaluate` — the commands that
actually process untrusted source documents — left `.env` unloaded and the redaction filter
uninstalled, meaning third-party (`anthropic`/`httpx`) log output bypassed it. `run()` now
bootstraps once at the top and hands the settings to `_banner()`, which no longer bootstraps a
second time.

**Decided the observability module's role rather than leaving it ambiguous.** The exploration
flagged that nothing in `src/` emits a log record, while the module's docstring read as though it
*were* the section-5.17 audit record. Reframed the docstring: the authoritative audit record is the
execution ledger (`services/execution_ledger.py`); this module's job is that whatever *does* reach a
log line — first-party via `bind()`, or third-party once bootstrap runs — is structured JSON and
passes the redaction filter. That is a real, testable value even with no first-party producers,
which is why the filter stays. Chose this over instrumenting the orchestrator with producers now:
the issue sanctioned either, and adding producers is better done in the workstream that owns the
orchestrator's error paths (WS3).

**`.DS_Store` is gitignored** in its own commented block, satisfying
`test_gitignore_rules_are_documented`.

## Tests

Removed the now-redundant `_clear_settings_cache` fixture from `test_entrypoint.py` (conftest covers
it) and added two tests: `run` installs the redaction filter for a real dispatched command
(`assessment list`), and `run` applies the configured log level. Full suite green (3655 passed),
mypy/ruff/pre-commit clean.

## Open next

WS2 (#443, store transactionality — the reproduced nested-transaction identifier reuse) is the next
correctness workstream; WS3 (#444) depends on it.
