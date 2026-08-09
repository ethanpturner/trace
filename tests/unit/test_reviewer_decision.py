"""Tests for `ReviewerDecision`: the record that makes a reviewer's overwrite non-silent.

The field set is held to `data-model.md` section 25 by the conformance guard. What is asserted here
is that the record cannot be empty of the thing it exists to hold.

`data-model.md` section 2.5 forbids overwriting generated content *silently*, and DEC-023 makes
recording the delta what turns an overwrite into a record. So an `edit` that cannot say what changed
is the failure this object exists to prevent, and `capture_edit` exists because the natural way to
get it wrong — assembling `prior_value` after the edit has been applied — produces a record that
looks complete and says nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain.component import Component
from trace_ai.domain.enums import ObjectStatus, ReviewDisposition
from trace_ai.domain.reviewer_decision import ReviewerDecision, changed_fields
from trace_ai.domain.system_context import FIRST_VERSION, SystemContext

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
ASSESSMENT = "asm-001"


def decision(**changes: Any) -> ReviewerDecision:
    return ReviewerDecision.model_validate(
        {
            "id": "dec-001",
            "assessment_id": ASSESSMENT,
            "subject_type": "component",
            "subject_id": "cmp-001",
            "disposition": ReviewDisposition.APPROVE,
            "created_at": NOW,
            **changes,
        }
    )


def component(**changes: Any) -> Component:
    return Component.model_validate(
        {
            "id": "cmp-001",
            "assessment_id": ASSESSMENT,
            "name": "Webhook Receiver",
            "component_type": "service",
            "internet_accessible": None,
            "status": ObjectStatus.CANDIDATE,
            **changes,
        }
    )


def system_context(**changes: Any) -> SystemContext:
    return SystemContext.model_validate(
        {
            "assessment_id": ASSESSMENT,
            "system_name": "ForgeFlow",
            "context_claim_ids": [],
            "component_ids": [],
            "asset_ids": [],
            "actor_ids": [],
            "data_flow_ids": [],
            "trust_boundary_ids": [],
            "version": FIRST_VERSION,
            **changes,
        }
    )


# --------------------------------------------------------------------------------------------
# The vocabulary
# --------------------------------------------------------------------------------------------


def test_the_disposition_vocabulary_is_section_four_point_six() -> None:
    """Seven values. `test_data_model_conformance.py` holds them to the document; this asserts the
    model uses that enum rather than a private one."""
    assert ReviewerDecision.model_fields["disposition"].annotation is ReviewDisposition
    assert len(list(ReviewDisposition)) == 7


def test_re_extraction_is_recorded_as_request_more_analysis() -> None:
    """`agent-design.md` section 9 lists "request re-extraction" and section 4.6 has no member for
    it. The mapping is documented rather than added, for the reason DEC-030 gives about severity:
    section 4.6 names dispositions the system records, section 9 names actions a reviewer takes, and
    the two do not correspond one to one."""
    recorded = decision(
        disposition=ReviewDisposition.REQUEST_MORE_ANALYSIS,
        rationale="Re-extract the context; the deployment guide was uploaded after extraction.",
    )
    assert recorded.disposition is ReviewDisposition.REQUEST_MORE_ANALYSIS
    assert "request_re_extraction" not in {member.value for member in ReviewDisposition}


# --------------------------------------------------------------------------------------------
# The delta
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("half", ["prior_value", "updated_value"])
def test_an_edit_without_both_halves_is_rejected(half: str) -> None:
    """An edit that cannot say what it changed records that something was overwritten and nothing
    else — which is the silent overwrite section 2.5 forbids, with a row next to it."""
    payload: dict[str, Any] = {
        "prior_value": {"name": "Webhook Receiver"},
        "updated_value": {"name": "Webhook receiver (public)"},
    }
    payload[half] = None
    with pytest.raises(ValidationError, match=half):
        decision(disposition=ReviewDisposition.EDIT, **payload)


@pytest.mark.parametrize("disposition", [ReviewDisposition.APPROVE, ReviewDisposition.REJECT])
def test_an_approval_carrying_a_delta_is_rejected(disposition: ReviewDisposition) -> None:
    """The other direction: a decision that changed a field is an edit, whatever it is labelled."""
    with pytest.raises(ValidationError, match="carries no delta"):
        decision(
            disposition=disposition,
            prior_value={"name": "a"},
            updated_value={"name": "b"},
        )


def test_both_halves_must_name_the_same_fields() -> None:
    """Otherwise the record says a field appeared or vanished, which a reviewer edit cannot do to a
    frozen, schema-validated object."""
    with pytest.raises(ValidationError, match="same fields"):
        decision(
            disposition=ReviewDisposition.EDIT,
            prior_value={"name": "a"},
            updated_value={"description": "b"},
        )


def test_a_deferral_may_carry_no_delta_and_is_not_forced_to() -> None:
    """`defer`, `convert_to_question`, and `convert_to_documentation_gap` are judgments about an
    object rather than changes to it, and section 25 makes both fields optional."""
    assert decision(disposition=ReviewDisposition.DEFER).prior_value is None


# --------------------------------------------------------------------------------------------
# Capturing an edit
# --------------------------------------------------------------------------------------------


def test_changed_fields_records_only_what_changed() -> None:
    """DEC-023: the delta, not a snapshot. Reviewer edit rate is a primary evaluation metric, and
    "changed the severity and left everything else" is a measurement in a way that "changed this
    finding" is not."""
    prior, updated = changed_fields(component(), component(internet_accessible=True))
    assert prior == {"internet_accessible": None}
    assert updated == {"internet_accessible": True}


