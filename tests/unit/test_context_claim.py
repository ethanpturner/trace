"""Tests for `ContextClaim` and the epistemic status it exists to carry.

The field set is held to `data-model.md` section 10 by the conformance guard. What is asserted here
is the behaviour that makes the status honest, because a claim whose status can be set to anything
is a claim that says nothing.

The asymmetry is the point. `documented` and `inferred` must cite evidence; `assumed` and `unknown`
must **not** be required to. A schema that demanded evidence everywhere would leave an extractor
choosing between dropping a claim and mislabelling it, and mislabelling is how missing documentation
becomes an asserted weakness — the failure DEC-009 exists to prevent and the one this project was
built around.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.enums import ConfidenceLevel, SourceOrigin

DATA_MODEL = PROJECT_ROOT / "docs" / "architecture" / "data-model.md"

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def claim(**changes: Any) -> ContextClaim:
    return ContextClaim.model_validate(
        {
            "id": "ctx-001",
            "assessment_id": "asm-001",
            "subject_type": "component",
            "subject_id": "cmp-001",
            "predicate": "authentication_provider",
            "value": "GitHub OAuth",
            "status": ClaimStatus.DOCUMENTED,
            "confidence": ConfidenceLevel.HIGH,
            "evidence_ids": ["evd-001"],
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "created_at": NOW,
            "updated_at": NOW,
            **changes,
        }
    )


def documented_claim_statuses() -> list[str]:
    """Section 10's `## Status values` list, parsed rather than retyped."""
    text = DATA_MODEL.read_text(encoding="utf-8")
    body = text.split("# 10. ContextClaim", 1)[1].split("## Status values", 1)[1]
    body = body.split("## ", 1)[0]
    return [
        line.strip() for line in body.splitlines() if re.fullmatch(r"[a-z][a-z_]*", line.strip())
    ]


# --------------------------------------------------------------------------------------------
# The vocabulary
# --------------------------------------------------------------------------------------------


def test_the_status_vocabulary_matches_the_document() -> None:
    """Seven values, from section 10 rather than section 4: this vocabulary belongs to the object."""
    documented = documented_claim_statuses()
    assert len(documented) == 7, documented
    assert [status.value for status in ClaimStatus] == documented


def test_there_is_no_confidence_score() -> None:
    """DEC-022 removed it. A decimal beside a three-value enum invites reading confidence as
    probability and conflates model confidence with evidence strength."""
    assert "confidence_score" not in ContextClaim.model_fields
    with pytest.raises(ValidationError):
        claim(confidence_score=0.87)


# --------------------------------------------------------------------------------------------
# Evidence follows status
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [ClaimStatus.DOCUMENTED, ClaimStatus.INFERRED])
def test_a_claim_about_a_document_must_cite_it(status: ClaimStatus) -> None:
    """`agent-design.md` section 7 lists "documented claims lack evidence" as a failure condition.
    An uncited `documented` claim is an assertion wearing a fact's label."""
    with pytest.raises(ValidationError, match="evidence_ids"):
        claim(status=status, evidence_ids=[], rationale="reasoned from the deployment diagram")


@pytest.mark.parametrize("status", [ClaimStatus.ASSUMED, ClaimStatus.UNKNOWN])
def test_a_claim_about_a_silence_cites_nothing_and_is_still_valid(status: ClaimStatus) -> None:
    """The DEC-009 path, and the assertion this whole file exists for.

    Where the documentation does not support a claim, the honest outcome is `assumed` or `unknown`.
    Requiring evidence there would make the honest label the expensive one, and an extractor under
    that pressure mislabels rather than drops — which is precisely how missing documentation turns
    into a reported vulnerability.
    """
    built = claim(
        status=status,
        evidence_ids=[],
        rationale="the documentation does not state how the cache is authenticated",
    )
    assert built.evidence_ids == []
    assert built.status is status


def test_an_unknown_claim_needs_no_rationale_either() -> None:
    """`unknown` is a statement that nothing is known, which needs no reasoning to justify."""
    assert claim(status=ClaimStatus.UNKNOWN, evidence_ids=[], rationale=None).rationale is None


@pytest.mark.parametrize("status", [ClaimStatus.INFERRED, ClaimStatus.ASSUMED])
def test_a_reasoned_claim_must_say_why(status: ClaimStatus) -> None:
    """DEC-022 added `rationale` because section 7 required one and the object had nowhere to put
    it. `reviewer_notes` is the reviewer's field."""
    with pytest.raises(ValidationError, match="rationale"):
        claim(status=status, rationale=None)


@pytest.mark.parametrize("status", [ClaimStatus.INFERRED, ClaimStatus.ASSUMED])
def test_reviewer_notes_do_not_satisfy_the_rationale_requirement(status: ClaimStatus) -> None:
    with pytest.raises(ValidationError, match="rationale"):
        claim(status=status, rationale=None, reviewer_notes="looks reasonable to me")


def test_a_whitespace_rationale_is_not_a_rationale() -> None:
    with pytest.raises(ValidationError, match="rationale"):
        claim(status=ClaimStatus.ASSUMED, evidence_ids=[], rationale="   ")


def test_a_user_confirmed_claim_needs_no_evidence() -> None:
    """The reviewer is the evidence, and `source_origin` records that."""
    built = claim(
        status=ClaimStatus.USER_CONFIRMED,
        evidence_ids=[],
        source_origin=SourceOrigin.USER_RESPONSE,
    )
    assert built.evidence_ids == []


def test_a_claim_carries_no_field_naming_what_contradicts_it() -> None:
    """DEC-021 makes the reference one-directional: a `SourceObservation` names the claim, not the
    other way round, so the two cannot disagree about whether they disagree."""
    assert ClaimStatus.CONTRADICTED in set(ClaimStatus)
    assert not [name for name in ContextClaim.model_fields if "contradict" in name]


# --------------------------------------------------------------------------------------------
# Subject coherence
# --------------------------------------------------------------------------------------------


def test_a_subject_type_and_subject_id_must_name_the_same_kind_of_object() -> None:
    """Field by field this validates; as a whole it describes the wrong object, and nothing
    downstream would notice."""
    with pytest.raises(ValidationError, match="Asset"):
        claim(subject_type="component", subject_id="ast-004")


def test_a_subject_type_outside_the_registry_is_left_alone() -> None:
    """`system` names no object with a prefix, and a claim about the system as a whole is normal."""
    assert claim(subject_type="system", subject_id=None).subject_type == "system"


def test_a_subject_id_that_is_not_an_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError):
        claim(subject_id="the frontend")


def test_a_subject_type_is_normalized() -> None:
    """DEC-036: a claim about a `Component` and one about a `component` are the same kind."""
    assert claim(subject_type="Component").subject_type == "component"


# --------------------------------------------------------------------------------------------
# `value` carries what a document actually says
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "GitHub OAuth",
        True,
        3,
        4.5,
        None,
        ["us-east-1", "us-west-2"],
        {"provider": "GitHub", "mfa": {"required": True, "methods": ["totp"]}},
        [{"name": "postgres", "encrypted": None}],
    ],
)
def test_a_value_round_trips_through_json(value: object) -> None:
    """DEC-020 persists these objects as JSON payloads, so a value that will not serialize is a
    value that cannot be stored. Section 10 types the field `any`; `JsonValue` is what strict
    typing can express and what persistence actually requires."""
    restored = ContextClaim.model_validate_json(claim(value=value).model_dump_json())
    assert restored.value == value


def test_a_value_that_is_not_json_compatible_is_rejected() -> None:
    with pytest.raises(ValidationError):
        claim(value={datetime: "not a string key"})
