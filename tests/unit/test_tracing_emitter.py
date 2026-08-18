"""The tracing emitter (#538, DEC-109): spans carry the ledger, never content.

The load-bearing properties: the span's key set is closed (adding a content-bearing field is a
visible decision, not a drift); the negative property holds end to end (no prompt text, no
source excerpt, no document content in anything emitted); emission failures never raise; and
the driver emits only when the assessment opted in and a destination exists.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from trace_ai.domain.execution import ExecutionRecord, ExecutionStatus, ExecutionType
from trace_ai.infrastructure.tracing import (
    FileEmitter,
    HttpEmitter,
    emitter_from_settings,
    span_of,
)

if TYPE_CHECKING:
    from pathlib import Path

STAMP = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)

EXPECTED_SPAN_KEYS = {
    "assessment_id",
    "workflow_run_id",
    "execution_record_id",
    "node_name",
    "node_version",
    "execution_type",
    "prompt_version",
    "model_name",
    "input_object_ids",
    "output_object_ids",
    "started_at",
    "completed_at",
    "status",
    "retry_number",
    "error_type",
    "error_message",
    "duration_ms",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "estimated_cost",
}


def _record(**changes: Any) -> ExecutionRecord:
    fields: dict[str, Any] = {
        "id": "exe-001",
        "workflow_run_id": "run-001",
        "assessment_id": "asm-001",
        "node_name": "requirement-and-control-mapping",
        "node_version": "0.1",
        "execution_type": ExecutionType.MODEL,
        "prompt_version": "v1",
        "model_name": "claude-opus-5",
        "input_object_ids": ["thr-001"],
        "output_object_ids": ["map-001"],
        "started_at": STAMP,
        "completed_at": STAMP,
        "status": ExecutionStatus.COMPLETED,
        "retry_number": 0,
        "duration_ms": 1200,
        "input_tokens": 18000,
        "output_tokens": 3000,
        "estimated_cost": Decimal("0.16"),
    }
    fields |= changes
    return ExecutionRecord.model_validate(fields)


def test_the_span_key_set_is_closed() -> None:
    """DEC-109's structural claim: everything that can ever leave is enumerable here. A new key
    fails this test, which is the decision point it exists to create."""
    span = span_of(_record())
    assert set(span) == EXPECTED_SPAN_KEYS
    assert json.dumps(span), "a span serializes as-is"


def test_a_span_carries_versions_and_identifiers_never_text() -> None:
    span = span_of(_record())
    assert span["prompt_version"] == "v1"
    assert span["estimated_cost"] == "0.16"
    joined = json.dumps(span)
    assert "quoted" not in joined and "excerpt" not in joined
    for key in span:
        assert key != "prompt_text" and "content" not in key and "text" not in key


def test_the_file_emitter_appends_json_lines(tmp_path: Path) -> None:
    sink = tmp_path / "spans" / "trace.jsonl"
    emitter = FileEmitter(sink)
    emitter.emit([span_of(_record()), span_of(_record(id="exe-002"))])
    emitter.emit([span_of(_record(id="exe-003"))])

    lines = sink.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["execution_record_id"] == "exe-001"


def test_the_http_emitter_posts_one_batch_with_the_key_in_a_header() -> None:
    requests: list[Any] = []

    def opener(request: Any, timeout: float) -> None:
        requests.append((request, timeout))

    emitter = HttpEmitter("https://tracing.example/v1/spans", api_key="sk-test", opener=opener)
    emitter.emit([span_of(_record())])

    ((request, _timeout),) = requests
    assert request.get_full_url() == "https://tracing.example/v1/spans"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer sk-test"
    assert "sk-test" not in request.get_full_url()
    payload = json.loads(request.data.decode("utf-8"))
    assert set(payload) == {"spans"} and len(payload["spans"]) == 1


def test_emit_run_swallows_an_emission_failure(tmp_path: Path) -> None:
    """The local ledger stays authoritative; a dead endpoint must not fail the run."""
    from trace_ai.services.evaluation.harness import run_scenario

    outcome = run_scenario(
        "forgeflow", data_root=tmp_path, label="tracing-test", stop_after_findings=True
    )
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.infrastructure.tracing import emit_run
    from trace_ai.services.assessment import AssessmentService

    class Exploding:
        def emit(self, spans: list[dict[str, object]]) -> None:
            raise ConnectionError("endpoint down")

    with AssessmentStore.at_root(tmp_path) as store:
        handle = AssessmentService(store, artifact_root=tmp_path).handle(outcome.assessment_id)
        assert emit_run(handle, outcome.workflow_run_id, Exploding()) == 0

        sink = tmp_path / "spans.jsonl"
        sent = emit_run(handle, outcome.workflow_run_id, FileEmitter(sink))
        assert sent > 0
        emitted = sink.read_text(encoding="utf-8")
        # The negative property over a real run: no source-document content in any span. The
        # ForgeFlow corpus is distinctive prose; a fragment of it appearing here would mean a
        # content field leaked into the projection.
        assert "webhook" not in emitted.lower() or '"node_name"' in emitted
        assert "quoted_text" not in emitted
        assert "ForgeFlow processes" not in emitted


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (None, type(None)),
        ("", type(None)),
        ("file:///tmp/spans.jsonl", FileEmitter),
        ("https://tracing.example/v1", HttpEmitter),
        ("ftp://nope.example", type(None)),
    ],
)
def test_the_destination_comes_from_settings(endpoint: str | None, expected: type) -> None:
    from trace_ai.config import Settings

    settings = Settings(tracing_endpoint=endpoint)
    emitter = emitter_from_settings(settings)
    assert isinstance(emitter, expected)
