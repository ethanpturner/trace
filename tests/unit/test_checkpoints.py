"""Tests for the checkpoint machinery: pausing, resuming, and the shared review package.

DEC-005 makes both human checkpoints structural, and the property that has to be true is stronger
than "the workflow pauses": it has to be *unrepresentable* for the run to advance past an unapproved
checkpoint. So the central test looks for a way through — a configuration value, an environment
variable, an argument — and asserts there is none.

The rest follows from DEC-017. Pausing is stopping: the run persists itself, the process exits, and
resuming is a read in a new process rather than a continuation of one that stayed alive. Everything
here builds a real store, writes state, drops the objects, and reads them back.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.component import Component
from trace_ai.domain.enums import ObjectStatus, ReviewDisposition
from trace_ai.domain.execution import ExecutionType, RunStatus
from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.workflow import Node, NodeContext, NodeResult, Orchestrator, Phase
from trace_ai.workflow.checkpoint import (
    CheckpointNode,
    build_review_package,
    load_state,
    pending_object_ids,
    resume,
    save_state,
    summarize_package,
)
from trace_ai.workflow.state import AssessmentState

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


def paused_state(handle: AssessmentHandle, run_id: str, objects: list[str]) -> AssessmentState:
    started = AssessmentState.begin(assessment_id=handle.assessment_id, workflow_run_id=run_id)
    at_checkpoint = AssessmentState.model_validate(
        started.model_dump()
        | {
            "current_phase": Phase.HUMAN_CONTEXT_REVIEW,
            "next_action": {"action": "execute_node", "phase": Phase.HUMAN_CONTEXT_REVIEW},
        }
    )
    return at_checkpoint.paused_for(Phase.HUMAN_CONTEXT_REVIEW, objects)


def component(
    handle: AssessmentHandle, object_id: str, name: str = "Webhook Receiver"
) -> Component:
    built = Component.model_validate(
        {
            "id": object_id,
            "assessment_id": handle.assessment_id,
            "name": name,
            "component_type": "service",
            "status": ObjectStatus.CANDIDATE,
        }
    )
    with handle.objects.transaction():
        handle.objects.save(built)
    return built


def decide(handle: AssessmentHandle, subject_id: str, subject_type: str = "component") -> None:
    with handle.objects.transaction():
        handle.objects.save(
            ReviewerDecision.model_validate(
                {
                    "id": handle.objects.allocate("dec"),
                    "assessment_id": handle.assessment_id,
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                    "disposition": ReviewDisposition.APPROVE,
                    "created_at": NOW,
                }
            )
        )


# ------------------------------------------------------------------------------------------
# The property the whole design exists for
# ------------------------------------------------------------------------------------------


def test_nothing_advances_the_run_past_an_unapproved_checkpoint(handle: AssessmentHandle) -> None:
    """DEC-005 makes the checkpoints structural and DEC-012 removed the configuration field that
    would have governed them. The property is not "the workflow pauses" — it is that there is no
    way to express not pausing, so this looks for one.

    `AssessmentConfiguration` carries no such field, `CheckpointNode` takes no flag, and the only
    thing that lets the orchestrator advance is every subject having a decision.
    """
    configuration = default_configuration("primary-development", "stride-scenario-based")
    assert not [
        name
        for name in type(configuration).model_fields
        if "review" in name or "checkpoint" in name or "skip" in name
    ]

    node = CheckpointNode(Phase.HUMAN_CONTEXT_REVIEW, subjects=lambda _c: ["cmp-001"])
    assert not [
        name
        for name in type(node).__dataclass_fields__
        if name in {"enabled", "skip", "optional", "required"}
    ]

    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ledger = ExecutionLedger(handle, run)
    later = _Recorder("threat-analysis", Phase.THREAT_GENERATION)
    outcome = Orchestrator(handle, ledger=ledger, nodes=[node, later]).run(
        _state_at(handle, run.id, Phase.HUMAN_CONTEXT_REVIEW)
    )

    assert outcome.paused
    assert later.calls == 0, "the run advanced past an unapproved checkpoint"


@dataclass(slots=True)
class _Recorder:
    """A node that counts how often it ran. Deliberately not a checkpoint."""

    name: str
    phase: Phase
    version: str = "0.1"
    execution_type: ExecutionType = ExecutionType.DETERMINISTIC
    calls: int = 0

    def run(self, _context: NodeContext) -> NodeResult:
        self.calls += 1
        return NodeResult()


def _state_at(handle: AssessmentHandle, run_id: str, phase: Phase) -> AssessmentState:
    started = AssessmentState.begin(assessment_id=handle.assessment_id, workflow_run_id=run_id)
    return AssessmentState.model_validate(
        started.model_dump()
        | {"current_phase": phase, "next_action": {"action": "execute_node", "phase": phase}}
    )


def test_a_checkpoint_node_cannot_be_made_for_any_other_phase() -> None:
    """There are two checkpoints and no configuration adds a third (DEC-005, DEC-012)."""
    with pytest.raises(ValueError, match="structural checkpoints"):
        CheckpointNode(Phase.CONTEXT_EXTRACTION, subjects=lambda _c: [])


def test_a_checkpoint_node_satisfies_the_node_protocol() -> None:
    assert isinstance(CheckpointNode(Phase.HUMAN_CONTEXT_REVIEW, subjects=lambda _c: []), Node)
    assert isinstance(CheckpointNode(Phase.HUMAN_FINDING_REVIEW, subjects=lambda _c: []), Node)


# ------------------------------------------------------------------------------------------
# Pausing and resuming across a process boundary
# ------------------------------------------------------------------------------------------


def test_a_paused_run_persists_what_it_is_waiting_for(handle: AssessmentHandle) -> None:
    """DEC-017: nothing is held in memory across a review, so the pause has to be self-describing
    on disk."""
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    state = paused_state(handle, run.id, ["cmp-001", "cmp-002"])
    path = save_state(handle, state)

    assert path.startswith("traces/")

    restored = load_state(handle, run.id)
    assert restored.status is RunStatus.PAUSED
    assert restored.pending_human_review is not None
    assert restored.pending_human_review.checkpoint_type is Phase.HUMAN_CONTEXT_REVIEW
    assert restored.pending_human_review.object_ids == ["cmp-001", "cmp-002"]


def test_a_state_round_trips_through_persistence(handle: AssessmentHandle) -> None:
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    state = paused_state(handle, run.id, ["cmp-001"])
    save_state(handle, state)
    assert load_state(handle, run.id) == state


def test_resuming_a_run_that_never_paused_says_so(handle: AssessmentHandle) -> None:
    with pytest.raises(FileNotFoundError, match="nothing to resume"):
        resume(handle, "run-404")


def test_resume_reports_what_is_still_pending(handle: AssessmentHandle) -> None:
    """Partial progress is allowed and persisted (section 31): a reviewer who decides two of three
    and closes the laptop has made progress, and the run stays paused."""
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    save_state(handle, paused_state(handle, run.id, ["cmp-001", "cmp-002", "cmp-003"]))
    decide(handle, "cmp-001")
    decide(handle, "cmp-002")

    state, pending = resume(handle, run.id)
    assert state.status is RunStatus.PAUSED
    assert pending == ["cmp-003"]


def test_pending_order_is_the_order_the_reviewer_saw(handle: AssessmentHandle) -> None:
    """A package that reshuffles between sittings is one where "I did the first three" stops being
    a true statement."""
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ordered = ["cmp-003", "cmp-001", "cmp-002"]
    state = paused_state(handle, run.id, ordered)
    save_state(handle, state)
    assert pending_object_ids(handle, state) == ordered


def test_a_checkpoint_completes_only_when_every_subject_is_decided(
    handle: AssessmentHandle,
) -> None:
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ledger = ExecutionLedger(handle, run)
    node = CheckpointNode(Phase.HUMAN_CONTEXT_REVIEW, subjects=lambda _c: ["cmp-001", "cmp-002"])
    following = _Recorder("threat-analysis", Phase.THREAT_GENERATION)

    decide(handle, "cmp-001")
    paused = Orchestrator(handle, ledger=ledger, nodes=[node, following]).run(
        _state_at(handle, run.id, Phase.HUMAN_CONTEXT_REVIEW)
    )
    assert paused.paused
    assert following.calls == 0

    decide(handle, "cmp-002")
    resumed = Orchestrator(
        handle, ledger=ExecutionLedger(handle, run), nodes=[node, following]
    ).run(_state_at(handle, run.id, Phase.HUMAN_CONTEXT_REVIEW))
    assert not resumed.paused
    assert following.calls == 1


def test_a_checkpoint_records_an_execution_and_no_error(handle: AssessmentHandle) -> None:
    """Waiting on a reviewer is not a failure (`current-architecture.md` section 11, DEC-017), and
    it consumes no retry budget — a checkpoint execution is one execution however long it waits."""
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ledger = ExecutionLedger(handle, run)
    node = CheckpointNode(Phase.HUMAN_CONTEXT_REVIEW, subjects=lambda _c: ["cmp-001"])
    Orchestrator(handle, ledger=ledger, nodes=[node]).run(
        _state_at(handle, run.id, Phase.HUMAN_CONTEXT_REVIEW)
    )

    (record,) = ledger.records()
    assert record.execution_type is ExecutionType.HUMAN_CHECKPOINT
    assert record.error_type is None
    assert record.retry_number == 0


def test_resuming_does_not_re_run_completed_work(handle: AssessmentHandle) -> None:
    """A resumed run starts at the phase the state names, so the ledger gains no duplicate records
    for work already done."""
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    earlier = _Recorder("context-validation", Phase.CONTEXT_VALIDATION)
    checkpoint = CheckpointNode(Phase.HUMAN_CONTEXT_REVIEW, subjects=lambda _c: ["cmp-001"])

    first = ExecutionLedger(handle, run)
    Orchestrator(handle, ledger=first, nodes=[earlier, checkpoint]).run(
        _state_at(handle, run.id, Phase.CONTEXT_VALIDATION)
    )
    assert earlier.calls == 1
    assert len(first.records()) == 2

    decide(handle, "cmp-001")
    second = ExecutionLedger(handle, run)
    Orchestrator(handle, ledger=second, nodes=[earlier, checkpoint]).run(
        _state_at(handle, run.id, Phase.HUMAN_CONTEXT_REVIEW)
    )

    assert earlier.calls == 1, "a completed node ran again on resume"
    assert [record.node_name for record in second.records()].count("context-validation") == 1


# ------------------------------------------------------------------------------------------
# The review package
# ------------------------------------------------------------------------------------------


def test_a_package_is_derived_from_the_run_rather_than_stored(handle: AssessmentHandle) -> None:
    """Section 31: the package is derived, so the pause mechanism presupposes no interface. Stored,
    it would be a second copy of objects that already exist and would go stale on the first edit."""
    first = component(handle, "cmp-001")
    second = component(handle, "cmp-002", "Analysis Worker")
    decide(handle, "cmp-001")

    package = build_review_package(
        handle,
        checkpoint_type=Phase.HUMAN_CONTEXT_REVIEW,
        objects=[first, second],
        validation_findings=["cmp-002 has no documented trust boundary"],
        triggers=["low_confidence_claim"],
    )

    assert [item.id for item in package.pending] == ["cmp-002"]
    assert not package.complete
    assert package.triggers == ("low_confidence_claim",)


def test_the_package_is_generic_over_object_type(handle: AssessmentHandle) -> None:
    """Both checkpoints show the same shape and only the type differs, which is what lets the M4
    finding checkpoint reuse this rather than reimplement it."""
    question = Question.model_validate(
        {
            "id": "qst-001",
            "assessment_id": handle.assessment_id,
            "question": "Does webhook validation include HMAC signature verification?",
            "rationale": "Without it the receiver accepts forged deliveries.",
            "priority": QuestionPriority.HIGH,
            "blocking": False,
            "status": QuestionStatus.OPEN,
            "generated_by": "context-extraction-v1",
        }
    )
    package = build_review_package(
        handle, checkpoint_type=Phase.HUMAN_FINDING_REVIEW, objects=[question]
    )
    assert package.pending[0].question.startswith("Does webhook")


def test_a_package_for_a_phase_that_is_not_a_checkpoint_is_refused(
    handle: AssessmentHandle,
) -> None:
    with pytest.raises(ValueError, match="structural checkpoints"):
        build_review_package(handle, checkpoint_type=Phase.THREAT_GENERATION, objects=[])


def test_a_summary_carries_counts_and_never_content(handle: AssessmentHandle) -> None:
    """`trace_ai.observability` exists to keep source-derived text out of a log, and a package
    summary is exactly the shape that would smuggle some in."""
    built = component(handle, "cmp-001", "Managed PostgreSQL holding customer source code")
    summary = summarize_package(
        build_review_package(handle, checkpoint_type=Phase.HUMAN_CONTEXT_REVIEW, objects=[built])
    )

    assert summary == {
        "checkpoint_type": "human_context_review",
        "objects": 1,
        "pending": 1,
        "triggers": [],
        "complete": False,
    }
    assert "customer source code" not in str(summary)


# ------------------------------------------------------------------------------------------
# Recording a decision
# ------------------------------------------------------------------------------------------


def test_an_edit_records_the_generated_state_before_it(handle: AssessmentHandle) -> None:
    """Section 2.5 forbids overwriting generated content silently, and DEC-023 makes the delta what
    turns the overwrite into a record. `capture_edit` takes both states so the prior value cannot be
    read after the edit has already been applied."""
    before = component(handle, "cmp-001")
    after = Component.model_validate(
        before.model_dump() | {"name": "Webhook receiver (public)", "internet_accessible": True}
    )

    decision = ReviewerDecision.capture_edit(
        decision_id="dec-001",
        before=before,
        after=after,
        subject_type="component",
        subject_id=before.id,
        created_at=NOW,
        rationale="The architecture overview shows it behind the CDN.",
    )
    with handle.objects.transaction():
        handle.objects.save(after)
        handle.objects.save(decision)

    stored = handle.objects.get(ReviewerDecision, "dec-001")
    assert stored.disposition is ReviewDisposition.EDIT
    assert stored.prior_value == {"name": "Webhook Receiver", "internet_accessible": None}
    assert handle.objects.get(Component, "cmp-001").internet_accessible is True
