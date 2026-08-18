"""The checkpoint timing instrument (DEC-117, issue #567).

Three properties carry the file. A session is recorded through the store with an allocated
`rvs` identifier, so the instrument obeys DEC-018 like every other object. The derivation
pairs the earliest session with the conclusion and refuses to measure without one — absent,
never zero, because a harness-decided checkpoint writes no session (the DEC-092 dash
discipline). And the metrics pass emits `finding_review_seconds` only when both halves exist,
so a replayed run's metric set is unchanged by this instrument's existence.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.enums import ReviewDisposition
from trace_ai.domain.review_session import ReviewCheckpoint, ReviewSession
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evaluation.metrics import compute_metrics
from trace_ai.services.execution_ledger import start_run
from trace_ai.services.review_timing import record_review_session, review_seconds


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[dict[str, Any]]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Timing", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield {"handle": handle, "run": run}


def a_finding_decision(handle: AssessmentHandle, decision_id: str, created_at: Any) -> None:
    decision = ReviewerDecision.model_validate(
        {
            "id": decision_id,
            "assessment_id": handle.assessment_id,
            "subject_type": "finding",
            "subject_id": "fnd-001",
            "disposition": ReviewDisposition.APPROVE,
            "reviewer_id": "eturner",
            "created_at": created_at,
        }
    )
    with handle.objects.transaction():
        handle.objects.save(decision)


def test_a_session_is_recorded_with_an_allocated_identifier(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    session = record_review_session(
        handle,
        ReviewCheckpoint.CONTEXT_APPROVAL,
        reviewer_id="eturner",
        workflow_run_id=prepared["run"].id,
    )

    assert session.id == "rvs-001"
    stored = handle.objects.list(ReviewSession)
    assert [row.id for row in stored] == ["rvs-001"]
    assert stored[0].checkpoint is ReviewCheckpoint.CONTEXT_APPROVAL


def test_no_session_measures_nothing(prepared: dict[str, Any]) -> None:
    """A harness-decided checkpoint has no session; its timing is absent, never zero."""
    assert review_seconds(prepared["handle"], ReviewCheckpoint.FINDING_APPROVAL, now()) is None


def test_the_earliest_session_starts_the_clock(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    first = record_review_session(
        handle, ReviewCheckpoint.FINDING_APPROVAL, reviewer_id=None, workflow_run_id=None
    )
    record_review_session(
        handle, ReviewCheckpoint.FINDING_APPROVAL, reviewer_id=None, workflow_run_id=None
    )
    concluded = first.created_at + timedelta(seconds=90)

    assert review_seconds(handle, ReviewCheckpoint.FINDING_APPROVAL, concluded) == 90.0


def test_a_session_after_the_conclusion_is_not_this_cycle(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    session = record_review_session(
        handle, ReviewCheckpoint.FINDING_APPROVAL, reviewer_id=None, workflow_run_id=None
    )
    earlier = session.created_at - timedelta(seconds=10)

    assert review_seconds(handle, ReviewCheckpoint.FINDING_APPROVAL, earlier) is None


def test_sessions_at_the_other_checkpoint_do_not_count(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    record_review_session(
        handle, ReviewCheckpoint.CONTEXT_APPROVAL, reviewer_id=None, workflow_run_id=None
    )

    assert review_seconds(handle, ReviewCheckpoint.FINDING_APPROVAL, now()) is None


def test_the_finding_timing_metric_is_emitted_with_a_session(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    session = record_review_session(
        handle, ReviewCheckpoint.FINDING_APPROVAL, reviewer_id="eturner", workflow_run_id=None
    )
    a_finding_decision(handle, "dec-001", session.created_at + timedelta(seconds=120))

    named = {result.metric_name: result for result in compute_metrics(handle, prepared["run"])}
    assert named["finding_review_seconds"].metric_value == 120.0
    assert named["finding_review_seconds"].unit == "seconds"


def test_the_timing_metrics_are_absent_without_a_session(prepared: dict[str, Any]) -> None:
    """A replayed or protocol-driven run gains no timing rows from this instrument."""
    handle = prepared["handle"]
    a_finding_decision(handle, "dec-001", now())

    names = {result.metric_name for result in compute_metrics(handle, prepared["run"])}
    assert "finding_review_seconds" not in names
    assert "context_review_seconds" not in names
