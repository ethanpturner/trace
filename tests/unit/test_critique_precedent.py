"""DEC-064's precedent feed, and DEC-080's cap: what reaches the critic, and as what.

Issue #339's acceptance criteria are the spine: a dismissal with a rationale appears as marked
precedent in the critique package for a matching subject; precedent never appears outside its
marked block; and a dismissal without a rationale is never fed. Around them, the deterministic
matching rule (requirement shared, or component name matched under DEC-056's normalization), the
context-not-subject boundary (precedent identifiers stay out of `referenceable_ids`), and
DEC-080's ordering and named exclusions.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest

from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    ReviewDisposition,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.finding import Finding
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.critique.input_package import (
    PRECEDENT_HEADING,
    SelectedObjects,
    assemble_review_group,
)
from trace_ai.services.critique.precedent import (
    PRECEDENT_CAP,
    PrecedentSelection,
    select_precedents,
)
from trace_ai.services.evidence.index import EvidenceIndex

PROFILE = resolve_profile("primary-development")

REVIEWER = "reviewer-local"

NAMES = {"cmp-001": "webhook receiver", "cmp-002": "job runner"}
"""Already normalized, the form `component_name_index` produces."""


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
        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
        "confidence": ConfidenceLevel.MEDIUM,
        "generated_by": "mapping-v1",
        "reviewer_status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return ControlMapping.model_validate(payload)


def lineage(**changes: Any) -> SelectedObjects:
    options: dict[str, Any] = {
        "threat": a_threat(),
        "mappings": (a_mapping(),),
        "controls": (),
        "assessments": (),
        "documentation_gaps": (),
    }
    options.update(changes)
    return SelectedObjects(**options)


def a_finding(finding_id: str = "fnd-001", **changes: Any) -> Finding:
    stamped = now()
    payload: dict[str, Any] = {
        "id": finding_id,
        "assessment_id": "asm-001",
        "title": "Webhook requests may be processed without verified authenticity",
        "summary": "The receiver may accept events without verifying their origin.",
        "description": "The documents describe validation as structural, not cryptographic.",
        "threat_ids": ["thr-900"],
        "requirement_ids": ["req-WEBHOOK-001"],
        "control_mapping_ids": ["map-900"],
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": [],
        "evidence_ids": ["evd-001"],
        "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
        "severity": Severity.UNASSIGNED,
        "impact": "Unauthorized job execution.",
        "recommendation": "Verify each event with the platform's signature mechanism.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.REJECTED,
        "generated_by": "finding-consolidation-v1",
        "created_at": stamped,
        "updated_at": stamped,
    }
    payload.update(changes)
    return Finding.model_validate(payload)


def a_dismissal(
    subject_id: str,
    decision_id: str = "dec-001",
    *,
    disposition: ReviewDisposition = ReviewDisposition.REJECT,
    rationale: str | None = "The cited passage covers the internal path, not the public one.",
    at: Any = None,
) -> ReviewerDecision:
    return ReviewerDecision.model_validate(
        {
            "id": decision_id,
            "assessment_id": "asm-001",
            "subject_type": "finding",
            "subject_id": subject_id,
            "disposition": disposition,
            "rationale": rationale,
            "reviewer_id": REVIEWER,
            "created_at": at if at is not None else now(),
        }
    )


def select(**changes: Any) -> PrecedentSelection:
    options: dict[str, Any] = {
        "selected": lineage(),
        "findings": [a_finding()],
        "decisions": [a_dismissal("fnd-001")],
        "component_names": NAMES,
    }
    options.update(changes)
    return select_precedents(**options)


# ------------------------------------------------------------------------------------------
# The deterministic match (DEC-064)
# ------------------------------------------------------------------------------------------


def test_a_requirement_sharing_dismissal_is_selected() -> None:
    selection = select()

    assert [p.finding_id for p in selection.precedents] == ["fnd-001"]
    assert selection.precedents[0].shared_requirement_ids == ("req-WEBHOOK-001",)
    assert selection.precedents[0].rationale.startswith("The cited passage")


def test_a_component_name_match_is_selected_under_normalization() -> None:
    """Requirements differ; only the affected component's normalized name matches."""
    selection = select(findings=[a_finding(requirement_ids=["req-AUTH-003"])])

    assert [p.finding_id for p in selection.precedents] == ["fnd-001"]
    assert selection.precedents[0].shared_requirement_ids == ()
    assert selection.precedents[0].matched_component_names == ("webhook receiver",)


def test_a_dismissal_without_a_rationale_is_never_fed() -> None:
    """Issue #339's second acceptance criterion: a bare rejection supplies no X."""
    assert not select(decisions=[a_dismissal("fnd-001", rationale=None)])
    assert not select(decisions=[a_dismissal("fnd-001", rationale="   ")])


def test_a_non_dismissal_decision_is_never_fed() -> None:
    approval = ReviewerDecision.model_validate(
        {
            "id": "dec-001",
            "assessment_id": "asm-001",
            "subject_type": "finding",
            "subject_id": "fnd-001",
            "disposition": ReviewDisposition.APPROVE,
            "rationale": "Sound analysis.",
            "created_at": now(),
        }
    )
    assert not select(decisions=[approval])


def test_a_dismissal_matching_nothing_is_not_selected() -> None:
    unrelated = a_finding(requirement_ids=["req-AUTH-003"], affected_component_ids=["cmp-002"])
    assert not select(findings=[unrelated])


def test_conversions_are_dismissals_too() -> None:
    for disposition in (
        ReviewDisposition.CONVERT_TO_QUESTION,
        ReviewDisposition.CONVERT_TO_DOCUMENTATION_GAP,
    ):
        selection = select(decisions=[a_dismissal("fnd-001", disposition=disposition)])
        assert selection.precedents[0].disposition == disposition.value


