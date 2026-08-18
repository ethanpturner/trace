"""Abandoned-run discovery and pruning (`trace runs prune`, DEC-017 amendment).

DEC-017 admitted the gap on the day pausing was decided: a paused run waiting indefinitely means
abandoned runs accumulate with no expiry, and nothing cleans them up. This module is the cleanup,
and it is deliberately narrow. A run is *abandoned* only when it is `paused` and either a later
run exists on the same assessment — resuming it would re-answer checkpoints a newer run has
already carried — or it paused longer ago than an age the caller states. Completed runs are the
assessment's record and failed runs carry their error record; neither is ever pruned, and the age
criterion applies nothing unless a person supplies it.

Pruning removes exactly what an abandoned run owns and nothing the assessment owns: the
`WorkflowRun` row, its `ExecutionRecord` rows, and its persisted state file under `traces/`.
Domain objects, reviewer decisions, and evaluation results stay — they belong to the assessment,
not to the run that produced them (DEC-031 lets an assessment outlive any run). The pruned runs'
recorded spend is returned so the caller can print it: deleting cost history is permitted here,
but never silently (the DEC-092 discipline).

Deletion goes through the scoped repository and the artifact store's area, never raw SQL or a
path a caller built. The identifier counters are untouched, so a pruned `run-002` is never
re-minted (DEC-018).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from trace_ai.domain.base import now
from trace_ai.domain.execution import ExecutionRecord, RunStatus, WorkflowRun
from trace_ai.workflow.checkpoint import STATE_AREA

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.services.assessment import AssessmentService

__all__ = ["AbandonedRun", "PruneResult", "abandoned_runs", "prune_runs"]


def _ordinal(identifier: str) -> int:
    """The numeric part of a generated identifier, for allocation-order comparison (DEC-089)."""
    return int(identifier.rpartition("-")[2])


@dataclass(frozen=True, slots=True)
class AbandonedRun:
    """One paused run nobody will resume, and why it qualifies."""

    assessment_id: str
    run_id: str
    reason: str
    """`superseded` -- a later run exists on the same assessment -- or `stale` -- paused longer
    ago than the caller's stated age."""

    started_at_display: str
    execution_record_count: int
    estimated_cost: Decimal | None
    has_state_file: bool


@dataclass(frozen=True, slots=True)
class PruneResult:
    """What pruning removed, for the caller to print."""

    runs_removed: int
    execution_records_removed: int
    state_files_removed: int
    estimated_cost_removed: Decimal


def abandoned_runs(
    service: AssessmentService,
    *,
    assessment_id: str | None = None,
    older_than_days: int | None = None,
) -> list[AbandonedRun]:
    """Every abandoned run, across the store or within one assessment.

    A paused run is abandoned when a run with a later allocation ordinal exists on the same
    assessment (whatever that run's status: even a failed successor means someone moved on), or
    when `older_than_days` is supplied and the run started longer ago. With no age stated, age
    alone abandons nothing -- an expiry nobody set is not a policy (DEC-036's discipline applied
    to time).
    """
    scope = (
        [assessment_id]
        if assessment_id is not None
        else [assessment.id for assessment in service.list()]
    )
    found: list[AbandonedRun] = []
    stamp = now()
    for scoped_id in scope:
        handle = service.handle(scoped_id)
        runs = sorted(handle.objects.list(WorkflowRun), key=lambda run: _ordinal(run.id))
        if not runs:
            continue
        latest = _ordinal(runs[-1].id)
        records = handle.objects.list(ExecutionRecord)
        for run in runs:
            if run.status is not RunStatus.PAUSED:
                continue
            reason: str | None = None
            if _ordinal(run.id) < latest:
                reason = "superseded"
            elif (
                older_than_days is not None
                and run.started_at is not None
                and (stamp - run.started_at).days >= older_than_days
            ):
                reason = "stale"
            if reason is None:
                continue
            owned = [record for record in records if record.workflow_run_id == run.id]
            state_path = handle.artifacts.area(STATE_AREA) / f"state-{run.id}.json"
            found.append(
                AbandonedRun(
                    assessment_id=scoped_id,
                    run_id=run.id,
                    reason=reason,
                    started_at_display=(
                        run.started_at.isoformat() if run.started_at is not None else "-"
                    ),
                    execution_record_count=len(owned),
                    estimated_cost=run.estimated_cost,
                    has_state_file=state_path.is_file(),
                )
            )
    return found


def prune_runs(service: AssessmentService, targets: Sequence[AbandonedRun]) -> PruneResult:
    """Remove each abandoned run's row, execution records, and state file.

    Rows go first, in one transaction per assessment, then the state files -- the DEC-089 purge
    ordering, for the same reason: a crash between the two leaves a stray state file a re-run of
    prune removes, never rows pointing at a record that is gone.
    """
    runs_removed = 0
    records_removed = 0
    state_files_removed = 0
    cost_removed = Decimal("0")
    by_assessment: dict[str, list[AbandonedRun]] = {}
    for target in targets:
        by_assessment.setdefault(target.assessment_id, []).append(target)

    for scoped_id, scoped_targets in by_assessment.items():
        handle = service.handle(scoped_id)
        records = handle.objects.list(ExecutionRecord)
        with handle.objects.transaction():
            for target in scoped_targets:
                for record in records:
                    if record.workflow_run_id == target.run_id and handle.objects.delete(
                        ExecutionRecord, record.id
                    ):
                        records_removed += 1
                if handle.objects.delete(WorkflowRun, target.run_id):
                    runs_removed += 1
                    if target.estimated_cost is not None:
                        cost_removed += target.estimated_cost
        for target in scoped_targets:
            state_path = handle.artifacts.area(STATE_AREA) / f"state-{target.run_id}.json"
            if state_path.is_file():
                state_path.unlink()
                state_files_removed += 1

    return PruneResult(
        runs_removed=runs_removed,
        execution_records_removed=records_removed,
        state_files_removed=state_files_removed,
        estimated_cost_removed=cost_removed,
    )
