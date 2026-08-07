"""Trace -- process entry point and startup wiring."""

from __future__ import annotations

import logging

from trace_ai.config import Settings, get_settings, load_env

__all__ = ["bootstrap", "configure_logging", "main"]

logger = logging.getLogger(__name__)


def configure_logging(settings: Settings) -> None:
    """Install a root logging config at the configured level.

    `force=True` replaces any handlers a library installed on import, so the
    configured level actually takes effect rather than being silently ignored.
    """
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        force=True,
    )


def bootstrap() -> Settings:
    """Prepare the process: load `.env`, read settings, configure logging.

    Order is load-then-read, and it matters. `load_env()` populates
    `os.environ`, which is the only thing the `openai`, `anthropic`, and
    `langsmith` SDKs consult when constructing a client -- they never see
    `Settings`. Call this before any client is built.
    """
    load_env()
    # get_settings() is cached, so anything that read settings before .env was
    # loaded would have pinned pre-load values. Drop that and re-read.
    get_settings.cache_clear()
    settings = get_settings()
    configure_logging(settings)
    return settings


def main() -> None:
    settings = bootstrap()
    logger.debug("Bootstrapped in %s environment", settings.app_env)

    # Booleans only -- never the key material itself.
    configured = [
        name.removesuffix("_api_key")
        for name in ("anthropic_api_key", "openai_api_key", "langsmith_api_key")
        if getattr(settings, name) is not None
    ]

    print("Hello from trace!")
    print(f"env: {settings.app_env}  log level: {settings.log_level}")
    print(f"credentials configured: {', '.join(configured) if configured else 'none'}")
