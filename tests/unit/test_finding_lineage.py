"""The lineage walk: section 32's chain, resolved for one finding (issue #100).

The acceptance criterion this file holds: for every surviving finding, a lineage walk reaches at
least one `EvidenceReference` through the chain in `data-model.md` section 32, and the walk fails
if any named link is missing. Sparse chains are ordinary — no assessment, no critique — but a
reference that resolves to nothing is a defect with a name.
"""

from __future__ import annotations

from typing import Any

import pytest

from trace_ai.domain.base import now
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.critique import Critique, CritiqueSubjectType, CritiqueType, RecommendedAction
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
from trace_ai.domain.source_document import (
    IngestionStatus,
    MediaType,
    SourceDocument,
    TrustLevel,
)
from trace_ai.domain.threat import Threat
from trace_ai.services.findings.lineage import LineageError, finding_lineage

PASSAGE = "The webhook receiver validates the payload structure before queuing."


def a_document(**changes: Any) -> SourceDocument:
    payload: dict[str, Any] = {
        "id": "src-001",
        "assessment_id": "asm-001",
        "filename": "architecture-overview.md",
        "media_type": MediaType.MARKDOWN,
        "origin": SourceOrigin.UPLOADED_DOCUMENT,
        "content_hash": content_hash(PASSAGE.encode()),
        "created_at": now(),
        "ingestion_status": IngestionStatus.REGISTERED,
        "trust_level": TrustLevel.UNTRUSTED,
    }
    payload.update(changes)
    return SourceDocument.model_validate(payload)


def an_evidence_reference(**changes: Any) -> EvidenceReference:
    payload: dict[str, Any] = {
        "id": "evd-001",
        "assessment_id": "asm-001",
        "source_document_id": "src-001",
        "start_line": 41,
        "end_line": 46,
        "quoted_text": PASSAGE,
        "content_hash": content_hash(PASSAGE.encode()),
        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
        "created_at": now(),
    }
    payload.update(changes)
    return EvidenceReference.model_validate(payload)


def a_claim(**changes: Any) -> ContextClaim:
    stamped = now()
    payload: dict[str, Any] = {
        "id": "ctx-001",
        "assessment_id": "asm-001",
        "subject_type": "component",
        "subject_id": "cmp-001",
        "predicate": "validates webhook payload structure",
        "value": "structural validation only",
        "status": ClaimStatus.ASSUMED,
        "confidence": ConfidenceLevel.MEDIUM,
        "rationale": "The overview describes validation without naming a mechanism.",
        "evidence_ids": ["evd-001"],
        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
        "created_at": stamped,
        "updated_at": stamped,
    }
    payload.update(changes)
    return ContextClaim.model_validate(payload)


def a_threat(**changes: Any) -> Threat:
    payload: dict[str, Any] = {
        "id": "thr-001",
        "assessment_id": "asm-001",
        "title": "Forged webhooks trigger unauthorized analysis jobs",
        "description": "An attacker submits webhook requests the receiver acts on.",
        "methodology": "stride-scenario-based",
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "impact": "Unauthorized jobs and denial of service.",
        "confidence": ConfidenceLevel.MEDIUM,
        "evidence_ids": ["evd-001"],
        "assumption_ids": ["ctx-001"],
        "status": ObjectStatus.APPROVED,
        "generated_by": "threat-analysis-v1",
        "created_at": now(),
    }
    payload.update(changes)
    return Threat.model_validate(payload)


