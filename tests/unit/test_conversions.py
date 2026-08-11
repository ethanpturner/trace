"""Conversions across the Finding / DocumentationGap / Question boundary, and what survives them.

`agent-design.md` section 16 gives the reclassification rules and section 4.6 gives the reviewer
the two dispositions. Neither says what a conversion preserves, and
`design-principles.md` section 16 is why it matters: a reviewer has to be able to explain why a
finding changed or disappeared.

Three properties carry the file.

**Nothing is fabricated.** Every field the target needs and the source lacks is a keyword argument
with no default, so omitting one is a `TypeError`, and a blank one is refused by name. The test
that matters is the severity case: a `Finding` *has* a severity and its gap may not use it, because
findings are created `unassigned` (DEC-030) and a gap may never be `unassigned` (DEC-045).

**Converting to a finding is not an escape hatch.** `documentation_gap_to_finding` builds through
`Finding.model_validate`, so DEC-013's outcome table and the minimum criteria both apply. A gap
that became a finding without new evidence would be the DEC-009 collapse arriving through a helper.

**The source is retained.** Section 2.6 separates current state from history, so the source moves
to `superseded` and stays retrievable rather than being deleted.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain.base import now
from trace_ai.domain.conversions import (
    ConversionChainError,
    conversion_chain,
    documentation_gap_to_finding,
    finding_to_documentation_gap,
    finding_to_question,
)
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, Severity, ValidationStatus
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import QuestionPriority, QuestionStatus


def a_finding(**changes: Any) -> Finding:
    stamped = now()
    payload: dict[str, Any] = {
        "id": "fnd-001",
        "assessment_id": "asm-001",
        "title": "Webhook requests may be processed without verified authenticity",
        "summary": "The receiver may accept events without verifying their origin.",
        "description": "The documents describe the validation as structural.",
        "threat_ids": ["thr-001"],
        "requirement_ids": ["req-WEBHOOK-001"],
        "control_mapping_ids": ["map-001"],
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "evidence_ids": ["evd-001", "evd-002"],
        "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
        "severity": Severity.UNASSIGNED,
        "impact": "Unauthorized job execution.",
        "recommendation": "Verify each event with the platform's signature mechanism.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "finding-consolidation-v1",
        "created_at": stamped,
        "updated_at": stamped,
    }
    payload.update(changes)
    return Finding.model_validate(payload)


def a_gap(**changes: Any) -> DocumentationGap:
    payload: dict[str, Any] = {
        "id": "gap-001",
        "assessment_id": "asm-001",
        "title": "Webhook authenticity mechanism is unstated",
        "description": "No supplied document says whether the validation is cryptographic.",
        "importance": "Whether forged events are rejected cannot be determined.",
        "related_object_ids": ["thr-001", "map-001"],
        "severity": Severity.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "mapping-v1",
        "evidence_ids": ["evd-001"],
    }
    payload.update(changes)
    return DocumentationGap.model_validate(payload)


def to_gap(finding: Finding, **changes: Any) -> Any:
    options: dict[str, Any] = {
        "gap_id": "gap-002",
        "importance": "Whether forged events are rejected cannot be determined.",
        "severity": Severity.MEDIUM,
        "generated_by": "reviewer_edit",
        **changes,
    }
    return finding_to_documentation_gap(finding, **options)


def to_question(finding: Finding, **changes: Any) -> Any:
    options: dict[str, Any] = {
        "question_id": "qst-001",
        "question": "Does webhook validation include cryptographic signature verification?",
        "rationale": "The answer decides whether forged events are rejected.",
        "priority": QuestionPriority.HIGH,
        "blocking": False,
        "generated_by": "reviewer_edit",
        **changes,
    }
    return finding_to_question(finding, **options)


def to_finding(gap: DocumentationGap, **changes: Any) -> Any:
    options: dict[str, Any] = {
        "finding_id": "fnd-002",
        "summary": "Signature verification is absent on the webhook receiver.",
        "threat_ids": ["thr-001"],
        "requirement_ids": ["req-WEBHOOK-001"],
        "control_mapping_ids": ["map-001"],
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "evidence_ids": ["evd-003"],
        "validation_status": ValidationStatus.SUPPORTED,
        "impact": "Forged events trigger unauthorized jobs.",
        "recommendation": "Verify the platform signature before queuing.",
        "confidence": ConfidenceLevel.HIGH,
        "generated_by": "reviewer_edit",
        **changes,
    }
    return documentation_gap_to_finding(gap, **options)


# Finding -> DocumentationGap


def test_a_finding_becomes_a_gap_preserving_its_evidence() -> None:
    finding = a_finding()

    gap, superseded = to_gap(finding)

    assert gap.evidence_ids == finding.evidence_ids
    assert gap.converted_from_id == "fnd-001"
    assert superseded.status is ObjectStatus.SUPERSEDED


def test_the_gap_keeps_every_originating_identifier() -> None:
    """Section 32: a gap that dropped them could not be traced to the analysis that raised it."""
    finding = a_finding()

    gap, _ = to_gap(finding)

    for identifier in ("thr-001", "req-WEBHOOK-001", "map-001", "cmp-001", "ast-001"):
        assert identifier in gap.related_object_ids


def test_the_source_finding_is_retained_and_otherwise_unchanged() -> None:
    """Section 2.6: current state and history are separate, so nothing is deleted."""
    finding = a_finding()

    _, superseded = to_gap(finding)

    assert superseded.id == finding.id
    assert superseded.title == finding.title
    assert superseded.evidence_ids == finding.evidence_ids
    assert finding.status is ObjectStatus.CANDIDATE


@pytest.mark.parametrize("value", ["", "   ", "\n"])
def test_a_blank_importance_is_refused(value: str) -> None:
    """The other half of "never invent": passing `""` to satisfy the signature."""
    with pytest.raises(ValueError, match="importance"):
        to_gap(a_finding(), importance=value)


def test_the_gap_severity_is_the_callers_and_not_the_findings() -> None:
    """DEC-030 and DEC-045 together: `unassigned` means nobody decided, and nobody ever will."""
    finding = a_finding(severity=Severity.UNASSIGNED)

    gap, _ = to_gap(finding, severity=Severity.HIGH)

    assert gap.severity is Severity.HIGH


def test_a_gap_cannot_inherit_an_unassigned_severity() -> None:
    with pytest.raises(ValidationError, match="DEC-045"):
        to_gap(a_finding(), severity=Severity.UNASSIGNED)


def test_the_helper_refuses_to_run_without_the_fields_it_cannot_derive() -> None:
    with pytest.raises(TypeError):
        finding_to_documentation_gap(a_finding(), gap_id="gap-002")  # type: ignore[call-arg]


# Finding -> Question


def test_a_finding_becomes_a_question_with_a_caller_supplied_rationale() -> None:
    finding = a_finding()

    asked, superseded = to_question(finding)

    assert asked.rationale == "The answer decides whether forged events are rejected."
    assert asked.converted_from_id == "fnd-001"
    assert asked.status is QuestionStatus.OPEN
    assert superseded.status is ObjectStatus.SUPERSEDED


def test_the_question_points_at_the_threat_the_finding_rested_on() -> None:
    asked, _ = to_question(a_finding())

    assert asked.related_object_id == "thr-001"
    assert asked.related_object_type == "threat"


@pytest.mark.parametrize("field", ["question", "rationale"])
def test_a_blank_required_question_field_is_refused(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        to_question(a_finding(), **{field: "   "})


def test_blocking_has_no_default() -> None:
    """`Question` leaves it undefaulted so an unset field cannot decide whether the run pauses."""
    with pytest.raises(TypeError):
        finding_to_question(  # type: ignore[call-arg]
            a_finding(),
            question_id="qst-001",
            question="Does validation include signature verification?",
            rationale="The answer decides whether forged events are rejected.",
            priority=QuestionPriority.HIGH,
            generated_by="reviewer_edit",
        )


# DocumentationGap -> Finding


def test_a_gap_becomes_a_finding_when_evidence_supports_it() -> None:
    gap = a_gap()

    finding, superseded = to_finding(gap)

    assert finding.converted_from_id == "gap-001"
    assert finding.title == gap.title
    assert superseded.status is ObjectStatus.SUPERSEDED


def test_the_converted_finding_is_created_unassigned() -> None:
    """DEC-030 and DEC-045: a gap's severity rates the gap, not a weakness."""
    gap = a_gap(severity=Severity.HIGH)

    finding, _ = to_finding(gap)

    assert finding.severity is Severity.UNASSIGNED


