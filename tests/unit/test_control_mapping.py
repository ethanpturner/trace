"""`Control`, `ControlMapping`, their proposals, and the promotions between them.

Most of this file is about one rule seen from two ends, because that rule is where DEC-009 either
holds or quietly stops holding:

**A status that asserts something cites evidence; a status that asserts nothing does not.**
`agent-design.md` section 12 makes "unverified controls are marked implemented" a failure condition
of the mapping step. `data-model.md` section 19 says a high proportion of `unverified` mappings "is
the expected result of assessing ordinary architecture documentation" and "must not be treated as a
defect". A schema requiring evidence everywhere would force every honest silence into a status that
asserts something. Both directions are tested.

The other half is DEC-026's inherited-control distinction, which is what the ForgeFlow intentional
non-findings turn on: a platform control the documentation states, and a platform control nothing
states, must not collapse to the same value.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain.base import now
from trace_ai.domain.control import (
    Control,
    ControlType,
    ImplementationStatus,
)
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, ValidationStatus
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.proposals.mapping import (
    MAPPING_AGENT,
    ControlProposal,
    MappingProposal,
    RequirementMappingProposal,
    promote_control,
    promote_mapping,
)


def a_control(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "ctl-001",
        "assessment_id": "asm-001",
        "name": "Managed database encryption at rest",
        "description": "The managed database platform encrypts stored data.",
        "control_type": ControlType.INHERITED,
        "provider_component_id": "cmp-002",
        "protected_asset_ids": ["ast-001"],
        "implementation_status": ImplementationStatus.IMPLEMENTED,
        "validation_status": ValidationStatus.NOT_EVALUATED,
        "evidence_ids": ["evd-001"],
        "generated_by": "context-extraction-v1",
        "created_at": now(),
        "status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return payload


def a_mapping(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "map-001",
        "assessment_id": "asm-001",
        "threat_id": "thr-001",
        "requirement_id": "req-DATA-001",
        "control_ids": ["ctl-001"],
        "applicability_status": ApplicabilityStatus.APPLICABLE,
        "applicability_reason": "The system stores customer source code in a managed database.",
        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
        "confidence": ConfidenceLevel.MEDIUM,
        "generated_by": MAPPING_AGENT,
        "reviewer_status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return payload


def a_control_proposal(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": "managed-db-encryption",
        "name": "Managed database encryption at rest",
        "description": "The managed database platform encrypts stored data.",
        "control_type": ControlType.INHERITED,
        "implementation_status": ImplementationStatus.IMPLEMENTED,
        "evidence_ids": ["evd-001"],
    }
    payload.update(changes)
    return payload


def a_mapping_proposal(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "threat_id": "thr-001",
        "requirement_id": "req-DATA-001",
        "control_keys": ["managed-db-encryption"],
        "applicability_status": ApplicabilityStatus.APPLICABLE,
        "applicability_reason": "The system stores customer source code in a managed database.",
        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
        "confidence": ConfidenceLevel.MEDIUM,
    }
    payload.update(changes)
    return payload


# ------------------------------------------------------------------------------------------
# Closed vocabularies
# ------------------------------------------------------------------------------------------


def test_the_control_vocabularies_are_closed() -> None:
    """Section 18 heads its lists "values", not "examples" — DEC-036's test for a named set."""
    assert [member.value for member in ControlType] == [
        "implemented",
        "inherited",
        "compensating",
        "planned",
        "recommended",
    ]
    assert [member.value for member in ImplementationStatus] == [
        "implemented",
        "partially_implemented",
        "claimed",
        "unknown",
        "absent",
        "not_applicable",
    ]


def test_the_mapping_vocabularies_are_closed() -> None:
    assert [member.value for member in ApplicabilityStatus] == [
        "applicable",
        "conditionally_applicable",
        "not_applicable",
        "unknown",
    ]
    assert [member.value for member in SatisfactionStatus] == [
        "satisfied",
        "partially_satisfied",
        "unverified",
        "unmet",
        "not_applicable",
    ]


@pytest.mark.parametrize("field", ["applicability_status", "satisfaction_status"])
def test_a_value_outside_the_set_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        ControlMapping.model_validate(a_mapping(**{field: "probably_fine"}))


