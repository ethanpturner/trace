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

A second orphan shape reaches the same verb (#641, DEC-144): a run whose row says `paused` while
its state file records a phase still `running`. A pause commits the row and then writes the state
file -- deliberately in that order, so a rolled-back `on_pause` cannot leave a paused state file
for an unpaused row -- and a process killed between the two writes leaves the halves disagreeing.
`resume` refuses such a run because the state file it would read is not a pause, and the gate above
refuses it because the row is not `running`, so before this it was reachable by no verb at all.
The row is what the run *is* (DEC-006: the persisted domain object is authoritative) and the state
file records where it *was* (`data-model.md` section 31: routing state, derived and rewritten), so
the disagreement is never two truths -- it is a row left stale by a process that died. Which is
exactly the judgment DEC-137 gives the operator rather than a heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from trace_ai.domain.execution import RunStatus, WorkflowRun
from trace_ai.services.execution_ledger import ExecutionLedger
from trace_ai.workflow.checkpoint import load_state

if TYPE_CHECKING:
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "DEFAULT_REASON",
    "RepairCandidate",
    "RunRepairError",
    "describe_run",
    "repair_run",
    "strand_description",
]

DEFAULT_REASON = "the process behind this run was killed externally"


class RunRepairError(ValueError):
    """A repair the run's status refuses: the run is neither an orphan nor a strand."""


def strand_description(handle: AssessmentHandle, run: WorkflowRun) -> str | None:
    """How a paused run's state file disagrees with its row, or `None` when they agree.

    Only a `paused` row can strand this way: a `running` row is DEC-137's original orphan, and a
    completed or failed run has nowhere left to disagree. The state file is read, never written --
    reporting the disagreement is this module's job, and reconciling it is the operator's.
    """
    if run.status is not RunStatus.PAUSED:
        return None
    try:
        state = load_state(handle, run.id)
    except FileNotFoundError:
        # A paused row with no state file at all is not a strand: repair exists to leave a run in a
        # state `resume` can restart, and `resume` reads the same file, so failing this row would
        # relabel it rather than recover it. An abandoned pause is `trace runs prune`'s (DEC-127).
        return None
    if state.status is RunStatus.PAUSED:
        return None
    return (
        f"the row says paused and the state file records {state.current_phase.value} "
        f"still {state.status.value}"
    )


@dataclass(frozen=True, slots=True)
class RepairCandidate:
    """One run as the repair dry run shows it, whatever its status."""

    run_id: str
    status: str
    started_at_display: str
    execution_record_count: int
    estimated_cost: Decimal | None
    strand: str | None = None


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
        strand=strand_description(handle, run),
    )


def repair_run(handle: AssessmentHandle, run_id: str, *, reason: str | None = None) -> WorkflowRun:
    """Mark an orphaned or stranded run failed, on the operator's stated assertion.

    Two shapes qualify: a `running` row whose process is gone (DEC-137), and a `paused` row whose
    state file disagrees with it (DEC-144). Any other status is refused with the verb that already
    covers it: a cleanly paused run is `trace resume`'s, a superseded paused run is `trace runs
    prune`'s, and a completed run needs nothing. The mechanics are the ledger's own
    `complete(error_summary=...)` -- the same close a run performs on itself -- so the repaired row
    is indistinguishable in shape from a run that failed while its process was alive, and the
    summary is what says otherwise. `trace resume` then restarts the phase the run stopped in.
    """
    run = handle.objects.get(WorkflowRun, run_id)
    strand = strand_description(handle, run)
    if run.status is not RunStatus.RUNNING and strand is None:
        applicable = {
            RunStatus.PENDING: "it has not started; there is no process to be gone",
            RunStatus.PAUSED: "resume it with `trace resume`, or prune it if abandoned",
            RunStatus.COMPLETED: "it finished; there is nothing to repair",
            RunStatus.FAILED: "it is already failed; resume it with `trace resume`",
        }[run.status]
        raise RunRepairError(f"{run.id} is {run.status.value}, not running; {applicable}")
    observed = f" ({strand})" if strand is not None else ""
    summary = f"repaired by `trace runs repair`{observed}: {reason or DEFAULT_REASON}"
    return ExecutionLedger(handle, run).complete(error_summary=summary)
