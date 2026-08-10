"""`EvidenceAssessment`, its proposal, and the promotion between them.

The object exists to hold one distinction: a conclusion the evidence supports, versus a conclusion
that has merely been repeated. `agent-design.md` section 14 makes "treat repeated model claims as
independent corroboration" a prohibited operation, and until this object exists that prohibition
has nowhere to live — three steps asserting the same thing look exactly like three passages saying
it.

Three rules carry most of the file:

**A status that says something about a passage names one.** Section 14's "unsupported claims are
marked supported" failure condition, enforced structurally. `unsupported` is deliberately *not* in
that set: "no passage supports this" is a statement about the evidence set rather than about a
passage, and requiring a citation for it would leave the ordinary DEC-009 case with nowhere to go.

**`evidence_strengths` and `evidence_ids` agree in both directions** (DEC-022). Both drifts are
invisible downstream and DEC-022's own tradeoffs name them.

**The evidence hierarchy is a vocabulary and not a score** (DEC-047). Section 14 says so in its own
words, and the test here is about the *module*: no function ranks two levels, and no field stores a
position. A rank helper would make the document's sentence false the moment anything compared two
values.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain import evidence_assessment as module
from trace_ai.domain.base import now
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ValidationStatus,
)
from trace_ai.domain.evidence_assessment import (
    EVIDENCE_HIERARCHY,
    EvidenceAssessment,
    EvidenceHierarchyLevel,
    Recommendation,
    SubjectType,
)
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.proposals.evidence_validation import (
    EVIDENCE_VALIDATION_AGENT,
    EvidenceAssessmentProposal,
    EvidenceValidationProposal,
    promote_assessment,
)


def an_assessment(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "eas-001",
        "assessment_id": "asm-001",
        "subject_type": SubjectType.CONTROL_MAPPING,
        "subject_id": "map-001",
        "evidence_ids": ["evd-001"],
        "evidence_strengths": {"evd-001": EvidenceStrength.DIRECT},
        "validation_status": ValidationStatus.SUPPORTED,
        "rationale": (
            "The passage names the identity provider and states the boundary of its "
            "responsibility, which is what the requirement asks for."
        ),
        "confidence": ConfidenceLevel.HIGH,
        "recommendation": Recommendation.CONTINUE,
        "generated_by": EVIDENCE_VALIDATION_AGENT,
        "created_at": now(),
    }
    payload.update(changes)
    return payload


def a_proposal(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subject_type": SubjectType.CONTROL_MAPPING,
        "subject_id": "map-001",
        "evidence_ids": ["evd-001"],
        "evidence_strengths": {"evd-001": EvidenceStrength.DIRECT},
        "validation_status": ValidationStatus.SUPPORTED,
        "rationale": "The passage names the identity provider.",
        "confidence": ConfidenceLevel.HIGH,
        "recommendation": Recommendation.CONTINUE,
    }
    payload.update(changes)
    return payload


# The section 20 field set


def test_an_assessment_accepts_the_section_20_fields() -> None:
    assessed = EvidenceAssessment.model_validate(an_assessment())

    assert assessed.id == "eas-001"
    assert assessed.validation_status is ValidationStatus.SUPPORTED
    assert assessed.evidence_strengths == {"evd-001": EvidenceStrength.DIRECT}


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError, match="severity"):
        EvidenceAssessment.model_validate(an_assessment(severity="high"))


@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_rationale_rejects_empty_or_whitespace_text(value: str) -> None:
    """A classification with no argument behind it is model confidence in a finding's shape."""
    with pytest.raises(ValidationError):
        EvidenceAssessment.model_validate(an_assessment(rationale=value))


def test_the_optional_fields_are_optional() -> None:
    payload = an_assessment()
    assessed = EvidenceAssessment.model_validate(payload)

    assert assessed.missing_evidence == []
    assert assessed.contradictions == []


# subject_type and subject_id