# ------------------------------------------------------------------------------------------
# The applicability rationale
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("reason", ["", "   ", "\n\t"])
def test_an_empty_applicability_reason_is_rejected(reason: str) -> None:
    """Section 12: "requirements are applied without an applicability rationale" is a failure."""
    with pytest.raises(ValidationError, match="applicability_reason"):
        ControlMapping.model_validate(a_mapping(applicability_reason=reason))

    with pytest.raises(ValidationError, match="applicability_reason"):
        RequirementMappingProposal.model_validate(a_mapping_proposal(applicability_reason=reason))


def test_a_not_applicable_mapping_still_states_why() -> None:
    """The rationale is the point of the object; a negative verdict needs one just as much."""
    mapping = ControlMapping.model_validate(
        a_mapping(
            applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
            satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
            applicability_reason="Inbound events are polled rather than delivered.",
        )
    )

    assert mapping.applicability_reason


# ------------------------------------------------------------------------------------------
# Evidence: the rule from both ends
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        SatisfactionStatus.SATISFIED,
        SatisfactionStatus.PARTIALLY_SATISFIED,
        SatisfactionStatus.UNMET,
    ],
)
def test_an_asserted_satisfaction_status_needs_evidence(status: SatisfactionStatus) -> None:
    with pytest.raises(ValidationError, match="evidence"):
        ControlMapping.model_validate(a_mapping(satisfaction_status=status, evidence_ids=[]))


def test_unverified_with_no_evidence_is_valid() -> None:
    """The expected result of assessing ordinary documentation (section 19), not a schema error.

    This is the assertion that keeps DEC-009 from being quietly inverted. A schema requiring
    evidence for every status would leave nowhere to record an honest silence.
    """
    mapping = ControlMapping.model_validate(
        a_mapping(satisfaction_status=SatisfactionStatus.UNVERIFIED, evidence_ids=[])
    )

    assert mapping.satisfaction_status is SatisfactionStatus.UNVERIFIED
    assert mapping.evidence_ids == []


def test_unmet_cannot_be_reached_by_silence() -> None:
    """Section 19 gives the mechanism: an EvidenceReference quotes real text, so absence has
    nothing to cite."""
    with pytest.raises(ValidationError):
        ControlMapping.model_validate(
            a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=[])
        )


@pytest.mark.parametrize(
    "status",
    [
        ImplementationStatus.IMPLEMENTED,
        ImplementationStatus.PARTIALLY_IMPLEMENTED,
        ImplementationStatus.ABSENT,
    ],
)
def test_an_asserted_implementation_status_needs_evidence(status: ImplementationStatus) -> None:
    with pytest.raises(ValidationError, match="evidence"):
        Control.model_validate(a_control(implementation_status=status, evidence_ids=[]))


@pytest.mark.parametrize("status", [ImplementationStatus.CLAIMED, ImplementationStatus.UNKNOWN])
def test_a_claimed_or_unknown_control_needs_no_evidence(status: ImplementationStatus) -> None:
    """The DEC-009 exemption. Removing it would leave an undocumented control nowhere to go but
    `absent`, which asserts a weakness nobody evidenced."""
    control = Control.model_validate(a_control(implementation_status=status, evidence_ids=[]))

    assert control.evidence_ids == []


@pytest.mark.parametrize("kind", [ControlType.PLANNED, ControlType.RECOMMENDED])
def test_a_proposed_control_needs_no_evidence(kind: ControlType) -> None:
    """No source passage describes something nobody has built."""
    control = Control.model_validate(
        a_control(
            control_type=kind,
            implementation_status=ImplementationStatus.IMPLEMENTED,
            evidence_ids=[],
        )
    )

    assert control.control_type is kind


# ------------------------------------------------------------------------------------------
# Inherited-control scope (DEC-026)
# ------------------------------------------------------------------------------------------


def test_there_is_no_inheritance_scope_string() -> None:
    """DEC-026 removed it. Prose could disagree with the structured fields and could not be
    compared against the architecture."""
    assert "inheritance_scope" not in Control.model_fields
    assert "inheritance_scope" not in ControlProposal.model_fields


def test_scope_is_expressed_by_the_structured_fields() -> None:
    control = Control.model_validate(
        a_control(
            provider_component_id="cmp-002",
            protected_component_ids=["cmp-001"],
            protected_asset_ids=["ast-001"],
            limitations=["covers data at rest only"],
        )
    )

    assert control.provider_component_id == "cmp-002"
    assert control.protected_asset_ids == ["ast-001"]
    assert control.limitations == ["covers data at rest only"]


