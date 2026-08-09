"""Tests for the Context Validation node, one per responsibility in `agent-design.md` section 8.

Section 8 lists ten responsibilities and one constraint: the node does not reinterpret architecture
or invent corrections. The constraint is what most of these tests are about, because a validator
that corrected its input would make architectural judgments with no evidence and no reviewer — and
the corrections would be invisible, since a corrected object validates.

The sharpest case is a `documented` claim with no evidence. Re-labelling it `assumed` would make it
pass, and would turn a claim the agent asserted into one nobody asserted, with a clean validation
record. It is an error with a retry instruction instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.data_flow import DataFlow, FlowDirection
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, SourceOrigin
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.domain.system_context import FIRST_VERSION, SystemContext
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.workflow.context_validation import (
    SECTION_7_TRIGGERS,
    validate_context,
)
from trace_ai.workflow.errors import ErrorClass

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
ASSESSMENT = "asm-001"


def component(object_id: str = "cmp-001", **changes: Any) -> Component:
    return Component.model_validate(
        {
            "id": object_id,
            "assessment_id": ASSESSMENT,
            "name": "Webhook Receiver",
            "component_type": "service",
            "status": ObjectStatus.CANDIDATE,
            "evidence_ids": ["evd-001"],
            **changes,
        }
    )


def boundary(object_id: str = "tb-001", **changes: Any) -> TrustBoundary:
    return TrustBoundary.model_validate(
        {
            "id": object_id,
            "assessment_id": ASSESSMENT,
            "name": "GitHub Boundary",
            "boundary_type": "organization_to_third_party",
            "inside_component_ids": ["cmp-001"],
            "status": ObjectStatus.CANDIDATE,
            **changes,
        }
    )


def claim(object_id: str = "ctx-001", **changes: Any) -> ContextClaim:
    return ContextClaim.model_validate(
        {
            "id": object_id,
            "assessment_id": ASSESSMENT,
            "subject_type": "system",
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


def uncited_claim(object_id: str = "ctx-002") -> ContextClaim:
    """A `documented` claim with no evidence, built past validation on purpose.

    `ContextClaim` refuses this outright, so the node's evidence rule is reachable only for an
    object that bypassed the schema — which is what a validator is for. `model_construct` is the
    only way to produce one, and using it here is the test saying so rather than hiding it.
    """
    return ContextClaim.model_construct(
        id=object_id,
        assessment_id=ASSESSMENT,
        subject_type="system",
        predicate="database_encryption",
        value="encrypted",
        status=ClaimStatus.DOCUMENTED,
        confidence=ConfidenceLevel.HIGH,
        rationale=None,
        evidence_ids=[],
        source_origin=SourceOrigin.UPLOADED_DOCUMENT,
        generated_by=None,
        reviewer_notes=None,
        created_at=NOW,
        updated_at=NOW,
        supersedes_id=None,
    )


def flow(object_id: str = "df-001", **changes: Any) -> DataFlow:
    return DataFlow.model_validate(
        {
            "id": object_id,
            "assessment_id": ASSESSMENT,
            "name": "Webhook delivery",
            "source_component_id": "cmp-001",
            "destination_component_id": "cmp-002",
            "direction": FlowDirection.ONE_WAY,
            "status": ObjectStatus.CANDIDATE,
            **changes,
        }
    )


def context(**changes: Any) -> SystemContext:
    payload: dict[str, Any] = {
        "assessment_id": ASSESSMENT,
        "system_name": "ForgeFlow",
        "system_purpose": "AI-assisted pull request review",
        "context_claim_ids": ["ctx-001"],
        "component_ids": ["cmp-001"],
        "asset_ids": [],
        "actor_ids": [],
        "data_flow_ids": [],
        "trust_boundary_ids": ["tb-001"],
        "version": FIRST_VERSION,
        **changes,
    }
    return SystemContext.model_validate(payload)


def healthy() -> tuple[SystemContext, list[Any]]:
    return context(), [component(), boundary(), claim()]


# ------------------------------------------------------------------------------------------
# The constraint: report, never correct
# ------------------------------------------------------------------------------------------


def test_a_valid_context_produces_no_errors() -> None:
    system, objects = healthy()
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    assert outcome.errors == ()
    assert outcome.ready_for_review


def test_the_node_changes_nothing_it_validates() -> None:
    """Section 8: the node does not reinterpret architecture or invent corrections. A correction
    here would be an architectural judgment with no evidence and no reviewer, and it would be
    invisible, because a corrected object validates."""
    system, objects = healthy()
    objects.append(uncited_claim())
    before = [obj.model_dump() for obj in objects]

    outcome = validate_context(system, objects, available_evidence={"evd-001"})

    assert outcome.errors, "the fixture was supposed to produce an error"
    assert [obj.model_dump() for obj in objects] == before


def test_a_documented_claim_without_evidence_is_an_error_not_a_downgrade() -> None:
    """The sharpest case. Re-labelling it `assumed` would make it pass and would turn a claim the
    agent asserted into one nobody asserted, with a clean validation record."""
    system, objects = healthy()
    offending = uncited_claim()
    objects.append(offending)

    outcome = validate_context(system, [*objects], available_evidence={"evd-001"})

    (error,) = [e for e in outcome.errors if e.object_id == "ctx-002" and e.field == "evidence_ids"]
    assert offending.status is ClaimStatus.DOCUMENTED, "the claim was silently downgraded"
    assert error.retry_instruction() in outcome.retry_instructions()


@pytest.mark.parametrize("status", [ClaimStatus.ASSUMED, ClaimStatus.UNKNOWN])
def test_a_claim_about_a_silence_passes_without_evidence(status: ClaimStatus) -> None:
    """DEC-009. Penalising these would make the honest label the expensive one, and an extractor
    under that pressure mislabels rather than drops."""
    system, objects = healthy()
    objects.append(
        claim(
            "ctx-002",
            status=status,
            evidence_ids=[],
            rationale="the documentation does not state how the cache is authenticated",
        )
    )
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    assert not [error for error in outcome.errors if error.object_id == "ctx-002"]


# ------------------------------------------------------------------------------------------
# Section 8's ten responsibilities
# ------------------------------------------------------------------------------------------


def test_responsibility_validate_schemas() -> None:
    """Every converted object still validates against `data-model.md` (section 33)."""
    system, objects = healthy()
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    assert not [error for error in outcome.errors if error.field == "*"]


def test_responsibility_confirm_object_identifiers_are_unique() -> None:
    system, objects = healthy()
    objects.append(component("cmp-001", name="Analysis Worker"))
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    assert any(error.field == "id" for error in outcome.errors)


def test_responsibility_confirm_referenced_objects_exist() -> None:
    system = context(component_ids=["cmp-001", "cmp-404"])
    outcome = validate_context(system, [component(), boundary(), claim()])
    (error,) = [e for e in outcome.errors if "cmp-404" in e.message]
    assert error.error_class is ErrorClass.MISSING_REQUIRED_RELATIONSHIP


def test_responsibility_detect_exact_duplicates_without_merging() -> None:
    """Exact only: section 11 permits semantic comparison for threats and requires the merge
    decision to stay explicit, and open question 8 is unresolved. Merging here would be a
    correction."""
    system, objects = healthy()
    objects.append(component("cmp-002", name="webhook receiver"))
    system = context(component_ids=["cmp-001", "cmp-002"])

    outcome = validate_context(system, objects, available_evidence={"evd-001"})

    assert outcome.duplicate_groups == (("cmp-001", "cmp-002"),)
    assert any("share a normalized name" in error.message for error in outcome.errors)
    assert len([obj for obj in objects if isinstance(obj, Component)]) == 2, "objects were merged"


def test_responsibility_detect_invalid_data_flows() -> None:
    """`data-model.md` section 14: unknown transport security is `unknown`, never false. Silence
    read as `false` is an asserted weakness nobody evidenced."""
    system = context(component_ids=["cmp-001", "cmp-002"], data_flow_ids=["df-001"])
    objects = [component(), component("cmp-002", name="Worker"), boundary(), claim()]
    objects.append(flow(encryption_in_transit="false"))

    outcome = validate_context(system, objects, available_evidence={"evd-001"})

    (error,) = [e for e in outcome.errors if e.field == "encryption_in_transit"]
    assert "not a statement of absence" in error.message


def test_responsibility_enforce_evidence_requirements() -> None:
    """A claim citing evidence the extractor was never given (`agent-design.md` section 14)."""
    system, objects = healthy()
    objects.append(claim("ctx-002", evidence_ids=["evd-999"]))
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    assert any("evd-999" in error.message for error in outcome.errors)


def test_responsibility_normalize_enumerated_values() -> None:
    """DEC-036: an unfamiliar term is reported, never rejected. The `KNOWN_*` lists illustrate, and
    a benchmark using only listed terms would prove nothing."""
    system, objects = healthy()
    objects[0] = component(component_type="Managed Database")

    outcome = validate_context(system, objects, available_evidence={"evd-001"})

    assert outcome.unfamiliar_terms == ()  # `managed_database` is a known ForgeFlow type
    assert objects[0].component_type == "managed_database"

    objects[0] = component(component_type="quantum annealer")
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    assert outcome.unfamiliar_terms == ("component_type=quantum_annealer",)
    assert not [error for error in outcome.errors if "quantum" in error.message]


def test_responsibility_identify_missing_required_fields() -> None:
    """Reported per object and field rather than as one failure for the whole response."""
    system, objects = healthy()
    objects.append(uncited_claim())
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    fields = {e.field for e in outcome.errors if e.object_id == "ctx-002"}
    assert "evidence_ids" in fields


def test_responsibility_confirm_confidence_is_a_member_and_nothing_more() -> None:
    """DEC-022: there is no numeric score and no range to check. This asserts the absence of the
    check as much as the presence of the field."""
    system, objects = healthy()
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    assert not [error for error in outcome.errors if error.field == "confidence"]
    assert "confidence_score" not in ContextClaim.model_fields


def test_responsibility_prevent_invalid_workflow_transitions() -> None:
    """A context with an outstanding blocking error is not one a reviewer should be asked to
    approve — they would be approving objects the application already knows are wrong."""
    system, objects = healthy()
    assert validate_context(system, objects, available_evidence={"evd-001"}).ready_for_review

    objects.append(uncited_claim())
    assert not validate_context(system, objects, available_evidence={"evd-001"}).ready_for_review


# ------------------------------------------------------------------------------------------
# Errors and routing
# ------------------------------------------------------------------------------------------


def test_errors_are_returned_rather_than_raised_on_the_first_failure() -> None:
    """A reviewer fixing a context wants the whole list; raising turns one pass into as many passes
    as there are mistakes."""
    system = context(component_ids=["cmp-404", "cmp-405"])
    outcome = validate_context(system, [uncited_claim()])
    assert len(outcome.errors) >= 3


def test_every_error_is_classified_for_routing() -> None:
    """The extraction node routes on a class rather than parsing a message (`agent-design.md`
    section 26)."""
    system = context(component_ids=["cmp-404"])
    outcome = validate_context(system, [claim()])
    for error in outcome.errors:
        assert isinstance(error.error_class, ErrorClass)
        assert isinstance(error.retryable, bool)


# ------------------------------------------------------------------------------------------
# Human-review triggers
# ------------------------------------------------------------------------------------------


def test_the_trigger_vocabulary_is_section_7_s_six() -> None:
    assert len(SECTION_7_TRIGGERS) == 6


def test_a_contradiction_triggers_review_and_names_what_caused_it() -> None:
    """A trigger is not an error: it is a reason a person should look, so it carries the objects
    rather than a verdict about them."""
    system, objects = healthy()
    objects.append(
        SourceObservation.model_validate(
            {
                "id": "obs-001",
                "assessment_id": ASSESSMENT,
                "kind": ObservationKind.CONTRADICTION,
                "summary": "Two documents disagree about retention.",
                "evidence_ids": ["evd-001", "evd-002"],
                "status": ObjectStatus.CANDIDATE,
                "created_at": NOW,
            }
        )
    )
    outcome = validate_context(system, objects, available_evidence={"evd-001", "evd-002"})
    (trigger,) = [t for t in outcome.triggers if t.name == "contradictory_high_impact_claims"]
    assert trigger.object_ids == ("obs-001",)


def test_an_unclear_system_purpose_triggers_review() -> None:
    system = context(system_purpose=None)
    outcome = validate_context(system, [component(), boundary(), claim()])
    assert any(t.name == "core_system_purpose_unclear" for t in outcome.triggers)


def test_an_empty_trust_boundary_triggers_review() -> None:
    system, objects = healthy()
    objects[1] = boundary(inside_component_ids=[])
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    (trigger,) = [t for t in outcome.triggers if t.name == "major_trust_boundaries_uncertain"]
    assert trigger.object_ids == ("tb-001",)


def test_a_component_citing_no_evidence_triggers_review() -> None:
    """It rests on inference rather than on documentation, which is section 7's trigger and not a
    reason to discard the component."""
    system, objects = healthy()
    objects[0] = component(evidence_ids=[])
    outcome = validate_context(system, objects, available_evidence={"evd-001"})
    assert any(
        t.name == "significant_component_inferred_rather_than_documented" for t in outcome.triggers
    )


def test_a_material_change_from_the_approved_revision_triggers_review() -> None:
    system, objects = healthy()
    previous = context(component_ids=["cmp-001", "cmp-009"])
    outcome = validate_context(system, objects, available_evidence={"evd-001"}, previous=previous)
    (trigger,) = [
        t for t in outcome.triggers if t.name == "material_change_from_prior_approved_version"
    ]
    assert trigger.object_ids == ("cmp-009",)


def test_every_computed_trigger_is_one_section_7_names() -> None:
    """A trigger the document does not list is one nobody decided to show a reviewer."""
    system = context(system_purpose=None, trust_boundary_ids=[])
    outcome = validate_context(system, [component(evidence_ids=[]), claim()])
    for trigger in outcome.triggers:
        assert trigger.name in SECTION_7_TRIGGERS
