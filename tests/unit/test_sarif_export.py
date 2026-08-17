"""The SARIF export (#487): DEC-072's second serializer, DEC-009 kept structural.

The load-bearing assertions: only approved objects export; a finding's `level` follows the
reviewer-assigned severity; a documentation gap is `kind: "review"` at `level: "none"` — never
an error or a warning, because a gap asserts nothing about the implementation; locations come
from the evidence chain; and an unapproved context is refused outright, like every export.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.finding import Finding
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.source_document import (
    IngestionStatus,
    SourceDocument,
    TrustLevel,
)
from trace_ai.domain.system_context import SystemContext
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.export import ExportError, export_sarif, write_sarif
from trace_ai.workflow.finding_review import approve_finding

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

REVIEWER = "sarif-test-reviewer"
PASSAGE = "The receiver enqueues webhook events after structural validation only."


def save(handle: AssessmentHandle, obj: Any) -> Any:
    with handle.objects.transaction():
        handle.objects.save(obj)
    return obj


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        stamped = now()

        save(
            handle,
            Component.model_validate(
                {
                    "id": "cmp-001",
                    "assessment_id": handle.assessment_id,
                    "name": "Webhook Receiver",
                    "component_type": "service",
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "status": ObjectStatus.APPROVED,
                }
            ),
        )
        save(
            handle,
            SourceDocument.model_validate(
                {
                    "id": "src-001",
                    "assessment_id": handle.assessment_id,
                    "filename": "architecture-overview.md",
                    "media_type": "text/markdown",
                    "content_hash": content_hash(b"doc"),
                    "origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "trust_level": TrustLevel.UNTRUSTED,
                    "ingestion_status": IngestionStatus.INGESTED,
                    "created_at": stamped,
                    "ingested_at": stamped,
                    "normalized_path": "normalized/architecture-overview.md",
                }
            ),
        )
        save(
            handle,
            EvidenceReference.model_validate(
                {
                    "id": "evd-001",
                    "assessment_id": handle.assessment_id,
                    "source_document_id": "src-001",
                    "section_title": "Webhook handling",
                    "start_line": 41,
                    "end_line": 46,
                    "quoted_text": PASSAGE,
                    "content_hash": content_hash(PASSAGE.encode()),
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "created_at": stamped,
                }
            ),
        )
        save(
            handle,
            Threat.model_validate(
                {
                    "id": "thr-001",
                    "assessment_id": handle.assessment_id,
                    "title": "Forged webhooks trigger unauthorized analysis jobs",
                    "description": "An attacker submits webhook requests the receiver acts on.",
                    "methodology": "stride-scenario-based",
                    "affected_component_ids": ["cmp-001"],
                    "affected_asset_ids": ["ast-001"],
                    "impact": "Unauthorized job execution.",
                    "confidence": ConfidenceLevel.MEDIUM,
                    "status": ObjectStatus.APPROVED,
                    "generated_by": "threat-analysis-v1",
                    "created_at": stamped,
                }
            ),
        )
        save(
            handle,
            ControlMapping.model_validate(
                {
                    "id": "map-001",
                    "assessment_id": handle.assessment_id,
                    "threat_id": "thr-001",
                    "requirement_id": "req-WEBHOOK-001",
                    "applicability_status": ApplicabilityStatus.APPLICABLE,
                    "applicability_reason": "The system accepts external webhook events.",
                    "satisfaction_status": SatisfactionStatus.UNVERIFIED,
                    "confidence": ConfidenceLevel.MEDIUM,
                    "generated_by": "mapping-v1",
                    "reviewer_status": ObjectStatus.CANDIDATE,
                }
            ),
        )
        save(
            handle,
            SystemContext.model_validate(
                {
                    "assessment_id": handle.assessment_id,
                    "system_name": "ForgeFlow",
                    "system_purpose": "AI-assisted pull request review platform",
                    "context_claim_ids": [],
                    "component_ids": ["cmp-001"],
                    "asset_ids": [],
                    "actor_ids": [],
                    "data_flow_ids": [],
                    "trust_boundary_ids": [],
                    "approved_at": stamped,
                    "approved_by": REVIEWER,
                    "version": 1,
                }
            ),
        )

        approved = Finding.model_validate(
            {
                "id": "fnd-001",
                "assessment_id": handle.assessment_id,
                "title": "Webhook requests may be processed without verified authenticity",
                "summary": "The receiver may accept events without verifying their origin.",
                "description": "The documents describe validation as structural, not cryptographic.",
                "threat_ids": ["thr-001"],
                "requirement_ids": ["req-WEBHOOK-001"],
                "control_mapping_ids": ["map-001"],
                "affected_component_ids": ["cmp-001"],
                "affected_asset_ids": [],
                "evidence_ids": ["evd-001"],
                "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
                "severity": Severity.HIGH,
                "impact": "Unauthorized job execution.",
                "recommendation": "Verify each event with the platform's signature mechanism.",
                "confidence": ConfidenceLevel.MEDIUM,
                "status": ObjectStatus.CANDIDATE,
                "generated_by": "finding-consolidation-v1",
                "created_at": stamped,
                "updated_at": stamped,
            }
        )
        save(handle, approved)
        approve_finding(handle, approved, reviewer_id=REVIEWER)

        save(
            handle,
            Finding.model_validate(
                {
                    **approved.model_dump(),
                    "id": "fnd-002",
                    "title": "A candidate finding that must not export",
                    "severity": Severity.UNASSIGNED,
                    "status": ObjectStatus.CANDIDATE,
                }
            ),
        )
        save(
            handle,
            DocumentationGap.model_validate(
                {
                    "id": "gap-001",
                    "assessment_id": handle.assessment_id,
                    "title": "Webhook authenticity verification is not documented",
                    "description": "It cannot be determined whether req-WEBHOOK-001 is met.",
                    "importance": "The endpoint accepts external events.",
                    "related_object_ids": ["thr-001", "map-001"],
                    "severity": Severity.MEDIUM,
                    "status": ObjectStatus.APPROVED,
                    "generated_by": "finding-consolidation-v1",
                    "evidence_ids": ["evd-001"],
                }
            ),
        )
        yield handle


def _results(document: dict[str, Any]) -> list[dict[str, Any]]:
    return list(document["runs"][0]["results"])


def test_the_export_is_a_sarif_log_of_approved_objects_only(handle: AssessmentHandle) -> None:
    document = export_sarif(handle)

    assert document["version"] == "2.1.0"
    results = _results(document)
    identifiers = {
        result["partialFingerprints"].get("traceAi/findingId")
        or result["partialFingerprints"].get("traceAi/gapId")
        for result in results
    }
    assert identifiers == {"fnd-001", "gap-001"}, "candidates must leave no trace"


def test_the_level_is_the_reviewer_assigned_severity(handle: AssessmentHandle) -> None:
    (finding_result,) = [
        r for r in _results(export_sarif(handle)) if "traceAi/findingId" in r["partialFingerprints"]
    ]
    assert finding_result["level"] == "error"  # HIGH
    assert finding_result["ruleId"] == "req-WEBHOOK-001"
    assert "verified authenticity" in finding_result["message"]["text"]


def test_a_documentation_gap_is_review_kind_at_level_none(handle: AssessmentHandle) -> None:
    """DEC-009, structurally: a gap asserts nothing about the implementation, so it is never an
    error or a warning — SARIF's own `review` kind is what it is."""
    (gap_result,) = [
        r for r in _results(export_sarif(handle)) if "traceAi/gapId" in r["partialFingerprints"]
    ]
    assert gap_result["kind"] == "review"
    assert gap_result["level"] == "none"
    assert gap_result["ruleId"] == "req-WEBHOOK-001", "resolved through the related mapping"
    assert gap_result["properties"]["traceAi"]["kind"] == "documentation-gap"