def test_changed_fields_compares_serialized_forms() -> None:
    """What is recorded is what would be persisted, so an enum and its value compare equal — which
    is the comparison a later reader of the record makes."""
    prior, updated = changed_fields(component(), component(status=ObjectStatus.APPROVED))
    assert prior == {"status": "candidate"}
    assert updated == {"status": "approved"}


def test_capture_edit_records_the_generated_state_before_the_edit() -> None:
    """The acceptance criterion: after the object has changed, the generated value is still
    recoverable from the decision."""
    before = component()
    after = component(name="Webhook receiver (public)", internet_accessible=True)

    recorded = ReviewerDecision.capture_edit(
        decision_id="dec-002",
        before=before,
        after=after,
        subject_type="component",
        subject_id=before.id,
        created_at=NOW,
        rationale="The architecture overview shows it behind the CDN, reachable from the internet.",
        reviewer_id="eturner",
    )

    assert recorded.disposition is ReviewDisposition.EDIT
    assert recorded.assessment_id == ASSESSMENT
    assert recorded.prior_value == {"name": "Webhook Receiver", "internet_accessible": None}
    assert recorded.updated_value == {
        "name": "Webhook receiver (public)",
        "internet_accessible": True,
    }


def test_capture_edit_refuses_a_change_that_did_not_happen() -> None:
    """The mistake this helper exists to prevent, in its most visible form: comparing an object
    with itself, which is what happens when the capture is written after the edit is applied."""
    edited = component(name="Webhook receiver (public)")
    with pytest.raises(ValueError, match="no edit to record"):
        ReviewerDecision.capture_edit(
            decision_id="dec-003",
            before=edited,
            after=edited,
            subject_type="component",
            subject_id=edited.id,
            created_at=NOW,
        )


# --------------------------------------------------------------------------------------------
# Subjects
# --------------------------------------------------------------------------------------------


def test_a_decision_names_the_kind_of_object_its_subject_is() -> None:
    with pytest.raises(ValidationError, match="Threat"):
        decision(subject_type="component", subject_id="thr-002")


@pytest.mark.parametrize(
    ("subject_type", "subject_id"),
    [("context_claim", "ctx-001"), ("component", "cmp-001"), ("question", "qst-004")],
)
def test_a_decision_may_be_recorded_against_any_context_object(
    subject_type: str, subject_id: str
) -> None:
    built = decision(subject_type=subject_type, subject_id=subject_id)
    assert built.subject_id == subject_id


def test_a_decision_about_a_system_context_is_allowed_without_an_identifier() -> None:
    """`SystemContext` has no `id` — it is keyed by `(assessment_id, version)` — so a decision about
    one names it by version rather than by identifier."""
    built = decision(subject_type="system_context", subject_id="asm-001@v1")
    assert built.subject_type == "system_context"
    assert system_context().version == FIRST_VERSION


# --------------------------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------------------------


def test_a_decision_round_trips_with_its_delta_intact() -> None:
    """The record is replayed to reconstruct history (DEC-023), so what survives persistence is
    what history is made of."""
    original = decision(
        disposition=ReviewDisposition.EDIT,
        prior_value={"data_classifications": ["Confidential"], "internet_accessible": None},
        updated_value={
            "data_classifications": ["Confidential", "Restricted"],
            "internet_accessible": True,
        },
    )
    restored = ReviewerDecision.model_validate_json(original.model_dump_json())
    assert restored == original
    assert restored.updated_value is not None
    assert restored.updated_value["data_classifications"] == ["Confidential", "Restricted"]
