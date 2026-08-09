"""Tests for startup wiring.

These exercise the ordering guarantees bootstrap() is responsible for, not
just that it runs without raising.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from trace_ai import bootstrap, configure_logging
from trace_ai.cli import run
from trace_ai.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Stop a cached Settings from leaking between tests."""
    get_settings.cache_clear()


def test_main_reports_environment_without_leaking_secrets(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("trace_ai.config.ENV_FILE", tmp_path / "absent.env")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-do-not-print-me")

    run([])

    out = capsys.readouterr().out
    assert "Hello from trace!" in out
    assert "anthropic" in out
    assert "sk-ant-do-not-print-me" not in out


def test_main_reports_none_when_no_credentials_configured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("trace_ai.config.ENV_FILE", tmp_path / "absent.env")
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    run([])

    assert "credentials configured: none" in capsys.readouterr().out


def test_bootstrap_loads_dotenv_into_os_environ(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The SDKs read os.environ, so .env must actually land there."""
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-openai-from-dotenv\n", encoding="utf-8")
    monkeypatch.setattr("trace_ai.config.ENV_FILE", env_file)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    bootstrap()

    assert os.environ["OPENAI_API_KEY"] == "sk-openai-from-dotenv"


def test_bootstrap_discards_settings_cached_before_dotenv_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A pre-bootstrap read must not pin stale values for the whole process."""
    env_file = tmp_path / ".env"
    env_file.write_text("LANGSMITH_PROJECT=from-dotenv\n", encoding="utf-8")
    monkeypatch.setattr("trace_ai.config.ENV_FILE", env_file)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    # Something reads settings too early, before .env has been loaded.
    stale = Settings(_env_file=None)
    assert stale.langsmith_project == "trace"
    get_settings.cache_clear()
    get_settings()

    settings = bootstrap()

    assert settings.langsmith_project == "from-dotenv"


def test_configure_logging_applies_the_settings_level(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("trace_ai.config.ENV_FILE", tmp_path / "absent.env")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    configure_logging(Settings(_env_file=None))

    assert logging.getLogger().level == logging.WARNING


def test_bootstrap_returns_usable_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("trace_ai.config.ENV_FILE", tmp_path / "absent.env")
    monkeypatch.setenv("APP_ENV", "ci")

    settings = bootstrap()

    assert settings.app_env == "ci"
