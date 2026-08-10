"""`DocumentationGap`, its proposal, and the promotion between them.

The object exists to hold one line: `data-model.md` section 23's *Important distinction*. A gap
means Trace could not determine whether a control exists; a finding means evidence supports the
conclusion that a weakness exists. DEC-009 says the same thing from the decision side. Most of this
file is therefore about what the schema **cannot** express, because that is the enforcement — a
shape with no recommendation, no impact, and no way to say a control is absent cannot be read as an
asserted weakness however the prose around it is worded.

The rest is DEC-045: `severity` here rates the gap rather than a weakness, the mapping step
proposes it, and `unassigned` is refused. That last rule is the one that will look wrong to anyone
arriving from DEC-030, and the reason it is not is that checkpoint 2 reviews findings —
`current-architecture.md` section 5.12 gives the reviewer no action on a gap, so a gap created
`unassigned` would be rendered `unassigned`.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain import documentation_gap
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.documentation_gap import DocumentationGap, warrants_documentation_gap
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, Severity
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.proposals.mapping import (
    MAPPING_AGENT,
    DocumentationGapProposal,
    MappingProposal,
    RequirementMappingProposal,
    promote_documentation_gap,
)


def a_gap(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "gap-001",
        "assessment_id": "asm-001",
        "title": "Webhook replay handling is undocumented",
        "description": (
            "No supplied document states whether delivery identifiers are recorded and rejected "
            "on repeat."
        ),
        "importance": (
            "A replayed delivery would re-run a build, and the assessment cannot say whether that "
            "is possible."
        ),
        "related_object_ids": ["thr-001", "cmp-002"],
        "requested_evidence": ["The webhook receiver's deduplication behaviour, if any."],
        "severity": Severity.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": MAPPING_AGENT,
        "evidence_ids": ["evd-001"],
    }
    payload.update(changes)
    return payload


def a_gap_proposal(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Webhook replay handling is undocumented",
        "description": "No supplied document states whether delivery identifiers are recorded.",
        "importance": "A replayed delivery would re-run a build.",
        "related_object_ids": ["thr-001"],
        "requested_evidence": ["The receiver's deduplication behaviour, if any."],
        "evidence_ids": ["evd-001"],
        "severity": Severity.MEDIUM,
    }
    payload.update(changes)
    return payload


def a_mapping(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "map-001",
        "assessment_id": "asm-001",
        "threat_id": "thr-001",
        "requirement_id": "req-WEBHOOK-001",
        "applicability_status": ApplicabilityStatus.APPLICABLE,
        "applicability_reason": "The system receives webhooks from an external forge.",
        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
        "confidence": ConfidenceLevel.MEDIUM,
        "generated_by": MAPPING_AGENT,
        "reviewer_status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return payload


# The section 23 field set


def test_a_gap_accepts_the_section_23_fields() -> None:
    gap = DocumentationGap.model_validate(a_gap())

    assert gap.id == "gap-001"
    assert gap.severity is Severity.MEDIUM
    assert gap.related_object_ids == ["thr-001", "cmp-002"]


def test_the_optional_fields_are_optional() -> None:
    """The ordinary gap is documentation that says nothing, and silence cannot be quoted."""
    payload = a_gap()
    for field in ("related_object_ids", "requested_evidence", "evidence_ids"):
        payload.pop(field)

    gap = DocumentationGap.model_validate(payload)

    assert gap.evidence_ids == []


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError, match="recommendation"):
        DocumentationGap.model_validate(a_gap(recommendation="Add signature verification."))


@pytest.mark.parametrize("field", ["title", "description", "importance", "generated_by"])
@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_the_required_prose_fields_reject_empty_text(field: str, value: str) -> None:
    """A gap with no stated reason it matters is indistinguishable from noise."""
    with pytest.raises(ValidationError):
        DocumentationGap.model_validate(a_gap(**{field: value}))


def test_a_related_object_id_that_is_not_an_identifier_is_refused() -> None:
    """A descriptive slug is what DEC-018 exists to stop, and it is caught here by name."""
    with pytest.raises(ValidationError, match="cmp-webhook-receiver"):
        DocumentationGap.model_validate(a_gap(related_object_ids=["cmp-webhook-receiver"]))


# The distinction from a finding


def test_a_gap_carries_no_field_that_asserts_a_weakness() -> None:
    """Section 23's distinction, enforced as a shape rather than as an instruction.

    Each name below is a field `Finding` (section 21) carries or that would let a gap claim
    something about the implementation. `extra="forbid"` means adding one is a validation error,
    but a field deliberately added to the model later would pass that and fail here.
    """
    forbidden = {
        "recommendation",
        "impact",
        "likelihood",
        "validation_status",
        "satisfaction_status",
        "affected_component_ids",
        "threat_ids",
        "requirement_ids",
    }

    assert not forbidden & set(DocumentationGap.model_fields)


def test_a_gap_is_not_a_question() -> None:
    """Section 22 asks a person for an answer; section 23 records that the material is thin."""
    assert "question" not in DocumentationGap.model_fields
    assert "blocking" not in DocumentationGap.model_fields


# DEC-045: severity


def test_unassigned_severity_is_refused() -> None:
    """Nothing downstream assigns a gap's severity, so an unassigned one ships unassigned."""
    with pytest.raises(ValidationError, match="DEC-045"):
        DocumentationGap.model_validate(a_gap(severity=Severity.UNASSIGNED))


