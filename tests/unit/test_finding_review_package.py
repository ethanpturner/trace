"""The checkpoint 2 review package: structured data first, formatting second (issue #101).

The acceptance criteria are the spine: every finding shows evidence with document, location, and
verbatim text; contradictory evidence appears beside supporting; every critique appears with its
recommended action and outcome; gaps are visibly distinct; a zero-finding assessment reads as a
result and not a failure; and the whole assembly makes no model call.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.critique import Critique, CritiqueSubjectType, CritiqueType, RecommendedAction
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import EvidenceAssessment, Recommendation, SubjectType
from trace_ai.domain.finding import Finding
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus
from trace_ai.domain.source_document import (
    IngestionStatus,
    MediaType,
    SourceDocument,
    TrustLevel,
)
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.findings.review_package import (
    FindingPresentation,
    FindingReviewPackage,
    GapPresentation,
    ReviewSummary,
    build_finding_review_package,
    render_markdown,
)
from trace_ai.workflow.critique_application import apply_critiques

MODULE = PROJECT_ROOT / "src" / "trace_ai" / "services" / "findings" / "review_package.py"

PASSAGE = "The webhook receiver validates the payload structure before queuing."
COUNTER_PASSAGE = "All webhook requests are verified against the provider signature."


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Review", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


def seed(handle: AssessmentHandle, **overrides: Any) -> dict[str, Any]:
    """One finding's worth of objects, persisted; `overrides` swaps whole collections out."""
    asm = handle.assessment_id
    stamped = now()

    objects: dict[str, Any] = {
        "documents": [
            SourceDocument.model_validate(
                {
                    "id": "src-001",
                    "assessment_id": asm,
                    "filename": "architecture-overview.md",
                    "media_type": MediaType.MARKDOWN,
                    "origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "content_hash": content_hash(PASSAGE.encode()),
                    "created_at": stamped,
                    "ingestion_status": IngestionStatus.REGISTERED,
                    "trust_level": TrustLevel.UNTRUSTED,
                }
            )
        ],
        "evidence": [
            EvidenceReference.model_validate(
                {
                    "id": "evd-001",
                    "assessment_id": asm,
                    "source_document_id": "src-001",
                    "section_title": "Webhook receiver",
                    "start_line": 41,
                    "end_line": 46,
                    "quoted_text": PASSAGE,
                    "content_hash": content_hash(PASSAGE.encode()),
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "created_at": stamped,
                }
            ),
            EvidenceReference.model_validate(
                {
                    "id": "evd-002",
                    "assessment_id": asm,
                    "source_document_id": "src-001",
                    "section_title": "Security controls",
                    "start_line": 90,
                    "end_line": 91,
                    "quoted_text": COUNTER_PASSAGE,
                    "content_hash": content_hash(COUNTER_PASSAGE.encode()),
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "created_at": stamped,
                }
            ),
        ],
        "threats": [
            Threat.model_validate(
                {
                    "id": "thr-001",
                    "assessment_id": asm,
                    "title": "Forged webhooks trigger unauthorized analysis jobs",
                    "description": "An attacker submits webhook requests the receiver acts on.",
                    "methodology": "stride-scenario-based",
                    "affected_component_ids": ["cmp-001"],
                    "affected_asset_ids": ["ast-001"],
                    "impact": "Unauthorized jobs and denial of service.",
                    "confidence": ConfidenceLevel.MEDIUM,
                    "status": ObjectStatus.APPROVED,
                    "generated_by": "threat-analysis-v1",
                    "created_at": stamped,
                }
            )
        ],
        "mappings": [
            ControlMapping.model_validate(
                {
                    "id": "map-001",
                    "assessment_id": asm,
                    "threat_id": "thr-001",
                    "requirement_id": "req-WEBHOOK-001",
                    "applicability_status": ApplicabilityStatus.APPLICABLE,
                    "applicability_reason": (
                        "The system exposes an endpoint accepting external events."
                    ),
                    "satisfaction_status": SatisfactionStatus.PARTIALLY_SATISFIED,
                    "evidence_ids": ["evd-001"],
                    "confidence": ConfidenceLevel.MEDIUM,
                    "generated_by": "mapping-v1",
                    "reviewer_status": ObjectStatus.CANDIDATE,
                }
            )
        ],
        "observations": [
            SourceObservation.model_validate(
                {
                    "id": "obs-001",
                    "assessment_id": asm,
                    "kind": ObservationKind.CONTRADICTION,
                    "summary": "Two documents disagree about webhook verification.",
                    "evidence_ids": ["evd-001", "evd-002"],
                    "status": ObjectStatus.CANDIDATE,
                    "created_at": stamped,
                }
            )
        ],
        "assessments": [
            EvidenceAssessment.model_validate(
                {
                    "id": "eas-001",
                    "assessment_id": asm,
                    "subject_type": SubjectType.CONTROL_MAPPING,
                    "subject_id": "map-001",
                    "evidence_ids": ["evd-001"],
                    "evidence_strengths": {"evd-001": EvidenceStrength.DIRECT},
                    "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
                    "rationale": "The passage describes structural validation only.",
                    "contradictions": ["obs-001"],
                    "confidence": ConfidenceLevel.MEDIUM,
                    "recommendation": Recommendation.CONTINUE,
                    "generated_by": "evidence-validation-v1",
                    "created_at": stamped,
                }
            )
        ],
        "critiques": [
            Critique.model_validate(
                {
                    "id": "crq-001",
                    "assessment_id": asm,
                    "subject_type": CritiqueSubjectType.FINDING,
                    "subject_id": "fnd-001",
                    "critique_type": CritiqueType.MISSING_EVIDENCE,
                    "description": "The cited passage does not name the verification mechanism.",
                    "rationale": "No passage establishes cryptographic verification.",
                    "recommended_action": RecommendedAction.REVISE,
                    "confidence": ConfidenceLevel.MEDIUM,
                    "status": ObjectStatus.CANDIDATE,
                    "generated_by": "critical-review-v1",
                }
            )
        ],
        "findings": [
            Finding.model_validate(
                {
                    "id": "fnd-001",
                    "assessment_id": asm,
                    "title": "Webhook requests may be processed without verified authenticity",
                    "summary": "The receiver may accept events without verifying their origin.",
                    "description": (
                        "The documents describe validation as structural, not cryptographic."
                    ),
                    "threat_ids": ["thr-001"],
                    "requirement_ids": ["req-WEBHOOK-001"],
                    "control_mapping_ids": ["map-001"],
                    "affected_component_ids": ["cmp-001"],
                    "affected_asset_ids": ["ast-001"],
                    "evidence_ids": ["evd-001"],
                    "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
                    "severity": Severity.UNASSIGNED,
                    "impact": "Unauthorized job execution and resource exhaustion.",
                    "recommendation": (
                        "Verify each event with the platform's signature mechanism."
                    ),
                    "confidence": ConfidenceLevel.MEDIUM,
                    "status": ObjectStatus.CANDIDATE,
                    "generated_by": "finding-consolidation-v1",
                    "created_at": stamped,
                    "updated_at": stamped,
                }
            )
        ],
        "gaps": [
            DocumentationGap.model_validate(
                {
                    "id": "gap-001",
                    "assessment_id": asm,
                    "title": "TLS termination is not described",
                    "description": "No document states where TLS terminates.",
                    "importance": "Whether transit encryption covers the internal hop is open.",
                    "severity": Severity.MEDIUM,
                    "status": ObjectStatus.CANDIDATE,
                    "generated_by": "finding-consolidation-v1",
                    "evidence_ids": ["evd-001"],
                }
            )
        ],
        "questions": [
            Question.model_validate(
                {
                    "id": "qst-001",
                    "assessment_id": asm,
                    "question": "Which service verifies webhook signatures, if any?",
                    "rationale": "The answer decides whether req-WEBHOOK-001 is met.",
                    "related_object_type": "threat",
                    "related_object_id": "thr-001",
                    "priority": QuestionPriority.HIGH,
                    "blocking": False,
                    "status": QuestionStatus.OPEN,
                    "generated_by": "finding-consolidation-v1",
                }
            )
        ],
    }
    objects.update(overrides)

    with handle.objects.transaction():
        for collection in objects.values():
            for obj in collection:
                handle.objects.save(obj)
    return objects