@pytest.mark.parametrize(
    "subject_type, subject_id",
    [
        (SubjectType.CONTEXT_CLAIM, "ctx-001"),
        (SubjectType.CONTROL, "ctl-001"),
        (SubjectType.CONTROL_MAPPING, "map-001"),
        (SubjectType.THREAT, "thr-001"),
        (SubjectType.FINDING, "fnd-001"),
    ],
)
def test_every_subject_type_has_a_matching_prefix(
    subject_type: SubjectType, subject_id: str
) -> None:
    assessed = EvidenceAssessment.model_validate(
        an_assessment(subject_type=subject_type, subject_id=subject_id)
    )

    assert assessed.subject_id == subject_id


def test_a_subject_id_of_the_wrong_type_is_rejected_with_both_values_named() -> None:
    with pytest.raises(ValidationError) as raised:
        EvidenceAssessment.model_validate(
            an_assessment(subject_type=SubjectType.THREAT, subject_id="map-001")
        )

    message = str(raised.value)
    assert "threat" in message
    assert "map-001" in message


def test_a_subject_id_that_is_not_an_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidenceAssessment.model_validate(an_assessment(subject_id="the-webhook-mapping"))


def test_documentation_gap_is_not_a_subject_type() -> None:
    """Section 14 lists gap candidates among the agent's outputs, not among what it evaluates."""
    assert "documentation_gap" not in {member.value for member in SubjectType}


def test_the_subject_types_are_section_20s_five() -> None:
    assert {member.value for member in SubjectType} == {
        "context_claim",
        "control",
        "control_mapping",
        "threat",
        "finding",
    }


# The evidence rule


@pytest.mark.parametrize(
    "status",
    [
        ValidationStatus.SUPPORTED,
        ValidationStatus.PARTIALLY_SUPPORTED,
    ],
)
def test_a_status_that_asserts_something_needs_evidence(status: ValidationStatus) -> None:
    with pytest.raises(ValidationError, match="cites no evidence"):
        EvidenceAssessment.model_validate(
            an_assessment(validation_status=status, evidence_ids=[], evidence_strengths={})
        )


def test_contradicted_with_no_evidence_is_refused() -> None:
    with pytest.raises(ValidationError, match="cites no evidence"):
        EvidenceAssessment.model_validate(
            an_assessment(
                validation_status=ValidationStatus.CONTRADICTED,
                evidence_ids=[],
                evidence_strengths={},
                contradictions=["obs-001"],
            )
        )


def test_not_evaluated_with_no_evidence_is_valid() -> None:
    """Not evaluating something is a legitimate state and must not require evidence."""
    assessed = EvidenceAssessment.model_validate(
        an_assessment(
            validation_status=ValidationStatus.NOT_EVALUATED,
            evidence_ids=[],
            evidence_strengths={},
            recommendation=Recommendation.CONTINUE,
        )
    )

    assert assessed.evidence_ids == []


@pytest.mark.parametrize(
    "status",
    [ValidationStatus.UNSUPPORTED, ValidationStatus.REQUIRES_CONFIRMATION],
)
def test_a_status_that_asserts_nothing_needs_no_evidence(status: ValidationStatus) -> None:
    """`unsupported` is a statement about the evidence set, not about a passage."""
    assessed = EvidenceAssessment.model_validate(
        an_assessment(validation_status=status, evidence_ids=[], evidence_strengths={})
    )

    assert assessed.validation_status is status


def test_contradicted_names_a_contradiction() -> None:
    """Scenario section 16.1: Trace must not silently choose the safer statement."""
    with pytest.raises(ValidationError, match="records no contradiction"):
        EvidenceAssessment.model_validate(
            an_assessment(validation_status=ValidationStatus.CONTRADICTED)
        )


def test_a_contradiction_is_referenced_by_observation_identifier() -> None:
    """DEC-021: free text here could not be joined back to the passages that disagree."""
    assessed = EvidenceAssessment.model_validate(
        an_assessment(validation_status=ValidationStatus.CONTRADICTED, contradictions=["obs-001"])
    )

    assert assessed.contradictions == ["obs-001"]


def test_a_contradiction_that_is_not_an_observation_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidenceAssessment.model_validate(
            an_assessment(
                validation_status=ValidationStatus.CONTRADICTED,
                contradictions=["the two documents disagree"],
            )
        )


