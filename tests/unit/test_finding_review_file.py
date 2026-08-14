"""The finding review file (#351): export, edit, apply.

The properties under test are the context file's, carried over: the file is derived, an
unchanged file applies nothing, an edited file writes the same `ReviewerDecision` rows as the
equivalent flags, and the conversion-or-decision rule refuses the combination.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

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
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import Question
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.findings.review_file import (
    apply_finding_review_file,
    export_finding_review_file,
    read_finding_review_file,
    write_finding_review_file,
)
from trace_ai.services.findings.review_package import build_finding_review_package
from trace_ai.workflow.finding_review import approve_finding, change_severity

REVIEWER = "reviewer-local"


def a_finding(handle: AssessmentHandle, **changes: Any) -> Finding:
    """A candidate finding, mirroring `test_finding_review.py`'s factory."""
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


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Review", default_configuration("offline-fake", "stride-scenario-based")
        )
        yield service.handle(created.id)


def exported(handle: AssessmentHandle) -> dict[str, Any]:
    package = build_finding_review_package(handle, index=EvidenceIndex(handle))
    return export_finding_review_file(package)


def dispositions(handle: AssessmentHandle) -> list[str]:
    return [
        decision.disposition.value
        for decision in handle.objects.list(ReviewerDecision)
        if decision.subject_type == "finding"
    ]


def test_an_unchanged_file_applies_nothing(handle: AssessmentHandle) -> None:
    a_finding(handle)
    document = exported(handle)
    assert apply_finding_review_file(handle, document, reviewer_id=REVIEWER) == []
    assert dispositions(handle) == []


def test_the_written_file_round_trips_through_the_reader(handle: AssessmentHandle) -> None:
    a_finding(handle)
    package = build_finding_review_package(handle, index=EvidenceIndex(handle))
    text = write_finding_review_file(package)
    assert read_finding_review_file(text) == export_finding_review_file(package)


def test_an_edited_file_records_the_same_decisions_as_the_flags(handle: AssessmentHandle) -> None:
    """The acceptance criterion: file and flags write identical rows, because both call the
    same functions. The file path runs here; the flag path is the same two calls made
    directly, compared by disposition and subject."""
    a_finding(handle)
    a_finding(handle, id="fnd-002")

    document = exported(handle)
    document["findings"][0]["severity"] = "medium"
    document["findings"][0]["decision"] = "approve"
    document["findings"][1]["decision"] = "reject"
    document["findings"][1]["rationale"] = "rests on silence"
    applied = apply_finding_review_file(handle, document, reviewer_id=REVIEWER)
    assert [d.disposition for d in applied] == [
        ReviewDisposition.EDIT,  # the severity assignment is recorded as an edit (DEC-030)
        ReviewDisposition.APPROVE,
        ReviewDisposition.REJECT,
    ]
    assert [d.subject_id for d in applied] == ["fnd-001", "fnd-001", "fnd-002"]

    # The flag path, on a fresh pair, produces the same rows.
    a_finding(handle, id="fnd-003")
    updated, severity_decision = change_severity(
        handle, handle.objects.get(Finding, "fnd-003"), Severity.MEDIUM, reviewer_id=REVIEWER
    )
    _, approve_decision = approve_finding(handle, updated, reviewer_id=REVIEWER)
    assert severity_decision.disposition is ReviewDisposition.EDIT
    assert approve_decision.disposition is ReviewDisposition.APPROVE


def test_defer_and_request_more_analysis_apply_from_the_file(handle: AssessmentHandle) -> None:
    a_finding(handle)
    a_finding(handle, id="fnd-002")
    document = exported(handle)
    document["findings"][0]["decision"] = "defer"
    document["findings"][1]["decision"] = "request_more_analysis"
    document["findings"][1]["rationale"] = "the mapping cites one document; check the runbook"
    applied = apply_finding_review_file(handle, document, reviewer_id=REVIEWER)
    assert [d.disposition for d in applied] == [
        ReviewDisposition.DEFER,
        ReviewDisposition.REQUEST_MORE_ANALYSIS,
    ]


def test_request_more_analysis_without_a_rationale_is_refused(handle: AssessmentHandle) -> None:
    a_finding(handle)
    document = exported(handle)
    document["findings"][0]["decision"] = "request_more_analysis"
    with pytest.raises(ValueError, match="what is missing"):
        apply_finding_review_file(handle, document, reviewer_id=REVIEWER)


def test_treatment_rationale_and_remediation_reach_their_actions(
    handle: AssessmentHandle,
) -> None:
    a_finding(handle)
    document = exported(handle)
    entry = document["findings"][0]
    entry["treatment"] = "accept"
    entry["treatment_rationale"] = "exposure is bounded by the internal network"
    entry["treatment_review_by"] = "2026-11-01"
    entry["reviewer_rationale"] = "confirmed against the runbook"
    entry["editable"]["recommendation"] = "Enable the provider's signing feature."
    apply_finding_review_file(handle, document, reviewer_id=REVIEWER)

    finding = handle.objects.get(Finding, "fnd-001")
    assert finding.risk_treatment is RiskTreatment.ACCEPT
    assert finding.treatment_rationale == "exposure is bounded by the internal network"
    assert finding.reviewer_notes == "confirmed against the runbook"
    assert finding.recommendation == "Enable the provider's signing feature."


