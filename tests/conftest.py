"""Session-wide test isolation, applied to every test by default.

Three duties, each of which was previously handled per-file or not at all, and each of which
fails silently the day it is forgotten:

* **No test reads a real `.env` or a real key.** `get_settings()` reads `trace_ai.config.ENV_FILE`,
  which exists on a configured developer machine, and the provider SDKs read `os.environ`. Left
  alone, the suite passes against whatever credentials happen to be present -- so it passes locally
  and fails in CI, or worse, quietly spends money. Pointing `ENV_FILE` at a path that cannot exist
  and clearing the three key variables makes the local suite match CI's no-key environment, which is
  the environment the "CI must never need a provider key" constraint is really about. A test that
  wants a key opts back in with `monkeypatch.setenv(...)`.

* **The settings cache does not leak between tests.** `get_settings` is `lru_cache`'d, so one test's
  environment would pin values for every test after it. Clearing it before and after each test makes
  the manipulation local.

* **The root logger is restored.** `bootstrap()`/`install()` replace every root handler and set the
  root level with no restore of their own (that is deliberate -- a real process wants exactly one
  handler). In a test process that would rip out pytest's log-capture handler for the remainder of
  the session, so any test that calls `run()` or `bootstrap()` would silently break `caplog` for the
  tests that follow it. Snapshotting and restoring the handlers and level confines the effect to the
  test that caused it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from trace_ai.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

_PROVIDER_KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY")


@pytest.fixture(autouse=True)
def _isolate_environment_and_logging(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    # Redirect the .env read at its source. Settings captured ENV_FILE into model_config when the
    # class was defined, but get_settings() passes it explicitly at call time (config.py), so this
    # patch is the one that actually governs the read.
    absent_env = tmp_path_factory.mktemp("no-env") / "absent.env"
    monkeypatch.setattr("trace_ai.config.ENV_FILE", absent_env)
    for var in _PROVIDER_KEY_VARS:
        monkeypatch.delenv(var, raising=False)

    get_settings.cache_clear()

    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        yield
    finally:
        get_settings.cache_clear()
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