# evidence_strengths (DEC-022)


def test_every_cited_reference_carries_a_strength() -> None:
    with pytest.raises(ValidationError, match="carry no strength"):
        EvidenceAssessment.model_validate(an_assessment(evidence_ids=["evd-001", "evd-002"]))


def test_a_strength_for_uncited_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError, match="not in evidence_ids"):
        EvidenceAssessment.model_validate(
            an_assessment(
                evidence_strengths={
                    "evd-001": EvidenceStrength.DIRECT,
                    "evd-002": EvidenceStrength.CONTEXTUAL,
                }
            )
        )


def test_the_strength_errors_name_the_offending_identifier() -> None:
    with pytest.raises(ValidationError, match="evd-002"):
        EvidenceAssessment.model_validate(an_assessment(evidence_ids=["evd-001", "evd-002"]))


# The evidence hierarchy (DEC-047)


def test_the_hierarchy_is_section_14s_seven_levels_in_order() -> None:
    assert EVIDENCE_HIERARCHY == (
        EvidenceHierarchyLevel.REVIEWER_CONFIRMED_FACT,
        EvidenceHierarchyLevel.DIRECT_IMPLEMENTATION_OR_CONFIGURATION,
        EvidenceHierarchyLevel.EXPLICIT_ARCHITECTURE_DOCUMENTATION,
        EvidenceHierarchyLevel.STRUCTURED_PROJECT_INPUT,
        EvidenceHierarchyLevel.MULTIPLE_CONSISTENT_CONTEXTUAL_REFERENCES,
        EvidenceHierarchyLevel.REASONABLE_INFERENCE,
        EvidenceHierarchyLevel.UNSUPPORTED_ASSUMPTION,
    )
    assert len(EVIDENCE_HIERARCHY) == len(EvidenceHierarchyLevel) == 7


def test_no_arithmetic_is_performed_over_the_hierarchy() -> None:
    """Section 14: "guidance, not a universal scoring formula" (DEC-047).

    The module exposes no callable that would let a level become a number. A rank helper is the
    natural implementation and it is the one that makes the document's sentence false, because a
    comparison downstream is a score whatever it is named.
    """
    defined = {
        name
        for name, value in vars(module).items()
        if not name.startswith("_")
        and inspect.isfunction(value)
        and value.__module__ == module.__name__
    }

    assert not defined, f"{sorted(defined)} could turn a hierarchy label into a comparison"


def test_no_field_stores_a_hierarchy_level() -> None:
    """The hierarchy is cited in a rationale, in the agent's words. It is not a column."""
    annotations = {str(field.annotation) for field in EvidenceAssessment.model_fields.values()}

    assert not any("EvidenceHierarchyLevel" in annotation for annotation in annotations)


def test_the_hierarchy_levels_carry_no_numeric_value() -> None:
    for level in EvidenceHierarchyLevel:
        assert isinstance(level.value, str)
        assert not level.value.isdigit()


# The recommendation (DEC-047)


def test_the_recommendation_is_a_closed_vocabulary() -> None:
    assert {member.value for member in Recommendation} == {
        "continue",
        "revise",
        "stop",
        "downgrade_to_question",
        "documentation_gap",
    }


@pytest.mark.parametrize("recommendation", list(Recommendation))
def test_every_recommendation_is_accepted(recommendation: Recommendation) -> None:
    assessed = EvidenceAssessment.model_validate(an_assessment(recommendation=recommendation))

    assert assessed.recommendation is recommendation


def test_the_recommendation_is_required() -> None:
    payload = an_assessment()
    payload.pop("recommendation")

    with pytest.raises(ValidationError):
        EvidenceAssessment.model_validate(payload)


# The proposal boundary


@pytest.mark.parametrize("field", ["id", "assessment_id", "generated_by", "created_at"])
def test_the_proposal_omits_the_application_owned_fields(field: str) -> None:
    assert field not in EvidenceAssessmentProposal.model_fields


