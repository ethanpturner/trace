"""`Critique`, its vocabularies, and the proposal boundary.

`agent-design.md` section 15 gives the critic six failure conditions and exactly two of them are
structural: critiques lacking target objects, and critiques lacking actionable recommendations.
This file is mostly about those two, because a schema is the only thing that can refuse output and
the other four are judgments.

The vocabularies are closed by DEC-049 and the reasoning is worth repeating where it is tested:
`recommended_action` is described in section 24 as "Keep, revise, reject, merge, investigate",
which names the values; `critique_type` is headed "Critique-type examples", which does not, and is
closed anyway because a type nobody can route on is section 15's "output cannot be traced to
specific issues" arriving through the schema.

`missing_high_impact_threat` is absent, and a test says so rather than leaving its absence to be
noticed. A missing threat has no target object — which section 15 makes invalid output — and
proposing one is the loop section 27's worked example forbids.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain.critique import (
    SEVERITY_CRITIQUE_TYPES,
    Critique,
    CritiqueSubjectType,
    CritiqueType,
    RecommendedAction,
)
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, Severity
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.proposals.critical_review import (
    CRITICAL_REVIEW_AGENT,
    CriticalReviewProposal,
    CritiqueProposal,
    promote_critique,
)


def a_critique(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "crq-001",
        "assessment_id": "asm-001",
        "subject_type": CritiqueSubjectType.CONTROL_MAPPING,
        "subject_id": "map-001",
        "critique_type": CritiqueType.DOCUMENTATION_GAP_ONLY,
        "description": (
            "The mapping concludes the control is unmet where the documentation is silent."
        ),
        "rationale": (
            "The cited passage lists webhook replay handling under known documentation gaps. "
            "That establishes that the topic is undocumented, not that the control is absent."
        ),
        "evidence_ids": ["evd-001"],
        "recommended_action": RecommendedAction.REVISE,
        "confidence": ConfidenceLevel.HIGH,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": CRITICAL_REVIEW_AGENT,
    }
    payload.update(changes)
    return payload


def a_proposal(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subject_type": CritiqueSubjectType.CONTROL_MAPPING,
        "subject_id": "map-001",
        "critique_type": CritiqueType.DOCUMENTATION_GAP_ONLY,
        "description": "The mapping concludes a weakness where the documentation is silent.",
        "rationale": "The cited passage says the topic is undocumented.",
        "evidence_ids": ["evd-001"],
        "recommended_action": RecommendedAction.REVISE,
        "confidence": ConfidenceLevel.HIGH,
    }
    payload.update(changes)
    return payload


# The section 24 field set


def test_a_critique_accepts_the_section_24_fields() -> None:
    critique = Critique.model_validate(a_critique())

    assert critique.id == "crq-001"
    assert critique.recommended_action is RecommendedAction.REVISE


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError, match="severity"):
        Critique.model_validate(a_critique(severity=Severity.HIGH))


@pytest.mark.parametrize("field", ["description", "rationale", "generated_by"])
@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_the_required_prose_fields_reject_empty_text(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Critique.model_validate(a_critique(**{field: value}))


@pytest.mark.parametrize(
    "field", ["subject_type", "subject_id", "description", "rationale", "recommended_action"]
)
def test_the_required_fields_are_required(field: str) -> None:
    payload = a_critique()
    payload.pop(field)

    with pytest.raises(ValidationError):
        Critique.model_validate(payload)


# Targets (section 15's first structural failure condition)


@pytest.mark.parametrize(
    "subject_type, subject_id",
    [
        (CritiqueSubjectType.THREAT, "thr-001"),
        (CritiqueSubjectType.CONTROL, "ctl-001"),
        (CritiqueSubjectType.CONTROL_MAPPING, "map-001"),
        (CritiqueSubjectType.EVIDENCE_ASSESSMENT, "eas-001"),
        (CritiqueSubjectType.DOCUMENTATION_GAP, "gap-001"),
        (CritiqueSubjectType.FINDING, "fnd-001"),
    ],
)
def test_every_subject_type_has_a_matching_prefix(
    subject_type: CritiqueSubjectType, subject_id: str
) -> None:
    critique = Critique.model_validate(a_critique(subject_type=subject_type, subject_id=subject_id))

    assert critique.subject_id == subject_id


def test_a_subject_id_of_the_wrong_type_is_rejected_with_both_values_named() -> None:
    with pytest.raises(ValidationError) as raised:
        Critique.model_validate(
            a_critique(subject_type=CritiqueSubjectType.THREAT, subject_id="map-001")
        )

    message = str(raised.value)
    assert "threat" in message
    assert "map-001" in message


def test_a_subject_id_that_is_not_an_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Critique.model_validate(a_critique(subject_id="the-webhook-mapping"))


def test_the_subject_types_are_dec_049s_six() -> None:
    assert {member.value for member in CritiqueSubjectType} == {
        "threat",
        "control",
        "control_mapping",
        "evidence_assessment",
        "documentation_gap",
        "finding",
    }


# The vocabularies (DEC-049)


def test_the_critique_types_are_section_24s_twelve_less_one() -> None:
    documented = {
        "unsupported_claim",
        "missing_evidence",
        "ignored_inherited_control",
        "duplicate",
        "severity_overstated",
        "severity_understated",
        "missing_precondition",
        "weak_attack_path",
        "generic_recommendation",
        "documentation_gap_only",
        "contradictory_analysis",
    }

    assert {member.value for member in CritiqueType} == documented
    assert len(CritiqueType) == 11


def test_missing_high_impact_threat_is_not_a_critique_type() -> None:
    """DEC-049: it has no target object, and proposing one starts the section 27 loop."""
    assert "missing_high_impact_threat" not in {member.value for member in CritiqueType}


def test_the_recommended_actions_are_section_24s_five() -> None:
    assert {member.value for member in RecommendedAction} == {
        "keep",
        "revise",
        "reject",
        "merge",
        "investigate",
    }


@pytest.mark.parametrize("value", ["nitpick", "severity", "unsupported"])
def test_an_unlisted_critique_type_is_refused(value: str) -> None:
    with pytest.raises(ValidationError):
        Critique.model_validate(a_critique(critique_type=value))


@pytest.mark.parametrize("value", ["approve", "escalate", "keep_and_approve"])
def test_an_unlisted_recommended_action_is_refused(value: str) -> None:
    with pytest.raises(ValidationError):
        Critique.model_validate(a_critique(recommended_action=value))


# The critic recommends; it never states an outcome


def test_the_model_carries_no_field_stating_an_outcome() -> None:
    """Section 15 prohibits directly approving findings; DEC-005 reserves approval for a human."""
    forbidden = {
        "approved",
        "approval",
        "accepted",
        "applied",
        "resolution",
        "outcome",
        "action_taken",
        "severity",
    }

    assert not forbidden & set(Critique.model_fields)


def test_status_is_the_critiques_own_review_state_not_its_targets() -> None:
    """Section 24's `status` is the critique's, and promotion always sets `candidate`."""
    critique = Critique.model_validate(a_critique())

    assert critique.status is ObjectStatus.CANDIDATE


# Severity critiques (DEC-030, DEC-045)


def test_the_severity_types_are_the_two_that_need_a_severity() -> None:
    assert {
        CritiqueType.SEVERITY_OVERSTATED,
        CritiqueType.SEVERITY_UNDERSTATED,
    } == SEVERITY_CRITIQUE_TYPES


@pytest.mark.parametrize("critique_type", sorted(SEVERITY_CRITIQUE_TYPES))
def test_a_severity_critique_against_unassigned_is_refused(critique_type: CritiqueType) -> None:
    critique = Critique.model_validate(
        a_critique(
            subject_type=CritiqueSubjectType.FINDING,
            subject_id="fnd-001",
            critique_type=critique_type,
        )
    )

    with pytest.raises(ValueError, match="DEC-030"):
        critique.check_severity_is_assigned(Severity.UNASSIGNED)


def test_a_severity_critique_against_a_subject_with_no_severity_is_refused() -> None:
    critique = Critique.model_validate(a_critique(critique_type=CritiqueType.SEVERITY_OVERSTATED))

    with pytest.raises(ValueError, match="carries no severity"):
        critique.check_severity_is_assigned(None)


def test_a_severity_critique_against_an_assigned_severity_passes() -> None:
    """DEC-045 makes a documentation gap's rating a real judgment to disagree with."""
    critique = Critique.model_validate(
        a_critique(
            subject_type=CritiqueSubjectType.DOCUMENTATION_GAP,
            subject_id="gap-001",
            critique_type=CritiqueType.SEVERITY_OVERSTATED,
        )
    )

    critique.check_severity_is_assigned(Severity.HIGH)


