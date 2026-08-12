"""Checkpoint 2: the finding-approval checkpoint and the reviewer's actions (issue #102).

The acceptance criteria are the spine: the workflow does not advance without a decision per
provisional finding, an interrupted run resumes without loss, each of section 18's actions
produces a `ReviewerDecision`, an edit preserves the generated value, a reviewer merge writes
the same record shape as an automated one, approval refuses an unassigned severity, and an
assessment where nothing is approved passes the checkpoint.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    ReviewDisposition,
    RiskTreatment,
    Severity,
    ValidationStatus,
)
from trace_ai.domain.execution import RunStatus
from trace_ai.domain.finding import Finding
from trace_ai.domain.finding_merge_record import FindingMergeRecord, MergeDecision
from trace_ai.domain.question import Question, QuestionPriority
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.workflow.checkpoint import load_state, resume, save_state
from trace_ai.workflow.context_review import ReviewerActionError
from trace_ai.workflow.finding_review import (
    FindingReviewNode,
    add_remediation_guidance,
    add_reviewer_rationale,
    approve_finding,
    assign_risk_treatment,
    change_severity,
    convert_to_documentation_gap,
    convert_to_question,
    defer_finding,
    edit_finding,
    merge_by_reviewer,
    reject_finding,
    request_more_analysis,
)
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.state import AssessmentState, NextAction, PendingHumanReview

MODULE = PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "finding_review.py"

REVIEWER = "reviewer-local"


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Checkpoint", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


def a_finding(handle: AssessmentHandle, **changes: Any) -> Finding:
    stamped = now()
    payload: dict[str, Any] = {
        "id": "fnd-001",
        "assessment_id": handle.assessment_id,
        "title": "Webhook requests may be processed without verified authenticity",
        "summary": "The receiver may accept events without verifying their origin.",
        "description": "The documents describe validation as structural, not cryptographic.",
        "threat_ids": ["thr-001"],
        "requirement_ids": ["req-WEBHOOK-001"],
        "control_mapping_ids": ["map-001"],
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "evidence_ids": ["evd-001"],
        "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
        "severity": Severity.UNASSIGNED,
        "impact": "Unauthorized job execution and resource exhaustion.",
        "recommendation": "Verify each event with the platform's signature mechanism.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "finding-consolidation-v1",
        "created_at": stamped,
        "updated_at": stamped,
    }
    payload.update(changes)
    finding = Finding.model_validate(payload)
    with handle.objects.transaction():
        handle.objects.save(finding)
    return finding


def a_state(handle: AssessmentHandle, finding_ids: list[str], run_id: str = "run-001") -> Any:
    return AssessmentState.model_validate(
        {
            "assessment_id": handle.assessment_id,
            "workflow_run_id": run_id,
            "status": RunStatus.PAUSED,
            "current_phase": Phase.HUMAN_FINDING_REVIEW,
            "next_action": NextAction.model_validate(
                {"action": "await_human_review", "phase": Phase.HUMAN_FINDING_REVIEW}
            ),
            "candidate_finding_ids": finding_ids,
            "pending_human_review": PendingHumanReview.model_validate(
                {
                    "checkpoint_type": Phase.HUMAN_FINDING_REVIEW,
                    "object_ids": finding_ids,
                }
            )
            if finding_ids
            else None,
        }
    )


# ------------------------------------------------------------------------------------------
# The checkpoint: no advance without a decision per finding
# ------------------------------------------------------------------------------------------


def test_the_checkpoint_waits_on_every_provisional_finding(handle: AssessmentHandle) -> None:
    first = a_finding(handle)
    second = a_finding(handle, id="fnd-002")
    state = a_state(handle, [first.id, second.id])

    result = FindingReviewNode().run(NodeContext(handle=handle, state=state))
    assert result.awaiting_review == ["fnd-001", "fnd-002"]

    change_severity(handle, first, Severity.HIGH, reviewer_id=REVIEWER)
    approve_finding(handle, handle.objects.get(Finding, first.id), reviewer_id=REVIEWER)
    result = FindingReviewNode().run(NodeContext(handle=handle, state=state))
    assert result.awaiting_review == ["fnd-002"], "one decided, one still waiting"


def test_rejecting_everything_completes_the_checkpoint(handle: AssessmentHandle) -> None:
    """Approving nothing is a valid outcome: the checkpoint completes on decisions, not
    approvals, and the report proceeds with an empty approved set."""
    first = a_finding(handle)
    second = a_finding(handle, id="fnd-002")
    state = a_state(handle, [first.id, second.id])

    reject_finding(handle, first, reviewer_id=REVIEWER)
    reject_finding(handle, second, reviewer_id=REVIEWER)

    result = FindingReviewNode().run(NodeContext(handle=handle, state=state))
    assert result.awaiting_review == []
    assert not handle.objects.list(Finding, status=ObjectStatus.APPROVED.value)


def test_an_interrupted_run_resumes_at_the_same_point_with_nothing_lost(
    handle: AssessmentHandle,
) -> None:
    first = a_finding(handle)
    second = a_finding(handle, id="fnd-002")
    state = a_state(handle, [first.id, second.id])
    save_state(handle, state)

    reject_finding(handle, first, reviewer_id=REVIEWER, workflow_run_id="run-001")

    # A new invocation: read the persisted state back (DEC-017) and pick up where it paused.
    reloaded, pending = resume(handle, "run-001")
    assert reloaded == load_state(handle, "run-001")
    assert pending == ["fnd-002"], "the decided finding is done; the other is still waiting"
    assert handle.objects.get(Finding, first.id).status is ObjectStatus.REJECTED
    assert handle.objects.get(Finding, second.id).status is ObjectStatus.CANDIDATE


# ------------------------------------------------------------------------------------------
# The severity rule (DEC-030)
# ------------------------------------------------------------------------------------------


def test_approval_with_unassigned_severity_is_refused(handle: AssessmentHandle) -> None:
    finding = a_finding(handle)
    with pytest.raises(ReviewerActionError, match="DEC-030"):
        approve_finding(handle, finding, reviewer_id=REVIEWER)


def test_severity_then_approval_works_and_both_are_recorded(handle: AssessmentHandle) -> None:
    finding = a_finding(handle)
    assigned, severity_decision = change_severity(
        handle, finding, Severity.HIGH, reviewer_id=REVIEWER, workflow_run_id="run-001"
    )
    approved, approval = approve_finding(
        handle, assigned, reviewer_id=REVIEWER, workflow_run_id="run-001"
    )

    assert severity_decision.disposition is ReviewDisposition.EDIT
    assert severity_decision.prior_value is not None
    assert severity_decision.prior_value["severity"] == "unassigned"
    assert severity_decision.updated_value is not None
    assert severity_decision.updated_value["severity"] == "high"
    assert approval.disposition is ReviewDisposition.APPROVE
    assert approval.workflow_run_id == "run-001"
    assert approved.status is ObjectStatus.APPROVED


def test_severity_cannot_be_unassigned_again(handle: AssessmentHandle) -> None:
    finding = a_finding(handle, severity=Severity.HIGH)
    with pytest.raises(ReviewerActionError, match="unassign"):
        change_severity(handle, finding, Severity.UNASSIGNED, reviewer_id=REVIEWER)


# ------------------------------------------------------------------------------------------
# Risk treatment (DEC-060): reviewer-assigned, undecided survives, accept needs a rationale
# ------------------------------------------------------------------------------------------


def test_a_finding_is_created_undecided(handle: AssessmentHandle) -> None:
    assert a_finding(handle).risk_treatment is RiskTreatment.UNDECIDED


def test_undecided_treatment_does_not_block_approval(handle: AssessmentHandle) -> None:
    """Unlike severity, treatment never gates approval; an undecided finding still approves."""
    finding = a_finding(handle, severity=Severity.HIGH)
    approved, _ = approve_finding(handle, finding, reviewer_id=REVIEWER)
    assert approved.status is ObjectStatus.APPROVED
    assert approved.risk_treatment is RiskTreatment.UNDECIDED


def test_approval_of_accept_without_a_rationale_is_refused(handle: AssessmentHandle) -> None:
    finding = a_finding(handle, severity=Severity.HIGH, risk_treatment=RiskTreatment.ACCEPT)
    with pytest.raises(ReviewerActionError, match="DEC-060"):
        approve_finding(handle, finding, reviewer_id=REVIEWER)


def test_a_non_accept_treatment_approves_without_a_rationale(handle: AssessmentHandle) -> None:
    finding = a_finding(handle, severity=Severity.HIGH, risk_treatment=RiskTreatment.MITIGATE)
    approved, _ = approve_finding(handle, finding, reviewer_id=REVIEWER)
    assert approved.status is ObjectStatus.APPROVED


def test_accept_with_a_rationale_is_assigned_as_an_edit_then_approves(
    handle: AssessmentHandle,
) -> None:
    finding = a_finding(handle, severity=Severity.HIGH)
    treated, decision = assign_risk_treatment(
        handle,
        finding,
        RiskTreatment.ACCEPT,
        rationale="Residual exposure is bounded to internal callers and accepted by the owner.",
        reviewer_id=REVIEWER,
        workflow_run_id="run-001",
    )
    assert decision.disposition is ReviewDisposition.EDIT
    assert decision.prior_value is not None
    assert decision.prior_value["risk_treatment"] == "undecided"
    assert decision.updated_value is not None
    assert decision.updated_value["risk_treatment"] == "accept"
    assert treated.risk_treatment is RiskTreatment.ACCEPT

    approved, approval = approve_finding(handle, treated, reviewer_id=REVIEWER)
    assert approval.disposition is ReviewDisposition.APPROVE
    assert approved.status is ObjectStatus.APPROVED


def test_a_review_by_date_is_recorded_with_the_treatment(handle: AssessmentHandle) -> None:
    from datetime import date

    finding = a_finding(handle, severity=Severity.HIGH)
    treated, _ = assign_risk_treatment(
        handle,
        finding,
        RiskTreatment.ACCEPT,
        rationale="Owner accepts the residual risk.",
        review_by=date(2027, 1, 1),
        reviewer_id=REVIEWER,
    )
    assert treated.treatment_review_by == date(2027, 1, 1)


# ------------------------------------------------------------------------------------------
# Episodic revisit (DEC-061, DEC-079): an expired acceptance re-enters, run-scoped completion
# ------------------------------------------------------------------------------------------


def _prior_decision(handle: AssessmentHandle, subject_id: str, run_id: str | None) -> None:
    from trace_ai.domain.reviewer_decision import ReviewerDecision

    decision = ReviewerDecision.model_validate(
        {
            "id": handle.objects.allocate("dec"),
            "assessment_id": handle.assessment_id,
            "subject_type": "finding",
            "subject_id": subject_id,
            "disposition": ReviewDisposition.APPROVE,
            "reviewer_id": REVIEWER,
            "created_at": now(),
            "workflow_run_id": run_id,
        }
    )
    with handle.objects.transaction():
        handle.objects.save(decision)


def test_decided_is_scoped_to_the_current_run(handle: AssessmentHandle) -> None:
    from trace_ai.workflow.checkpoint import decided_in_run

    finding = a_finding(handle, severity=Severity.HIGH)
    _prior_decision(handle, finding.id, run_id="run-000")
    assert finding.id not in decided_in_run(handle, "run-001"), "a prior run's decision is history"
    assert finding.id in decided_in_run(handle, "run-000"), "its own run counts it"

    other = a_finding(handle, id="fnd-002", severity=Severity.HIGH)
    _prior_decision(handle, other.id, run_id=None)
    assert other.id in decided_in_run(handle, "run-001"), "a run-less decision stays current"


def test_an_expired_acceptance_is_revisit_due_and_re_enters(handle: AssessmentHandle) -> None:
    from datetime import date, timedelta

    from trace_ai.workflow.reason_codes import revisit_due_findings

    finding = a_finding(
        handle,
        severity=Severity.HIGH,
        status=ObjectStatus.APPROVED,
        risk_treatment=RiskTreatment.ACCEPT,
        treatment_rationale="Owner accepted the residual risk last quarter.",
        treatment_review_by=date.today() - timedelta(days=1),
    )
    _prior_decision(handle, finding.id, run_id="run-000")

    assert finding.id in revisit_due_findings(handle, date.today())
    # On a new run the finding is a subject again, and its prior-run approval does not satisfy it.
    state = a_state(handle, [finding.id], run_id="run-001")
    result = FindingReviewNode().run(NodeContext(handle=handle, state=state))
    assert result.awaiting_review == [finding.id]


def test_an_unexpired_acceptance_does_not_re_prompt(handle: AssessmentHandle) -> None:
    from datetime import date, timedelta

    from trace_ai.workflow.reason_codes import revisit_due_findings

    finding = a_finding(
        handle,
        severity=Severity.HIGH,
        status=ObjectStatus.APPROVED,
        risk_treatment=RiskTreatment.ACCEPT,
        treatment_rationale="Accepted, revisit next year.",
        treatment_review_by=date.today() + timedelta(days=90),
    )
    assert finding.id not in revisit_due_findings(handle, date.today())


def test_re_deciding_in_the_current_run_completes_the_revisit(handle: AssessmentHandle) -> None:
    from datetime import date, timedelta

    finding = a_finding(
        handle,
        severity=Severity.HIGH,
        status=ObjectStatus.APPROVED,
        risk_treatment=RiskTreatment.ACCEPT,
        treatment_rationale="Prior acceptance.",
        treatment_review_by=date.today() - timedelta(days=1),
    )
    _prior_decision(handle, finding.id, run_id="run-000")
    # A fresh decision in the current run satisfies the checkpoint; the prior accept still stands.
    reject_finding(handle, finding, reviewer_id=REVIEWER, workflow_run_id="run-001")
    state = a_state(handle, [finding.id], run_id="run-001")
    result = FindingReviewNode().run(NodeContext(handle=handle, state=state))
    assert result.awaiting_review == []


def test_a_merged_duplicate_cannot_be_approved(handle: AssessmentHandle) -> None:
    a_finding(handle)
    duplicate = a_finding(handle, id="fnd-002", severity=Severity.HIGH, duplicate_of_id="fnd-001")
    with pytest.raises(ReviewerActionError, match="merged into"):
        approve_finding(handle, duplicate, reviewer_id=REVIEWER)


# ------------------------------------------------------------------------------------------
# Edits preserve the generated value (DEC-023)
# ------------------------------------------------------------------------------------------


def test_an_edit_preserves_the_generated_value_and_it_is_recoverable(
    handle: AssessmentHandle,
) -> None:
    finding = a_finding(handle)
    generated = finding.impact
    edited, decision = edit_finding(
        handle,
        finding,
        {"impact": "Unauthorized job execution only; exhaustion is bounded by the queue."},
        reviewer_id=REVIEWER,
        workflow_run_id="run-001",
    )

    assert decision.disposition is ReviewDisposition.EDIT
    assert decision.prior_value is not None
    assert decision.prior_value["impact"] == generated, "the original is recoverable"
    assert decision.updated_value is not None
    assert decision.updated_value["impact"] == edited.impact
    assert decision.workflow_run_id == "run-001"
    assert handle.objects.get(Finding, finding.id).impact == edited.impact


def test_add_reviewer_rationale_and_remediation_guidance_are_edits(
    handle: AssessmentHandle,
) -> None:
    finding = a_finding(handle)
    noted, note_decision = add_reviewer_rationale(
        handle, finding, "Confirmed against the deployment notes.", reviewer_id=REVIEWER
    )
    guided, guide_decision = add_remediation_guidance(
        handle,
        noted,
        "Adopt provider signature verification with key rotation.",
        reviewer_id=REVIEWER,
    )

    assert note_decision.disposition is ReviewDisposition.EDIT
    assert noted.reviewer_notes == "Confirmed against the deployment notes."
    assert guide_decision.disposition is ReviewDisposition.EDIT
    assert guide_decision.prior_value is not None
    assert guide_decision.prior_value["recommendation"] == finding.recommendation
    assert guided.recommendation.startswith("Adopt provider signature")


# ------------------------------------------------------------------------------------------
# Defer, request more analysis, conversions
# ------------------------------------------------------------------------------------------


def test_defer_records_a_decision_and_changes_nothing(handle: AssessmentHandle) -> None:
    finding = a_finding(handle)
    unchanged, decision = defer_finding(
        handle, finding, reviewer_id=REVIEWER, workflow_run_id="run-001"
    )
    assert decision.disposition is ReviewDisposition.DEFER
    assert unchanged == finding
    assert handle.objects.get(Finding, finding.id).status is ObjectStatus.CANDIDATE


def test_request_more_analysis_requires_a_reason(handle: AssessmentHandle) -> None:
    finding = a_finding(handle)
    with pytest.raises(ReviewerActionError, match="repetition"):
        request_more_analysis(handle, finding, reviewer_id=REVIEWER, rationale="  ")
    _, decision = request_more_analysis(
        handle, finding, reviewer_id=REVIEWER, rationale="Check the deployment manifests."
    )
    assert decision.disposition is ReviewDisposition.REQUEST_MORE_ANALYSIS


def test_convert_to_question_uses_the_helper_and_records_the_disposition(
    handle: AssessmentHandle,
) -> None:
    finding = a_finding(handle)
    asked, superseded, decision = convert_to_question(
        handle,
        finding,
        question="Which service verifies webhook signatures, if any?",
        question_rationale="The answer decides whether the finding stands.",
        priority=QuestionPriority.HIGH,
        blocking=False,
        reviewer_id=REVIEWER,
    )
    assert isinstance(asked, Question)
    assert asked.converted_from_id == finding.id
    assert superseded.status is ObjectStatus.SUPERSEDED
    assert decision.disposition is ReviewDisposition.CONVERT_TO_QUESTION
    assert handle.objects.get(Finding, finding.id).status is ObjectStatus.SUPERSEDED


def test_convert_to_documentation_gap_uses_the_helper_and_records_the_disposition(
    handle: AssessmentHandle,
) -> None:
    finding = a_finding(handle)
    gap, superseded, decision = convert_to_documentation_gap(
        handle,
        finding,
        importance="Whether verification exists cannot be determined from the documents.",
        severity=Severity.MEDIUM,
        reviewer_id=REVIEWER,
    )
    assert isinstance(gap, DocumentationGap)
    assert gap.converted_from_id == finding.id
    assert gap.severity is Severity.MEDIUM
    assert decision.disposition is ReviewDisposition.CONVERT_TO_DOCUMENTATION_GAP
    assert superseded.status is ObjectStatus.SUPERSEDED


# ------------------------------------------------------------------------------------------
# The reviewer merge (DEC-054)
# ------------------------------------------------------------------------------------------


def test_a_reviewer_merge_produces_the_same_record_shape_as_an_automated_one(
    handle: AssessmentHandle,
) -> None:
    a_finding(handle)
    a_finding(
        handle,
        id="fnd-002",
        threat_ids=["thr-002"],
        requirement_ids=["req-TLS-001"],
        control_mapping_ids=["map-002"],
        evidence_ids=["evd-002"],
    )

    _, record, decisions = merge_by_reviewer(
        handle,
        "fnd-001",
        ["fnd-002"],
        reviewer_id=REVIEWER,
        rationale="Both describe the same missing verification, reworded.",
        workflow_run_id="run-001",
    )

    assert isinstance(record, FindingMergeRecord)
    assert record.decision is MergeDecision.REVIEWER
    assert record.surviving_finding_id == "fnd-001"
    assert record.merged_finding_ids == ["fnd-002"]
    assert record.id.startswith("mrg-")
    assert handle.objects.get(FindingMergeRecord, record.id) == record

    survivor = handle.objects.get(Finding, "fnd-001")
    assert survivor.evidence_ids == ["evd-001", "evd-002"], "the same unions as the rule's merge"
    merged = handle.objects.get(Finding, "fnd-002")
    assert merged.duplicate_of_id == "fnd-001"

    assert all(decision.disposition is ReviewDisposition.EDIT for decision in decisions)
    edited_subjects = {decision.subject_id for decision in decisions}
    assert edited_subjects == {"fnd-001", "fnd-002"}
    by_subject = {decision.subject_id: decision for decision in decisions}
    assert by_subject["fnd-002"].prior_value is not None
    assert by_subject["fnd-002"].prior_value["duplicate_of_id"] is None
    assert by_subject["fnd-002"].updated_value is not None
    assert by_subject["fnd-002"].updated_value["duplicate_of_id"] == "fnd-001"


def test_a_reviewer_merge_with_no_shared_features_is_recordable(
    handle: AssessmentHandle,
) -> None:
    """The DEC-054 case: nothing structural matched, and the rationale is the reason."""
    a_finding(handle)
    a_finding(
        handle,
        id="fnd-002",
        threat_ids=["thr-002"],
        requirement_ids=["req-TLS-001"],
        control_mapping_ids=["map-002"],
        affected_component_ids=["cmp-002"],
        affected_asset_ids=["ast-002"],
        evidence_ids=["evd-002"],
    )
    _, record, _ = merge_by_reviewer(
        handle,
        "fnd-001",
        ["fnd-002"],
        reviewer_id=REVIEWER,
        rationale="One weakness described from two documents.",
    )
    assert record.matched_features == []
    assert record.decision is MergeDecision.REVIEWER


def test_a_reviewer_merge_requires_a_rationale(handle: AssessmentHandle) -> None:
    a_finding(handle)
    a_finding(handle, id="fnd-002")
    with pytest.raises(ReviewerActionError, match="rationale"):
        merge_by_reviewer(handle, "fnd-001", ["fnd-002"], reviewer_id=REVIEWER, rationale=" ")


def test_a_merge_naming_a_missing_finding_is_refused(handle: AssessmentHandle) -> None:
    a_finding(handle)
    with pytest.raises(ReviewerActionError, match="fnd-099"):
        merge_by_reviewer(
            handle, "fnd-001", ["fnd-099"], reviewer_id=REVIEWER, rationale="One finding."
        )


# ------------------------------------------------------------------------------------------
# No model, no configuration escape
# ------------------------------------------------------------------------------------------


def test_the_checkpoint_makes_no_model_call() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "StructuredModel" not in source
    assert "anthropic" not in source


def test_the_node_consults_no_configuration() -> None:
    """DEC-012: no configuration field governs a checkpoint; the module never reads one, and
    the node's constructor accepts nothing that could change the completion condition."""
    source = MODULE.read_text(encoding="utf-8")
    assert "AssessmentConfiguration" not in source

    import inspect

    parameters = inspect.signature(FindingReviewNode).parameters
    assert set(parameters) == {"version"}, "no flag, no skip, nothing to pass"


def test_the_node_is_the_one_the_phase_registry_lists() -> None:
    from trace_ai.workflow.phases import NODES_BY_PHASE

    assert FindingReviewNode().name in NODES_BY_PHASE[Phase.HUMAN_FINDING_REVIEW]
