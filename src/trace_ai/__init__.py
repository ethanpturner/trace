"""Trace -- process entry point and startup wiring."""

from __future__ import annotations

import logging

from trace_ai.config import Settings, get_settings, load_env
from trace_ai.observability import install

__all__ = ["bootstrap", "configure_logging", "main"]

logger = logging.getLogger(__name__)


def configure_logging(settings: Settings) -> None:
    """Install the structured handler at the configured level.

    Existing root handlers are replaced, which is what `basicConfig(force=True)` did before: a
    handler a library installed on import would otherwise keep emitting records that never pass
    through the redaction filter, which is the failure mode worth preventing rather than the
    duplicate output.
    """
    install(settings.log_level)


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


def main() -> int:
    """The `trace` console entry point, routed through the command surface.

    The import is deferred rather than done at module scope: `trace_ai.cli` imports from
    `trace_ai.config` and the domain packages, all of which import `trace_ai` first, so a
    top-level import here would be circular.
    """
    from trace_ai.cli import run

    return run()
