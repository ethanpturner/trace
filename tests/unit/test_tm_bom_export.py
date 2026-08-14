"""DEC-072's first export: the TM-BOM serializer, held to the vendored schema (issue #347).

The acceptance criterion is double-ended: the export validates against the TM-BOM schema
(vendored at `schemas/tm-bom/`, so the check runs offline), and it derives only from approved
objects — a candidate component, an unapproved threat, and a rejected finding must leave no
trace in the document. Around that: approved text serializes verbatim (the DEC-035 no-rewriting
discipline), unstated facts become conservative schema values named by `unconfirmed` assumption
rows rather than silent guesses (DEC-009 under a boolean-only schema), and an assessment with no
approved context is refused outright.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.finding import Finding
from trace_ai.domain.system_context import SystemContext
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.export import TM_BOM_SCHEMA_PATH, ExportError, export_tm_bom, write_tm_bom
from trace_ai.workflow.finding_review import approve_finding

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

REVIEWER = "reviewer-local"


def save(handle: AssessmentHandle, obj: Any) -> Any:
    with handle.objects.transaction():
        handle.objects.save(obj)
    return obj


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.actor import Actor
    from trace_ai.domain.component import Component
    from trace_ai.domain.control import Control, ControlType, ImplementationStatus
    from trace_ai.domain.data_flow import DataFlow
    from trace_ai.domain.threat import Threat

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        stamped = now()

        def component(cid: str, name: str, zone: str | None, status: ObjectStatus) -> None:
            save(
                handle,
                Component.model_validate(
                    {
                        "id": cid,
                        "assessment_id": handle.assessment_id,
                        "name": name,
                        "component_type": "service",
                        "deployment_zone": zone,
                        "internet_accessible": True if cid == "cmp-001" else None,
                        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                        "status": status,
                    }
                ),
            )

        component("cmp-001", "Webhook Receiver", "public", ObjectStatus.APPROVED)
        component("cmp-002", "Analysis Worker", "private", ObjectStatus.APPROVED)
        component("cmp-003", "Rejected Candidate", "private", ObjectStatus.CANDIDATE)

        save(
            handle,
            Actor.model_validate(
                {
                    "id": "act-001",
                    "assessment_id": handle.assessment_id,
                    "name": "Software Developer",
                    "actor_type": "end_user",
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                }
            ),
        )
        save(
            handle,
            Actor.model_validate(
                {
                    "id": "act-002",
                    "assessment_id": handle.assessment_id,
                    "name": "External Attacker",
                    "actor_type": "external_attacker",
                    "skill_level": "organized_group",
                    "access_level": "anonymous",
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                }
            ),
        )
        save(
            handle,
            DataFlow.model_validate(
                {
                    "id": "df-001",
                    "assessment_id": handle.assessment_id,
                    "name": "Webhook events to worker",
                    "source_component_id": "cmp-001",
                    "destination_component_id": "cmp-002",
                    "direction": "one_way",
                    "encryption_in_transit": "unknown",
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "status": ObjectStatus.APPROVED,
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
                    "threat_actor_ids": ["act-002"],
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
            Threat.model_validate(
                {
                    "id": "thr-002",
                    "assessment_id": handle.assessment_id,
                    "title": "An unapproved candidate threat",
                    "description": "Must not export.",
                    "methodology": "stride-scenario-based",
                    "affected_component_ids": ["cmp-001"],
                    "affected_asset_ids": ["ast-001"],
                    "impact": "None.",
                    "confidence": ConfidenceLevel.LOW,
                    "status": ObjectStatus.CANDIDATE,
                    "generated_by": "threat-analysis-v1",
                    "created_at": stamped,
                }
            ),
        )
        save(
            handle,
            Control.model_validate(
                {
                    "id": "ctl-001",
                    "assessment_id": handle.assessment_id,
                    "name": "Webhook signature validation",
                    "description": "Signatures are validated before enqueueing.",
                    "control_type": ControlType.IMPLEMENTED,
                    "implementation_status": ImplementationStatus.IMPLEMENTED,
                    "validation_status": ValidationStatus.SUPPORTED,
                    "evidence_ids": ["evd-001"],
                    "generated_by": "mapping-v1",
                    "created_at": stamped,
                    "status": ObjectStatus.CANDIDATE,
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
                    "business_criticality": "medium",
                    "context_claim_ids": [],
                    "component_ids": ["cmp-001", "cmp-002", "cmp-003"],
                    "asset_ids": [],
                    "actor_ids": ["act-001", "act-002"],
                    "data_flow_ids": ["df-001"],
                    "trust_boundary_ids": [],
                    "approved_at": stamped,
                    "approved_by": REVIEWER,
                    "version": 1,
                }
            ),
        )

        finding = Finding.model_validate(
            {
                "id": "fnd-001",
                "assessment_id": handle.assessment_id,
                "title": "Webhook requests may be processed without verified authenticity",
                "summary": "The receiver may accept events without verifying their origin.",
                "description": "The documents describe validation as structural, not cryptographic.",
                "threat_ids": ["thr-001"],
                "requirement_ids": ["req-WEBHOOK-001"],
                "control_mapping_ids": [],
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
        save(handle, finding)
        approve_finding(handle, finding, reviewer_id=REVIEWER)
        yield handle


def test_the_export_validates_against_the_vendored_schema(handle: AssessmentHandle) -> None:
    """Issue #347's acceptance criterion, first half — offline, against the pinned schema."""
    import jsonschema

    schema = json.loads(TM_BOM_SCHEMA_PATH.read_text(encoding="utf-8"))
    document = export_tm_bom(handle)
    jsonschema.validate(document, schema)