def test_a_non_severity_critique_ignores_the_check() -> None:
    critique = Critique.model_validate(a_critique())

    critique.check_severity_is_assigned(None)


# The proposal boundary


@pytest.mark.parametrize("field", ["id", "assessment_id", "generated_by", "status"])
def test_the_proposal_omits_the_application_owned_fields(field: str) -> None:
    assert field not in CritiqueProposal.model_fields


@pytest.mark.parametrize(
    "field, value",
    [
        ("id", "crq-001"),
        ("assessment_id", "asm-001"),
        ("generated_by", "critical-review-v1"),
        ("status", ObjectStatus.APPROVED),
    ],
)
def test_a_proposal_carrying_an_application_owned_field_is_refused(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError, match=field):
        CritiqueProposal.model_validate(a_proposal(**{field: value}))


def test_promotion_sets_candidate_and_the_agent_version() -> None:
    proposal = CritiqueProposal.model_validate(a_proposal())

    critique = promote_critique(proposal, critique_id="crq-002", assessment_id="asm-001")

    assert critique.id == "crq-002"
    assert critique.status is ObjectStatus.CANDIDATE
    assert critique.generated_by == CRITICAL_REVIEW_AGENT == "critical-review-v1"


def test_an_empty_response_is_valid() -> None:
    """Section 15 makes superficial volume a failure; a schema demanding one would ask for it."""
    proposal = CriticalReviewProposal.model_validate({})

    assert proposal.critiques == []


