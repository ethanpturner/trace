"""The checkpoint machinery: pausing, resuming, and the review package both checkpoints share.

DEC-005 makes two human checkpoints structural — context approval and finding approval — and
`agent-design.md` section 9 states the rule unconditionally: threat analysis does not begin until
the context checkpoint is approved. This module is what both checkpoints are built from, so the M4
finding checkpoint reuses it rather than reimplementing it.

**Disabling a checkpoint is unrepresentable, not discouraged.** There is no parameter here that
skips one, no configuration field consulted, and no argument that advances an unapproved run:
`CheckpointNode.run` returns the pending objects and the orchestrator stops. DEC-012 removed
`require_context_review` from `AssessmentConfiguration` for exactly this reason, and a test asserts
that no configuration value, environment variable, or argument gets past an unapproved checkpoint.

**Pausing is stopping** (DEC-017). The run persists itself and the process exits; nothing is held in
memory while a reviewer reads, and a paused run waits indefinitely. Resuming is a later invocation
that reads the persisted run and its state — not a framework checkpoint restore, and not a
continuation of a process that stayed alive.

**The completion condition is per object.** A checkpoint completes when every identifier in
`pending_human_review.object_ids` has a `ReviewerDecision` (section 31). Partial progress is
allowed and persisted: a reviewer who decides three of eight and closes the laptop has made
progress, and the run stays paused.

Two references in the issue that created this module are stale, and both are recorded here rather
than implemented. `WorkflowRun.checkpoint_reference` was removed by DEC-017 — `current_node` says
where a run stopped and `pending_human_review` says what it is waiting for, so a third field
pointing at a framework object that no longer exists would be vestigial. And a human-review
*timeout* was removed by the same decision: waiting costs nothing, so there is nothing to time out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.execution import ExecutionType, RunStatus
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.infrastructure.filesystem.atomic import write_text_atomic
from trace_ai.workflow.nodes import NodeResult
from trace_ai.workflow.phases import PAUSE_PHASES, Phase
from trace_ai.workflow.state import AssessmentState

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from trace_ai.domain.base import DomainModel
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.workflow.nodes import NodeContext

__all__ = [
    "STATE_AREA",
    "CheckpointNode",
    "ReviewPackage",
    "decided_in_run",
    "decided_object_ids",
    "load_state",
    "pending_object_ids",
    "save_state",
]

# Where a paused run's state is written. `current-architecture.md` section 5.16 lists "exported
# workflow state" among the artifact store's contents, and `traces/` is the area for it. Writing
# through the path rather than the store's `_write` is deliberate: the store refuses to overwrite
# stored content with different content, which is right for evidence and wrong for a state file
# that changes every time the run advances.
STATE_AREA: Final = "traces"


def _state_filename(workflow_run_id: str) -> str:
    return f"state-{workflow_run_id}.json"


def save_state(handle: AssessmentHandle, state: AssessmentState) -> str:
    """Persist the workflow state, returning its path relative to the assessment root.

    Written atomically: the state file is rewritten on every phase, and a crash mid-write would
    otherwise leave a truncated file that `load_state` cannot parse, making the run unresumable.
    """
    path = handle.artifacts.area(STATE_AREA) / _state_filename(state.workflow_run_id)
    write_text_atomic(path, state.model_dump_json(indent=2))
    return str(path.relative_to(handle.artifacts.assessment_root))


def load_state(handle: AssessmentHandle, workflow_run_id: str) -> AssessmentState:
    """Read a persisted state back.

    This is what resuming is (DEC-017): a read, in a new process, of what the previous one wrote.
    """
    path = handle.artifacts.area(STATE_AREA) / _state_filename(workflow_run_id)
    if not path.exists():
        raise FileNotFoundError(
            f"no persisted state for {workflow_run_id} in {STATE_AREA}/. A run that paused wrote "
            f"one; a run that never started has nothing to resume."
        )
    return AssessmentState.model_validate(json.loads(path.read_text(encoding="utf-8")))


def decided_object_ids(handle: AssessmentHandle) -> set[str]:
    """Every object this assessment has a `ReviewerDecision` for, across every run."""
    return {decision.subject_id for decision in handle.objects.list(ReviewerDecision)}


def decided_in_run(handle: AssessmentHandle, workflow_run_id: str) -> set[str]:
    """Subjects a checkpoint treats as decided for the run now executing (DEC-079).

    A decision counts when it carries this run's identifier, or none at all — the run-less form a
    recorded replay or a file-applied decision writes, kept current so those paths are unaffected. A
    decision made in a *different* run does not count, which is what lets a revisit subject carried
    across a run re-enter the checkpoint despite its prior decision (DEC-061). Ordinary subjects are
    generated and decided within one run, and a resume keeps the same run identifier, so this is
    invisible to them.
    """
    return {
        decision.subject_id
        for decision in handle.objects.list(ReviewerDecision)
        if decision.workflow_run_id in (workflow_run_id, None)
    }


def pending_object_ids(handle: AssessmentHandle, state: AssessmentState) -> list[str]:
    """The objects a paused run is still waiting on, in the order they were presented.

    Order is preserved rather than sorted so a reviewer returning to a half-finished review sees
    the same list in the same sequence — a review package that reshuffles between sittings is one
    where "I did the first three" stops being a true statement. Decided is scoped to the run
    (DEC-079), so a revisit subject re-presented this run stays pending until this run decides it.
    """
    if state.pending_human_review is None:
        return []
    decided = decided_in_run(handle, state.workflow_run_id)
    return [
        object_id for object_id in state.pending_human_review.object_ids if object_id not in decided
    ]


@dataclass(frozen=True, slots=True)
class ReviewPackage[T: "DomainModel"]:
    """What a reviewer is shown at a checkpoint, derived rather than stored.

    Section 31 makes the point that matters: the package is derived from the run, so the pause
    mechanism presupposes no interface. A package stored in the state would be a second copy of
    objects that already exist, and it would go stale the moment a reviewer edited one.

    Generic over the object type because both checkpoints show the same shape — objects awaiting a
    decision, what validation said about them, and which triggers fired — and only the type differs.
    """

    checkpoint_type: Phase
    objects: tuple[T, ...]
    validation_findings: tuple[str, ...] = ()
    """What the preceding validation node said. Reasons, not verdicts: the reviewer decides."""

    triggers: tuple[str, ...] = ()
    """The human-review triggers that fired (`agent-design.md` section 7) — a contradiction, a
    low-confidence claim, an unresolved question. Named so the reviewer knows why they are here."""

    decided_object_ids: frozenset[str] = frozenset()

    @property
    def pending(self) -> tuple[T, ...]:
        """The objects still awaiting a decision, in presentation order."""
        return tuple(
            item
            for item in self.objects
            if getattr(item, "id", None) not in self.decided_object_ids
        )

    @property
    def complete(self) -> bool:
        """Whether every object in the package has been decided (section 31)."""
        return not self.pending


def build_review_package[T: "DomainModel"](
    handle: AssessmentHandle,
    *,
    checkpoint_type: Phase,
    objects: Sequence[T],
    validation_findings: Sequence[str] = (),
    triggers: Sequence[str] = (),
    workflow_run_id: str | None = None,
) -> ReviewPackage[T]:
    """Assemble the package for a checkpoint from objects that already exist.

    `workflow_run_id` scopes the decided set to that run (DEC-079), so a revisit subject
    re-presented this run reads as pending in the derived package the way it does at the node. Left
    unscoped, the package reflects every decision ever recorded — the historical view.
    """
    if checkpoint_type not in PAUSE_PHASES:
        raise ValueError(
            f"{checkpoint_type.value} is not one of the two structural checkpoints (DEC-005)"
        )
    decided = (
        decided_in_run(handle, workflow_run_id)
        if workflow_run_id is not None
        else decided_object_ids(handle)
    )
    return ReviewPackage(
        checkpoint_type=checkpoint_type,
        objects=tuple(objects),
        validation_findings=tuple(validation_findings),
        triggers=tuple(triggers),
        decided_object_ids=frozenset(decided),
    )


@dataclass(slots=True)
class CheckpointNode:
    """A human checkpoint as a workflow node, parameterised by which of the two it is.

    It has no `skip`, no `enabled`, and no configuration input. The only way past it is for every
    object it names to have a `ReviewerDecision`, which is the DEC-005 property expressed as a
    control flow with nowhere to put an exception.
    """

    checkpoint_type: Phase
    subjects: Callable[[NodeContext], list[str]]
    """What this checkpoint is waiting on, computed from the state when the node runs."""

    version: str = "0.1"
    execution_type: ExecutionType = field(default=ExecutionType.HUMAN_CHECKPOINT, init=False)

    def __post_init__(self) -> None:
        if self.checkpoint_type not in PAUSE_PHASES:
            raise ValueError(
                f"{self.checkpoint_type.value} is not one of the two structural checkpoints "
                f"(DEC-005): a checkpoint node cannot be created for any other phase"
            )

    @property
    def name(self) -> str:
        return self.checkpoint_type.value.replace("_", "-")

    @property
    def phase(self) -> Phase:
        return self.checkpoint_type

    def run(self, context: NodeContext) -> NodeResult:
        """Return the objects awaiting a decision, or nothing if the checkpoint is complete.

        Returning nothing is what lets the orchestrator advance, and it happens only when every
        subject has a decision. There is no branch here that returns nothing for any other reason.
        """
        subjects = self.subjects(context)
        decided = decided_in_run(context.handle, context.state.workflow_run_id)
        awaiting = [object_id for object_id in subjects if object_id not in decided]
        return NodeResult(
            awaiting_review=awaiting,
            consumed_object_ids=list(subjects),
            metadata={
                "checkpoint_type": self.checkpoint_type.value,
                "subjects": len(subjects),
                "decided": len(subjects) - len(awaiting),
            },
        )


def resume(handle: AssessmentHandle, workflow_run_id: str) -> tuple[AssessmentState, list[str]]:
    """Load a paused run's state and the objects it is still waiting on.

    Returns the state as persisted rather than an advanced one: whether the checkpoint is complete
    is the checkpoint node's judgment when it runs again, not this function's. A resume that
    decided for itself would be a second place the approval condition is evaluated.
    """
    state = load_state(handle, workflow_run_id)
    if state.status is not RunStatus.PAUSED:
        raise ValueError(
            f"{workflow_run_id} is {state.status}, not paused; there is nothing to resume"
        )
    return state, pending_object_ids(handle, state)


def summarize_package(package: ReviewPackage[Any]) -> dict[str, object]:
    """A package as counts and identifiers, for a log line or a command-line summary.

    Identifiers and counts only. The objects themselves are what the reviewer reads; a summary that
    carried their content would put source-derived text into a log, which `trace_ai.observability`
    exists to prevent.
    """
    return {
        "checkpoint_type": package.checkpoint_type.value,
        "objects": len(package.objects),
        "pending": len(package.pending),
        "triggers": list(package.triggers),
        "complete": package.complete,
    }