def test_the_conversion_runs_the_minimum_criteria() -> None:
    with pytest.raises(ValidationError, match="threat_ids"):
        to_finding(a_gap(), threat_ids=[])


def test_the_conversion_runs_the_outcome_table() -> None:
    """A gap converted forward on a status the table reaches no finding from is refused."""
    with pytest.raises(ValidationError, match="DEC-013"):
        to_finding(a_gap(), validation_status=ValidationStatus.UNSUPPORTED)


def test_the_conversion_is_not_an_escape_hatch_around_dec_009() -> None:
    """The whole point of the helper being a thin wrapper over `model_validate`.

    A gap says a control could not be determined. Converting it forward with no new evidence and
    the same unsupported status would be concluding a weakness from the same silence that produced
    the gap.
    """
    with pytest.raises(ValidationError):
        to_finding(a_gap(), evidence_ids=[])

    with pytest.raises(ValidationError, match="DEC-013"):
        to_finding(a_gap(), validation_status=ValidationStatus.REQUIRES_CONFIRMATION)


def test_the_finding_cites_its_own_evidence_rather_than_the_gaps() -> None:
    """A gap's evidence shows ambiguity; a finding's has to support the weakness."""
    gap = a_gap(evidence_ids=["evd-001"])

    finding, _ = to_finding(gap, evidence_ids=["evd-003"])

    assert finding.evidence_ids == ["evd-003"]


