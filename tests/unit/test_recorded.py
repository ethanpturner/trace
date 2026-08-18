"""The recorded-response envelope (#461).

A recording is `{"schema": <ProposalName>, "usage": {...}, "response": {...}}`: the response
validates against the named schema (field-level errors on a mismatch), and the usage, when present,
is what `DeterministicModel` replays so an offline ledger carries real cost rather than zeros. A bare
proposal is still read as a legacy file, inferred structurally and replayed with no usage.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from trace_ai.domain.proposals.report_sections import ReportSections
from trace_ai.infrastructure.model.fake import DeterministicModel
from trace_ai.infrastructure.model.recorded import (
    RecordedResponse,
    parse_recorded_response,
)
from trace_ai.infrastructure.model.seam import GenerationSettings, ModelSuccess, ModelUsage


def _report_response() -> dict[str, object]:
    return ReportSections(
        executive_summary="A summary.",
        system_overview="An overview.",
        risk_summary="The risks.",
        limitations=[],
    ).model_dump(mode="json")


def _envelope(**overrides: object) -> str:
    envelope: dict[str, object] = {
        "schema": "ReportSections",
        "response": _report_response(),
    }
    envelope.update(overrides)
    return json.dumps(envelope)


def test_an_envelope_validates_against_its_named_schema() -> None:
    recorded = parse_recorded_response(_envelope(), described_as="test")
    assert isinstance(recorded, RecordedResponse)
    assert isinstance(recorded.response, ReportSections)
    assert recorded.usage is None


def test_an_envelope_replays_its_recorded_usage() -> None:
    usage = {
        "model": "claude-opus-5",
        "input_tokens": 1200,
        "output_tokens": 340,
        "estimated_cost": "0.0512",
        "duration_seconds": 4.2,
    }
    recorded = parse_recorded_response(_envelope(usage=usage), described_as="test")
    assert recorded.usage is not None
    assert recorded.usage.input_tokens == 1200
    assert recorded.usage.estimated_cost == Decimal("0.0512")


def test_the_deterministic_model_replays_recorded_usage_into_the_ledger() -> None:
    """The point of the envelope: an offline call carries the recorded cost, not zeros (#461)."""
    recorded = parse_recorded_response(
        _envelope(usage={"model": "m", "output_tokens": 500, "estimated_cost": "0.10"}),
        described_as="test",
    )
    model = DeterministicModel([recorded])

    outcome = model.generate(prompt="p", schema=ReportSections, settings=GenerationSettings())

    assert isinstance(outcome, ModelSuccess)
    assert outcome.usage.output_tokens == 500
    assert outcome.usage.estimated_cost == Decimal("0.10")


def test_a_bare_proposal_replays_with_no_usage() -> None:
    """A legacy recording carries no envelope, so the fake reports zeros as it always did."""
    recorded = parse_recorded_response(json.dumps(_report_response()), described_as="legacy")
    assert recorded.usage is None

    model = DeterministicModel([recorded])
    outcome = model.generate(prompt="p", schema=ReportSections, settings=GenerationSettings())
    assert isinstance(outcome, ModelSuccess)
    assert outcome.usage.estimated_cost == ModelUsage(model="deterministic-fake").estimated_cost


def test_a_response_that_does_not_fit_its_named_schema_reports_the_field() -> None:
    """The envelope's whole point: name the schema so a mismatch is a field error, not a blanket
    'matched no schema' (#461)."""
    broken = json.dumps({"schema": "ReportSections", "response": {"executive_summary": 12345}})
    with pytest.raises(ValueError, match="does not validate as ReportSections"):
        parse_recorded_response(broken, described_as="broken")


def test_an_unknown_named_schema_is_refused() -> None:
    payload = json.dumps({"schema": "NotAProposal", "response": {}})
    with pytest.raises(ValueError, match="not a recorded-response schema"):
        parse_recorded_response(payload, described_as="unknown")


def test_every_committed_agent_recording_is_a_valid_envelope() -> None:
    """The migration wrapped the corpus (#461); this keeps it wrapped. A bare recording added later
    fails here, and each committed recording is parsed against its named schema as a side effect."""
    from trace_ai.config import PROJECT_ROOT

    roots = (PROJECT_ROOT / "demo" / "forgeflow", PROJECT_ROOT / "benchmarks")
    files = [
        path
        for root in roots
        for path in root.rglob("[0-9]*.json")
        if "recorded" in path.parts and "baselines" not in path.parts
    ]
    assert files, "no agent recordings were found to check"
    for path in files:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        assert isinstance(data, dict) and "schema" in data and "response" in data, (
            f"{path} is not an envelope; run scripts/migrate_recordings.py"
        )
        parse_recorded_response(text, described_as=str(path))
