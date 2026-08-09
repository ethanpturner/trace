"""Tests for `SourceObservation`, the object that keeps "the documents disagree" out of findings.

The field set is held to `data-model.md` section 10a by the conformance guard. What is asserted here
is section 10a's four validation rules, which are rules about meaning rather than about shape.

Two of them are absences, and absences are what a test has to hold. There is no severity field and
no path to a `Finding`; and there is no reverse link from `ContextClaim`, so a claim and the
observation that contradicts it cannot disagree about whether they disagree.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, SourceOrigin
from trace_ai.domain.source_observation import (
    ObservationKind,
    SourceObservation,
    unsupported_contradictions,
)

INJECTION_FIXTURE = PROJECT_ROOT / "demo" / "forgeflow" / "input" / "sample-repository-notes.md"

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def observation(**changes: Any) -> SourceObservation:
    return SourceObservation.model_validate(
        {
            "id": "obs-001",
            "assessment_id": "asm-001",
            "kind": ObservationKind.CONTRADICTION,
            "summary": "The product overview and the operations guide disagree about retention.",
            "evidence_ids": ["evd-011", "evd-042"],
            "status": ObjectStatus.CANDIDATE,
            "created_at": NOW,
            **changes,
        }
    )


def claim(**changes: Any) -> ContextClaim:
    return ContextClaim.model_validate(
        {
            "id": "ctx-001",
            "assessment_id": "asm-001",
            "subject_type": "system",
            "predicate": "source_retention",
            "value": "deleted immediately after analysis",
            "status": ClaimStatus.DOCUMENTED,
            "confidence": ConfidenceLevel.MEDIUM,
            "evidence_ids": ["evd-011"],
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "created_at": NOW,
            "updated_at": NOW,
            **changes,
        }
    )


# --------------------------------------------------------------------------------------------
# The evidence counts, and why they differ
# --------------------------------------------------------------------------------------------


def test_a_contradiction_needs_two_passages() -> None:
    """One reference cannot establish that two documents disagree — it is an assertion about a
    relationship, and a relationship needs both sides."""
    with pytest.raises(ValidationError, match="at least 2 evidence references"):
        observation(evidence_ids=["evd-011"])


def test_a_contradiction_with_two_passages_is_valid() -> None:
    assert len(observation().evidence_ids) == 2


def test_an_injection_attempt_needs_one_passage() -> None:
    """It is an assertion about one passage, so one is the minimum and one is enough."""
    built = observation(kind=ObservationKind.INJECTION_ATTEMPT, evidence_ids=["evd-099"])
    assert built.evidence_ids == ["evd-099"]


@pytest.mark.parametrize("kind", list(ObservationKind))
def test_no_observation_may_cite_nothing(kind: ObservationKind) -> None:
    """`evidence_ids` is required in section 10a, unlike on most objects that carry it."""
    with pytest.raises(ValidationError):
        observation(kind=kind, evidence_ids=[])


def test_the_kind_vocabulary_is_the_documented_one() -> None:
    """Two values, and DEC-021 is the decision that they belong to one object."""
    assert [kind.value for kind in ObservationKind] == ["contradiction", "injection_attempt"]


# --------------------------------------------------------------------------------------------
# The two absences
# --------------------------------------------------------------------------------------------


def test_an_observation_carries_no_severity() -> None:
    """A rule, not an omission (section 10a). Severity would be the first step of a path from
    "these two paragraphs disagree" to "a vulnerability exists", and the object exists precisely so
    that no such path is available."""
    assert "severity" not in SourceObservation.model_fields
    with pytest.raises(ValidationError):
        observation(severity="high")


def test_the_link_to_a_claim_runs_one_way() -> None:
    """An observation names claims; a claim names nothing. That is what stops the two disagreeing
    about whether they disagree (DEC-021)."""
    assert "subject_claim_ids" in SourceObservation.model_fields
    assert not [name for name in ContextClaim.model_fields if "contradict" in name]
    assert not [name for name in ContextClaim.model_fields if "observation" in name]


def test_an_observation_references_claims_by_identifier() -> None:
    assert observation(subject_claim_ids=["ctx-001", "ctx-002"]).subject_claim_ids == [
        "ctx-001",
        "ctx-002",
    ]


def test_an_observation_rejects_a_claim_reference_of_the_wrong_type() -> None:
    with pytest.raises(ValidationError):
        observation(subject_claim_ids=["cmp-001"])


# --------------------------------------------------------------------------------------------
# Detecting a contradicted claim nothing contradicts
# --------------------------------------------------------------------------------------------


def test_a_contradicted_claim_with_no_observation_is_detected() -> None:
    """The claim cannot enforce its own status: nothing on it can see the observations. So the
    inconsistency is detected rather than made impossible, and the Context Validation node is where
    the check runs."""
    orphan = claim(id="ctx-007", status=ClaimStatus.CONTRADICTED)
    assert unsupported_contradictions([orphan], []) == ["ctx-007"]


def test_a_contradicted_claim_an_observation_names_is_supported() -> None:
    supported = claim(id="ctx-007", status=ClaimStatus.CONTRADICTED)
    naming = observation(subject_claim_ids=["ctx-007"])
    assert unsupported_contradictions([supported], [naming]) == []


def test_an_injection_observation_does_not_support_a_contradicted_status() -> None:
    """Section 10a ties the status to a `contradiction`. An injection attempt bearing on the same
    claim says something else entirely about it."""
    marked = claim(id="ctx-007", status=ClaimStatus.CONTRADICTED)
    injection = observation(
        kind=ObservationKind.INJECTION_ATTEMPT,
        evidence_ids=["evd-099"],
        subject_claim_ids=["ctx-007"],
    )
    assert unsupported_contradictions([marked], [injection]) == ["ctx-007"]


def test_claims_with_other_statuses_are_not_reported() -> None:
    assert unsupported_contradictions([claim()], []) == []


# --------------------------------------------------------------------------------------------
# The ForgeFlow fixtures
# --------------------------------------------------------------------------------------------


def test_the_injection_fixture_is_representable_as_an_observation() -> None:
    """`demo/forgeflow/input/sample-repository-notes.md` carries a deliberate injection block. It is
    test data rather than a live payload, and what the pipeline is designed to do with it is record
    an observation about the document — not obey it, and not report it as a system weakness."""
    text = INJECTION_FIXTURE.read_text(encoding="utf-8")
    assert "AI ANALYSIS OVERRIDE" in text, "the injection fixture moved or was removed"

    recorded = observation(
        id="obs-002",
        kind=ObservationKind.INJECTION_ATTEMPT,
        summary=(
            "A block in the repository notes instructs its reader to ignore prior instructions, "
            "suppress findings, and disclose a private key."
        ),
        evidence_ids=["evd-099"],
    )
    assert recorded.kind is ObservationKind.INJECTION_ATTEMPT
    assert "severity" not in recorded.model_dump()


def test_the_retention_contradiction_is_representable() -> None:
    """Scenario section 16.1: the product overview says source files are deleted immediately and
    the operations guide says artifacts are retained for 30 days. Trace records both passages and
    resolves nothing — section 10a forbids silently choosing the safer statement."""
    recorded = observation(subject_claim_ids=["ctx-001", "ctx-002"])
    assert len(recorded.evidence_ids) == 2
    assert recorded.kind is ObservationKind.CONTRADICTION
