"""The orchestrator: the one thing that routes, and the only thing that enforces a ceiling.

DEC-016 rejects an orchestration framework and gives the shape instead — a node protocol, an
explicit transition table, and a persisted `WorkflowRun` row. This module is the loop that walks
the table, and it is deliberately small: everything interesting is in the table, the budget, and
the nodes.

**Every step is bounded before it runs.** A node execution checks the count and the elapsed time; a
model call checks the call ceiling and the projected cost. `agent-design.md` section 27 lists five
ceilings and this is where all five are enforced, because a limit checked in a node is a limit each
node has to remember.

**A run stops rather than degrades.** Exceeding a ceiling records a classified error and marks the
run failed. It does not skip a node, shrink a request, or continue with what it has: a limit that
degrades gracefully is one that never stops anything, and the failure mode section 27 exists to
prevent is a pipeline that keeps going.

**Pausing is stopping** (DEC-017). A checkpoint node returns the objects awaiting a decision, the
orchestrator writes the pause into the state and the run, and the loop exits. Nothing is held in
memory across a human review, and a paused run waits indefinitely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from trace_ai.domain.base import now
from trace_ai.domain.execution import ExecutionType, RunStatus
from trace_ai.workflow.limits import Budget, LimitExceededError
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.phases import NODES_BY_PHASE, PAUSE_PHASES, Phase, successor
from trace_ai.workflow.state import AssessmentState

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.infrastructure.model.seam import StructuredModel
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.execution_ledger import ExecutionLedger
    from trace_ai.workflow.nodes import Node, NodeResult

__all__ = ["Orchestrator", "RunOutcome"]


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
    ) -> None:
        self.handle = handle
        self.ledger = ledger
        self.budget = budget if budget is not None else Budget()
        self.model = model
        self._nodes: dict[Phase, Node] = {}
        for node in nodes:
            self.register(node)

    def register(self, node: Node) -> None:
        """Register a node against the phase it declares.

        A node whose name is not listed for that phase in `NODES_BY_PHASE` is refused. The mapping
        is the corpus's, so this is the orchestrator checking a registration against the documented
        pipeline rather than against a list it keeps for itself.
        """
        permitted = NODES_BY_PHASE[node.phase]
        if node.name not in permitted:
            allowed = ", ".join(permitted) if permitted else "no nodes"
            raise ValueError(
                f"node {node.name!r} declares phase {node.phase.value!r}, which runs {allowed}. "
                f"A node in an undeclared phase runs correctly and in the wrong place."
            )
        if node.phase in self._nodes:
            raise ValueError(
                f"phase {node.phase.value!r} already has node {self._nodes[node.phase].name!r}; "
                f"which of two nodes runs is not something to leave to registration order"
            )
        self._nodes[node.phase] = node

    def run(self, state: AssessmentState) -> RunOutcome:
        """Execute from the state's current phase until the run pauses, completes, or stops."""
        started_at = self.ledger.run.started_at or now()
        current = state

        while True:
            phase = current.current_phase

            if phase is Phase.ASSESSMENT_COMPLETION:
                completed = self._complete(current)
                return RunOutcome(state=completed, stopped_because="completed")

            node = self._nodes.get(phase)
            if node is None:
                return self._stop(current, f"no node is registered for phase {phase.value}")

            try:
                self.budget.check_duration(started_at=started_at, at=now())
                self.budget.check_node_execution()
            except LimitExceededError as error:
                return self._stop(current, str(error), kind=error.kind.value)

            try:
                result = self._execute(node, current)
            except LimitExceededError as error:
                return self._stop(current, str(error), kind=error.kind.value)

            current = current.with_limits(self.budget.remaining())

            if phase in PAUSE_PHASES and result.awaiting_review:
                paused = current.paused_for(phase, result.awaiting_review)
                self._persist_pause(paused)
                return RunOutcome(state=paused, stopped_because="paused")

            destination = successor(phase)
            if destination is None:  # pragma: no cover - completion is handled above
                return self._stop(current, f"{phase.value} is terminal and did not complete")
            current = current.advance(destination, **result.state_changes)

    # -- one node --------------------------------------------------------------------------

    def _execute(self, node: Node, state: AssessmentState) -> NodeResult:
        """Run one node, recording it, and account for what it spent."""
        context = NodeContext(
            handle=self.handle,
            state=state,
            model=self.model if node.execution_type is ExecutionType.MODEL else None,
        )

        if node.execution_type is ExecutionType.MODEL:
            self.budget.check_model_call()

        self.budget.spend_node_execution()
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
        self.ledger.complete(error_summary=message)
        return RunOutcome(state=failed, stopped_because=kind or "error")

    def _complete(self, state: AssessmentState) -> AssessmentState:
        self.ledger.complete()
        return AssessmentState.model_validate(
            state.model_dump()
            | {
                "status": RunStatus.COMPLETED,
                "next_action": {"action": "stop", "phase": Phase.ASSESSMENT_COMPLETION},
            }
        )

    def _persist_pause(self, state: AssessmentState) -> None:
        """Record the pause on the run, so a resumed invocation reads it rather than infers it."""
        self.ledger.pause(current_node=state.current_phase.value)
