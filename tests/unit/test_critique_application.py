"""Critique application during consolidation (DEC-053, issue #100).

The acceptance criteria are the spine: every change records its critique, a rejection retains the
candidate with the critique as its stated reason, a revision preserves the pre-revision state, a
`documentation_gap_only` critique produces a gap and not a softened finding, and no critique path
can approve anything. With no critiques, the output is the input.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.critique import Critique, CritiqueSubjectType, CritiqueType, RecommendedAction
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    Severity,
    ValidationStatus,
)
from trace_ai.domain.evidence_assessment import (
    EvidenceAssessment,
    Recommendation,
    SubjectType,
)
from trace_ai.domain.finding import Finding
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.workflow.critique_application import (
    GENERATED_BY,
    CritiqueApplicationOutcome,
    apply_critiques,
    persist_application,
)

MODULE = PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "critique_application.py"


def a_finding(**changes: Any) -> Finding:
    stamped = now()
    payload: dict[str, Any] = {
        "id": "fnd-001",
        "assessment_id": "asm-001",
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
    return Finding.model_validate(payload)


def a_critique(**changes: Any) -> Critique:
    payload: dict[str, Any] = {
        "id": "crq-001",
        "assessment_id": "asm-001",
        "subject_type": CritiqueSubjectType.FINDING,
        "subject_id": "fnd-001",
        "critique_type": CritiqueType.UNSUPPORTED_CLAIM,
        "description": "The cited passage describes intent, not an implemented check.",
        "rationale": "Section 3 of the notes is a roadmap item, and no other passage verifies it.",
        "recommended_action": RecommendedAction.REVISE,
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "critical-review-v1",
    }
    payload.update(changes)
    return Critique.model_validate(payload)


# ------------------------------------------------------------------------------------------
# Nothing to apply
# ------------------------------------------------------------------------------------------


def test_no_critiques_means_the_output_is_the_input() -> None:
    findings = [a_finding()]
    outcome = apply_critiques((), findings=findings)
    assert outcome == CritiqueApplicationOutcome(findings=tuple(findings))


# ------------------------------------------------------------------------------------------
# The five actions
# ------------------------------------------------------------------------------------------


def test_keep_is_recorded_and_changes_nothing() -> None:
    findings = [a_finding()]
    outcome = apply_critiques(
        [a_critique(recommended_action=RecommendedAction.KEEP)], findings=findings
    )
    assert outcome.findings == tuple(findings)
    assert len(outcome.applied) == 1
    assert outcome.applied[0].critique_id == "crq-001"


def test_a_rejected_candidate_is_retained_with_the_critique_as_its_stated_reason() -> None:
    outcome = apply_critiques(
        [a_critique(recommended_action=RecommendedAction.REJECT)], findings=[a_finding()]
    )
    assert outcome.findings == (), "absent from the provisional finding set"
    assert len(outcome.rejected) == 1
    retained = outcome.rejected[0]
    assert retained.finding.id == "fnd-001"
    assert retained.finding.status is ObjectStatus.REJECTED
    assert retained.critique_id == "crq-001"
    assert "crq-001" in retained.reason


def test_a_revision_preserves_the_pre_revision_state_and_both_are_retrievable() -> None:
    original = a_finding()
    outcome = apply_critiques([a_critique()], findings=[original])

    assert len(outcome.revisions) == 1
    record = outcome.revisions[0]
    assert record.before == original
    assert record.after == outcome.findings[0]
    assert record.after != record.before


def test_a_revision_adds_and_never_rewrites() -> None:
    """DEC-053: the criticism joins `limitations` under the critique's identifier, the critique's
    evidence joins the finding's, and nothing the pipeline asserted is altered."""
    original = a_finding()
    critique = a_critique(evidence_ids=["evd-002"])
    revised = apply_critiques([critique], findings=[original]).findings[0]

    assert revised.limitations == [f"crq-001: {critique.description}"]
    assert revised.evidence_ids == ["evd-001", "evd-002"]
    assert revised.description == original.description
    assert revised.impact == original.impact
    assert revised.recommendation == original.recommendation
    assert revised.status is ObjectStatus.CANDIDATE


