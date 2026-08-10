"""`Threat`, `ThreatProposal`, and the promotion between them.

Three things are worth testing beyond field presence, which
`tests/unit/test_data_model_conformance.py` already covers against the document.

**The proposal cannot carry what the application owns.** Not "is ignored if present" -- fails.
That is the mechanism `agent-design.md` section 22 relies on, and a test that only checks the
happy path would pass against a schema that silently dropped an `id`.

**The non-empty rules come from `agent-design.md` section 10, not from section 16.** The data
model marks `affected_component_ids`, `affected_asset_ids`, and `impact` required and says nothing
about emptiness; section 10 names an empty answer to each as an invalid output. An empty list
satisfies "required" and satisfies nothing else.

**Categories are open and normalized** (DEC-041). The tests assert both halves: an unfamiliar
category is accepted, and three spellings of one category become one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus
from trace_ai.domain.proposals.threat_analysis import (
    THREAT_ANALYSIS_AGENT,
    ThreatProposal,
    promote_threat,
)
from trace_ai.domain.threat import (
    AI_THREAT_CATEGORIES,
    KNOWN_THREAT_CATEGORIES,
    STRIDE_CATEGORIES,
    Threat,
)

# `data-model.md` section 16's worked example, transcribed. The folded scalars are joined and the
# referenced identifiers are the ones the document carries after section 2.1's form was applied to
# its examples; nothing else is changed.
SECTION_16_EXAMPLE: dict[str, Any] = {
    "id": "thr-007",
    "assessment_id": "asm-001",
    "title": "Forged repository webhooks trigger unauthorized analysis jobs",
    "description": (
        "An attacker who can submit unsigned or incorrectly validated webhook requests may "
        "trigger analysis jobs for repositories they do not control."
    ),
    "methodology": "stride-scenario-based",
    "category": ["spoofing", "elevation_of_privilege"],
    "affected_component_ids": ["cmp-004", "cmp-007"],
    "affected_asset_ids": ["ast-002", "ast-005"],
    "preconditions": [
        "webhook endpoint is reachable",
        "signature validation is absent or bypassable",
    ],
    "impact": "Unauthorized jobs, data exposure, and denial of service",
    "confidence": "medium",
    "status": "candidate",
    "generated_by": "threat-analysis-v1",
    "created_at": datetime(2026, 8, 9, tzinfo=UTC),
}


def a_proposal(**changes: Any) -> dict[str, Any]:
    """A valid proposal payload, with `changes` applied."""
    payload: dict[str, Any] = {
        "title": "Forged repository webhooks trigger unauthorized analysis jobs",
        "description": "An attacker submits unsigned webhook requests and triggers jobs.",
        "methodology": "stride-scenario-based",
        "category": ["spoofing"],
        "affected_component_ids": ["cmp-004"],
        "affected_asset_ids": ["ast-002"],
        "impact": "Unauthorized jobs and denial of service",
        "confidence": "medium",
    }
    payload.update(changes)
    return payload


# --------------------------------------------------------------------------------------------
# The worked example
# --------------------------------------------------------------------------------------------


def test_the_section_sixteen_example_validates() -> None:
    threat = Threat.model_validate(SECTION_16_EXAMPLE)

    assert threat.id == "thr-007"
    assert threat.category == ["spoofing", "elevation_of_privilege"]
    assert threat.confidence is ConfidenceLevel.MEDIUM
    assert threat.status is ObjectStatus.CANDIDATE
    assert threat.generated_by == THREAT_ANALYSIS_AGENT


def test_created_at_keeps_its_timezone() -> None:
    threat = Threat.model_validate(SECTION_16_EXAMPLE)

    assert threat.created_at.tzinfo is not None


# --------------------------------------------------------------------------------------------
# Section 10's invalid outputs are refused by the schema
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["affected_component_ids", "affected_asset_ids"])
def test_a_threat_affecting_nothing_is_refused(field: str) -> None:
    """`agent-design.md` section 10: "Threats do not identify affected assets or components"."""
    with pytest.raises(ValidationError, match=field):
        Threat.model_validate({**SECTION_16_EXAMPLE, field: []})

    with pytest.raises(ValidationError, match=field):
        ThreatProposal.model_validate(a_proposal(**{field: []}))


@pytest.mark.parametrize("impact", ["", "   ", "\n\t "])
def test_a_threat_with_no_impact_is_refused(impact: str) -> None:
    """Section 10: "Threats lack plausible security impact".

    Whitespace-only text arrives empty because `DomainModel` sets `str_strip_whitespace`, so the
    `min_length` is what refuses it rather than a separate validator.
    """
    with pytest.raises(ValidationError, match="impact"):
        Threat.model_validate({**SECTION_16_EXAMPLE, "impact": impact})

    with pytest.raises(ValidationError, match="impact"):
        ThreatProposal.model_validate(a_proposal(impact=impact))


def test_a_reference_to_the_wrong_kind_of_object_is_refused() -> None:
    """An asset identifier in the component list is a mistake the annotated types catch."""
    with pytest.raises(ValidationError, match="Component"):
        Threat.model_validate({**SECTION_16_EXAMPLE, "affected_component_ids": ["ast-002"]})


def test_confidence_takes_only_the_three_values() -> None:
    with pytest.raises(ValidationError, match="confidence"):
        Threat.model_validate({**SECTION_16_EXAMPLE, "confidence": "very_high"})


# --------------------------------------------------------------------------------------------
# Categories: open, normalized, optional (DEC-041)
# --------------------------------------------------------------------------------------------


def test_the_known_categories_are_stride_plus_the_ai_set() -> None:
    assert len(STRIDE_CATEGORIES) == 6
    assert "elevation_of_privilege" in STRIDE_CATEGORIES
    assert "prompt_injection" in AI_THREAT_CATEGORIES
    assert KNOWN_THREAT_CATEGORIES == STRIDE_CATEGORIES | AI_THREAT_CATEGORIES


def test_a_category_outside_the_known_set_is_accepted() -> None:
    """DEC-041. STRIDE has no category for ForgeFlow's THR-001, and neither will the next one."""
    threat = Threat.model_validate({**SECTION_16_EXAMPLE, "category": ["supply_chain_compromise"]})

    assert threat.category == ["supply_chain_compromise"]
    assert "supply_chain_compromise" not in KNOWN_THREAT_CATEGORIES


