"""Structured logging, and the two things that must never reach a log line.

**This module is not the audit record.** The authoritative account of a run -- run identifiers,
node names, versions, timings, errors, retries, and status transitions, the fields
`current-architecture.md` section 5.17 asks for -- is the execution ledger
(`services/execution_ledger.py`), which persists structured `ExecutionRecord` rows the pipeline
owns. What this module governs is different and narrower: whatever *does* reach a log line, from
`trace_ai` code or from a third-party library, is emitted as JSON with its context as keys, and is
stripped of the two things a log line must never carry. The redaction filter earns its place even
with no first-party producers, because once `bootstrap()` runs for a real command the `anthropic`
and `httpx` clients log through this handler, and their records pass the same filter. `bind()` and
`bound_context()` are the first-party path for when a caller does want a structured record; they
are deliberately available rather than mandatory.

Two categories of content are excluded, for different reasons.

**Provider credentials.** `Settings` holds them as `SecretStr`, which protects `repr()` and
tracebacks. It does not protect a caller who logs `key.get_secret_value()`, and it does nothing
for a raw key string that never went through `Settings` at all. `RedactionFilter` covers both by
value type and by field name.

**Source-document content.** Section 12 makes source documents untrusted input, and they may carry
anything the reviewed organization put in them. The rule is stated once, here, and enforced by the
same filter: **source-derived text is referenced by `SourceDocument.id` or `EvidenceReference.id`,
never quoted into a log record.** An identifier and a length are enough to debug with, and they
are all that is safe to keep -- `data-model.md` section 36 governs retention of the content
itself, and a log file is not covered by it.

The filter is installed on the handler rather than on a logger. A logger-level filter sees only
records logged directly to that logger, so anything from `trace_ai.services.ingestion` would
bypass a filter attached to `trace_ai`. Every record reaching the handler passes through this one.

**What this cannot do.** A secret interpolated into the message string before `logging` sees it is
already a plain string with no field name and no type, and nothing here can distinguish it from
prose. Pass values as structured context, never as pre-formatted message text.

**Why this is not called `logging.py`.** It was, briefly, and the import broke on the first run.
Absolute imports mean a module named `trace_ai/logging.py` can import the stdlib `logging` from
inside itself perfectly well -- so the name looks safe, and the reasoning that it is namespaced
and therefore harmless is wrong for a reason that only shows up one level up. Importing a
submodule binds it as an attribute of its package, so `from trace_ai.logging import install` in
`trace_ai/__init__.py` sets `trace_ai.logging` to this module, shadowing that file's own
`import logging` and turning its next `logging.getLogger` call into an `AttributeError`. It is the
same failure the package name records -- `trace` shadowing the stdlib `trace` -- displaced one
level down, where the reassuring argument about namespacing happens to be exactly backwards.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from pydantic import SecretStr

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "RedactionFilter",
    "StructuredFormatter",
    "bind",
    "bound_context",
    "install",
]

# Not a credential; ruff's S105 flags the assignment by name, and the name is the clear one.
SECRET_PLACEHOLDER: Final = "[redacted secret]"  # noqa: S105

# Field names whose value is a credential regardless of its type. Matched exactly or as a
# suffix, so `anthropic_api_key` and `langsmith_api_key` are covered by `api_key`.
SECRET_FIELD_SUFFIXES: Final = (
    "api_key",
    "secret",
    "token",
    "password",
    "credential",
    "authorization",
)

# Field names carrying text taken from a source document. These are the field names the data
# model uses for verbatim content: `quoted_text` on EvidenceReference (DEC-015 makes it the
# verbatim excerpt), and the normalized and raw text a loader holds.
SOURCE_FIELD_SUFFIXES: Final = (
    "quoted_text",
    "source_text",
    "normalized_text",
    "raw_text",
    "document_text",
    "content",
    "excerpt",
    "passage",
)

# Context keys that identify source-derived content, used to point a redacted field at the
# object it came from. In priority order.
REFERENCE_KEYS: Final = ("evidence_id", "source_document_id", "assessment_id")

# `logging.LogRecord`'s own attributes. Anything else on a record came from `extra=` and is
# treated as bound context.
_RESERVED: Final = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}

# Defaults to None rather than to an empty dict: a mutable default on a ContextVar is shared
# across every context that never sets it, so one caller mutating it would alter the others.
_context: ContextVar[dict[str, object] | None] = ContextVar("trace_ai_log_context", default=None)


def bound_context() -> dict[str, object]:
    """The context currently bound, as a copy."""
    return dict(_context.get() or {})


@contextmanager
def bind(**fields: object) -> Iterator[None]:
    """Attach fields to every record emitted inside the block.

    Scoped rather than global: the token is reset on exit, so a record emitted afterwards does
    not carry the assessment that was being processed before it. Nesting merges, with the inner
    binding winning on a repeated key.

        with bind(assessment_id="asm-001", workflow_run_id="run-001"):
            logger.info("node completed", extra={"node": "context_validation"})
    """
    token = _context.set(bound_context() | fields)
    try:
        yield
    finally:
        _context.reset(token)


def _is_secret_field(name: str) -> bool:
    lowered = name.casefold()
    return any(lowered == suffix or lowered.endswith(suffix) for suffix in SECRET_FIELD_SUFFIXES)


def _is_source_field(name: str) -> bool:
    lowered = name.casefold()
    return any(lowered == suffix or lowered.endswith(suffix) for suffix in SOURCE_FIELD_SUFFIXES)


def _describe_source_value(value: object, reference: str | None) -> str:
    """What replaces source-derived text: a length, and where to find the real thing."""
    length = len(value) if isinstance(value, str | bytes) else len(str(value))
    where = f"; see {reference}" if reference else ""
    return f"[redacted source content: {length} chars{where}]"


def _redact_value(value: object) -> object:
    """Replace a `SecretStr` anywhere it appears, including inside a container."""
    if isinstance(value, SecretStr):
        return SECRET_PLACEHOLDER
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(_redact_value(item) for item in value)
    return value


class RedactionFilter(logging.Filter):
    """Strips credentials and source-document content from a record before it is formatted.

    Returns `True` always: the record is emitted, with the offending values replaced. Dropping
    the record instead would lose the event, and the event is usually the thing worth keeping.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        context = bound_context() | {
            key: value for key, value in record.__dict__.items() if key not in _RESERVED
        }
        reference = next((str(context[key]) for key in REFERENCE_KEYS if key in context), None)

        cleaned: dict[str, object] = {}
        for key, value in context.items():
            if _is_secret_field(key):
                cleaned[key] = SECRET_PLACEHOLDER
            elif _is_source_field(key):
                cleaned[key] = _describe_source_value(value, reference)
            else:
                cleaned[key] = _redact_value(value)

        if record.args:
            record.args = (
                _redact_value(record.args)
                if isinstance(record.args, dict)
                else tuple(_redact_value(arg) for arg in record.args)  # type: ignore[assignment]
            )

        record.trace_context = cleaned
        return True


class StructuredFormatter(logging.Formatter):
    """Emits one JSON object per record: the fields section 5.17 asks for, as keys."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        context = getattr(record, "trace_context", None)
        if isinstance(context, dict):
            # Context cannot displace the four fields above: a bound `level` would otherwise
            # make one record's severity mean something different from every other record's.
            payload.update({k: v for k, v in context.items() if k not in payload})

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def install(level: int | str) -> logging.Handler:
    """Replace the root handlers with one that formats structurally and redacts.

    `force=True` semantics are preserved by clearing existing handlers: a library that installed
    one on import would otherwise keep emitting unfiltered records alongside these.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(RedactionFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
    return handler
