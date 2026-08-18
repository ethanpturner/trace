"""`trace runs prune` (DEC-017 amendment, #602): abandoned paused runs, found and removed.

The acceptance criterion from the issue is the spine: zero abandoned runs after prune over a
seeded store. The seeding is honest lifecycle machinery — `start_run`, the ledger's `pause` and
`complete`, `save_state` — not hand-set statuses, so the pruner is tested against rows the
pipeline itself would write.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.execution import (
    ExecutionRecord,
    ExecutionStatus,
    ExecutionType,
    RunStatus,
    WorkflowRun,
)
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.run_pruning import abandoned_runs, prune_runs
from trace_ai.workflow.checkpoint import STATE_AREA, save_state
from trace_ai.workflow.state import AssessmentState


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[tuple[AssessmentService, AssessmentHandle]]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Pruning", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service, service.handle(created.id)


def paused_run(handle: AssessmentHandle, *, records: int = 1) -> WorkflowRun:
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ledger = ExecutionLedger(handle, run)
    stamped = now()
    with handle.objects.transaction():
        for _ in range(records):
            handle.objects.save(
                ExecutionRecord.model_validate(
                    {
                        "id": handle.objects.allocate("exe"),
                        "workflow_run_id": run.id,
                        "assessment_id": handle.assessment_id,
                        "node_name": "context-extraction",
                        "node_version": "0.1",
                        "execution_type": ExecutionType.MODEL,
                        "started_at": stamped,
                        "completed_at": stamped,
                        "status": ExecutionStatus.COMPLETED,
                        "retry_number": 0,
                        "estimated_cost": Decimal("0.25"),
                    }
                )
            )
    paused = ledger.pause(current_node="human_context_review")
    save_state(
        handle,
        AssessmentState.begin(assessment_id=handle.assessment_id, workflow_run_id=run.id),
    )
    return paused


def completed_run(handle: AssessmentHandle) -> WorkflowRun:
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    return ExecutionLedger(handle, run).complete()


def test_a_superseded_paused_run_is_abandoned_and_pruned_whole(
    prepared: tuple[AssessmentService, AssessmentHandle],
) -> None:
    service, handle = prepared
    old = paused_run(handle, records=2)
    completed_run(handle)

    found = abandoned_runs(service)
    assert [(run.run_id, run.reason) for run in found] == [(old.id, "superseded")]
    assert found[0].execution_record_count == 2
    assert found[0].has_state_file

    result = prune_runs(service, found)
    assert result.runs_removed == 1
    assert result.execution_records_removed == 2
    assert result.state_files_removed == 1
    assert result.estimated_cost_removed == Decimal("0.50"), (
        "the two records' rolled-up spend is reported with the deletion, never silently dropped"
    )

    assert abandoned_runs(service) == []
    remaining = handle.objects.list(WorkflowRun)
    assert [run.status for run in remaining] == [RunStatus.COMPLETED]
    assert handle.objects.list(ExecutionRecord) == []
    assert not (handle.artifacts.area(STATE_AREA) / f"state-{old.id}.json").exists()


def test_the_latest_paused_run_is_not_abandoned_without_a_stated_age(
    prepared: tuple[AssessmentService, AssessmentHandle],
) -> None:
    service, handle = prepared
    paused_run(handle)

    assert abandoned_runs(service) == []


def test_a_stated_age_of_zero_days_abandons_the_latest_paused_run(
    prepared: tuple[AssessmentService, AssessmentHandle],
) -> None:
    service, handle = prepared
    run = paused_run(handle)

    found = abandoned_runs(service, older_than_days=0)
    assert [(entry.run_id, entry.reason) for entry in found] == [(run.id, "stale")]


def test_completed_runs_are_never_abandoned(
    prepared: tuple[AssessmentService, AssessmentHandle],
) -> None:
    service, handle = prepared
    completed_run(handle)
    completed_run(handle)

    assert abandoned_runs(service, older_than_days=0) == []


def test_the_assessment_and_its_objects_survive_a_prune(
    prepared: tuple[AssessmentService, AssessmentHandle],
) -> None:
    service, handle = prepared
    paused_run(handle)
    completed_run(handle)

    prune_runs(service, abandoned_runs(service))
    assert service.get(handle.assessment_id) is not None


def test_a_targeted_delete_leaves_the_identifier_counter_alone(
    prepared: tuple[AssessmentService, AssessmentHandle],
) -> None:
    """A pruned run-001 must never let a later run become a second run-001 (DEC-018)."""
    service, handle = prepared
    old = paused_run(handle)
    completed_run(handle)
    prune_runs(service, abandoned_runs(service))

    fresh = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    assert fresh.id != old.id