def test_merge_is_deferred_to_the_dedup_operation() -> None:
    """One recommendation must not merge through a second door with no merge record (DEC-052)."""
    original = a_finding()
    outcome = apply_critiques(
        [a_critique(recommended_action=RecommendedAction.MERGE)], findings=[original]
    )
    assert outcome.findings == (original,), "unchanged"
    assert len(outcome.deferred) == 1
    assert "DEC-052" in outcome.deferred[0].reason


def test_investigate_is_deferred_to_the_reviewer() -> None:
    outcome = apply_critiques(
        [a_critique(recommended_action=RecommendedAction.INVESTIGATE)], findings=[a_finding()]
    )
    assert len(outcome.deferred) == 1
    assert "reviewer" in outcome.deferred[0].reason


# ------------------------------------------------------------------------------------------
# documentation_gap_only: reclassification, not a softened description
# ------------------------------------------------------------------------------------------


def test_a_documentation_gap_only_critique_produces_a_gap_not_a_softened_finding() -> None:
    critique = a_critique(
        critique_type=CritiqueType.DOCUMENTATION_GAP_ONLY,
        recommended_action=RecommendedAction.REVISE,
    )
    outcome = apply_critiques([critique], findings=[a_finding()])

    assert outcome.findings == (), "the candidate is no longer a finding"
    assert len(outcome.converted) == 1
    gap = outcome.converted[0]
    assert isinstance(gap, DocumentationGap)
    assert gap.converted_from_id == "fnd-001"
    assert gap.importance == critique.rationale
    assert gap.generated_by == GENERATED_BY

    assert len(outcome.superseded) == 1
    assert outcome.superseded[0].id == "fnd-001"
    assert outcome.superseded[0].status is ObjectStatus.SUPERSEDED


def test_the_gap_only_type_outranks_the_recommended_action() -> None:
    """Even `keep` yields the conversion: the type asserts the finding should not exist as one."""
    critique = a_critique(
        critique_type=CritiqueType.DOCUMENTATION_GAP_ONLY,
        recommended_action=RecommendedAction.KEEP,
    )
    outcome = apply_critiques([critique], findings=[a_finding()])
    assert outcome.findings == ()
    assert len(outcome.converted) == 1


# ------------------------------------------------------------------------------------------
# Resolution: subjects other than the finding itself
# ------------------------------------------------------------------------------------------


def test_a_threat_critique_reaches_the_candidates_built_from_it() -> None:
    critique = a_critique(
        subject_type=CritiqueSubjectType.THREAT,
        subject_id="thr-001",
        recommended_action=RecommendedAction.REJECT,
    )
    outcome = apply_critiques([critique], findings=[a_finding()])
    assert outcome.findings == ()
    assert outcome.rejected[0].finding.id == "fnd-001"


def test_a_mapping_critique_reaches_the_candidates_built_from_it() -> None:
    critique = a_critique(
        subject_type=CritiqueSubjectType.CONTROL_MAPPING,
        subject_id="map-001",
        recommended_action=RecommendedAction.REJECT,
    )
    outcome = apply_critiques([critique], findings=[a_finding()])
    assert outcome.rejected[0].finding.id == "fnd-001"


def test_an_evidence_assessment_critique_resolves_through_the_assessment() -> None:
    assessed = EvidenceAssessment.model_validate(
        {
            "id": "eas-001",
            "assessment_id": "asm-001",
            "subject_type": SubjectType.CONTROL_MAPPING,
            "subject_id": "map-001",
            "evidence_ids": ["evd-001"],
            "evidence_strengths": {"evd-001": EvidenceStrength.CONTEXTUAL},
            "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
            "rationale": "The passage partially establishes the check.",
            "confidence": ConfidenceLevel.MEDIUM,
            "recommendation": Recommendation.CONTINUE,
            "generated_by": "evidence-validation-v1",
            "created_at": now(),
        }
    )
    critique = a_critique(
        subject_type=CritiqueSubjectType.EVIDENCE_ASSESSMENT,
        subject_id="eas-001",
        recommended_action=RecommendedAction.REJECT,
    )
    outcome = apply_critiques([critique], findings=[a_finding()], assessments=[assessed])
    assert outcome.rejected[0].finding.id == "fnd-001"


