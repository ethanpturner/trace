"""`AssessmentState`: identifiers and routing, and deliberately nothing else.

`data-model.md` section 31 describes the workflow-facing state and then states the rule that shapes
this module: **do not place full source documents, full prompt transcripts, or every generated
object into one continuously growing workflow-state payload.** The state holds identifiers; the
objects live in the assessment store and are retrieved when needed.

That rule is not about size. A state carrying object *content* becomes a second copy of the
authoritative data, and the two disagree the first time one is written and the other is not — which
is the same objection DEC-016 raises to a framework checkpointer and DEC-006 to a conversational
transcript. Holding identifiers makes the disagreement impossible rather than unlikely.

`pending_human_review` is what makes a paused run self-describing (DEC-017): the checkpoint it
stopped at, and every object awaiting a decision. The review package a reviewer sees is *derived*
from the run rather than stored in it, so the pause mechanism presupposes no interface.

The state is frozen, like every other object here. A phase advance builds a new state with
`model_validate`, which is the DEC-023 rule applied to routing: the copy API validates nothing, and
a state that can be edited in place is one whose history cannot be replayed.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.execution import RunStatus
from trace_ai.domain.identifiers import (
    AssessmentId,
    WorkflowRunId,
)
from trace_ai.workflow.phases import PAUSE_PHASES, Phase, check_transition

__all__ = ["AssessmentState", "NextAction", "PendingHumanReview", "RemainingLimits"]


class NextAction(DomainModel):
    """What the orchestrator should do next, named rather than inferred."""

    action: str
    """`execute_node`, `await_human_review`, or `stop`."""

    phase: Phase


class PendingHumanReview(DomainModel):
    """What a paused run is waiting for (section 31, DEC-017)."""

    checkpoint_type: Phase
    object_ids: list[str] = Field(min_length=1)
    """Every object awaiting a decision. The checkpoint completes when each has a
    `ReviewerDecision`; partial progress is allowed and persisted, and a run with some objects
    decided stays paused."""


class RemainingLimits(DomainModel):
    """What the run has left, as section 31's `execution_limits` block records it.

    Remaining rather than consumed, because that is what the block in the document shows and what a
    reader of a paused run wants: the question at a checkpoint is whether there is budget to
    finish, not how much has gone.
    """

    model_calls_remaining: int | None = Field(default=None, ge=0)
    cost_remaining: Decimal | None = Field(default=None, ge=0)


class AssessmentState(DomainModel):
    """The orchestrator's view of one run (section 31).

    Every list holds identifiers. Nothing here holds document text, prompt text, or a generated
    object — `tests/unit/test_workflow_state.py` asserts it, because the rule is one that erodes by
    convenience rather than by decision.
    """

    assessment_id: AssessmentId
    workflow_run_id: WorkflowRunId
    status: RunStatus
    current_phase: Phase
    next_action: NextAction

    source_document_ids: list[str] = Field(default_factory=list)
    system_context_version: int | None = Field(default=None, ge=1)
    context_claim_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    actor_ids: list[str] = Field(default_factory=list)
    data_flow_ids: list[str] = Field(default_factory=list)
    trust_boundary_ids: list[str] = Field(default_factory=list)
    candidate_threat_ids: list[str] = Field(default_factory=list)
    control_mapping_ids: list[str] = Field(default_factory=list)
    candidate_finding_ids: list[str] = Field(default_factory=list)
    open_question_ids: list[str] = Field(default_factory=list)
    documentation_gap_ids: list[str] = Field(default_factory=list)
    source_observation_ids: list[str] = Field(default_factory=list)

    pending_human_review: PendingHumanReview | None = None
    execution_limits: RemainingLimits = Field(default_factory=RemainingLimits)
    errors: list[str] = Field(default_factory=list)

    @classmethod
    def begin(
        cls, *, assessment_id: str, workflow_run_id: str, limits: RemainingLimits | None = None
    ) -> Self:
        """A run at its first phase, before anything has executed."""
        phase = Phase.ASSESSMENT_INITIALIZATION
        return cls.model_validate(
            {
                "assessment_id": assessment_id,
                "workflow_run_id": workflow_run_id,
                "status": RunStatus.RUNNING,
                "current_phase": phase,
                "next_action": {"action": "execute_node", "phase": phase},
                "execution_limits": (limits or RemainingLimits()).model_dump(),
            }
        )

    def advance(self, destination: Phase, **changes: object) -> Self:
        """The state one permitted transition later.

        The transition is checked here rather than by the caller, so there is one place a
        disallowed move is refused — including the self-transition that would be the smallest
        uncontrolled loop (`agent-design.md` section 27).
        """
        check_transition(self.current_phase, destination)
        action = "await_human_review" if destination in PAUSE_PHASES else "execute_node"
        return type(self).model_validate(
            self.model_dump()
            | {
                "current_phase": destination,
                "next_action": {"action": action, "phase": destination},
                **changes,
            }
        )

    def absorb(self, **changes: object) -> Self:
        """This state with a node's `state_changes` applied, still in the same phase.

        A phase may run more than one declared node, and a later node reads what an earlier one
        recorded — the threat validator reads the candidate ids the analysis node returned. The
        changes are applied through `model_validate` like every other mutation here; what this
        method deliberately lacks is a destination, because absorbing results is not routing.
        """
        if not changes:
            return self
        return type(self).model_validate(self.model_dump() | changes)

    def resumed(self) -> Self:
        """This state, running again after a completed checkpoint.

        `paused_for` sets the status and names the waiting objects; nothing else clears them, so a
        resumed run would otherwise carry `paused` and a stale `pending_human_review` through every
        later phase. The orchestrator calls this at the moment the checkpoint's completion
        condition holds — every subject decided — which is DEC-017's resume condition.
        """
        return type(self).model_validate(
            self.model_dump()
            | {
                "status": RunStatus.RUNNING,
                "pending_human_review": None,
                "next_action": {"action": "execute_node", "phase": self.current_phase},
            }
        )

    def paused_for(self, checkpoint: Phase, object_ids: list[str]) -> Self:
        """This state, paused at a checkpoint with the objects awaiting a decision named."""
        if checkpoint not in PAUSE_PHASES:
            raise ValueError(
                f"{checkpoint.value} is not one of the two structural checkpoints (DEC-005): "
                f"{', '.join(sorted(phase.value for phase in PAUSE_PHASES))}"
            )
        return type(self).model_validate(
            self.model_dump()
            | {
                "status": RunStatus.PAUSED,
                "pending_human_review": {
                    "checkpoint_type": checkpoint,
                    "object_ids": object_ids,
                },
                "next_action": {"action": "await_human_review", "phase": checkpoint},
            }
        )

    def with_limits(self, limits: RemainingLimits) -> Self:
        """This state with the remaining budget updated."""
        return type(self).model_validate(
            self.model_dump() | {"execution_limits": limits.model_dump()}
        )

    def failed(self, error: str) -> Self:
        """This state, stopped. The error joins `errors`; nothing is cleared."""
        return type(self).model_validate(
            self.model_dump()
            | {
                "status": RunStatus.FAILED,
                "errors": [*self.errors, error],
                "next_action": {"action": "stop", "phase": self.current_phase},
            }
        )

    def restarted(self) -> Self:
        """This state, running again after a failure, at the phase it stopped in.

        Resuming a failed run re-executes the phase that failed; the phases before it completed, so
        their objects already exist and their nodes are not re-run. `errors` is kept as history —
        the run failed once, and a later reader should see that it did. This is the failed-run
        counterpart to `resumed()`, which is the checkpoint case.
        """
        return type(self).model_validate(
            self.model_dump()
            | {
                "status": RunStatus.RUNNING,
                "next_action": {"action": "execute_node", "phase": self.current_phase},
            }
        )
