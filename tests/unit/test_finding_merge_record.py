"""`FindingMergeRecord`: the object that keeps a merge traceable after the run that decided it.

`data-model.md` section 21a is authoritative for the fields and DEC-052 for the shape. The tests
that matter most here are the refusals: a record naming a documentation gap, a record whose
survivor is also merged, and a feature naming a comparison no code performs are all states a
reader could not resolve, and each is refused with the reason.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain.base import now
from trace_ai.domain.finding_merge_record import (
    MERGE_FEATURES,
    FindingMergeRecord,
    MergeDecision,
)


def a_record(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "mrg-001",
        "assessment_id": "asm-001",
        "surviving_finding_id": "fnd-001",
        "merged_finding_ids": ["fnd-002"],
        "matched_features": ["threats", "requirements"],
        "decision": MergeDecision.STRUCTURAL,
        "detail": "fnd-002 merged into fnd-001: shared threats thr-001; shared requirements "
        "req-WEBHOOK-001.",
        "generated_by": "finding-dedup-v1",
        "created_at": now(),
    }
    payload.update(changes)
    return payload


def test_a_record_accepts_the_section_21a_fields() -> None:
    record = FindingMergeRecord.model_validate(a_record())
    assert record.surviving_finding_id == "fnd-001"
    assert record.merged_finding_ids == ["fnd-002"]
    assert record.decision is MergeDecision.STRUCTURAL


def test_the_decision_vocabulary_is_structural_and_model_assisted() -> None:
    """Section 21a names exactly two values, and the node only ever writes the first."""
    assert {decision.value for decision in MergeDecision} == {"structural", "model_assisted"}


def test_a_survivor_cannot_also_be_merged() -> None:
    with pytest.raises(ValidationError, match="duplicate of itself"):
        FindingMergeRecord.model_validate(a_record(merged_finding_ids=["fnd-001"]))


def test_a_merged_finding_is_listed_once() -> None:
    with pytest.raises(ValidationError, match="twice"):
        FindingMergeRecord.model_validate(a_record(merged_finding_ids=["fnd-002", "fnd-002"]))


def test_a_merge_that_merged_nothing_is_refused() -> None:
    with pytest.raises(ValidationError):
        FindingMergeRecord.model_validate(a_record(merged_finding_ids=[]))


def test_a_documentation_gap_identifier_is_refused_on_both_sides() -> None:
    """Half of the DEC-009 boundary: a merge across the finding/gap line is unrepresentable.

    The fields are `FindingId`-typed, so a `gap-` identifier fails schema validation rather than
    being stored and discovered later. The other half is `dedupe_findings` refusing non-`Finding`
    input by type, tested with the operation.
    """
    with pytest.raises(ValidationError, match="DocumentationGap"):
        FindingMergeRecord.model_validate(a_record(surviving_finding_id="gap-001"))
    with pytest.raises(ValidationError, match="DocumentationGap"):
        FindingMergeRecord.model_validate(a_record(merged_finding_ids=["gap-001"]))


def test_a_feature_outside_the_vocabulary_is_refused() -> None:
    """A matched feature names a comparison the dedup rule ran; `severity` names none."""
    with pytest.raises(ValidationError, match="severity"):
        FindingMergeRecord.model_validate(a_record(matched_features=["severity"]))


def test_a_feature_listed_twice_is_refused() -> None:
    with pytest.raises(ValidationError, match="twice"):
        FindingMergeRecord.model_validate(a_record(matched_features=["threats", "threats"]))


def test_the_vocabulary_is_the_one_section_21a_names() -> None:
    assert MERGE_FEATURES == ("threats", "requirements", "control_mappings", "components", "assets")


def test_an_invented_field_is_refused() -> None:
    """`extra="forbid"` inherited from `DomainModel`, asserted where it protects this object."""
    with pytest.raises(ValidationError):
        FindingMergeRecord.model_validate(a_record(approved=True))