def test_a_documented_inheritance_is_distinguishable_from_an_assumed_one() -> None:
    """DEC-026's table, and what the ForgeFlow intentional non-findings turn on.

    Platform provides it and the documentation says so; platform probably provides it and nothing
    says so. These must not collapse to one value — the second becomes a `Question` and never an
    assertion that the control is absent.
    """
    documented = Control.model_validate(
        a_control(
            control_type=ControlType.INHERITED,
            implementation_status=ImplementationStatus.IMPLEMENTED,
            evidence_ids=["evd-001"],
        )
    )
    assumed = Control.model_validate(
        a_control(
            control_type=ControlType.INHERITED,
            implementation_status=ImplementationStatus.CLAIMED,
            evidence_ids=[],
        )
    )

    assert documented.is_documented_inheritance
    assert not assumed.is_documented_inheritance
    assert assumed.implementation_status is not ImplementationStatus.ABSENT


def test_an_unevidenced_inherited_control_is_never_absent() -> None:
    """DEC-013: it never resolves to `unmet`, and the schema will not let it be `absent` either."""
    with pytest.raises(ValidationError):
        Control.model_validate(
            a_control(
                control_type=ControlType.INHERITED,
                implementation_status=ImplementationStatus.ABSENT,
                evidence_ids=[],
            )
        )


# ------------------------------------------------------------------------------------------
# Suppressed conclusions (DEC-025)
# ------------------------------------------------------------------------------------------


def test_a_suppression_records_both_halves() -> None:
    mapping = ControlMapping.model_validate(
        a_mapping(
            suppressed_conclusion="signature verification is missing",
            suppressed_by="documentation stating only that requests are validated",
        )
    )

    assert mapping.suppressed_conclusion
    assert mapping.suppressed_by


@pytest.mark.parametrize(
    "changes",
    [
        {"suppressed_conclusion": "signature verification is missing"},
        {"suppressed_by": "documentation stating only that requests are validated"},
    ],
)
def test_half_a_suppression_is_rejected(changes: dict[str, str]) -> None:
    """A conclusion marked as not drawn, with nothing saying why, reads as an unexplained
    omission rather than a deliberate one."""
    with pytest.raises(ValidationError, match="DEC-025"):
        ControlMapping.model_validate(a_mapping(**changes))


# ------------------------------------------------------------------------------------------
# Provenance (DEC-044)
# ------------------------------------------------------------------------------------------


def test_a_control_records_which_node_created_it() -> None:
    assert "generated_by" in Control.model_fields
    assert Control.model_fields["generated_by"].is_required()


@pytest.mark.parametrize("origin", ["context-extraction-v1", "mapping-v1", "reviewer_edit"])
def test_the_three_origins_are_recordable(origin: str) -> None:
    control = Control.model_validate(a_control(generated_by=origin))

    assert control.generated_by == origin


# ------------------------------------------------------------------------------------------
# The proposals carry nothing the application owns
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "ctl-001"),
        ("assessment_id", "asm-001"),
        ("generated_by", "mapping-v1"),
        ("validation_status", "supported"),
        ("status", "approved"),
        ("created_at", "2026-08-09T00:00:00Z"),
    ],
)
def test_the_control_proposal_refuses_what_the_application_owns(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match=field):
        ControlProposal.model_validate(a_control_proposal(**{field: value}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "map-001"),
        ("assessment_id", "asm-001"),
        ("generated_by", "mapping-v1"),
        ("reviewer_status", "approved"),
    ],
)
def test_the_mapping_proposal_refuses_what_the_application_owns(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match=field):
        RequirementMappingProposal.model_validate(a_mapping_proposal(**{field: value}))


def test_a_control_is_proposed_by_key_and_a_threat_by_identifier() -> None:
    """The one place the mapping step needs both. A control does not exist yet; a threat does."""
    proposal = RequirementMappingProposal.model_validate(a_mapping_proposal())

    assert proposal.control_keys == ["managed-db-encryption"]
    assert proposal.threat_id == "thr-001"


def test_a_control_key_shaped_like_an_identifier_is_refused() -> None:
    """DEC-018. An agent-chosen `ctl-001` could collide with a record that already exists."""
    with pytest.raises(ValidationError):
        ControlProposal.model_validate(a_control_proposal(key="ctl-001"))