# References and distinctness


def test_a_target_outside_the_review_group_is_refused() -> None:
    proposal = CriticalReviewProposal.model_validate(
        {"critiques": [a_proposal(subject_id="map-909")]}
    )

    with pytest.raises(ProposalError, match="map-909"):
        proposal.validate_references({"map-001", "evd-001"})


def test_a_target_inside_the_review_group_passes() -> None:
    proposal = CriticalReviewProposal.model_validate({"critiques": [a_proposal()]})

    proposal.validate_references({"map-001", "evd-001"})


def test_a_citation_outside_the_review_group_is_refused() -> None:
    proposal = CriticalReviewProposal.model_validate(
        {"critiques": [a_proposal(evidence_ids=["evd-909"])]}
    )

    with pytest.raises(ProposalError, match="evd-909"):
        proposal.validate_references({"map-001", "evd-001"})


def test_the_same_challenge_twice_against_one_target_is_refused() -> None:
    proposal = CriticalReviewProposal.model_validate(
        {"critiques": [a_proposal(), a_proposal(description="Said differently.")]}
    )

    with pytest.raises(ProposalError, match="more than once"):
        proposal.validate_distinctness()


def test_two_different_challenges_against_one_target_pass() -> None:
    proposal = CriticalReviewProposal.model_validate(
        {
            "critiques": [
                a_proposal(),
                a_proposal(critique_type=CritiqueType.IGNORED_INHERITED_CONTROL),
            ]
        }
    )

    proposal.validate_distinctness()


def test_the_same_challenge_against_two_targets_passes() -> None:
    proposal = CriticalReviewProposal.model_validate(
        {"critiques": [a_proposal(), a_proposal(subject_id="map-002")]}
    )

    proposal.validate_distinctness()
