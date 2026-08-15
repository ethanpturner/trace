"""Tests for typed settings and secret handling.

Every Settings instance here passes `_env_file=None`. Without it the tests read
the developer's real .env and pass or fail depending on whose machine they run
on -- green locally, red in CI, or worse, the reverse.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from trace_ai.config import ENV_FILE, PROJECT_ROOT, MissingSettingError, Settings, load_env

ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


def _example_keys() -> set[str]:
    keys: set[str] = set()
    for raw in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip().lower())
    return keys


def test_defaults_apply_with_no_environment() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "local"
    assert settings.log_level == "INFO"
    assert settings.anthropic_api_key is None
    assert settings.openai_api_key is None


def test_reads_provider_keys_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")

    settings = Settings(_env_file=None)

    assert settings.require("anthropic_api_key") == "sk-ant-test"
    assert settings.require("openai_api_key") == "sk-openai-test"


def test_secrets_do_not_leak_through_repr_or_str(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-super-secret")

    settings = Settings(_env_file=None)

    assert "sk-ant-super-secret" not in repr(settings)
    assert "sk-ant-super-secret" not in str(settings)
    assert "sk-ant-super-secret" not in str(settings.model_dump())


def test_require_raises_actionable_error_when_unset() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(MissingSettingError) as excinfo:
        settings.require("anthropic_api_key")

    assert "ANTHROPIC_API_KEY" in str(excinfo.value)
    assert ".env" in str(excinfo.value)


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_key_is_treated_as_unset(blank: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The `cp .env.example .env` path leaves keys blank; that must read as unset."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", blank)

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key is None
    with pytest.raises(MissingSettingError):
        settings.require("anthropic_api_key")


def test_invalid_enum_value_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "CHATTY")

    with pytest.raises(ValueError, match="log_level"):
        Settings(_env_file=None)


def test_settings_are_frozen() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ValueError, match="frozen"):
        settings.app_env = "prod"  # type: ignore[misc]


def test_env_example_matches_settings_fields() -> None:
    """.env.example must document every setting, and document nothing extra."""
    documented = _example_keys()
    declared = set(Settings.model_fields)

    assert documented - declared == set(), "documented in .env.example but not a Settings field"
    assert declared - documented == set(), "Settings field missing from .env.example"


def test_env_example_ships_no_real_secret_values() -> None:
    """Placeholders only -- a filled-in example is a committed credential."""
    for raw in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if key.lower().endswith(("_api_key", "_token", "_secret", "_password")):
            assert value == "", f"{key} in .env.example must be empty, found a value"


def test_load_env_is_a_no_op_when_file_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("trace_ai.config.ENV_FILE", tmp_path / "nope.env")

    assert load_env() is False


def test_env_file_points_at_repo_root() -> None:
    assert ENV_FILE == PROJECT_ROOT / ".env"
    assert (PROJECT_ROOT / "pyproject.toml").is_file()