def test_an_unresolvable_critique_is_reported_not_dropped() -> None:
    original = a_finding()
    critique = a_critique(subject_id="fnd-099", recommended_action=RecommendedAction.REJECT)
    outcome = apply_critiques([critique], findings=[original])
    assert outcome.findings == (original,)
    assert len(outcome.unapplied) == 1
    assert "fnd-099" in outcome.unapplied[0].reason


def test_a_second_critique_of_a_rejected_candidate_is_reported() -> None:
    critiques = [
        a_critique(recommended_action=RecommendedAction.REJECT),
        a_critique(id="crq-002", recommended_action=RecommendedAction.REVISE),
    ]
    outcome = apply_critiques(critiques, findings=[a_finding()])
    assert len(outcome.rejected) == 1
    assert len(outcome.unapplied) == 1
    assert outcome.unapplied[0].critique_id == "crq-002"


# ------------------------------------------------------------------------------------------
# Every change records its critique; nothing can approve
# ------------------------------------------------------------------------------------------


def test_every_change_records_the_originating_critique_identifier() -> None:
    critiques = [
        a_critique(recommended_action=RecommendedAction.REVISE),
        a_critique(
            id="crq-002",
            subject_id="fnd-002",
            recommended_action=RecommendedAction.REJECT,
        ),
    ]
    findings = [
        a_finding(),
        a_finding(id="fnd-002", control_mapping_ids=["map-002"]),
    ]
    outcome = apply_critiques(critiques, findings=findings)
    assert {record.critique_id for record in outcome.applied} == {"crq-001", "crq-002"}
    assert all(record.target_id for record in outcome.applied)


def test_no_critique_path_can_set_a_finding_to_approved() -> None:
    """Approval is checkpoint 2's (DEC-005). Every action, every type: nothing comes out approved."""
    findings = [a_finding()]
    for action in RecommendedAction:
        for critique_type in CritiqueType:
            outcome = apply_critiques(
                [a_critique(critique_type=critique_type, recommended_action=action)],
                findings=findings,
            )
            everything: list[Finding | DocumentationGap] = [
                *outcome.findings,
                *outcome.superseded,
                *(record.finding for record in outcome.rejected),
                *(record.after for record in outcome.revisions),
                *outcome.documentation_gaps,
            ]
            for obj in everything:
                assert obj.status is not ObjectStatus.APPROVED, (
                    f"{action}/{critique_type} produced an approved object"
                )


def test_the_module_never_writes_approved() -> None:
    """The claim above, confirmable by reading: the module names no approval status at all."""
    assert "APPROVED" not in MODULE.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------
# Persistence (DEC-018)
# ------------------------------------------------------------------------------------------


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Critiques", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


def test_persist_application_writes_the_changes_and_re_mints_only_the_gaps(
    handle: AssessmentHandle,
) -> None:
    repository = handle.objects
    with repository.transaction():
        first_id = repository.allocate("fnd")
        second_id = repository.allocate("fnd")
    findings = [
        a_finding(id=first_id, assessment_id=handle.assessment_id),
        a_finding(
            id=second_id, assessment_id=handle.assessment_id, control_mapping_ids=["map-002"]
        ),
    ]
    with repository.transaction():
        for finding in findings:
            repository.save(finding)

    critiques = [
        a_critique(
            assessment_id=handle.assessment_id,
            subject_id=first_id,
            critique_type=CritiqueType.DOCUMENTATION_GAP_ONLY,
        ),
        a_critique(
            id="crq-002",
            assessment_id=handle.assessment_id,
            subject_id=second_id,
            recommended_action=RecommendedAction.REVISE,
        ),
    ]
    stored = persist_application(handle, apply_critiques(critiques, findings=findings))

    gap = stored.converted[0]
    assert gap.id.startswith("gap-"), "the gap identifier comes from the store"
    assert repository.get(DocumentationGap, gap.id).converted_from_id == first_id
    assert repository.get(Finding, first_id).status is ObjectStatus.SUPERSEDED

    revised = repository.get(Finding, second_id)
    assert revised.limitations, "the persisted finding carries the criticism"
    assert "crq-002" in revised.limitations[0]