@pytest.mark.parametrize(
    "severity",
    [s for s in Severity if s is not Severity.UNASSIGNED],
)
def test_every_other_severity_is_accepted(severity: Severity) -> None:
    assert DocumentationGap.model_validate(a_gap(severity=severity)).severity is severity


def test_the_docstring_states_what_severity_means_here() -> None:
    """The field reuses one vocabulary for two quantities; the docstring is the only cue."""
    combined = (documentation_gap.__doc__ or "") + (DocumentationGap.__doc__ or "")

    assert "section 23" in combined
    assert "not a weakness" in combined or "not a security weakness" in combined


# The proposal boundary


def test_the_proposal_omits_the_application_owned_fields() -> None:
    for field in ("id", "assessment_id", "generated_by", "status"):
        assert field not in DocumentationGapProposal.model_fields


@pytest.mark.parametrize(
    "field, value",
    [
        ("id", "gap-001"),
        ("assessment_id", "asm-001"),
        ("generated_by", "mapping-v1"),
        ("status", ObjectStatus.APPROVED),
    ],
)
def test_a_proposal_carrying_an_application_owned_field_is_refused(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError, match=field):
        DocumentationGapProposal.model_validate(a_gap_proposal(**{field: value}))


def test_the_proposal_carries_severity() -> None:
    """DEC-045: unlike a finding's, a gap's severity is the mapping step's to propose."""
    assert "severity" in DocumentationGapProposal.model_fields

    proposal = DocumentationGapProposal.model_validate(a_gap_proposal(severity=Severity.LOW))

    assert proposal.severity is Severity.LOW


def test_a_proposal_may_not_propose_unassigned_at_promotion() -> None:
    proposal = DocumentationGapProposal.model_validate(a_gap_proposal(severity=Severity.UNASSIGNED))

    with pytest.raises(ValidationError, match="DEC-045"):
        promote_documentation_gap(proposal, gap_id="gap-001", assessment_id="asm-001")


def test_promotion_sets_candidate_and_the_application_owned_fields() -> None:
    proposal = DocumentationGapProposal.model_validate(a_gap_proposal())

    gap = promote_documentation_gap(proposal, gap_id="gap-002", assessment_id="asm-001")

    assert gap.id == "gap-002"
    assert gap.assessment_id == "asm-001"
    assert gap.status is ObjectStatus.CANDIDATE
    assert gap.generated_by == MAPPING_AGENT
    assert gap.title == proposal.title