def test_locations_come_from_the_evidence_chain(handle: AssessmentHandle) -> None:
    (finding_result,) = [
        r for r in _results(export_sarif(handle)) if "traceAi/findingId" in r["partialFingerprints"]
    ]
    physical = [
        location["physicalLocation"]
        for location in finding_result["locations"]
        if "physicalLocation" in location
    ]
    assert physical[0]["artifactLocation"]["uri"] == "architecture-overview.md"
    assert physical[0]["region"] == {"startLine": 41, "endLine": 46}
    logical = [
        location["logicalLocations"]
        for location in finding_result["locations"]
        if "logicalLocations" in location
    ]
    assert logical[0][0]["name"] == "Webhook Receiver"


def test_the_cited_requirements_become_rules(handle: AssessmentHandle) -> None:
    rules = export_sarif(handle)["runs"][0]["tool"]["driver"]["rules"]
    assert [rule["id"] for rule in rules] == ["req-WEBHOOK-001"]


def test_an_unapproved_context_is_refused(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Unapproved", default_configuration("offline-fake", "stride-scenario-based")
        )
        with pytest.raises(ExportError, match="context"):
            export_sarif(service.handle(created.id))


def test_the_export_writes_to_the_outputs_area(handle: AssessmentHandle) -> None:
    written = write_sarif(handle)
    assert written.name.startswith("findings-")
    assert written.name.endswith(".sarif")
    assert written.is_file()