def test_the_export_derives_only_from_approved_objects(handle: AssessmentHandle) -> None:
    """Issue #347's acceptance criterion, second half."""
    document = export_tm_bom(handle)
    serialized = json.dumps(document)

    assert "cmp-003" not in serialized  # candidate component
    assert "thr-002" not in serialized  # candidate threat
    assert {row["symbolic_name"] for row in document["components"]} == {"cmp-001", "cmp-002"}
    assert [row["symbolic_name"] for row in document["threats"]] == ["thr-001"]


def test_approved_text_serializes_verbatim(handle: AssessmentHandle) -> None:
    """The DEC-035 discipline, applied to the export family: no rewriting, anywhere."""
    document = export_tm_bom(handle)

    (threat,) = document["threats"]
    assert threat["description"] == "An attacker submits webhook requests the receiver acts on."

    (finding,) = document["extensions"]["trace-ai.local/findings"]
    assert (
        finding["description"]
        == "The documents describe validation as structural, not cryptographic."
    )
    assert finding["severity"] == "high"  # the reviewer-assigned value, nothing derived


def test_unstated_facts_become_named_assumptions_not_silent_guesses(
    handle: AssessmentHandle,
) -> None:
    """DEC-009 under a boolean-only schema: conservative values, each named as unconfirmed."""
    document = export_tm_bom(handle)

    (flow,) = document["data_flows"]
    assert flow["encrypted"] is False  # `unknown` never becomes `true`
    descriptions = [row["description"] for row in document["assumptions"]]
    assert any("df-001" in text and "not an asserted weakness" in text for text in descriptions)
    assert all(row["validity"] in {"unconfirmed", "confirmed"} for row in document["assumptions"])


def test_the_adversarial_actor_becomes_a_persona_with_its_dec_068_fields(
    handle: AssessmentHandle,
) -> None:
    document = export_tm_bom(handle)

    persona_names = {row["symbolic_name"] for row in document["threat_personas"]}
    assert "act-002" in persona_names
    persona = next(row for row in document["threat_personas"] if row["symbolic_name"] == "act-002")
    assert persona["skill_level"] == "oc_sponsored"  # organized_group, mapped
    assert persona["access_level"] == "anonymous"
    assert (threat := document["threats"][0])["threat_persona"] == "act-002"
    assert threat["symbolic_name"] == "thr-001"
    # The legitimate actor stays an actor.
    assert {row["symbolic_name"] for row in document["actors"]} == {"act-001"}


def test_an_unapproved_context_is_refused(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Unapproved", default_configuration("offline-fake", "stride-scenario-based")
        )
        with pytest.raises(ExportError, match="no extracted context"):
            export_tm_bom(service.handle(created.id))


def test_the_export_writes_to_the_outputs_area(handle: AssessmentHandle) -> None:
    written = write_tm_bom(handle)
    assert written.parent.name == "outputs"
    document = json.loads(written.read_text(encoding="utf-8"))
    assert document["scope"]["title"] == "ForgeFlow"
    # Content-addressed: writing again after nothing changed lands on the same artifact.
    assert write_tm_bom(handle) == written
