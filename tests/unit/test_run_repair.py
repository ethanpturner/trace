"""`trace runs repair` (DEC-137, #613): an orphaned running run, repaired on assertion.

The seeding is honest lifecycle machinery — `start_run` leaves a run `running`, the ledger's
verbs produce every other status — so the repair is tested against rows the pipeline itself
would write, never a hand-set status.
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
from trace_ai.services.run_repair import (
    DEFAULT_REASON,
    RunRepairError,
    describe_run,
    repair_run,
    strand_description,
)
from trace_ai.workflow.checkpoint import save_state
from trace_ai.workflow.phases import Phase, successor
from trace_ai.workflow.state import AssessmentState


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Repair", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


def running_run(handle: AssessmentHandle, *, records: int = 0) -> WorkflowRun:
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    stamped = now()
    with handle.objects.transaction():
        for _ in range(records):
            handle.objects.save(
                ExecutionRecord.model_validate(
                    {
                        "id": handle.objects.allocate("exe"),
                        "workflow_run_id": run.id,
                        "assessment_id": handle.assessment_id,
                        "node_name": "evidence-validation",
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
    return run


def test_repair_marks_the_running_run_failed_with_the_asserting_summary(
    handle: AssessmentHandle,
) -> None:
    orphan = running_run(handle, records=2)

    repaired = repair_run(handle, orphan.id)

    assert repaired.status is RunStatus.FAILED
    assert repaired.completed_at is not None
    assert repaired.error_summary is not None
    assert "`trace runs repair`" in repaired.error_summary
    assert DEFAULT_REASON in repaired.error_summary
    # The close is the ledger's own: spend rolls up from the records the orphan actually wrote.
    assert repaired.estimated_cost == Decimal("0.50")
    persisted = handle.objects.get(WorkflowRun, orphan.id)
    assert persisted.status is RunStatus.FAILED


def test_repair_carries_the_operator_reason_into_the_summary(handle: AssessmentHandle) -> None:
    orphan = running_run(handle)

    repaired = repair_run(handle, orphan.id, reason="laptop slept during the capture")

    assert repaired.error_summary is not None
    assert "laptop slept during the capture" in repaired.error_summary


def test_repair_refuses_every_status_but_running(handle: AssessmentHandle) -> None:
    """Each refusal names the verb that already covers the status (DEC-137)."""
    paused = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ExecutionLedger(handle, paused).pause(current_node="human_context_review")
    completed = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ExecutionLedger(handle, completed).complete()
    failed = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ExecutionLedger(handle, failed).complete(error_summary="a provider failure")

    with pytest.raises(RunRepairError, match="paused"):
        repair_run(handle, paused.id)
    with pytest.raises(RunRepairError, match="nothing to repair"):
        repair_run(handle, completed.id)
    with pytest.raises(RunRepairError, match="already failed"):
        repair_run(handle, failed.id)
    # Nothing moved: the refusals changed no row.
    assert handle.objects.get(WorkflowRun, paused.id).status is RunStatus.PAUSED
    assert handle.objects.get(WorkflowRun, completed.id).status is RunStatus.COMPLETED


def test_describe_run_reports_record_backed_cost_whatever_the_status(
    handle: AssessmentHandle,
) -> None:
    """The dry run's cost comes from the records, not the orphan's stale rollup row."""
    orphan = running_run(handle, records=3)

    candidate = describe_run(handle, orphan.id)

    assert candidate.run_id == orphan.id
    assert candidate.status == "running"
    assert candidate.execution_record_count == 3
    assert candidate.estimated_cost == Decimal("0.75")
    assert orphan.estimated_cost is None, (
        "the row's rollup is stale by construction — the honest figure is the records'"
    )


def _walked_to(handle: AssessmentHandle, run_id: str, destination: Phase) -> AssessmentState:
    """A state advanced to `destination` along the declared transition table, never hand-set."""
    state = AssessmentState.begin(assessment_id=handle.assessment_id, workflow_run_id=run_id)
    while state.current_phase is not destination:
        following = successor(state.current_phase)
        assert following is not None, f"{destination.value} is not reachable from the first phase"
        state = state.advance(following)
    return state


def stranded_run(handle: AssessmentHandle) -> WorkflowRun:
    """A run killed in the window a pause is not atomic across (DEC-144, #641).

    `_persist_pause` commits the run row and *then* writes the state file — deliberately, so a
    rolled-back `on_pause` cannot leave a paused state file for an unpaused row. A process killed
    between the two writes leaves the row paused and the state file still recording the phase it
    was running. Both halves here are written by the machinery that writes them in production.
    """
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    save_state(handle, _walked_to(handle, run.id, Phase.HUMAN_CONTEXT_REVIEW))
    ExecutionLedger(handle, run).pause(current_node=Phase.HUMAN_CONTEXT_REVIEW.value)
    return handle.objects.get(WorkflowRun, run.id)


def paused_run_with_its_state_file(handle: AssessmentHandle) -> WorkflowRun:
    """A clean pause: row and state file agree, and `trace resume` reaches it."""
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    walked = _walked_to(handle, run.id, Phase.HUMAN_CONTEXT_REVIEW)
    save_state(handle, walked.paused_for(Phase.HUMAN_CONTEXT_REVIEW, ["ctx-001"]))
    ExecutionLedger(handle, run).pause(current_node=Phase.HUMAN_CONTEXT_REVIEW.value)
    return handle.objects.get(WorkflowRun, run.id)


def test_a_strand_is_named_by_the_disagreement_it_is(handle: AssessmentHandle) -> None:
    stranded = stranded_run(handle)

    described = strand_description(handle, stranded)

    assert described is not None
    assert "paused" in described
    assert Phase.HUMAN_CONTEXT_REVIEW.value in described
    assert RunStatus.RUNNING.value in described


def test_a_clean_pause_is_not_a_strand(handle: AssessmentHandle) -> None:
    """The halves agree, so `trace resume` reaches it and repair must not touch it."""
    assert strand_description(handle, paused_run_with_its_state_file(handle)) is None


def test_a_paused_row_with_no_state_file_is_not_a_strand(handle: AssessmentHandle) -> None:
    """Repair leaves a run `resume` can restart, and `resume` reads the same missing file.

    Failing this row would relabel it, not recover it; an abandoned pause is prune's (DEC-127).
    """
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ExecutionLedger(handle, run).pause(current_node="human_context_review")

    assert strand_description(handle, handle.objects.get(WorkflowRun, run.id)) is None


def test_repair_reaches_a_strand_and_names_the_condition_in_the_summary(
    handle: AssessmentHandle,
) -> None:
    stranded = stranded_run(handle)

    repaired = repair_run(handle, stranded.id, reason="the laptop slept mid-resume")

    assert repaired.status is RunStatus.FAILED
    assert repaired.completed_at is not None
    assert repaired.error_summary is not None
    assert "the laptop slept mid-resume" in repaired.error_summary
    # The row's history says which disagreement was repaired, not merely that one was.
    assert Phase.HUMAN_CONTEXT_REVIEW.value in repaired.error_summary
    assert handle.objects.get(WorkflowRun, stranded.id).status is RunStatus.FAILED


def test_repair_still_refuses_a_resumable_pause(handle: AssessmentHandle) -> None:
    """The run a reviewer is holding is not repair's, however a killed one nearby looks."""
    resumable = paused_run_with_its_state_file(handle)

    with pytest.raises(RunRepairError, match="resume it with `trace resume`"):
        repair_run(handle, resumable.id)

    assert handle.objects.get(WorkflowRun, resumable.id).status is RunStatus.PAUSED


def test_describe_run_carries_the_strand_into_the_dry_run(handle: AssessmentHandle) -> None:
    """The operator confirms the disagreement before asserting the process is gone."""
    stranded = stranded_run(handle)

    candidate = describe_run(handle, stranded.id)

    assert candidate.status == RunStatus.PAUSED.value
    assert candidate.strand is not None
    assert describe_run(handle, paused_run_with_its_state_file(handle).id).strand is None