def test_a_conversion_block_converts_and_supersedes(handle: AssessmentHandle) -> None:
    a_finding(handle)
    document = exported(handle)
    document["findings"][0]["convert_to_question"] = {
        "question": "Is the validation cryptographic?",
        "rationale": "the documents say validated without saying how",
        "priority": "high",
        "blocking": False,
    }
    applied = apply_finding_review_file(handle, document, reviewer_id=REVIEWER)
    assert [d.disposition for d in applied] == [ReviewDisposition.CONVERT_TO_QUESTION]
    assert handle.objects.get(Finding, "fnd-001").status is ObjectStatus.SUPERSEDED
    assert any(
        question.question == "Is the validation cryptographic?"
        for question in handle.objects.list(Question)
    )


def test_a_gap_conversion_carries_importance_and_severity(handle: AssessmentHandle) -> None:
    a_finding(handle)
    document = exported(handle)
    document["findings"][0]["convert_to_documentation_gap"] = {
        "importance": "whether the control exists cannot be determined",
        "severity": "medium",
        "requested_evidence": ["the signature configuration"],
    }
    applied = apply_finding_review_file(handle, document, reviewer_id=REVIEWER)
    assert [d.disposition for d in applied] == [ReviewDisposition.CONVERT_TO_DOCUMENTATION_GAP]
    gaps = handle.objects.list(DocumentationGap)
    assert len(gaps) == 1
    assert gaps[0].requested_evidence == ["the signature configuration"]


def test_a_conversion_beside_a_decision_is_refused(handle: AssessmentHandle) -> None:
    a_finding(handle)
    document = exported(handle)
    document["findings"][0]["decision"] = "approve"
    document["findings"][0]["convert_to_question"] = {
        "question": "Is it?",
        "rationale": "unclear",
        "priority": "medium",
        "blocking": False,
    }
    with pytest.raises(ValueError, match="conversion and a decision"):
        apply_finding_review_file(handle, document, reviewer_id=REVIEWER)


def test_a_reviewer_merge_applies_before_decisions(handle: AssessmentHandle) -> None:
    a_finding(handle)
    a_finding(handle, id="fnd-002")
    document = exported(handle)
    document["merges"] = [
        {
            "survivor": "fnd-001",
            "merged": ["fnd-002"],
            "rationale": "one weakness stated twice, once per document",
        }
    ]
    document["findings"][0]["severity"] = "medium"
    document["findings"][0]["decision"] = "approve"
    applied = apply_finding_review_file(handle, document, reviewer_id=REVIEWER)
    assert handle.objects.get(Finding, "fnd-002").duplicate_of_id == "fnd-001"
    assert applied[-1].disposition is ReviewDisposition.APPROVE
    assert applied[-1].subject_id == "fnd-001"


def test_a_file_for_another_assessment_is_refused(handle: AssessmentHandle) -> None:
    a_finding(handle)
    document = exported(handle)
    document["assessment_id"] = "asm-999"
    with pytest.raises(ValueError, match="asm-999"):
        apply_finding_review_file(handle, document, reviewer_id=REVIEWER)


def test_the_package_renders_recorded_decisions(handle: AssessmentHandle) -> None:
    """#351: a deferred finding shows its deferral when the reviewer returns to it."""
    from trace_ai.services.findings.review_package import render_markdown
    from trace_ai.workflow.finding_review import defer_finding

    finding = a_finding(handle)
    defer_finding(handle, finding, reviewer_id=REVIEWER, rationale="waiting on the runbook")
    package = build_finding_review_package(handle, index=EvidenceIndex(handle))
    rendered = render_markdown(package)
    assert "Decisions recorded: defer by reviewer-local — waiting on the runbook" in rendered


def test_every_reviewer_action_is_reachable_from_the_cli() -> None:
    """The acceptance criterion (#351): every action in `finding_review.__all__` — minus the
    checkpoint node and its subject helper, which are the workflow's, not a reviewer's — is
    called from the CLI surface: a flag in `cli.py` or a review-file entry in
    `review_file.py`, both of which route through the same functions."""
    import inspect

    from trace_ai import cli
    from trace_ai.services.findings import review_file
    from trace_ai.workflow import finding_review

    surface = inspect.getsource(cli) + inspect.getsource(review_file)
    actions = set(finding_review.__all__) - {"FindingReviewNode", "finding_review_subjects"}
    unreachable = sorted(action for action in actions if action not in surface)
    assert not unreachable, f"no CLI route calls: {unreachable}"