def test_prompt_injection_is_a_category_a_threat_can_carry() -> None:
    """ForgeFlow's first expected threat, and the reason a closed STRIDE enum was rejected."""
    threat = Threat.model_validate({**SECTION_16_EXAMPLE, "category": ["prompt_injection"]})

    assert threat.category == ["prompt_injection"]


@pytest.mark.parametrize(
    "written",
    ["Elevation of Privilege", "elevation-of-privilege", "ELEVATION_OF_PRIVILEGE"],
)
def test_spellings_of_one_category_collapse(written: str) -> None:
    """What DEC-041 refuses is drift, not vocabulary."""
    threat = Threat.model_validate({**SECTION_16_EXAMPLE, "category": [written]})

    assert threat.category == ["elevation_of_privilege"]


def test_a_threat_may_carry_no_category() -> None:
    """An uncategorisable threat is recorded uncategorised, not forced into the nearest bucket."""
    payload = {key: value for key, value in SECTION_16_EXAMPLE.items() if key != "category"}

    assert Threat.model_validate(payload).category == []


def test_a_boolean_category_is_refused() -> None:
    with pytest.raises(ValidationError):
        Threat.model_validate({**SECTION_16_EXAMPLE, "category": [False]})


# --------------------------------------------------------------------------------------------
# The proposal carries nothing the application owns
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "thr-007"),
        ("assessment_id", "asm-001"),
        ("status", "approved"),
        ("generated_by", "threat-analysis-v1"),
        ("created_at", "2026-08-09T00:00:00Z"),
    ],
)
def test_the_proposal_refuses_what_the_application_owns(field: str, value: str) -> None:
    """Refused, not ignored. `extra="forbid"` is what makes the write model structural."""
    with pytest.raises(ValidationError, match=field):
        ThreatProposal.model_validate(a_proposal(**{field: value}))


