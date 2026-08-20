"""The orchestrator: the one thing that routes, and the only thing that enforces a ceiling.

DEC-016 rejects an orchestration framework and gives the shape instead — a node protocol, an
explicit transition table, and a persisted `WorkflowRun` row. This module is the loop that walks
the table, and it is deliberately small: everything interesting is in the table, the budget, and
the nodes.

**Every step is bounded before it runs.** A node execution checks the count and the elapsed time; a
model call checks the call ceiling and the projected cost. `agent-design.md` section 27 lists five
ceilings; four are checks on the budget made here or at the call site, and the fifth — retries —
is a policy the budget issues to each agent node's attempt loop (DEC-084), because a retry
decision happens between a classified failure and the next attempt, where the orchestrator never
stands. Either way the value is the configuration's, held in one budget.

**A run stops rather than degrades.** Exceeding a ceiling records a classified error and marks the
run failed. It does not skip a node, shrink a request, or continue with what it has: a limit that
degrades gracefully is one that never stops anything, and the failure mode section 27 exists to
prevent is a pipeline that keeps going.

**Pausing is stopping** (DEC-017). A checkpoint node returns the objects awaiting a decision, the
orchestrator writes the pause into the state and the run, and the loop exits. Nothing is held in
memory across a human review, and a paused run waits indefinitely.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from trace_ai.domain.base import now
from trace_ai.domain.execution import ExecutionType, RunStatus
from trace_ai.services.execution_ledger import safe_message
from trace_ai.workflow.checkpoint import save_state
from trace_ai.workflow.errors import ErrorClass, WorkflowError
from trace_ai.workflow.limits import Budget, LimitExceededError
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.phases import NODES_BY_PHASE, PAUSE_PHASES, Phase, successor
from trace_ai.workflow.state import AssessmentState

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from trace_ai.infrastructure.model.seam import StructuredModel
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.execution_ledger import ExecutionLedger
    from trace_ai.workflow.nodes import Node, NodeResult

__all__ = ["Orchestrator", "PhaseProgress", "RunOutcome"]


@dataclass(frozen=True, slots=True)
class PhaseProgress:
    """What the phase observer is told when the run enters a phase (DEC-138).

    A snapshot of facts the state and the ledger already record — identifiers, a phase name, and
    counters — assembled for notification rather than stored anywhere. It carries no
    source-derived content by construction: everything here is safe for a progress line under the
    observability rules.
    """

    workflow_run_id: str
    phase: Phase
    phase_number: int
    """1-based position in the fourteen-phase table, for `(6/14)`-style rendering."""
    phase_total: int
    model_calls: int
    """Model calls recorded so far this run, computed from the execution records."""
    estimated_cost: Decimal | None
    """Summed estimated cost of those calls, or None when no record reported one."""


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """Where a run got to, and why it stopped."""

    state: AssessmentState
    stopped_because: str
    """`completed`, `paused`, or the name of the limit or error that stopped it."""

    @property
    def paused(self) -> bool:
        return self.state.status is RunStatus.PAUSED

    @property
    def completed(self) -> bool:
        return self.state.status is RunStatus.COMPLETED


class Orchestrator:
    """Walks the transition table, executing the node registered for each phase."""

    def __init__(
        self,
        handle: AssessmentHandle,
        *,
        ledger: ExecutionLedger,
        nodes: Sequence[Node],
        budget: Budget | None = None,
        model: StructuredModel | None = None,
        on_pause: Callable[[AssessmentState], None] | None = None,
        on_phase: Callable[[PhaseProgress], None] | None = None,
    ) -> None:
        self.handle = handle
        self.ledger = ledger
        self.budget = budget if budget is not None else Budget()
        self.model = model
        self._on_pause = on_pause
        self._on_phase = on_phase
        self._nodes: dict[Phase, dict[str, Node]] = {}
        for node in nodes:
            self.register(node)

    def register(self, node: Node) -> None:
        """Register a node against the phase and name it declares.

        A node whose name is not listed for that phase in `NODES_BY_PHASE` is refused. The mapping
        is the corpus's, so this is the orchestrator checking a registration against the documented
        pipeline rather than against a list it keeps for itself.

        A phase may declare more than one node — six of them do — and each declared name may be
        registered exactly once. Which of two nodes runs first is the table's order, never
        registration order, so registering both nodes of a two-node phase decides nothing.
        """
        permitted = NODES_BY_PHASE[node.phase]
        if node.name not in permitted:
            allowed = ", ".join(permitted) if permitted else "no nodes"
            raise ValueError(
                f"node {node.name!r} declares phase {node.phase.value!r}, which runs {allowed}. "
                f"A node in an undeclared phase runs correctly and in the wrong place."
            )
        slots = self._nodes.setdefault(node.phase, {})
        if node.name in slots:
            raise ValueError(
                f"phase {node.phase.value!r} already has a node named {node.name!r}; "
                f"which of two same-named nodes runs is not something to leave to registration "
                f"order"
            )
        slots[node.name] = node

    def run(self, state: AssessmentState, *, stop_before: Phase | None = None) -> RunOutcome:
        """Execute from the state's current phase until the run pauses, completes, or stops.

        `stop_before` halts cleanly the moment the run is about to advance into that phase — the
        evaluation harness uses it to measure the finding set without running the report, which
        the pipeline itself never needs (there is no analytical reason to stop early). The run's
        status stays what it was; a clean early stop is neither a failure nor a checkpoint pause.
        """
        # The ceiling bounds this process's active segment, not the wall clock since the run
        # first began. DEC-017 pauses by exiting and waiting costs nothing — measured from the
        # run row's started_at, a resume after an hour of review would stop on its first step
        # with maximum_workflow_duration (#396).
        started_at = now()
        current = state

        # One try around the whole loop, not just `_execute`. A `WorkflowError` or a ceiling is a
        # classified stop; anything else -- a `StoreError`, a `ValidationError` from a typo'd state
        # key in `absorb`, a `TransitionError` from `advance`, an `OSError` from a node -- used to
        # escape and leave the run row `running` forever, with no classified error and no way for
        # `_paused_run` to find it. It is now `unexpected_application_failure` (section 11's class
        # for a fault in this application), recorded and persisted like any other stop.
        try:
            while True:
                phase = current.current_phase
                self._notify_phase(current)

                if phase is Phase.ASSESSMENT_COMPLETION:
                    completed = self._complete(current)
                    return RunOutcome(state=completed, stopped_because="completed")

                slots = self._nodes.get(phase, {})
                if not slots:
                    return self._stop(current, f"no node is registered for phase {phase.value}")

                for name in NODES_BY_PHASE[phase]:
                    node = slots.get(name)
                    if node is None:
                        return self._stop(
                            current,
                            f"phase {phase.value} declares node {name!r} and none is registered; "
                            f"a run that continued would have skipped it",
                        )

                    self.budget.check_duration(started_at=started_at, at=now())
                    self.budget.check_node_execution()

                    result = self._execute(node, current)

                    current = current.absorb(**result.state_changes).with_limits(
                        self.budget.remaining()
                    )

                    if phase in PAUSE_PHASES and result.awaiting_review:
                        paused = current.paused_for(phase, result.awaiting_review)
                        self._persist_pause(paused)
                        return RunOutcome(state=paused, stopped_because="paused")

                if phase in PAUSE_PHASES and current.pending_human_review is not None:
                    current = current.resumed()

                destination = successor(phase)
                if destination is None:  # pragma: no cover - completion is handled above
                    return self._stop(current, f"{phase.value} is terminal and did not complete")
                if destination is stop_before:
                    return RunOutcome(
                        state=current, stopped_because=f"stopped_before_{destination.value}"
                    )
                current = current.advance(destination)
                # Persist after every advance so a crash or a stop leaves an accurate, resumable
                # record of where the run reached -- not a state file frozen at the last pause.
                save_state(self.handle, current)
        except LimitExceededError as error:
            return self._stop(current, str(error), kind=error.kind.value)
        except WorkflowError as error:
            return self._stop(current, str(error), kind=error.error_class.value)
        except Exception as error:
            return self._stop(
                current,
                safe_message(error),
                kind=ErrorClass.UNEXPECTED_APPLICATION_FAILURE.value,
            )

    # -- narration -------------------------------------------------------------------------

    def _notify_phase(self, state: AssessmentState) -> None:
        """Tell the observer the run entered a phase (DEC-138). Notify-only, and guarded.

        The observer is given a snapshot and no way back in: it cannot route, spend, or stop
        anything, and an exception it raises — or a ledger read failing underneath the snapshot —
        is suppressed, because a progress line must never be what stops a run. Routing and
        ceilings stay exactly where DEC-016 put them.
        """
        if self._on_phase is None:
            return
        with contextlib.suppress(Exception):
            counters = self.ledger.counters()
            calls = counters.get("total_model_calls")
            cost = counters.get("estimated_cost")
            order = list(Phase)
            self._on_phase(
                PhaseProgress(
                    workflow_run_id=state.workflow_run_id,
                    phase=state.current_phase,
                    phase_number=order.index(state.current_phase) + 1,
                    phase_total=len(order),
                    model_calls=calls if isinstance(calls, int) else 0,
                    estimated_cost=cost if isinstance(cost, Decimal) else None,
                )
            )

    # -- one node --------------------------------------------------------------------------

    def _execute(self, node: Node, state: AssessmentState) -> NodeResult:
        """Run one node, recording it, and account for what it spent.

        A node that records its own execution — one that holds the ledger and writes one record
        for the node, carrying every attempt's usage and the retries consumed, the way the agent
        nodes do — says so with a true `records_own_execution` attribute, and the orchestrator
        neither records it again nor re-spends its usage. Recording such a node here would double
        it: `counters()` counts model calls by record, so a wrapper record is not harmless
        bookkeeping but a second call that never happened.
        """
        context = NodeContext(
            handle=self.handle,
            state=state,
            model=self.model if node.execution_type is ExecutionType.MODEL else None,
        )

        if node.execution_type is ExecutionType.MODEL:
            self.budget.check_model_call()

        self.budget.spend_node_execution()

        if getattr(node, "records_own_execution", False):
            return node.run(context)

        with self.ledger.record(
            node.name,
            node_version=node.version,
            execution_type=node.execution_type,
        ) as execution:
            result = node.run(context)
            execution.consumed(*result.consumed_object_ids)
            execution.produced(*result.produced_object_ids)
            execution.prompt_version = result.prompt_version
            execution.model_name = result.model_name
            execution.metadata.update(result.metadata)
            for usage in result.model_usages:
                execution.record_usage(usage)

        for usage in result.model_usages:
            self.budget.spend_model_call(usage.estimated_cost)

        return result

    # -- stopping --------------------------------------------------------------------------

    def _stop(self, state: AssessmentState, message: str, *, kind: str | None = None) -> RunOutcome:
        failed = state.failed(message)
        # Persist the failed state before closing the run, so `traces/` records where it stopped and
        # why -- `resume_assessment` reads this to restart from the failed phase rather than
        # re-running the whole pipeline. Best-effort: a stop that cannot even write its own state
        # must still mark the run failed rather than raise a second, masking exception.
        self._save_state_quietly(failed)
        self.ledger.complete(error_summary=message)
        return RunOutcome(state=failed, stopped_because=kind or "error")

    def _complete(self, state: AssessmentState) -> AssessmentState:
        completed = AssessmentState.model_validate(
            state.model_dump()
            | {
                "status": RunStatus.COMPLETED,
                "next_action": {"action": "stop", "phase": Phase.ASSESSMENT_COMPLETION},
            }
        )
        # The state file used to be frozen at the last pause forever; now a completed run's record
        # says completed.
        self._save_state_quietly(completed)
        self.ledger.complete()
        return completed

    def _save_state_quietly(self, state: AssessmentState) -> None:
        """Persist state without letting a write failure mask the outcome being recorded.

        Called only from the stop/complete paths, where the run's fate is already decided: a failed
        `save_state` there must not turn a recorded failure into an unrecorded one, so it is
        swallowed. The ordinary per-phase `save_state` in `run` is not guarded -- a write failure
        mid-run is itself a stop.
        """
        # pragma: no cover - disk-full on the failure path is not reproducible here
        with contextlib.suppress(OSError):
            save_state(self.handle, state)

    def _persist_pause(self, state: AssessmentState) -> None:
        """Record the pause on the run and write the state file a resumed invocation reads.

        Both halves are DEC-017's: the run row says the run is paused and where, and the state file
        under `traces/` is the self-describing record a later process loads. A pause that wrote
        only the row would be one nobody could resume.

        `on_pause` runs inside the same transaction as the run-row update. It exists for DEC-031,
        which requires the assessment's move to `pending_review` to commit with the pause that
        causes it — the driver supplies the callback because the deliverable's lifecycle belongs to
        `AssessmentService`, not to this loop.

        The state file is written *after* the transaction commits, not before. If `on_pause` were to
        raise, the transaction rolls back the run-row pause; writing the state file first would then
        leave a `paused` state file for a run whose row never became paused -- the two stores
        disagreeing about whether a pause happened.
        """
        with self.handle.objects.transaction():
            self.ledger.pause(current_node=state.current_phase.value)
            if self._on_pause is not None:
                self._on_pause(state)
        save_state(self.handle, state)
