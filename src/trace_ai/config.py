"""Typed application settings, loaded from the environment and an optional .env file.

Secrets are held as `SecretStr` so they cannot leak through `repr()`, logs, or
tracebacks. Reach the real value deliberately via `Settings.require()` or
`.get_secret_value()`.

Two distinct mechanisms are at work here, and the difference matters:

* `Settings` reads `.env` itself, but does **not** put anything into
  `os.environ`. It is the typed, validated view of configuration.
* Provider SDKs (`openai`, `anthropic`, `langsmith`) read `os.environ`
  directly at client-construction time and never see `Settings`. Call
  `load_env()` once at process start so those SDKs pick up `.env` too.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/trace_ai/config.py -> src/trace_ai -> src -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


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
    # where no key exists; use require() at the point of actual use.
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    # LangSmith tracing.
    langsmith_api_key: SecretStr | None = None
    langsmith_tracing: bool = False
    langsmith_project: str = "trace"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    @field_validator("anthropic_api_key", "openai_api_key", "langsmith_api_key", mode="before")
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
