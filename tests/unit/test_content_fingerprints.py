"""DEC-066: the persisted content fingerprint, equal to the matcher's computation by construction.

The acceptance criterion for issue #341 is stated as an equality: for the same object, the value
`persist_consolidation` stores is the value `services/evaluation/matching.py` computes. The tests
here assert that equality directly, then walk the identity rules — rewording leaves the
fingerprint alone, an identity-field edit moves it and the move lands in the captured delta, a
merge follows the survivor's unions, and a DEC-051 conversion fingerprints the gap it creates.

Coarseness is asserted deliberately: two findings citing the same requirements against the same
component names share a fingerprint whatever their prose says, because DEC-056 accepted exactly
that coarseness and the fingerprint is that rule promoted to an object property.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

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
from trace_ai.domain.finding import Finding
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evaluation.matching import (
    finding_fingerprint,
    gap_fingerprint,
    normalized_name,
)
from trace_ai.services.findings.fingerprints import (
    component_name_index,
    gap_identity_indexes,
)
from trace_ai.workflow.finding_consolidation import ConsolidationOutcome, persist_consolidation
from trace_ai.workflow.finding_dedup import dedupe_findings, persist_dedup
from trace_ai.workflow.finding_review import (
    convert_to_documentation_gap,
    edit_finding,
    merge_by_reviewer,
)

REVIEWER = "reviewer-local"


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Fingerprints", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


def save[ModelT](handle: AssessmentHandle, obj: ModelT) -> ModelT:
    with handle.objects.transaction():
        handle.objects.save(obj)  # type: ignore[arg-type]
    return obj


def a_component(handle: AssessmentHandle, component_id: str, name: str) -> Component:
    return save(
        handle,
        Component.model_validate(
            {
                "id": component_id,
                "assessment_id": handle.assessment_id,
                "name": name,
                "component_type": "service",
                "internet_accessible": False,
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        ),
    )


def a_threat(handle: AssessmentHandle, **changes: Any) -> Threat:
    payload: dict[str, Any] = {
        "id": "thr-001",
        "assessment_id": handle.assessment_id,
        "title": "Forged webhooks trigger unauthorized analysis jobs",
        "description": "An attacker submits webhook requests the receiver acts on.",
        "methodology": "stride-scenario-based",
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "impact": "Unauthorized jobs and denial of service.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.APPROVED,
        "generated_by": "threat-analysis-v1",
        "created_at": now(),
    }
    payload.update(changes)
    return save(handle, Threat.model_validate(payload))


def a_mapping(handle: AssessmentHandle, **changes: Any) -> ControlMapping:
    payload: dict[str, Any] = {
        "id": "map-001",
        "assessment_id": handle.assessment_id,
        "threat_id": "thr-001",
        "requirement_id": "req-WEBHOOK-001",
        "applicability_status": ApplicabilityStatus.APPLICABLE,
        "applicability_reason": "The system exposes an endpoint accepting external events.",
        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
        "confidence": ConfidenceLevel.MEDIUM,
        "generated_by": "mapping-v1",
        "reviewer_status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return save(handle, ControlMapping.model_validate(payload))


def a_finding(handle: AssessmentHandle, *, persist: bool = True, **changes: Any) -> Finding:
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
    return save(handle, finding) if persist else finding


def a_gap(handle: AssessmentHandle, *, persist: bool = True, **changes: Any) -> DocumentationGap:
    payload: dict[str, Any] = {
        "id": "gap-001",
        "assessment_id": handle.assessment_id,
        "title": "Webhook authenticity verification is not documented",
        "description": "The documents do not establish whether req-WEBHOOK-001 is met.",
        "importance": "The endpoint accepts external events; its verification is unassessed.",
        "related_object_ids": ["thr-001", "map-001"],
        "severity": Severity.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "finding-consolidation-v1",
    }
    payload.update(changes)
    gap = DocumentationGap.model_validate(payload)
    return save(handle, gap) if persist else gap


# ------------------------------------------------------------------------------------------
# The persisted value is the matcher's value
# ------------------------------------------------------------------------------------------


def test_a_persisted_finding_carries_the_matchers_fingerprint(handle: AssessmentHandle) -> None:
    a_component(handle, "cmp-001", "Webhook  Receiver")
    a_threat(handle)
    a_mapping(handle)

    outcome = ConsolidationOutcome(findings=(a_finding(handle, persist=False),))
    stored = persist_consolidation(handle, outcome).findings[0]

    # The index the evaluation matcher builds, constructed the way metrics.py constructs it.
    matcher_index = {
        component.id: normalized_name(component.name)
        for component in handle.objects.list(Component)
    }
    assert stored.content_fingerprint == finding_fingerprint(stored, matcher_index)
    assert stored.content_fingerprint is not None
    assert stored.content_fingerprint.startswith("sha256:")
    assert handle.objects.get(Finding, stored.id).content_fingerprint == stored.content_fingerprint


def test_a_persisted_gap_carries_the_matchers_fingerprint(handle: AssessmentHandle) -> None:
    a_component(handle, "cmp-001", "Webhook Receiver")
    a_threat(handle)
    a_mapping(handle)

    outcome = ConsolidationOutcome(documentation_gaps=(a_gap(handle, persist=False),))
    stored = persist_consolidation(handle, outcome).documentation_gaps[0]

    requirement_by_mapping, component_names_by_mapping = gap_identity_indexes(handle)
    assert stored.content_fingerprint == gap_fingerprint(
        stored,
        requirement_by_mapping=requirement_by_mapping,
        component_names_by_mapping=component_names_by_mapping,
    )
    assert stored.content_fingerprint is not None
    assert stored.content_fingerprint.startswith("sha256:")


def test_the_identity_is_structural_not_prose(handle: AssessmentHandle) -> None:
    """Two findings over the same ground share a fingerprint whatever their wording."""
    a_component(handle, "cmp-001", "Webhook Receiver")
    names = component_name_index(handle)

    one = a_finding(handle, persist=False)
    other = a_finding(
        handle,
        persist=False,
        id="fnd-002",
        title="Entirely different words",
        summary="Different summary.",
        description="Different description.",
    )
    assert finding_fingerprint(one, names) == finding_fingerprint(other, names)


def test_the_component_name_is_normalized_before_hashing(handle: AssessmentHandle) -> None:
    """`Webhook  Receiver` and `webhook receiver` are one component to DEC-056, so one identity."""
    a_component(handle, "cmp-001", "Webhook  Receiver")
    spaced = component_name_index(handle)

    with handle.objects.transaction():
        handle.objects.save(
            Component.model_validate(
                {
                    **handle.objects.get(Component, "cmp-001").model_dump(),
                    "name": "webhook receiver",
                }
            )
        )
    folded = component_name_index(handle)

    finding = a_finding(handle, persist=False)
    assert finding_fingerprint(finding, spaced) == finding_fingerprint(finding, folded)


# ------------------------------------------------------------------------------------------
# Recomputation follows identity fields, and only identity fields
# ------------------------------------------------------------------------------------------


def test_a_rewording_edit_leaves_the_fingerprint_alone(handle: AssessmentHandle) -> None:
    a_component(handle, "cmp-001", "Webhook Receiver")
    finding = a_finding(handle)
    original = component_name_index(handle)
    fingerprinted = save(
        handle,
        Finding.model_validate(
            {**finding.model_dump(), "content_fingerprint": finding_fingerprint(finding, original)}
        ),
    )

    edited, _ = edit_finding(
        handle,
        fingerprinted,
        {"description": "Reworded entirely, same ground."},
        reviewer_id=REVIEWER,
    )
    assert edited.content_fingerprint == fingerprinted.content_fingerprint


def test_an_identity_edit_recomputes_and_the_delta_records_it(handle: AssessmentHandle) -> None:
    a_component(handle, "cmp-001", "Webhook Receiver")
    a_component(handle, "cmp-002", "Job Runner")
    finding = a_finding(handle)
    names = component_name_index(handle)
    fingerprinted = save(
        handle,
        Finding.model_validate(
            {**finding.model_dump(), "content_fingerprint": finding_fingerprint(finding, names)}
        ),
    )

    edited, decision = edit_finding(
        handle,
        fingerprinted,
        {"affected_component_ids": ["cmp-001", "cmp-002"]},
        reviewer_id=REVIEWER,
    )
    assert edited.content_fingerprint == finding_fingerprint(edited, names)
    assert edited.content_fingerprint != fingerprinted.content_fingerprint
    # The identity change is itself observable: the recomputed fingerprint is in the delta.
    assert decision.prior_value is not None
    assert "content_fingerprint" in decision.prior_value


def test_a_requirement_edit_recomputes(handle: AssessmentHandle) -> None:
    a_component(handle, "cmp-001", "Webhook Receiver")
    finding = a_finding(handle)
    names = component_name_index(handle)
    fingerprinted = save(
        handle,
        Finding.model_validate(
            {**finding.model_dump(), "content_fingerprint": finding_fingerprint(finding, names)}
        ),
    )

    edited, _ = edit_finding(
        handle,
        fingerprinted,
        {"requirement_ids": ["req-WEBHOOK-001", "req-AUTH-003"]},
        reviewer_id=REVIEWER,
    )
    assert edited.content_fingerprint == finding_fingerprint(edited, names)
    assert edited.content_fingerprint != fingerprinted.content_fingerprint


# ------------------------------------------------------------------------------------------
# Merges move the survivor's fingerprint with its unions
# ------------------------------------------------------------------------------------------


def test_an_automatic_merge_refingerprints_the_survivor(handle: AssessmentHandle) -> None:
    a_component(handle, "cmp-001", "Webhook Receiver")
    a_component(handle, "cmp-002", "Job Runner")
    names = component_name_index(handle)

    survivor = a_finding(handle)
    duplicate = a_finding(
        handle, id="fnd-002", affected_component_ids=["cmp-002"], affected_asset_ids=[]
    )
    outcome = persist_dedup(handle, dedupe_findings([survivor, duplicate]))

    merged = next(f for f in outcome.findings if f.id == survivor.id)
    assert merged.affected_component_ids == ["cmp-001", "cmp-002"]
    assert merged.content_fingerprint == finding_fingerprint(merged, names)
    assert handle.objects.get(Finding, survivor.id).content_fingerprint == (
        merged.content_fingerprint
    )


def test_a_reviewer_merge_refingerprints_the_survivor(handle: AssessmentHandle) -> None:
    a_component(handle, "cmp-001", "Webhook Receiver")
    a_component(handle, "cmp-002", "Job Runner")
    names = component_name_index(handle)

    survivor = a_finding(handle)
    other = a_finding(
        handle,
        id="fnd-002",
        threat_ids=["thr-002"],
        requirement_ids=["req-AUTH-003"],
        affected_component_ids=["cmp-002"],
    )
    changed, _, _ = merge_by_reviewer(
        handle,
        survivor.id,
        [other.id],
        reviewer_id=REVIEWER,
        rationale="One weakness reported twice.",
    )

    merged = next(f for f in changed if f.id == survivor.id)
    assert merged.requirement_ids == ["req-WEBHOOK-001", "req-AUTH-003"]
    assert merged.content_fingerprint == finding_fingerprint(merged, names)


# ------------------------------------------------------------------------------------------
# A conversion fingerprints the gap it creates
# ------------------------------------------------------------------------------------------


def test_a_converted_gap_is_fingerprinted(handle: AssessmentHandle) -> None:
    a_component(handle, "cmp-001", "Webhook Receiver")
    a_threat(handle)
    a_mapping(handle)
    finding = a_finding(handle)

    gap, _, _ = convert_to_documentation_gap(
        handle,
        finding,
        importance="The verification question stands; the weakness claim did not.",
        severity=Severity.MEDIUM,
        reviewer_id=REVIEWER,
    )

    requirement_by_mapping, component_names_by_mapping = gap_identity_indexes(handle)
    assert gap.content_fingerprint == gap_fingerprint(
        gap,
        requirement_by_mapping=requirement_by_mapping,
        component_names_by_mapping=component_names_by_mapping,
    )
    assert gap.content_fingerprint is not None