def test_the_latest_dismissal_is_the_standing_reason() -> None:
    stamped = now()
    selection = select(
        decisions=[
            a_dismissal("fnd-001", "dec-001", rationale="First reason.", at=stamped),
            a_dismissal(
                "fnd-001",
                "dec-002",
                disposition=ReviewDisposition.CONVERT_TO_DOCUMENTATION_GAP,
                rationale="Second reason.",
                at=stamped + timedelta(minutes=5),
            ),
        ]
    )
    assert len(selection.precedents) == 1
    assert selection.precedents[0].rationale == "Second reason."
    assert selection.precedents[0].decision_id == "dec-002"


# ------------------------------------------------------------------------------------------
# DEC-080: cap, ordering, and named exclusions
# ------------------------------------------------------------------------------------------


def _many_matches(count: int) -> tuple[list[Finding], list[ReviewerDecision]]:
    stamped = now()
    findings = []
    decisions = []
    for index in range(count):
        finding_id = f"fnd-{index + 1:03d}"
        findings.append(a_finding(finding_id))
        decisions.append(
            a_dismissal(
                finding_id,
                f"dec-{index + 1:03d}",
                at=stamped + timedelta(minutes=index),
            )
        )
    return findings, decisions


def test_the_cap_holds_and_names_what_it_excluded() -> None:
    findings, decisions = _many_matches(PRECEDENT_CAP + 2)
    selection = select(findings=findings, decisions=decisions)

    assert len(selection.precedents) == PRECEDENT_CAP
    assert len(selection.excluded_finding_ids) == 2
    # Recency orders within the class, so the two oldest dismissals are the ones displaced.
    assert selection.excluded_finding_ids == ("fnd-002", "fnd-001")


def test_requirement_matches_precede_name_only_matches() -> None:
    stamped = now()
    name_only = a_finding("fnd-001", requirement_ids=["req-AUTH-003"])
    requirement = a_finding("fnd-002")
    selection = select(
        findings=[name_only, requirement],
        decisions=[
            # The name-only dismissal is more recent; tightness still wins (DEC-080).
            a_dismissal("fnd-001", "dec-001", at=stamped + timedelta(minutes=5)),
            a_dismissal("fnd-002", "dec-002", at=stamped),
        ],
    )
    assert [p.finding_id for p in selection.precedents] == ["fnd-002", "fnd-001"]


def test_recency_orders_within_a_match_class() -> None:
    findings, decisions = _many_matches(3)
    selection = select(findings=findings, decisions=decisions)

    assert [p.finding_id for p in selection.precedents] == ["fnd-003", "fnd-002", "fnd-001"]


# ------------------------------------------------------------------------------------------
# The marked block (issue #339's first and second acceptance criteria)
# ------------------------------------------------------------------------------------------


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Precedent", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        with handle.objects.transaction():
            handle.objects.save(
                Component.model_validate(
                    {
                        "id": "cmp-001",
                        "assessment_id": handle.assessment_id,
                        "name": "Webhook Receiver",
                        "component_type": "service",
                        "internet_accessible": True,
                        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                        "status": ObjectStatus.APPROVED,
                    }
                )
            )
        yield handle


def _package(handle: AssessmentHandle, precedents: PrecedentSelection | None) -> Any:
    return assemble_review_group(
        assessment_id=handle.assessment_id,
        selected=lineage(threat=a_threat(assessment_id=handle.assessment_id)),
        index=EvidenceIndex(handle),
        profile=PROFILE,
        precedents=precedents,
    )


def _marked_block(trusted: str) -> str:
    """The text between the precedent heading and the next section heading."""
    start = trusted.index(f"## {PRECEDENT_HEADING}")
    rest = trusted[start + len(f"## {PRECEDENT_HEADING}") :]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def test_a_matching_dismissal_appears_as_marked_precedent(handle: AssessmentHandle) -> None:
    package = _package(handle, select())

    block = _marked_block(package.trusted)
    assert "The cited passage covers the internal path" in block
    assert "fnd-001" in block
    assert "dec-001" in block


def test_precedent_never_appears_outside_its_marked_block(handle: AssessmentHandle) -> None:
    package = _package(handle, select())

    rationale = "The cited passage covers the internal path, not the public one."
    outside = package.trusted.replace(_marked_block(package.trusted), "")
    assert rationale not in outside
    assert "fnd-001" not in outside
    assert rationale not in package.untrusted


def test_precedent_identifiers_are_not_referenceable(handle: AssessmentHandle) -> None:
    """Context, never subject: a critique targeting a precedent fails reference validation."""
    package = _package(handle, select())

    assert "fnd-001" not in package.referenceable_ids()
    assert "dec-001" not in package.referenceable_ids()
    assert package.metadata["precedents"] == 1


def test_an_empty_selection_renders_no_block(handle: AssessmentHandle) -> None:
    empty = select(decisions=[])
    assert not empty

    for precedents in (None, empty):
        package = _package(handle, precedents)
        assert PRECEDENT_HEADING not in package.trusted
        assert package.metadata["precedents"] == 0


def test_cap_exclusions_are_named_in_the_block(handle: AssessmentHandle) -> None:
    findings, decisions = _many_matches(PRECEDENT_CAP + 1)
    package = _package(handle, select(findings=findings, decisions=decisions))

    block = _marked_block(package.trusted)
    assert "excluded_by_cap" in block
    assert package.metadata["precedents"] == PRECEDENT_CAP
    assert package.metadata["precedents_excluded_by_cap"] == 1