def a_mapping(**changes: Any) -> ControlMapping:
    payload: dict[str, Any] = {
        "id": "map-001",
        "assessment_id": "asm-001",
        "threat_id": "thr-001",
        "requirement_id": "req-WEBHOOK-001",
        "applicability_status": ApplicabilityStatus.APPLICABLE,
        "applicability_reason": "The system exposes an endpoint accepting external events.",
        "satisfaction_status": SatisfactionStatus.UNMET,
        "evidence_ids": ["evd-002"],
        "confidence": ConfidenceLevel.MEDIUM,
        "generated_by": "mapping-v1",
        "reviewer_status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return ControlMapping.model_validate(payload)


def an_assessment(**changes: Any) -> EvidenceAssessment:
    payload: dict[str, Any] = {
        "id": "eas-001",
        "assessment_id": "asm-001",
        "subject_type": SubjectType.CONTROL_MAPPING,
        "subject_id": "map-001",
        "evidence_ids": ["evd-001"],
        "evidence_strengths": {"evd-001": EvidenceStrength.DIRECT},
        "validation_status": ValidationStatus.SUPPORTED,
        "rationale": "The passage establishes that only structural validation occurs.",
        "confidence": ConfidenceLevel.MEDIUM,
        "recommendation": Recommendation.CONTINUE,
        "generated_by": "evidence-validation-v1",
        "created_at": now(),
    }
    payload.update(changes)
    return EvidenceAssessment.model_validate(payload)


def a_critique(**changes: Any) -> Critique:
    payload: dict[str, Any] = {
        "id": "crq-001",
        "assessment_id": "asm-001",
        "subject_type": CritiqueSubjectType.CONTROL_MAPPING,
        "subject_id": "map-001",
        "critique_type": CritiqueType.MISSING_EVIDENCE,
        "description": "The unmet conclusion cites one passage about a different endpoint.",
        "rationale": "No cited evidence bears on the webhook receiver itself.",
        "recommended_action": RecommendedAction.REVISE,
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "critical-review-v1",
    }
    payload.update(changes)
    return Critique.model_validate(payload)


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
        "validation_status": ValidationStatus.SUPPORTED,
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


def full_chain(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "threats": [a_threat()],
        "control_mappings": [a_mapping()],
        "evidence_assessments": [an_assessment()],
        "critiques": [a_critique()],
        "context_claims": [a_claim()],
        "evidence_references": [
            an_evidence_reference(),
            an_evidence_reference(id="evd-002", start_line=50, end_line=52),
        ],
        "source_documents": [a_document()],
    }
    defaults.update(overrides)
    return defaults


# ------------------------------------------------------------------------------------------
# The walk resolves, and reaches evidence
# ------------------------------------------------------------------------------------------


def test_the_walk_resolves_the_whole_section_32_chain() -> None:
    lineage = finding_lineage(a_finding(), **full_chain())
    assert [doc.id for doc in lineage.source_documents] == ["src-001"]
    assert {ref.id for ref in lineage.evidence_references} == {"evd-001", "evd-002"}
    assert [claim.id for claim in lineage.context_claims] == ["ctx-001"]
    assert [threat.id for threat in lineage.threats] == ["thr-001"]
    assert [mapping.id for mapping in lineage.control_mappings] == ["map-001"]
    assert [assessed.id for assessed in lineage.evidence_assessments] == ["eas-001"]
    assert [critique.id for critique in lineage.critiques] == ["crq-001"]


def test_the_walk_reaches_at_least_one_evidence_reference() -> None:
    """The acceptance criterion, stated directly. `evidence_ids` is non-empty by schema, so a
    walk that resolves cannot come back evidence-free."""
    lineage = finding_lineage(a_finding(), **full_chain())
    assert len(lineage.evidence_references) >= 1


def test_a_sparse_chain_is_ordinary() -> None:
    """No assessment, no critique, no assumption claims: still a readable history."""
    lineage = finding_lineage(
        a_finding(),
        threats=[a_threat(assumption_ids=[], evidence_ids=[])],
        control_mappings=[a_mapping(evidence_ids=["evd-001"])],
        evidence_references=[an_evidence_reference()],
        source_documents=[a_document()],
    )
    assert lineage.evidence_assessments == ()
    assert lineage.critiques == ()
    assert lineage.context_claims == ()
    assert [ref.id for ref in lineage.evidence_references] == ["evd-001"]


def test_critiques_are_gathered_from_every_subject_in_the_chain() -> None:
    """A critique of the finding, its threat, its mapping, or an assessment over its mapping is
    part of its history; one about an unrelated mapping is not."""
    chain = full_chain(
        critiques=[
            a_critique(),
            a_critique(id="crq-002", subject_type=CritiqueSubjectType.THREAT, subject_id="thr-001"),
            a_critique(
                id="crq-003", subject_type=CritiqueSubjectType.FINDING, subject_id="fnd-001"
            ),
            a_critique(
                id="crq-004",
                subject_type=CritiqueSubjectType.EVIDENCE_ASSESSMENT,
                subject_id="eas-001",
            ),
            a_critique(
                id="crq-005",
                subject_type=CritiqueSubjectType.CONTROL_MAPPING,
                subject_id="map-099",
            ),
        ]
    )
    lineage = finding_lineage(a_finding(), **chain)
    assert [critique.id for critique in lineage.critiques] == [
        "crq-001",
        "crq-002",
        "crq-003",
        "crq-004",
    ]


# ------------------------------------------------------------------------------------------
# A missing link fails, by name
# ------------------------------------------------------------------------------------------


def test_a_missing_threat_fails_the_walk() -> None:
    with pytest.raises(LineageError, match="thr-001"):
        finding_lineage(a_finding(), **full_chain(threats=[]))


def test_a_missing_mapping_fails_the_walk() -> None:
    with pytest.raises(LineageError, match="map-001"):
        finding_lineage(a_finding(), **full_chain(control_mappings=[]))


def test_a_missing_evidence_reference_fails_the_walk() -> None:
    with pytest.raises(LineageError, match="evd-002"):
        finding_lineage(a_finding(), **full_chain(evidence_references=[an_evidence_reference()]))


def test_a_missing_context_claim_fails_the_walk() -> None:
    with pytest.raises(LineageError, match="ctx-001"):
        finding_lineage(a_finding(), **full_chain(context_claims=[]))


def test_a_missing_source_document_fails_the_walk() -> None:
    with pytest.raises(LineageError, match="src-001"):
        finding_lineage(a_finding(), **full_chain(source_documents=[]))


def test_the_error_names_the_section_32_requirement() -> None:
    with pytest.raises(LineageError, match="section 32"):
        finding_lineage(a_finding(), **full_chain(threats=[]))