@pytest.mark.parametrize("field", ["summary", "impact", "recommendation"])
def test_a_blank_required_finding_field_is_refused(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        to_finding(a_gap(), **{field: " "})


# The chain


def test_a_converted_object_names_its_source() -> None:
    finding = a_finding()
    gap, superseded = to_gap(finding)

    assert conversion_chain(gap, [gap, superseded]) == ["gap-002", "fnd-001"]


def test_a_chain_of_conversions_walks_back_to_the_original() -> None:
    """Finding, converted to a gap, converted forward to a finding again."""
    original = a_finding()
    gap, superseded_finding = to_gap(original)
    revived, superseded_gap = to_finding(gap, finding_id="fnd-002")

    chain = conversion_chain(revived, [revived, superseded_gap, superseded_finding])

    assert chain == ["fnd-002", "gap-002", "fnd-001"]


def test_an_unconverted_object_is_its_own_chain() -> None:
    finding = a_finding()

    assert conversion_chain(finding, [finding]) == ["fnd-001"]


def test_a_chain_whose_source_is_gone_is_refused() -> None:
    """Section 32: an incomplete history presented as a complete one is worse than an error."""
    gap = a_gap(id="gap-002", converted_from_id="fnd-909")

    with pytest.raises(ConversionChainError, match="fnd-909"):
        conversion_chain(gap, [gap])


def test_a_circular_chain_is_refused() -> None:
    first = a_finding(id="fnd-001", converted_from_id="gap-001")
    second = a_gap(id="gap-001", converted_from_id="fnd-001")

    with pytest.raises(ConversionChainError, match="closes on itself"):
        conversion_chain(first, [first, second])


def test_the_chain_crosses_object_types() -> None:
    """`converted_from_id` is a plain identifier because a chain is not one kind of thing."""
    original = a_finding()
    gap, superseded = to_gap(original)
    asked, superseded_gap = finding_to_question(
        a_finding(id="fnd-003", converted_from_id=None),
        question_id="qst-001",
        question="Does validation include signature verification?",
        rationale="The answer decides whether forged events are rejected.",
        priority=QuestionPriority.LOW,
        blocking=False,
        generated_by="reviewer_edit",
    )

    assert conversion_chain(gap, [gap, superseded]) == ["gap-002", "fnd-001"]
    assert conversion_chain(asked, [asked, superseded_gap]) == ["qst-001", "fnd-003"]