def test_the_proposal_has_no_severity_field() -> None:
    """DEC-030: severity is the reviewer's at checkpoint 2, and no node proposes one."""
    assert "severity" not in ThreatProposal.model_fields
    assert "severity" not in Threat.model_fields


def test_the_proposal_carries_identifiers_rather_than_local_keys() -> None:
    """Unlike `ContextExtractionProposal`, because the agent selects from a context that exists.

    A local key here would be an invented component. The extractor invents components and cannot
    know their identifiers; the threat agent is handed identifiers in its input package.
    """
    with pytest.raises(ValidationError):
        ThreatProposal.model_validate(a_proposal(affected_component_ids=["webhook-receiver"]))


def test_a_valid_proposal_validates() -> None:
    proposal = ThreatProposal.model_validate(a_proposal())

    assert proposal.title.startswith("Forged repository webhooks")
    assert proposal.confidence is ConfidenceLevel.MEDIUM


# --------------------------------------------------------------------------------------------
# Promotion
# --------------------------------------------------------------------------------------------


def test_promotion_produces_a_candidate() -> None:
    proposal = ThreatProposal.model_validate(a_proposal())

    threat = promote_threat(proposal, threat_id="thr-001", assessment_id="asm-001")

    assert threat.status is ObjectStatus.CANDIDATE
    assert threat.id == "thr-001"
    assert threat.assessment_id == "asm-001"
    assert threat.generated_by == THREAT_ANALYSIS_AGENT
    assert threat.created_at.tzinfo is not None


def test_promotion_cannot_be_asked_for_an_approved_threat() -> None:
    """There is no parameter that would produce one, which is the point (DEC-005)."""
    import inspect

    parameters = inspect.signature(promote_threat).parameters

    assert "status" not in parameters


def test_promotion_carries_every_proposed_field_across() -> None:
    proposal = ThreatProposal.model_validate(
        a_proposal(
            threat_actor_ids=["act-001"],
            related_data_flow_ids=["df-001"],
            preconditions=["webhook endpoint is reachable"],
            attack_path=["forge a request", "submit it"],
            likelihood="medium",
            evidence_ids=["evd-031"],
            assumption_ids=["ctx-002"],
            open_question_ids=["qst-004"],
        )
    )

    threat = promote_threat(proposal, threat_id="thr-001", assessment_id="asm-001")

    for name in ThreatProposal.model_fields:
        assert getattr(threat, name) == getattr(proposal, name), name


def test_promotion_takes_the_identifier_rather_than_minting_one() -> None:
    """DEC-018 allocates at insert from a store-held counter."""
    proposal = ThreatProposal.model_validate(a_proposal())

    assert promote_threat(proposal, threat_id="thr-042", assessment_id="asm-001").id == "thr-042"


def test_promotion_refuses_an_identifier_of_the_wrong_kind() -> None:
    proposal = ThreatProposal.model_validate(a_proposal())

    with pytest.raises(ValidationError, match="Threat"):
        promote_threat(proposal, threat_id="fnd-001", assessment_id="asm-001")


def test_promotion_accepts_a_supplied_timestamp() -> None:
    proposal = ThreatProposal.model_validate(a_proposal())
    stamped = datetime(2026, 8, 9, 12, tzinfo=UTC)

    threat = promote_threat(
        proposal, threat_id="thr-001", assessment_id="asm-001", created_at=stamped
    )

    assert threat.created_at == stamped


def test_a_promoted_threat_is_frozen() -> None:
    threat = promote_threat(
        ThreatProposal.model_validate(a_proposal()), threat_id="thr-001", assessment_id="asm-001"
    )

    with pytest.raises(ValidationError):
        threat.title = "something else"  # type: ignore[misc]
