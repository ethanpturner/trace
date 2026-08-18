"""The tracing emitter: execution spans out, content never (#538, DEC-109).

`current-architecture.md` section 5.17 fixes the shape: the local audit records — the
`ExecutionRecord` rows the ledger persists — remain the authoritative execution history, and
sensitive prompt content and source data are not sent to an external tracing provider. This
module is that boundary implemented. A span is built from an `ExecutionRecord`'s own fields —
identifiers, node name and version, prompt *version*, model name, statuses, timings, token
counts, cost — and nothing else. There is no field a prompt, an excerpt, or a document could
travel in; `error_message` is included because section 27 requires it to be safe (an
exception's type and reason, never content), and the test suite holds the span's key set
closed.

**Emission never breaks a run.** The emitter makes one attempt per span batch and a failure is
logged (identifiers and counts only) and swallowed: tracing is observability, and a run that
failed because its observability endpoint was down would invert the priority. The flag that
gates all of this is `AssessmentConfiguration.enable_external_tracing`, default off, and the
destination comes from `Settings` — a run with the flag on and no endpoint configured emits
nothing and says so in the log.

Two destinations exist: `file://<path>` appends spans as JSON lines (the offline exporter the
tests and a local operator use), and `http(s)://` posts the batch as one JSON document with
one attempt and no retry. The scheme is the whole configuration surface.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlparse

from trace_ai.domain.execution import ExecutionRecord

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.config import Settings
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "FileEmitter",
    "HttpEmitter",
    "TracingEmitter",
    "emit_run",
    "emitter_from_settings",
    "span_of",
]

_LOGGER = logging.getLogger(__name__)


def span_of(record: ExecutionRecord) -> dict[str, object]:
    """One record as one span: section 5.17's fields, and no field content could travel in."""
    return {
        "assessment_id": record.assessment_id,
        "workflow_run_id": record.workflow_run_id,
        "execution_record_id": record.id,
        "node_name": record.node_name,
        "node_version": record.node_version,
        "execution_type": record.execution_type.value,
        "prompt_version": record.prompt_version,
        "model_name": record.model_name,
        "input_object_ids": list(record.input_object_ids),
        "output_object_ids": list(record.output_object_ids),
        "started_at": record.started_at.isoformat(),
        "completed_at": (
            record.completed_at.isoformat() if record.completed_at is not None else None
        ),
        "status": record.status.value,
        "retry_number": record.retry_number,
        "error_type": record.error_type,
        "error_message": record.error_message,
        "duration_ms": record.duration_ms,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "cache_read_tokens": record.cache_read_tokens,
        "cache_creation_tokens": record.cache_creation_tokens,
        "estimated_cost": (
            str(record.estimated_cost) if record.estimated_cost is not None else None
        ),
    }


class TracingEmitter(Protocol):
    """Where a batch of spans goes. One attempt; a failure is the caller's to log, not raise."""

    def emit(self, spans: list[dict[str, object]]) -> None: ...


class FileEmitter:
    """Spans appended as JSON lines — the offline exporter."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def emit(self, spans: list[dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as sink:
            for span in spans:
                sink.write(json.dumps(span, sort_keys=True) + "\n")


class HttpEmitter:
    """The batch as one JSON POST, one attempt, no retry.

    The API key travels in a header and never in the URL or the payload; the opener is
    injectable so the offline tests assert the request shape without a socket.
    """

    def __init__(self, endpoint: str, *, api_key: str | None = None, opener: object = None) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._opener = opener if opener is not None else urllib.request.urlopen

    def emit(self, spans: list[dict[str, object]]) -> None:
        payload = json.dumps({"spans": spans}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(  # noqa: S310 - scheme is validated by the factory
            self._endpoint, data=payload, headers=headers, method="POST"
        )
        opener = self._opener
        opener(request, timeout=10)  # type: ignore[operator]


def emitter_from_settings(settings: Settings) -> TracingEmitter | None:
    """The configured destination, or `None` when tracing has nowhere to go."""
    endpoint = settings.tracing_endpoint
    if not endpoint:
        return None
    parsed = urlparse(endpoint)
    if parsed.scheme == "file":
        from pathlib import Path

        return FileEmitter(Path(parsed.path))
    if parsed.scheme in ("http", "https"):
        key = settings.tracing_api_key
        return HttpEmitter(endpoint, api_key=key.get_secret_value() if key else None)
    _LOGGER.warning(
        "tracing endpoint scheme is not supported; nothing will be emitted",
        extra={"scheme": parsed.scheme},
    )
    return None


def emit_run(handle: AssessmentHandle, workflow_run_id: str, emitter: TracingEmitter) -> int:
    """Export one run's execution records as spans. Returns how many were sent.

    One attempt for the whole batch; an emission failure is logged with identifiers and counts
    and swallowed — the local ledger stays authoritative, and a run must never fail because its
    observability endpoint did.
    """
    spans = [
        span_of(record)
        for record in sorted(
            (
                record
                for record in handle.objects.list(ExecutionRecord)
                if record.workflow_run_id == workflow_run_id
            ),
            key=lambda record: (record.started_at, record.id),
        )
    ]
    if not spans:
        return 0
    try:
        emitter.emit(spans)
    except Exception:
        _LOGGER.warning(
            "tracing emission failed; the local ledger remains authoritative",
            extra={"workflow_run_id": workflow_run_id, "spans": len(spans)},
            exc_info=True,
        )
        return 0
    return len(spans)
