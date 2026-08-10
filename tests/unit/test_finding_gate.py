"""The approved-finding gate, the approved-set accessor, and retention (issue #103, DEC-055).

The acceptance criteria are the spine: an approved finding without a decision cannot be consumed
as approved, a non-carried validation status is refused without an explicit recorded override,
missing remediation and missing evidence are refused outright, rejected and deferred candidates
are retained with reasons and excluded from the approved set, one accessor owns that set, and
zero approved findings is a valid terminal state.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.critique import Critique, CritiqueSubjectType, CritiqueType, RecommendedAction
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    ValidationStatus,
)
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import QuestionPriority
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.findings.approved import (
    ApprovalIntegrityError,
    approved_findings,
    retained_candidates,
)
from trace_ai.workflow.context_review import ReviewerActionError
from trace_ai.workflow.finding_review import (
    approve_finding,
    change_severity,
    conclude_finding_review,
    convert_to_question,
    defer_finding,
    reject_finding,
)

APPROVED_MODULE = Path("src/trace_ai/services/findings/approved.py")
REVIEWER = "reviewer-local"


@pytest.fixture
def service(tmp_path: Any) -> Iterator[AssessmentService]:
    with AssessmentStore.at_root(tmp_path) as store:
        yield AssessmentService(store, artifact_root=tmp_path)


@pytest.fixture
def handle(service: AssessmentService) -> AssessmentHandle:
    from trace_ai.domain.assessment import default_configuration

    created = service.create(
        "Gate", default_configuration("primary-development", "stride-scenario-based")
    )
    return service.handle(created.id)


def finding_payload(handle: AssessmentHandle, **changes: Any) -> dict[str, Any]:
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
        "severity": Severity.HIGH,
        "impact": "Unauthorized job execution and resource exhaustion.",
        "recommendation": "Verify each event with the platform's signature mechanism.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "finding-consolidation-v1",
        "created_at": stamped,
        "updated_at": stamped,
    }
    payload.update(changes)
    return payload


def a_finding(handle: AssessmentHandle, **changes: Any) -> Finding:
    finding = Finding.model_validate(finding_payload(handle, **changes))
    with handle.objects.transaction():
        handle.objects.save(finding)
    return finding


def a_constructed_finding(handle: AssessmentHandle, **changes: Any) -> Finding:
    """A finding built past the validators, for testing the gate's own checks.

    `model_construct` is the only way to hold an object the schema refuses — which is the point:
    the gate must not assume the schema was upstream of every caller (DEC-055).
    """
    return Finding.model_construct(**finding_payload(handle, **changes))


# ------------------------------------------------------------------------------------------
# The gate's refusals
# ------------------------------------------------------------------------------------------


def test_a_non_carried_validation_status_is_refused_without_an_override(
    handle: AssessmentHandle,
) -> None:
    ghost = a_constructed_finding(handle, validation_status=ValidationStatus.UNSUPPORTED)
    with pytest.raises(ReviewerActionError, match="override_rationale"):
        approve_finding(handle, ghost, reviewer_id=REVIEWER)


def test_an_override_passes_the_gate_and_the_schema_still_refuses(
    handle: AssessmentHandle,
) -> None:
    """DEC-055 records the situation: DEC-013 and DEC-050 make an unsupported finding
    unconstructible, so the override converts the gate's refusal into an attempt and the schema
    refuses the object at persistence. The DEC-009 backstop holds twice."""
    from pydantic import ValidationError

    ghost = a_constructed_finding(handle, validation_status=ValidationStatus.UNSUPPORTED)
    with pytest.raises(ValidationError, match="never produces a finding"):
        approve_finding(
            handle,
            ghost,
            reviewer_id=REVIEWER,
            override_rationale="The customer confirmed the weakness out of band.",
        )


def test_a_blank_override_is_no_override(handle: AssessmentHandle) -> None:
    """An override is recorded, never inferred — whitespace does not become a rationale."""
    ghost = a_constructed_finding(handle, validation_status=ValidationStatus.CONTRADICTED)
    with pytest.raises(ReviewerActionError, match="override_rationale"):
        approve_finding(handle, ghost, reviewer_id=REVIEWER, override_rationale="   ")


def test_missing_remediation_is_refused_outright(handle: AssessmentHandle) -> None:
    ghost = a_constructed_finding(handle, recommendation="", acceptance_criteria=[])
    with pytest.raises(ReviewerActionError, match="recommendation"):
        approve_finding(handle, ghost, reviewer_id=REVIEWER)


def test_missing_evidence_is_refused_outright(handle: AssessmentHandle) -> None:
    ghost = a_constructed_finding(handle, evidence_ids=[])
    with pytest.raises(ReviewerActionError, match="DEC-009"):
        approve_finding(handle, ghost, reviewer_id=REVIEWER)


# ------------------------------------------------------------------------------------------
# The accessor: one owner for the approved set
# ------------------------------------------------------------------------------------------


def test_an_approved_finding_without_a_decision_is_refused_by_the_accessor(
    handle: AssessmentHandle,
) -> None:
    """The AC, enforced where consumers read: a row claiming approval nobody recorded cannot be
    consumed as approved, however it was persisted."""
    finding = Finding.model_validate(finding_payload(handle, status=ObjectStatus.APPROVED))
    with handle.objects.transaction():
        handle.objects.save(finding)

    with pytest.raises(ApprovalIntegrityError, match="fnd-001"):
        approved_findings(handle)


def test_the_gate_approves_and_the_accessor_returns_it(handle: AssessmentHandle) -> None:
    finding = a_finding(handle, severity=Severity.UNASSIGNED)
    assigned, _ = change_severity(handle, finding, Severity.HIGH, reviewer_id=REVIEWER)
    approve_finding(handle, assigned, reviewer_id=REVIEWER)

    approved = approved_findings(handle)
    assert [item.id for item in approved] == ["fnd-001"]


def test_zero_approved_findings_is_a_valid_terminal_state(handle: AssessmentHandle) -> None:
    finding = a_finding(handle)
    reject_finding(handle, finding, reviewer_id=REVIEWER, rationale="Not supported on review.")
    assert approved_findings(handle) == []


def test_no_other_module_queries_findings_by_approved_status() -> None:
    """One accessor owns the approved set (DEC-055). Report generation, rendering, and
    evaluation consume it; a module assembling its own approved-set query fails here."""
    offenders = []
    for path in (PROJECT_ROOT / "src").rglob("*.py"):
        if path.resolve() == (PROJECT_ROOT / APPROVED_MODULE).resolve():
            continue
        source = path.read_text(encoding="utf-8")
        if (
            "list(Finding, status=ObjectStatus.APPROVED" in source
            or 'list(Finding, status="approved"' in source
        ):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert not offenders, (
        f"{offenders} query findings by approved status directly; the approved set has one "
        f"accessor, services/findings/approved.py (DEC-055)"
    )


def test_the_accessor_module_makes_no_model_call() -> None:
    source = (PROJECT_ROOT / APPROVED_MODULE).read_text(encoding="utf-8")
    assert "StructuredModel" not in source
    assert "anthropic" not in source


# ------------------------------------------------------------------------------------------
# Retention: rejected, deferred, superseded, merged — with reasons
# ------------------------------------------------------------------------------------------


def test_rejected_and_deferred_candidates_are_retained_with_reasons(
    handle: AssessmentHandle,
) -> None:
    first = a_finding(handle)
    second = a_finding(handle, id="fnd-002", control_mapping_ids=["map-002"])
    reject_finding(
        handle, first, reviewer_id=REVIEWER, rationale="The cited passage describes intent."
    )
    defer_finding(
        handle, second, reviewer_id=REVIEWER, rationale="Waiting on the deployment manifest."
    )

    retained = {item.finding.id: item for item in retained_candidates(handle)}
    assert retained["fnd-001"].disposition == "rejected"
    assert "describes intent" in retained["fnd-001"].reason
    assert retained["fnd-002"].disposition == "deferred"
    assert "deployment manifest" in retained["fnd-002"].reason
    assert approved_findings(handle) == []


def test_a_critique_driven_rejection_carries_the_critique_as_its_reason(
    handle: AssessmentHandle,
) -> None:
    """DEC-053 deferred the persisted linkage for consolidation's rejections here: the finding
    is `rejected` in the store, and the rejecting critique is the retrievable reason."""
    rejected = Finding.model_validate(finding_payload(handle, status=ObjectStatus.REJECTED))
    critique = Critique.model_validate(
        {
            "id": "crq-001",
            "assessment_id": handle.assessment_id,
            "subject_type": CritiqueSubjectType.FINDING,
            "subject_id": rejected.id,
            "critique_type": CritiqueType.UNSUPPORTED_CLAIM,
            "description": "The cited passage does not establish the weakness.",
            "rationale": "No passage names the mechanism.",
            "recommended_action": RecommendedAction.REJECT,
            "confidence": ConfidenceLevel.MEDIUM,
            "status": ObjectStatus.CANDIDATE,
            "generated_by": "critical-review-v1",
        }
    )
    with handle.objects.transaction():
        handle.objects.save(rejected)
        handle.objects.save(critique)

    (retained,) = retained_candidates(handle)
    assert retained.disposition == "rejected"
    assert "crq-001" in retained.reason


def test_converted_and_merged_candidates_are_retained(handle: AssessmentHandle) -> None:
    first = a_finding(handle)
    convert_to_question(
        handle,
        first,
        question="Which service verifies webhook signatures, if any?",
        question_rationale="The answer decides whether the finding stands.",
        priority=QuestionPriority.HIGH,
        blocking=False,
        reviewer_id=REVIEWER,
    )
    a_finding(handle, id="fnd-002", duplicate_of_id="fnd-001", severity=Severity.HIGH)

    retained = {item.finding.id: item for item in retained_candidates(handle)}
    assert retained["fnd-001"].disposition == "superseded"
    assert retained["fnd-002"].disposition == "merged"
    assert "fnd-001" in retained["fnd-002"].reason


# ------------------------------------------------------------------------------------------
# The assessment advances through the existing verb (DEC-031)
# ------------------------------------------------------------------------------------------


def test_conclude_refuses_while_a_finding_is_undecided(
    service: AssessmentService, handle: AssessmentHandle
) -> None:
    a_finding(handle)
    service.begin_review(handle.assessment_id)
    with pytest.raises(ReviewerActionError, match="fnd-001"):
        conclude_finding_review(service, handle.assessment_id)


def test_conclude_advances_the_assessment_once_everything_is_decided(
    service: AssessmentService, handle: AssessmentHandle
) -> None:
    finding = a_finding(handle)
    service.begin_review(handle.assessment_id)
    reject_finding(handle, finding, reviewer_id=REVIEWER, rationale="Not supported on review.")

    concluded = conclude_finding_review(service, handle.assessment_id)
    assert concluded.status is ObjectStatus.DRAFT, (
        "resume_from_review: the run continues to report generation (DEC-031)"
    )
    assert approved_findings(handle) == [], "zero approved findings is a valid terminal state"


def test_a_disposition_of_every_kind_counts_as_decided(
    service: AssessmentService, handle: AssessmentHandle
) -> None:
    """Deferral is a decision for completion purposes; the deferred finding stays a candidate
    and is retained, not lost."""
    finding = a_finding(handle)
    service.begin_review(handle.assessment_id)
    defer_finding(handle, finding, reviewer_id=REVIEWER, rationale="Next sitting.")

    concluded = conclude_finding_review(service, handle.assessment_id)
    assert concluded.status is ObjectStatus.DRAFT
    assert retained_candidates(handle)[0].disposition == "deferred"