def build(handle: AssessmentHandle, **kwargs: Any) -> FindingReviewPackage:
    return build_finding_review_package(handle, index=EvidenceIndex(handle), **kwargs)


# ------------------------------------------------------------------------------------------
# Evidence: present, located, verbatim
# ------------------------------------------------------------------------------------------


def test_every_finding_shows_a_citation_with_document_location_and_text(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    package = build(handle)
    assert package.summary.finding_count == 1
    supporting = package.findings[0].supporting
    assert len(supporting) >= 1
    excerpt = supporting[0]
    assert excerpt.document == "architecture-overview.md"
    assert "Webhook receiver" in excerpt.location
    assert "lines 41-46" in excerpt.location


def test_quoted_evidence_matches_the_stored_text_byte_for_byte(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    package = build(handle)
    assert package.findings[0].supporting[0].text == PASSAGE


def test_contradictory_evidence_appears_beside_supporting(handle: AssessmentHandle) -> None:
    """The DEC-021 chain: assessment names the observation, the observation cites the passage."""
    seed(handle)
    item = build(handle).findings[0]
    assert COUNTER_PASSAGE in [excerpt.text for excerpt in item.contradictory]
    assert item.supporting, "contradictory evidence is shown alongside, not instead"


def test_a_low_confidence_finding_states_its_justification(handle: AssessmentHandle) -> None:
    objects = seed(handle)
    finding = objects["findings"][0]
    low = Finding.model_validate(
        {
            **finding.model_dump(),
            "confidence": ConfidenceLevel.LOW,
            "low_confidence_justification": (
                "A copy of the receiver's configuration would settle the mechanism."
            ),
        }
    )
    with handle.objects.transaction():
        handle.objects.save(low)

    item = build(handle).findings[0]
    assert "low-confidence justification" in item.evidence_statement
    assert "receiver's configuration" in item.evidence_statement


def test_a_low_confidence_finding_carries_the_low_confidence_routing_reason(
    handle: AssessmentHandle,
) -> None:
    """DEC-062: the confidence field derives a typed `low_confidence` reason at build time."""
    objects = seed(handle)
    finding = objects["findings"][0]
    low = Finding.model_validate(
        {
            **finding.model_dump(),
            "confidence": ConfidenceLevel.LOW,
            "low_confidence_justification": "More evidence on the receiver would raise confidence.",
        }
    )
    with handle.objects.transaction():
        handle.objects.save(low)

    package = build(handle)
    assert "low_confidence" in package.reasons_for(low.id)
    assert "low_confidence" in render_markdown(package), "the reason renders in `findings show`"


def test_a_medium_confidence_finding_carries_no_routing_reason(handle: AssessmentHandle) -> None:
    """A subject with no reasons is routine, not exempt (DEC-062): absence reads as nothing said."""
    objects = seed(handle)
    package = build(handle)
    assert package.reasons_for(objects["findings"][0].id) == ()


# ------------------------------------------------------------------------------------------
# Critiques, threats, mappings, questions
# ------------------------------------------------------------------------------------------


def test_every_critique_appears_with_its_action_and_outcome(handle: AssessmentHandle) -> None:
    objects = seed(handle)
    application = apply_critiques(objects["critiques"], findings=objects["findings"])
    package = build(handle, application=application)

    raised = package.findings[0].critiques
    assert [presented.critique.id for presented in raised] == ["crq-001"]
    assert raised[0].critique.recommended_action is RecommendedAction.REVISE
    assert "crq-001" in raised[0].outcome or "limitations" in raised[0].outcome


def test_without_application_records_the_critique_says_so(handle: AssessmentHandle) -> None:
    seed(handle)
    raised = build(handle).findings[0].critiques
    assert "no application record" in raised[0].outcome


def test_the_originating_threat_and_mapping_appear_with_the_applicability_rationale(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    item = build(handle).findings[0]
    assert [threat.id for threat in item.threats] == ["thr-001"]
    assert [mapping.id for mapping in item.mappings] == ["map-001"]
    assert "endpoint accepting external events" in item.mappings[0].applicability_reason


def test_related_open_questions_appear_with_priority_and_blocking(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    item = build(handle).findings[0]
    assert [question.id for question in item.questions] == ["qst-001"]
    assert item.questions[0].priority is QuestionPriority.HIGH
    assert item.questions[0].blocking is False


# ------------------------------------------------------------------------------------------
# Gaps beside findings, visibly distinct
# ------------------------------------------------------------------------------------------


def test_gaps_appear_and_are_distinguished_from_findings(handle: AssessmentHandle) -> None:
    seed(handle)
    package = build(handle)
    assert package.summary.documentation_gap_count == 1
    assert isinstance(package.documentation_gaps[0], GapPresentation)
    rendered = render_markdown(package)
    assert "asserts nothing about the implementation" in rendered
    assert "gap-001" in rendered


# ------------------------------------------------------------------------------------------
# Zero findings is a result
# ------------------------------------------------------------------------------------------


def test_zero_findings_produces_a_complete_package_that_is_not_a_failure(
    handle: AssessmentHandle,
) -> None:
    seed(handle, findings=[], critiques=[])
    package = build(handle)
    assert package.summary.finding_count == 0
    assert "No provisional findings were proposed" in package.summary.statement
    assert "successful" in package.summary.statement
    rendered = render_markdown(package)
    assert "fail" not in rendered.casefold()
    assert "gap-001" in rendered, "the rest of the package is intact"


def test_a_duplicate_or_rejected_finding_is_not_in_the_provisional_set(
    handle: AssessmentHandle,
) -> None:
    objects = seed(handle)
    finding = objects["findings"][0]
    extra = Finding.model_validate(
        {**finding.model_dump(), "id": "fnd-002", "duplicate_of_id": "fnd-001"}
    )
    dismissed = Finding.model_validate(
        {**finding.model_dump(), "id": "fnd-003", "status": ObjectStatus.REJECTED}
    )
    with handle.objects.transaction():
        handle.objects.save(extra)
        handle.objects.save(dismissed)

    package = build(handle)
    assert [item.finding.id for item in package.findings] == ["fnd-001"]


# ------------------------------------------------------------------------------------------
# Severity is first-class (DEC-030)
# ------------------------------------------------------------------------------------------


def test_the_summary_counts_findings_awaiting_severity(handle: AssessmentHandle) -> None:
    seed(handle)
    package = build(handle)
    assert package.summary.awaiting_severity_count == 1
    assert "DEC-030" in package.summary.statement
    assert "assignment required before approval" in render_markdown(package)


# ------------------------------------------------------------------------------------------
# Structured data first; no model
# ------------------------------------------------------------------------------------------


def test_formatting_is_a_separate_step_over_the_structured_data() -> None:
    """`render_markdown` reads only the package: a hand-built one renders with no store at all."""
    package = FindingReviewPackage(
        summary=ReviewSummary(
            finding_count=0,
            documentation_gap_count=0,
            open_question_count=0,
            awaiting_severity_count=0,
            statement="No provisional findings were proposed.",
        ),
        findings=(),
        documentation_gaps=(),
        questions=(),
    )
    rendered = render_markdown(package)
    assert rendered.startswith("# Finding review")
    assert "No provisional findings were proposed." in rendered


def test_the_package_is_structured_data(handle: AssessmentHandle) -> None:
    seed(handle)
    package = build(handle)
    assert isinstance(package, FindingReviewPackage)
    assert all(isinstance(item, FindingPresentation) for item in package.findings)


def test_assembly_makes_no_model_call() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "StructuredModel" not in source
    assert "anthropic" not in source
    assert "model_profile" not in source
