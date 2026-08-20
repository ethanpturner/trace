"""Operator-asserted repair of an orphaned running run (`trace runs repair`, DEC-137).

A killed process leaves its `WorkflowRun` at `running` with no process behind it (#613, found
during the #484 sweep pilot). `resume` refuses -- the run is neither paused nor failed -- and the
DEC-017 amendment's prune is deliberately narrow: paused runs only. This module is the sanctioned
surface over the sanctioned mechanics: `ExecutionLedger.complete(error_summary=...)` closes the
row as `failed` with the counters recomputed from the records the run actually wrote, and `trace
resume` then restarts the failed phase in a fresh process (DEC-017).

The assertion is the operator's, never the system's. No heartbeat exists, and a running run that
looks stale may be a slow provider call -- the DEC-135 pilots watched a single evidence-validation
batch hold a run for over two hours. Nothing here inspects time, processes, or progress; the
caller states that the process is gone, and the error summary names the assertion so the row's
history says who decided (DEC-127's explicitness precedent).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from trace_ai.domain.execution import RunStatus, WorkflowRun
from trace_ai.services.execution_ledger import ExecutionLedger

if TYPE_CHECKING:
    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["DEFAULT_REASON", "RepairCandidate", "RunRepairError", "describe_run", "repair_run"]

DEFAULT_REASON = "the process behind this run was killed externally"


class RunRepairError(ValueError):
    """A repair the run's status refuses: only a `running` run can be an orphan."""


@dataclass(frozen=True, slots=True)
class RepairCandidate:
    """One run as the repair dry run shows it, whatever its status."""

    run_id: str
    status: str
    started_at_display: str
    execution_record_count: int
    estimated_cost: Decimal | None


def describe_run(handle: AssessmentHandle, run_id: str) -> RepairCandidate:
    """The facts the operator confirms before asserting the run is an orphan.

    Cost comes from the run's execution records, not the run row: an orphan died between rollups,
    so its row understates what the records already booked.
    """
    run = handle.objects.get(WorkflowRun, run_id)
    records = ExecutionLedger(handle, run).records()
    cost = sum((record.estimated_cost or Decimal(0) for record in records), Decimal(0))
    return RepairCandidate(
        run_id=run.id,
        status=run.status.value,
        started_at_display=run.started_at.isoformat() if run.started_at is not None else "-",
        execution_record_count=len(records),
        estimated_cost=cost or None,
    )


def repair_run(handle: AssessmentHandle, run_id: str, *, reason: str | None = None) -> WorkflowRun:
    """Mark a `running` run failed, on the operator's stated assertion.

    Any other status is refused with the verb that already covers it: a paused or failed run is
    `trace resume`'s, a superseded paused run is `trace runs prune`'s, and a completed run needs
    nothing. The mechanics are the ledger's own `complete(error_summary=...)` -- the same close a
    run performs on itself -- so the repaired row is indistinguishable in shape from a run that
    failed while its process was alive, and the summary is what says otherwise.
    """
    run = handle.objects.get(WorkflowRun, run_id)
    if run.status is not RunStatus.RUNNING:
        applicable = {
            RunStatus.PENDING: "it has not started; there is no process to be gone",
            RunStatus.PAUSED: "resume it with `trace resume`, or prune it if abandoned",
            RunStatus.COMPLETED: "it finished; there is nothing to repair",
            RunStatus.FAILED: "it is already failed; resume it with `trace resume`",
        }[run.status]
        raise RunRepairError(f"{run.id} is {run.status.value}, not running; {applicable}")
    summary = f"repaired by `trace runs repair`: {reason or DEFAULT_REASON}"
    return ExecutionLedger(handle, run).complete(error_summary=summary)