def test_a_gap_referencing_something_the_package_never_supplied_is_refused() -> None:
    """Resolution needs the assessment's contents, so it happens where they are known."""
    proposal = MappingProposal.model_validate(
        {
            "documentation_gaps": [a_gap_proposal(related_object_ids=["thr-404"])],
        }
    )

    with pytest.raises(ProposalError, match="thr-404"):
        proposal.validate_references({"thr-001", "evd-001"})


def test_a_gap_referencing_supplied_objects_passes() -> None:
    proposal = MappingProposal.model_validate({"documentation_gaps": [a_gap_proposal()]})

    proposal.validate_references({"thr-001", "evd-001"})


def test_a_gaps_missing_reference_does_not_mask_a_mappings() -> None:
    """Both collections are checked, and the error names identifiers from each."""
    proposal = MappingProposal.model_validate(
        {
            "mappings": [
                RequirementMappingProposal.model_validate(
                    {
                        "threat_id": "thr-404",
                        "requirement_id": "req-WEBHOOK-001",
                        "applicability_status": ApplicabilityStatus.APPLICABLE,
                        "applicability_reason": "The system receives webhooks.",
                        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
                        "confidence": ConfidenceLevel.LOW,
                    }
                ).model_dump()
            ],
            "documentation_gaps": [a_gap_proposal(related_object_ids=["cmp-909"])],
        }
    )

    with pytest.raises(ProposalError) as raised:
        proposal.validate_references({"req-WEBHOOK-001", "thr-001", "evd-001"})

    assert "thr-404" in str(raised.value)
    assert "cmp-909" in str(raised.value)


# Section 16: gap candidate or nothing


def test_an_unverified_mapping_is_a_gap_candidate() -> None:
    mapping = ControlMapping.model_validate(a_mapping())

    assert warrants_documentation_gap(mapping) is True


def test_a_not_applicable_requirement_produces_nothing() -> None:
    """ForgeFlow's absent local password policy: not documentation missing, just not applicable."""
    mapping = ControlMapping.model_validate(
        a_mapping(
            applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
            applicability_reason="The system delegates authentication and stores no passwords.",
            satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
        )
    )

    assert warrants_documentation_gap(mapping) is False


def test_a_not_applicable_requirement_produces_nothing_even_when_unverified() -> None:
    """Applicability decides first. A requirement that does not apply cannot be unverifiable."""
    mapping = ControlMapping.model_validate(
        a_mapping(
            applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
            applicability_reason="The system delegates authentication.",
            satisfaction_status=SatisfactionStatus.UNVERIFIED,
        )
    )

    assert warrants_documentation_gap(mapping) is False


@pytest.mark.parametrize(
    "satisfaction",
    [
        SatisfactionStatus.SATISFIED,
        SatisfactionStatus.PARTIALLY_SATISFIED,
        SatisfactionStatus.UNMET,
    ],
)
def test_an_evidenced_conclusion_is_not_a_gap(satisfaction: SatisfactionStatus) -> None:
    """These cite a passage by schema, so inability to verify is not the primary issue."""
    mapping = ControlMapping.model_validate(
        a_mapping(satisfaction_status=satisfaction, evidence_ids=["evd-001"])
    )

    assert warrants_documentation_gap(mapping) is False


@pytest.mark.parametrize(
    "applicability",
    [
        ApplicabilityStatus.APPLICABLE,
        ApplicabilityStatus.CONDITIONALLY_APPLICABLE,
        ApplicabilityStatus.UNKNOWN,
    ],
)
def test_every_applicability_short_of_not_applicable_admits_a_gap(
    applicability: ApplicabilityStatus,
) -> None:
    mapping = ControlMapping.model_validate(a_mapping(applicability_status=applicability))

    assert warrants_documentation_gap(mapping) is True