# ------------------------------------------------------------------------------------------
# Reference and key validation
# ------------------------------------------------------------------------------------------


def test_an_identifier_the_package_did_not_supply_is_refused() -> None:
    proposal = MappingProposal.model_validate(
        {
            "controls": [a_control_proposal()],
            "mappings": [a_mapping_proposal()],
        }
    )

    # The package supplied the requirement and the evidence but not the threat, so the threat
    # the mapping names is the one that has to be reported.
    with pytest.raises(ProposalError, match="thr-001"):
        proposal.validate_references({"req-DATA-001", "evd-001"})


def test_a_control_key_referenced_by_nothing_proposed_is_refused() -> None:
    proposal = MappingProposal.model_validate({"controls": [], "mappings": [a_mapping_proposal()]})

    with pytest.raises(ProposalError, match="managed-db-encryption"):
        proposal.validate_keys()


def test_two_controls_sharing_a_key_are_refused() -> None:
    proposal = MappingProposal.model_validate(
        {
            "controls": [a_control_proposal(), a_control_proposal(name="Another")],
            "mappings": [],
        }
    )

    with pytest.raises(ProposalError, match="twice"):
        proposal.validate_keys()


def test_a_well_formed_proposal_validates() -> None:
    proposal = MappingProposal.model_validate(
        {"controls": [a_control_proposal()], "mappings": [a_mapping_proposal()]}
    )

    proposal.validate_keys()
    proposal.validate_references({"thr-001", "req-DATA-001", "evd-001"})


def test_an_empty_mapping_response_is_valid() -> None:
    """A requirement that applies to no threat in scope produces nothing."""
    assert MappingProposal.model_validate({}).mappings == []


# ------------------------------------------------------------------------------------------
# Promotion
# ------------------------------------------------------------------------------------------


def test_promoting_a_control_produces_a_candidate_that_has_not_been_evaluated() -> None:
    """`validation_status` is not a parameter: whether the evidence supports the control is the
    Evidence Validation step's answer."""
    control = promote_control(
        ControlProposal.model_validate(a_control_proposal()),
        control_id="ctl-007",
        assessment_id="asm-001",
    )

    assert control.id == "ctl-007"
    assert control.status is ObjectStatus.CANDIDATE
    assert control.validation_status is ValidationStatus.NOT_EVALUATED
    assert control.generated_by == MAPPING_AGENT


def test_promoting_a_mapping_resolves_control_keys_to_identifiers() -> None:
    mapping = promote_mapping(
        RequirementMappingProposal.model_validate(a_mapping_proposal()),
        mapping_id="map-004",
        assessment_id="asm-001",
        control_ids={"managed-db-encryption": "ctl-007"},
    )

    assert mapping.control_ids == ["ctl-007"]
    assert mapping.reviewer_status is ObjectStatus.CANDIDATE


def test_promotion_keeps_existing_control_identifiers_alongside_resolved_keys() -> None:
    mapping = promote_mapping(
        RequirementMappingProposal.model_validate(
            a_mapping_proposal(existing_control_ids=["ctl-002"])
        ),
        mapping_id="map-004",
        assessment_id="asm-001",
        control_ids={"managed-db-encryption": "ctl-007"},
    )

    assert mapping.control_ids == ["ctl-007", "ctl-002"]


def test_promotion_refuses_before_producing_a_mapping_pointing_at_nothing() -> None:
    with pytest.raises(ProposalError, match="managed-db-encryption"):
        promote_mapping(
            RequirementMappingProposal.model_validate(a_mapping_proposal()),
            mapping_id="map-004",
            assessment_id="asm-001",
            control_ids={},
        )


def test_promotion_cannot_be_asked_for_an_approved_object() -> None:
    import inspect

    assert "status" not in inspect.signature(promote_control).parameters
    assert "reviewer_status" not in inspect.signature(promote_mapping).parameters


def test_a_promoted_mapping_still_obeys_the_evidence_rule() -> None:
    """The proposal cannot route around the domain object's validator."""
    with pytest.raises(ValidationError):
        promote_mapping(
            RequirementMappingProposal.model_validate(
                a_mapping_proposal(
                    satisfaction_status=SatisfactionStatus.SATISFIED, evidence_ids=[]
                )
            ),
            mapping_id="map-004",
            assessment_id="asm-001",
            control_ids={"managed-db-encryption": "ctl-007"},
        )