@pytest.mark.parametrize(
    "field, value",
    [
        ("id", "eas-001"),
        ("assessment_id", "asm-001"),
        ("generated_by", "evidence-validation-v1"),
    ],
)
def test_a_proposal_carrying_an_application_owned_field_is_refused(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match=field):
        EvidenceAssessmentProposal.model_validate(a_proposal(**{field: value}))


def test_the_proposal_carries_no_finding_and_no_approval() -> None:
    """Section 14 prohibits approving findings; DEC-005 reserves approval for the checkpoint."""
    fields = set(EvidenceAssessmentProposal.model_fields)

    assert not fields & {"finding", "approved", "status", "reviewer_status", "severity"}


def test_promotion_sets_the_application_owned_fields() -> None:
    proposal = EvidenceAssessmentProposal.model_validate(a_proposal())

    assessed = promote_assessment(proposal, assessment_id="eas-002", parent_assessment_id="asm-001")

    assert assessed.id == "eas-002"
    assert assessed.assessment_id == "asm-001"
    assert assessed.generated_by == EVIDENCE_VALIDATION_AGENT == "evidence-validation-v1"
    assert assessed.recommendation is Recommendation.CONTINUE


def test_promotion_drops_the_quoted_text() -> None:
    """It exists to have been checked; a stored second copy is the divergence to avoid."""
    proposal = EvidenceAssessmentProposal.model_validate(
        a_proposal(quoted_text={"evd-001": "the identity provider"})
    )

    assessed = promote_assessment(proposal, assessment_id="eas-002", parent_assessment_id="asm-001")

    assert "quoted_text" not in assessed.model_dump()


# References and quotations


def test_an_identifier_the_package_never_supplied_is_refused() -> None:
    proposal = EvidenceValidationProposal.model_validate(
        {"assessments": [a_proposal(subject_id="map-909")]}
    )

    with pytest.raises(ProposalError, match="map-909"):
        proposal.validate_references({"map-001", "evd-001"})


def test_a_supplied_identifier_passes() -> None:
    proposal = EvidenceValidationProposal.model_validate({"assessments": [a_proposal()]})

    proposal.validate_references({"map-001", "evd-001"})


def test_a_contradiction_the_package_never_supplied_is_refused() -> None:
    proposal = EvidenceValidationProposal.model_validate(
        {
            "assessments": [
                a_proposal(
                    validation_status=ValidationStatus.CONTRADICTED,
                    contradictions=["obs-909"],
                )
            ]
        }
    )

    with pytest.raises(ProposalError, match="obs-909"):
        proposal.validate_references({"map-001", "evd-001"})


def test_a_matching_quotation_passes() -> None:
    proposal = EvidenceValidationProposal.model_validate(
        {"assessments": [a_proposal(quoted_text={"evd-001": "identity provider"})]}
    )

    proposal.validate_quotations({"evd-001": "The service uses an identity provider."})


def test_a_rewrapped_quotation_passes() -> None:
    """Re-wrapping changes neither the words nor the meaning (section 14's own wording)."""
    proposal = EvidenceValidationProposal.model_validate(
        {"assessments": [a_proposal(quoted_text={"evd-001": "an\n  identity   provider"})]}
    )

    proposal.validate_quotations({"evd-001": "The service uses an identity provider."})


def test_a_changed_quotation_is_refused() -> None:
    proposal = EvidenceValidationProposal.model_validate(
        {"assessments": [a_proposal(quoted_text={"evd-001": "no identity provider"})]}
    )

    with pytest.raises(ProposalError, match="not in the passage"):
        proposal.validate_quotations({"evd-001": "The service uses an identity provider."})


def test_a_quotation_naming_unknown_evidence_is_refused() -> None:
    proposal = EvidenceValidationProposal.model_validate(
        {"assessments": [a_proposal(quoted_text={"evd-909": "anything"})]}
    )

    with pytest.raises(ProposalError, match="evd-909"):
        proposal.validate_quotations({"evd-001": "The service uses an identity provider."})


def test_an_empty_assessment_set_is_valid() -> None:
    """A package with no conclusion needing a test produces no assessment."""
    proposal = EvidenceValidationProposal.model_validate({})

    assert proposal.assessments == []
