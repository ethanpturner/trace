"""Typed application settings, loaded from the environment and an optional .env file.

Secrets are held as `SecretStr` so they cannot leak through `repr()`, logs, or
tracebacks. Reach the real value deliberately via `Settings.require()` or
`.get_secret_value()`.

Two distinct mechanisms are at work here, and the difference matters:

* `Settings` reads `.env` itself, but does **not** put anything into
  `os.environ`. It is the typed, validated view of configuration.
* A provider SDK (`anthropic`) reads `os.environ` directly at
  client-construction time and never sees `Settings`. Call `load_env()` once
  at process start so it picks up `.env` too.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

from dotenv import load_dotenv
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/trace_ai/config.py -> src/trace_ai -> src -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# Whether the process is running from a source checkout (DEC-090). v0.1 is clone-only: the prompts,
# the requirements catalog, the report template, and the benchmark scenarios are version-controlled
# files that live in the repository, not package data in the wheel, so a command that reads any of
# them needs the repository present. `PROJECT_ROOT` is the repo root from a clone (and an editable
# `uv sync`) and site-packages' parent from an installed wheel, where no `pyproject.toml` sits
# beside it -- so its presence is the marker.
IS_SOURCE_CHECKOUT: Final[bool] = (PROJECT_ROOT / "pyproject.toml").is_file()


class SourceCheckoutRequiredError(RuntimeError):
    """A command that needs the repository's version-controlled assets was run outside a checkout.

    Stated rather than left to surface as a dangling `FileNotFoundError` deep in a report render or
    a catalog load. DEC-090 makes v0.1 clone-only; installability is a later decision.
    """

    def __init__(self) -> None:
        super().__init__(
            "Trace v0.1 runs from a source checkout, not an installed wheel (DEC-090): its prompts, "
            "requirements catalog, report template, and benchmark scenarios are version-controlled "
            "files in the repository. Clone it and run from there, e.g. `uv run trace ...`."
        )


def require_source_checkout() -> None:
    """Raise `SourceCheckoutRequiredError` unless the repository's assets are present."""
    if not IS_SOURCE_CHECKOUT:
        raise SourceCheckoutRequiredError()


class MissingSettingError(RuntimeError):
    """A required setting was not configured."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"{name.upper()} is not set. Copy .env.example to .env and fill it in, "
            f"or export {name.upper()} in the environment."
        )
        self.name = name


class Settings(BaseSettings):
    """Configuration for the application.

    Field names map to upper-case environment variables of the same name, which
    is deliberate: `anthropic_api_key` reads `ANTHROPIC_API_KEY`, the same
    variable the Anthropic SDK looks for. One name, one source of truth.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    app_env: Literal["local", "ci", "staging", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Model providers. Optional so the app imports cleanly in CI and in tests,
    # where no key exists; use require() at the point of actual use. `openai_api_key` is here
    # because the seam is provider-agnostic (DEC-014) and a second adapter would read it; the
    # `langsmith` settings were removed with the unwired dependency (DEC-090).
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    # External tracing (#538, DEC-109). The destination for execution spans when an
    # assessment's `enable_external_tracing` is on: `file://<path>` appends JSON lines,
    # `http(s)://` posts the batch. Absent means tracing has nowhere to go and emits nothing.
    # The spans carry the ledger's identifiers and numbers, never prompt or source content.
    tracing_endpoint: str | None = None
    tracing_api_key: SecretStr | None = None

    # Repository ingestion (#597). Optional: public repositories fetch unauthenticated, and a
    # configured token reaches only the clone subprocess's URL — never metadata, never a log.
    github_token: SecretStr | None = None

    @field_validator(
        "anthropic_api_key", "openai_api_key", "tracing_api_key", "github_token", mode="before"
    )
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        """Treat an empty variable as absent rather than as an empty secret.

        `cp .env.example .env` leaves every key blank. Without this, blanks
        parse as SecretStr("") -- which is not None, so require() would hand an
        empty string to the SDK and the developer would debug a 401 instead of
        reading a message telling them the key is unset.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def require(self, name: str) -> str:
        """Return a configured secret, or raise a message that says how to fix it.

        Prefer this over `.get_secret_value()` at call sites, so a missing key
        fails with actionable guidance instead of `NoneType has no attribute`.
        """
        value = getattr(self, name)
        if value is None:
            raise MissingSettingError(name)
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        return str(value)


def load_env(*, override: bool = False) -> bool:
    """Populate `os.environ` from `.env` so provider SDKs auto-configure.

    Real environment variables win by default; pass `override=True` only when
    you intend `.env` to take precedence over the ambient environment.
    """
    return load_dotenv(ENV_FILE, override=override)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, read once and cached.

    Call `get_settings.cache_clear()` in tests that manipulate the environment.

    The dotenv path is passed at call time rather than left to `model_config`, which captured
    `ENV_FILE` when the class was defined: a test that monkeypatches `trace_ai.config.ENV_FILE`
    must actually redirect this read, or the test only passes on machines with no real `.env` —
    exactly the machines that stop existing the day someone configures a key (#417).
    """
    return Settings(_env_file=ENV_FILE)
