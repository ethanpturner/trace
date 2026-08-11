"""`Finding`, DEC-013's outcome table, and the invariant that keeps the two sides of DEC-009 apart.

A finding means evidence supports a weakness. A documentation gap means it cannot be determined
whether a control exists. `design-principles.md` section 7 says a rule whose violation makes the
system behave incorrectly does not belong in a prompt, so the separation is a validator and this
file is what holds it.

**The invariant is not enforced twice.** `domain/outcomes.py` holds DEC-013's table and
`FINDING_VALIDATION_STATUSES` is derived from it, so `Finding` has no opinion of its own about
when a finding is reachable. A test asserts the derivation rather than the constant, because a
hardcoded set that happened to agree today is the second opinion the module exists to prevent.

**The table is checked over its whole cross product.** Thirty cells. The property that matters —
no cell produces a finding from silence — is checked over all of them rather than over the rows
somebody remembered, which is the difference between a test of the rule and a test of the example.

The ForgeFlow fixtures at the end are the ones scenario section 22 lists as claims Trace should not
make. Each fails the minimum criteria on the evidence actually available, and the test says which
criterion.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain.base import now
from trace_ai.domain.control_mapping import SatisfactionStatus
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, Severity, ValidationStatus
from trace_ai.domain.finding import DuplicateChainError, Finding, canonical_finding_id
from trace_ai.domain.outcomes import FINDING_VALIDATION_STATUSES, Outcome, outcome_for


def a_finding(**changes: Any) -> dict[str, Any]:
    stamped = now()
    payload: dict[str, Any] = {
        "id": "fnd-001",
        "assessment_id": "asm-001",
        "title": "Webhook requests may be processed without verified authenticity",
        "summary": "The receiver may accept events without verifying their origin.",
        "description": (
            "The documents describe an internet-accessible webhook endpoint and a passage "
            "describes the validation performed as structural rather than cryptographic."
        ),
        "threat_ids": ["thr-001"],
        "requirement_ids": ["req-WEBHOOK-001"],
        "control_mapping_ids": ["map-001"],
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "evidence_ids": ["evd-001"],
        "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
        "severity": Severity.UNASSIGNED,
        "impact": "Unauthorized job execution and resource exhaustion.",
        "recommendation": "Verify each event with the platform's signature mechanism.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "finding-consolidation-v1",
        "created_at": stamped,
        "updated_at": stamped,
    }
    payload.update(changes)
    return payload


# ------------------------------------------------------------------------------------------
# DEC-013's outcome table
# ------------------------------------------------------------------------------------------


ALL_CELLS = list(itertools.product(SatisfactionStatus, ValidationStatus))


def test_the_table_is_total() -> None:
    """Five satisfaction statuses times six validation statuses. A partial table fails open."""
    assert len(ALL_CELLS) == 30

    for satisfaction, validation in ALL_CELLS:
        assert isinstance(outcome_for(satisfaction, validation), Outcome)


def test_no_cell_produces_a_finding_from_silence() -> None:
    """DEC-013's own sentence, checked over the whole table.

    `unverified` is what silence resolves to. If any validation status paired with it reached a
    provisional finding, absence of documentation would be a route to an asserted weakness — the
    exact failure DEC-009 exists to prevent.
    """
    for validation in ValidationStatus:
        assert (
            outcome_for(SatisfactionStatus.UNVERIFIED, validation)
            is not Outcome.PROVISIONAL_FINDING
        )


def test_an_evaluated_unverified_mapping_becomes_a_gap_or_a_question() -> None:
    """The `unverified | any` row, over the statuses that mean something was evaluated."""
    for validation in ValidationStatus:
        if validation is ValidationStatus.NOT_EVALUATED:
            continue
        assert outcome_for(SatisfactionStatus.UNVERIFIED, validation) is Outcome.GAP_OR_QUESTION


def test_not_evaluated_wins_over_the_unverified_row() -> None:
    """Two of DEC-013's rows both match `unverified` + `not_evaluated`, and it does not say which.

    `unverified | any` says documentation gap or question; `any | not_evaluated` says no output.
    The second wins, on the reason the table gives it: the mapping is incomplete, not negative.
    A gap says Trace could not determine whether a control exists, and a mapping nobody evaluated
    has not established that — it has established nothing. Emitting one would turn an unfinished
    run into a reported conclusion. DEC-050 records the precedence.
    """
    assert (
        outcome_for(SatisfactionStatus.UNVERIFIED, ValidationStatus.NOT_EVALUATED)
        is Outcome.NO_OUTPUT
    )


def test_not_evaluated_produces_nothing_whatever_the_satisfaction_status() -> None:
    """ "The mapping is incomplete, not negative." An unfinished run must not read as a clean one."""
    for satisfaction in SatisfactionStatus:
        assert outcome_for(satisfaction, ValidationStatus.NOT_EVALUATED) is Outcome.NO_OUTPUT


def test_a_not_applicable_requirement_produces_nothing() -> None:
    for validation in ValidationStatus:
        assert outcome_for(SatisfactionStatus.NOT_APPLICABLE, validation) is Outcome.NO_OUTPUT


@pytest.mark.parametrize(
    "satisfaction",
    [SatisfactionStatus.PARTIALLY_SATISFIED, SatisfactionStatus.UNMET],
)
@pytest.mark.parametrize(
    "validation",
    [ValidationStatus.SUPPORTED, ValidationStatus.PARTIALLY_SUPPORTED],
)
def test_a_shortfall_the_evidence_carries_is_a_provisional_finding(
    satisfaction: SatisfactionStatus, validation: ValidationStatus
) -> None:
    assert outcome_for(satisfaction, validation) is Outcome.PROVISIONAL_FINDING


def test_exactly_four_cells_reach_a_finding() -> None:
    """Four of thirty. Stated as a number so widening the route is a visible change."""
    reaching = [cell for cell in ALL_CELLS if outcome_for(*cell) is Outcome.PROVISIONAL_FINDING]

    assert len(reaching) == 4


@pytest.mark.parametrize(
    "validation",
    [
        ValidationStatus.UNSUPPORTED,
        ValidationStatus.CONTRADICTED,
        ValidationStatus.REQUIRES_CONFIRMATION,
    ],
)
def test_an_unmet_the_evidence_does_not_carry_is_downgraded(
    validation: ValidationStatus,
) -> None:
    assert outcome_for(SatisfactionStatus.UNMET, validation) is Outcome.DOWNGRADE_ONLY


@pytest.mark.parametrize(
    "validation",
    [
        ValidationStatus.UNSUPPORTED,
        ValidationStatus.CONTRADICTED,
        ValidationStatus.REQUIRES_CONFIRMATION,
    ],
)
def test_a_satisfied_claim_the_evidence_does_not_carry_becomes_a_question(
    validation: ValidationStatus,
) -> None:
    assert outcome_for(SatisfactionStatus.SATISFIED, validation) is Outcome.QUESTION_AFTER_DOWNGRADE


def test_a_satisfied_claim_the_evidence_carries_produces_nothing() -> None:
    for validation in (ValidationStatus.SUPPORTED, ValidationStatus.PARTIALLY_SUPPORTED):
        assert outcome_for(SatisfactionStatus.SATISFIED, validation) is Outcome.NO_OUTPUT


def test_the_permitted_finding_statuses_are_derived_from_the_table() -> None:
    """Not a constant that happens to agree — recomputed here from the table itself."""
    derived = {
        validation
        for satisfaction, validation in ALL_CELLS
        if outcome_for(satisfaction, validation) is Outcome.PROVISIONAL_FINDING
    }

    assert derived == FINDING_VALIDATION_STATUSES
    assert {
        ValidationStatus.SUPPORTED,
        ValidationStatus.PARTIALLY_SUPPORTED,
    } == FINDING_VALIDATION_STATUSES


# ------------------------------------------------------------------------------------------
# The section 21 field set
# ------------------------------------------------------------------------------------------


def test_a_finding_accepts_the_section_21_fields() -> None:
    finding = Finding.model_validate(a_finding())

    assert finding.id == "fnd-001"
    assert finding.severity is Severity.UNASSIGNED


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError, match="importance"):
        Finding.model_validate(a_finding(importance="high"))


@pytest.mark.parametrize(
    "field", ["title", "summary", "description", "impact", "recommendation", "generated_by"]
)
@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_the_required_prose_fields_reject_empty_text(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(a_finding(**{field: value}))


def test_the_optional_fields_are_optional() -> None:
    finding = Finding.model_validate(a_finding())

    assert finding.likelihood is None
    assert finding.acceptance_criteria == []
    assert finding.duplicate_of_id is None
    assert finding.reviewer_notes is None


# ------------------------------------------------------------------------------------------
# Section 21's minimum validation rules, each named
# ------------------------------------------------------------------------------------------


def test_a_finding_needs_a_related_threat() -> None:
    with pytest.raises(ValidationError, match="threat_ids"):
        Finding.model_validate(a_finding(threat_ids=[]))


def test_a_finding_needs_an_applicable_requirement() -> None:
    with pytest.raises(ValidationError, match="requirement_ids"):
        Finding.model_validate(a_finding(requirement_ids=[]))


def test_a_finding_needs_an_affected_component_or_asset() -> None:
    with pytest.raises(ValidationError, match="affected component or asset"):
        Finding.model_validate(a_finding(affected_component_ids=[], affected_asset_ids=[]))


def test_either_an_affected_component_or_an_affected_asset_satisfies_the_rule() -> None:
    """The rule is *or*, so neither list can carry a minimum of its own."""
    Finding.model_validate(a_finding(affected_component_ids=[]))
    Finding.model_validate(a_finding(affected_asset_ids=[]))


def test_a_finding_needs_evidence() -> None:
    with pytest.raises(ValidationError, match="evidence_ids"):
        Finding.model_validate(a_finding(evidence_ids=[]))


def test_a_finding_needs_a_described_impact() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(a_finding(impact="  "))


@pytest.mark.parametrize("field", ["validation_status", "confidence"])
def test_a_finding_needs_a_status_and_a_confidence(field: str) -> None:
    payload = a_finding()
    payload.pop(field)

    with pytest.raises(ValidationError, match=field):
        Finding.model_validate(payload)


# ------------------------------------------------------------------------------------------
# The DEC-009 separation invariant
# ------------------------------------------------------------------------------------------


def test_dec_009_a_candidate_supported_only_by_missing_documentation_cannot_become_a_finding() -> (
    None
):
    """The exact failure case, constructed and refused.

    A mapping resolved `unverified` because no document settles whether the control exists. Under
    DEC-013 that reaches `Outcome.GAP_OR_QUESTION` under every validation status, so the correct
    output is a documentation gap or a question. The `Finding` schema refuses the object at both
    of the two points such a candidate would try to enter through: with no evidence at all, and
    with a validation status the table produces no finding from.
    """
    # It cannot enter with no evidence: silence cannot be quoted.
    with pytest.raises(ValidationError, match="evidence_ids"):
        Finding.model_validate(a_finding(evidence_ids=[]))

    # Nor by citing the passage that says the topic is undocumented, because the assessment over
    # that passage is not one the table reaches a finding from.
    with pytest.raises(ValidationError, match="DEC-013"):
        Finding.model_validate(
            a_finding(validation_status=ValidationStatus.UNSUPPORTED, evidence_ids=["evd-001"])
        )

    # And the outcome table says what the right answer is instead.
    assert (
        outcome_for(SatisfactionStatus.UNVERIFIED, ValidationStatus.UNSUPPORTED)
        is Outcome.GAP_OR_QUESTION
    )


@pytest.mark.parametrize(
    "validation",
    [
        ValidationStatus.UNSUPPORTED,
        ValidationStatus.CONTRADICTED,
        ValidationStatus.REQUIRES_CONFIRMATION,
        ValidationStatus.NOT_EVALUATED,
    ],
)
def test_a_validation_status_the_table_never_reaches_a_finding_from_is_refused(
    validation: ValidationStatus,
) -> None:
    with pytest.raises(ValidationError, match="DEC-013"):
        Finding.model_validate(a_finding(validation_status=validation))


@pytest.mark.parametrize("validation", sorted(FINDING_VALIDATION_STATUSES))
def test_the_two_statuses_the_table_does_reach_a_finding_from_are_accepted(
    validation: ValidationStatus,
) -> None:
    assert Finding.model_validate(a_finding(validation_status=validation))


def test_the_refusal_names_what_is_permitted_instead() -> None:
    """The question after this fires is "then what may it be", so the answer is in the message."""
    with pytest.raises(ValidationError) as raised:
        Finding.model_validate(a_finding(validation_status=ValidationStatus.CONTRADICTED))

    message = str(raised.value)
    assert "partially_supported" in message
    assert "supported" in message
    assert "documentation gap" in message


# ------------------------------------------------------------------------------------------
# Severity (DEC-030) and the low-confidence justification (DEC-013, DEC-050)
# ------------------------------------------------------------------------------------------


def test_a_finding_is_created_unassigned() -> None:
    """DEC-030: the reviewer assigns severity at checkpoint 2, so construction accepts it."""
    finding = Finding.model_validate(a_finding(severity=Severity.UNASSIGNED))

    assert finding.severity is Severity.UNASSIGNED


@pytest.mark.parametrize("severity", list(Severity))
def test_every_severity_is_accepted_at_construction(severity: Severity) -> None:
    """The hard rule is about *approval*, and that belongs to the gate rather than the model."""
    assert Finding.model_validate(a_finding(severity=severity)).severity is severity


def test_low_confidence_requires_a_justification() -> None:
    with pytest.raises(ValidationError, match="DEC-050"):
        Finding.model_validate(a_finding(confidence=ConfidenceLevel.LOW))


def test_low_confidence_with_a_justification_is_accepted() -> None:
    finding = Finding.model_validate(
        a_finding(
            confidence=ConfidenceLevel.LOW,
            low_confidence_justification=(
                "Confirmation that the receiver performs no signature check would raise this. "
                "It is worth surfacing now because the endpoint is internet-accessible."
            ),
        )
    )

    assert finding.low_confidence_justification


def test_the_justification_does_not_substitute_for_evidence() -> None:
    """DEC-013 is explicit that it qualifies rather than substitutes."""
    with pytest.raises(ValidationError, match="evidence_ids"):
        Finding.model_validate(
            a_finding(
                evidence_ids=[],
                confidence=ConfidenceLevel.LOW,
                low_confidence_justification="Worth surfacing before the evidence exists.",
            )
        )


def test_a_justification_on_a_confident_finding_is_refused() -> None:
    """It explains low confidence; elsewhere it explains something that is not the case."""
    with pytest.raises(ValidationError, match="explanation of something that is not the case"):
        Finding.model_validate(
            a_finding(
                confidence=ConfidenceLevel.HIGH,
                low_confidence_justification="Confirmation would raise this.",
            )
        )


# ------------------------------------------------------------------------------------------
# Duplicates
# ------------------------------------------------------------------------------------------


def test_a_finding_cannot_be_a_duplicate_of_itself() -> None:
    with pytest.raises(ValidationError, match="duplicate of itself"):
        Finding.model_validate(a_finding(duplicate_of_id="fnd-001"))


def test_a_duplicate_resolves_to_its_canonical_finding() -> None:
    canonical = Finding.model_validate(a_finding(id="fnd-001"))
    duplicate = Finding.model_validate(a_finding(id="fnd-002", duplicate_of_id="fnd-001"))

    assert canonical_finding_id(duplicate, [canonical, duplicate]) == "fnd-001"


def test_a_chain_of_duplicates_resolves_to_the_end() -> None:
    canonical = Finding.model_validate(a_finding(id="fnd-001"))
    middle = Finding.model_validate(a_finding(id="fnd-002", duplicate_of_id="fnd-001"))
    last = Finding.model_validate(a_finding(id="fnd-003", duplicate_of_id="fnd-002"))

    assert canonical_finding_id(last, [canonical, middle, last]) == "fnd-001"


def test_a_canonical_finding_resolves_to_itself() -> None:
    canonical = Finding.model_validate(a_finding(id="fnd-001"))

    assert canonical_finding_id(canonical, [canonical]) == "fnd-001"


def test_a_duplicate_pointing_at_nothing_is_refused() -> None:
    orphan = Finding.model_validate(a_finding(id="fnd-002", duplicate_of_id="fnd-909"))

    with pytest.raises(DuplicateChainError, match="fnd-909"):
        canonical_finding_id(orphan, [orphan])


def test_a_duplicate_cycle_is_refused() -> None:
    """Section 32: lineage stays traceable, and a cycle has no canonical finding in it."""
    first = Finding.model_validate(a_finding(id="fnd-001", duplicate_of_id="fnd-002"))
    second = Finding.model_validate(a_finding(id="fnd-002", duplicate_of_id="fnd-001"))

    with pytest.raises(DuplicateChainError, match="closes on itself"):
        canonical_finding_id(first, [first, second])


def test_a_longer_cycle_is_refused() -> None:
    first = Finding.model_validate(a_finding(id="fnd-001", duplicate_of_id="fnd-002"))
    second = Finding.model_validate(a_finding(id="fnd-002", duplicate_of_id="fnd-003"))
    third = Finding.model_validate(a_finding(id="fnd-003", duplicate_of_id="fnd-001"))

    with pytest.raises(DuplicateChainError, match="closes on itself"):
        canonical_finding_id(first, [first, second, third])


# ------------------------------------------------------------------------------------------
# ForgeFlow section 22: the claims Trace should not make
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "claim, criterion, changes",
    [
        (
            "ForgeFlow lacks a password-complexity policy.",
            "no applicable requirement — authentication is delegated and no local store exists",
            {"requirement_ids": []},
        ),
        (
            "The managed database is unencrypted.",
            "the passage documents the platform's encryption, so the assessment is not one the "
            "outcome table reaches a finding from",
            {"validation_status": ValidationStatus.CONTRADICTED},
        ),
        (
            "Redis is publicly accessible.",
            "no evidence — nothing places the queue on a public network",
            {"evidence_ids": []},
        ),
        (
            "Multi-factor authentication is completely absent.",
            "the requirement does not apply, so no mapping reaches a finding",
            {"requirement_ids": []},
        ),
        (
            "ForgeFlow lacks webhook replay protection.",
            "the only passage records the topic as undocumented, which is unverified and "
            "resolves to a gap",
            {"validation_status": ValidationStatus.UNSUPPORTED},
        ),
    ],
)
def test_a_scenario_section_22_claim_fails_the_minimum_criteria(
    claim: str, criterion: str, changes: dict[str, Any]
) -> None:
    """Each rejected claim fails on the evidence actually available, and the test says which rule.

    `demo/forgeflow/expected/expected-rejections.yaml` holds all eleven with the catalog entry
    that suppresses each, and `tests/evaluation/test_forgeflow_regressions.py` asserts the
    mechanism. These five are the ones whose refusal is visible at the `Finding` schema itself
    rather than upstream in the mapping.
    """
    with pytest.raises(ValidationError):
        Finding.model_validate(a_finding(title=claim, **changes))


def test_the_replay_claim_is_the_one_a_generic_review_gets_wrong() -> None:
    """Scenario section 22 names it, and DEC-029 resolves it to GAP-004 rather than FND-001."""
    assert (
        outcome_for(SatisfactionStatus.UNVERIFIED, ValidationStatus.UNSUPPORTED)
        is Outcome.GAP_OR_QUESTION
    )

    with pytest.raises(ValidationError, match="DEC-013"):
        Finding.model_validate(
            a_finding(
                title="ForgeFlow lacks webhook replay protection.",
                validation_status=ValidationStatus.UNSUPPORTED,
            )
        )
