"""Tests for the Threat Validation node.

The node is deterministic and makes no model call, so these tests construct threats directly and
call `validate_threats`. There is no fake model here because there is nothing to fake.

Two properties carry most of the weight.

**Nothing is corrected.** A validator that fixed its input would be making security judgments with
no evidence and no reviewer, and the fix would be invisible because a corrected object validates.
A test asserts the threats are unchanged after a run that produces errors.

**Nothing is merged.** `agent-design.md` section 11 requires the merge decision to stay explicit
and traceable, and section 16 gives the merge itself to M4. What this node emits is a proposal
carrying both identifiers and the features that matched.
"""

from __future__ import annotations

from typing import Any

import pytest

from trace_ai.domain.base import now
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, SourceOrigin
from trace_ai.domain.system_context import SystemContext
from trace_ai.domain.threat import Threat
from trace_ai.workflow.errors import ErrorClass
from trace_ai.workflow.threat_validation import (
    DUPLICATE_THRESHOLD,
    SECTION_10_TRIGGERS,
    duplicate_groups,
    validate_threats,
)

COMPONENTS = ["cmp-001", "cmp-002", "cmp-003"]
ASSETS = ["ast-001", "ast-002"]
ACTORS = ["act-001"]
FLOWS = ["df-001"]


def a_context(**changes: Any) -> SystemContext:
    payload: dict[str, Any] = {
        "assessment_id": "asm-001",
        "system_name": "ForgeFlow",
        "component_ids": list(COMPONENTS),
        "asset_ids": list(ASSETS),
        "actor_ids": list(ACTORS),
        "data_flow_ids": list(FLOWS),
        "trust_boundary_ids": [],
        "context_claim_ids": [],
        "version": 2,
        "approved_at": now(),
        "approved_by": "reviewer",
    }
    payload.update(changes)
    return SystemContext.model_validate(payload)


def a_threat(identifier: str = "thr-001", **changes: Any) -> Threat:
    payload: dict[str, Any] = {
        "id": identifier,
        "assessment_id": "asm-001",
        "title": "Forged repository webhooks trigger unauthorized analysis jobs",
        "description": "An attacker submits unsigned webhook requests and triggers jobs.",
        "methodology": "stride-scenario-based",
        "category": ["spoofing"],
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "impact": "Unauthorized jobs and denial of service",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "threat-analysis-v1",
        "created_at": now(),
    }
    payload.update(changes)
    return Threat.model_validate(payload)


def a_claim(identifier: str, status: ClaimStatus) -> ContextClaim:
    """A claim of the given status.

    `ContextClaim` already enforces DEC-009 and DEC-022 at the schema: a `documented` claim cites
    evidence and an `assumed` one carries a rationale. Both are supplied here so the fixture is
    constructing a real claim rather than fighting its own model.
    """
    stamped = now()
    payload: dict[str, Any] = {
        "id": identifier,
        "assessment_id": "asm-001",
        "subject_type": "component",
        "subject_id": "cmp-001",
        "predicate": "signature_verification",
        "value": "unstated",
        "status": status,
        "confidence": ConfidenceLevel.LOW,
        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
        "created_at": stamped,
        "updated_at": stamped,
    }
    if status in {ClaimStatus.DOCUMENTED, ClaimStatus.INFERRED}:
        payload["evidence_ids"] = ["evd-001"]
    if status in {ClaimStatus.ASSUMED, ClaimStatus.INFERRED}:
        payload["rationale"] = "the platform documentation implies it"
    return ContextClaim.model_validate(payload)


# ------------------------------------------------------------------------------------------
# The node is deterministic and changes nothing
# ------------------------------------------------------------------------------------------


def test_a_single_well_formed_threat_passes() -> None:
    """A low threat count is never a validation failure (`agent-design.md` section 10)."""
    outcome = validate_threats([a_threat()], context=a_context())

    assert outcome.valid
    assert not outcome.blocking_errors
    assert not outcome.merge_proposals


def test_an_empty_threat_set_is_not_an_error() -> None:
    outcome = validate_threats([], context=a_context())

    assert outcome.valid
    assert not outcome.errors


def test_the_threats_are_unchanged_by_a_run_that_produces_errors() -> None:
    """The constraint that matters more than any convenience this node could offer."""
    threat = a_threat(affected_component_ids=["cmp-404"], impact="x")
    before = threat.model_dump()

    validate_threats([threat], context=a_context())

    assert threat.model_dump() == before


def test_the_node_imports_no_provider_sdk() -> None:
    """Section 4 classifies this node as deterministic, and DEC-014 keeps providers behind a seam."""
    import trace_ai.workflow.threat_validation as module

    source = module.__file__
    assert source is not None
    text = open(source, encoding="utf-8").read()  # noqa: SIM115, PTH123
    assert "import anthropic" not in text
    assert "StructuredModel" not in text


# ------------------------------------------------------------------------------------------
# References must exist in the approved context
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("affected_component_ids", "cmp-404"),
        ("affected_asset_ids", "ast-404"),
        ("threat_actor_ids", "act-404"),
        ("related_data_flow_ids", "df-404"),
    ],
)
def test_a_reference_absent_from_the_context_is_rejected_by_name(field: str, bad: str) -> None:
    outcome = validate_threats([a_threat("thr-001", **{field: [bad]})], context=a_context())

    (error,) = [e for e in outcome.errors if e.field == field]
    assert bad in error.message
    assert error.error_class is ErrorClass.MISSING_REQUIRED_RELATIONSHIP
    assert error.retryable


def test_a_rejected_component_is_not_in_the_approved_context() -> None:
    """DEC-040 recomputes membership at approval, so a threat naming a rejected object fails."""
    narrowed = a_context(component_ids=["cmp-002"])

    outcome = validate_threats([a_threat(affected_component_ids=["cmp-001"])], context=narrowed)

    assert not outcome.valid
    assert "cmp-001" in outcome.errors[0].message


def test_a_reference_error_is_retryable_and_names_the_threat_and_the_field() -> None:
    """The error itself carries what a correction needs — the threat, the field, and the message.
    The aggregate retry-instruction surface was removed with DEC-086: no path re-runs this
    validator's agent, so the actionable content lives on the error, where the run's stop
    reporting reads it."""
    outcome = validate_threats([a_threat(affected_component_ids=["cmp-404"])], context=a_context())

    (error,) = outcome.errors
    assert error.retryable
    assert error.threat_id == "thr-001"
    assert error.field == "affected_component_ids"


# ------------------------------------------------------------------------------------------
# Impact and attack paths
# ------------------------------------------------------------------------------------------


def test_a_threat_with_no_component_or_asset_is_rejected() -> None:
    """Constructed past the schema, which already refuses this. A validator exists for that case."""
    threat = a_threat()
    object.__setattr__(threat, "affected_asset_ids", [])

    outcome = validate_threats([threat], context=a_context())

    assert any("cannot be mapped to a requirement" in error.message for error in outcome.errors)


def test_a_whitespace_only_impact_is_rejected() -> None:
    threat = a_threat()
    object.__setattr__(threat, "impact", "   ")

    outcome = validate_threats([threat], context=a_context())

    (error,) = [e for e in outcome.errors if e.field == "impact"]
    assert "empty" in error.message


def test_a_circular_attack_path_is_rejected_and_names_the_repeated_step() -> None:
    threat = a_threat(
        attack_path=[
            "forge a delivery",
            "submit it to the receiver",
            "Forge a delivery",
        ]
    )

    outcome = validate_threats([threat], context=a_context())

    (error,) = [e for e in outcome.errors if e.field == "attack_path"]
    assert "Forge a delivery" in error.message


def test_an_absent_attack_path_is_not_an_error() -> None:
    """`attack_path` is optional in section 16. A threat described through preconditions and
    impact, with no ordered path, is a legitimate one."""
    outcome = validate_threats([a_threat(attack_path=[])], context=a_context())

    assert not [e for e in outcome.errors if e.field == "attack_path"]


def test_a_non_repeating_attack_path_passes() -> None:
    threat = a_threat(attack_path=["forge a delivery", "submit it", "observe the job run"])

    outcome = validate_threats([threat], context=a_context())

    assert outcome.valid


# ------------------------------------------------------------------------------------------
# Categories (DEC-041)
# ------------------------------------------------------------------------------------------


def test_an_unfamiliar_category_is_reported_and_not_rejected() -> None:
    """DEC-041: the known set illustrates. STRIDE has no category for several ForgeFlow threats."""
    outcome = validate_threats(
        [a_threat(category=["supply_chain_compromise"])], context=a_context()
    )

    assert outcome.valid
    assert outcome.unfamiliar_categories == ("supply_chain_compromise",)


def test_a_known_category_is_not_reported_as_unfamiliar() -> None:
    outcome = validate_threats([a_threat(category=["prompt_injection"])], context=a_context())

    assert not outcome.unfamiliar_categories


# ------------------------------------------------------------------------------------------
# Threats resting entirely on unsupported assumptions
# ------------------------------------------------------------------------------------------


def test_a_threat_citing_only_assumed_claims_and_no_evidence_is_flagged() -> None:
    claims = [a_claim("ctx-001", ClaimStatus.ASSUMED), a_claim("ctx-002", ClaimStatus.UNKNOWN)]
    threat = a_threat(assumption_ids=["ctx-001", "ctx-002"], evidence_ids=[])

    outcome = validate_threats([threat], context=a_context(), claims=claims)

    (error,) = [e for e in outcome.errors if e.field == "assumption_ids"]
    assert error.error_class is ErrorClass.INSUFFICIENT_EVIDENCE


def test_an_unsupported_assumption_is_never_retried() -> None:
    """Section 26. Asking again invites the agent to supply support it does not have."""
    claims = [a_claim("ctx-001", ClaimStatus.ASSUMED)]
    threat = a_threat(assumption_ids=["ctx-001"], evidence_ids=[])

    outcome = validate_threats([threat], context=a_context(), claims=claims)

    assert not any(error.retryable for error in outcome.errors)


def test_an_unsupported_assumption_does_not_block_the_threat_set() -> None:
    """It is a condition of the material, not a defect in the output. The reviewer decides."""
    claims = [a_claim("ctx-001", ClaimStatus.ASSUMED)]
    threat = a_threat(assumption_ids=["ctx-001"], evidence_ids=[])

    outcome = validate_threats([threat], context=a_context(), claims=claims)

    assert outcome.valid


def test_an_assumption_alongside_evidence_is_ordinary_threat_modelling() -> None:
    """Section 11 names a threat resting *entirely* on assumptions. Partly is what preconditions
    are for."""
    claims = [a_claim("ctx-001", ClaimStatus.ASSUMED)]
    threat = a_threat(assumption_ids=["ctx-001"], evidence_ids=["evd-001"])

    outcome = validate_threats([threat], context=a_context(), claims=claims)

    assert not [e for e in outcome.errors if e.field == "assumption_ids"]


def test_an_assumption_that_is_actually_documented_is_not_flagged() -> None:
    claims = [a_claim("ctx-001", ClaimStatus.DOCUMENTED)]
    threat = a_threat(assumption_ids=["ctx-001"], evidence_ids=[])

    outcome = validate_threats([threat], context=a_context(), claims=claims)

    assert not [e for e in outcome.errors if e.field == "assumption_ids"]


# ------------------------------------------------------------------------------------------
# Duplicate detection (DEC-043)
# ------------------------------------------------------------------------------------------


def test_two_identical_threats_are_proposed_as_duplicates() -> None:
    outcome = validate_threats([a_threat("thr-001"), a_threat("thr-002")], context=a_context())

    (proposal,) = outcome.merge_proposals
    assert proposal.threat_ids == ("thr-001", "thr-002")
    assert proposal.score >= DUPLICATE_THRESHOLD
    assert set(proposal.matched_features) == {"title", "targets", "category"}


def test_a_merge_proposal_never_mutates_or_deletes_a_threat() -> None:
    """The constraint section 11 states, asserted rather than assumed."""
    threats = [a_threat("thr-001"), a_threat("thr-002")]
    before = [threat.model_dump() for threat in threats]

    outcome = validate_threats(threats, context=a_context())

    assert outcome.merge_proposals
    assert [threat.model_dump() for threat in threats] == before


def test_a_merge_proposal_does_not_block_control_mapping() -> None:
    """Two overlapping threats are still two threats worth mapping."""
    outcome = validate_threats([a_threat("thr-001"), a_threat("thr-002")], context=a_context())

    assert outcome.valid


def test_an_identical_title_alone_is_not_enough() -> None:
    """0.50 of 0.75. Two different scenarios can share a title and hit different objects."""
    outcome = validate_threats(
        [
            a_threat("thr-001", affected_component_ids=["cmp-001"], affected_asset_ids=["ast-001"]),
            a_threat(
                "thr-002",
                affected_component_ids=["cmp-002"],
                affected_asset_ids=["ast-002"],
                category=["tampering"],
            ),
        ],
        context=a_context(),
    )

    assert not outcome.merge_proposals


def test_identical_targets_alone_are_not_enough() -> None:
    """0.35 of 0.75. One component has more than one threat against it."""
    outcome = validate_threats(
        [
            a_threat("thr-001", title="Forged webhooks trigger unauthorized jobs"),
            a_threat(
                "thr-002",
                title="Replayed events exhaust analysis capacity",
                category=["denial_of_service"],
            ),
        ],
        context=a_context(),
    )

    assert not outcome.merge_proposals


def test_two_threats_with_no_categories_are_not_similar_on_that_feature() -> None:
    """Two empty sets score 0.0, not 1.0. DEC-041 makes `category` optional."""
    outcome = validate_threats(
        [
            a_threat("thr-001", title="Forged webhooks trigger jobs", category=[]),
            a_threat("thr-002", title="Replayed events exhaust capacity", category=[]),
        ],
        context=a_context(),
    )

    assert not outcome.merge_proposals


def test_a_pair_is_proposed_once_and_in_sorted_order() -> None:
    outcome = validate_threats([a_threat("thr-002"), a_threat("thr-001")], context=a_context())

    assert len(outcome.merge_proposals) == 1
    assert outcome.merge_proposals[0].threat_ids == ("thr-001", "thr-002")


def test_the_proposal_names_the_features_that_matched() -> None:
    outcome = validate_threats([a_threat("thr-001"), a_threat("thr-002")], context=a_context())

    (proposal,) = outcome.merge_proposals
    assert "title" in proposal.detail
    assert proposal.detail.count("Forged repository webhooks") == 2


def test_transitive_pairs_collapse_into_one_group_for_presentation() -> None:
    outcome = validate_threats(
        [a_threat("thr-001"), a_threat("thr-002"), a_threat("thr-003")], context=a_context()
    )

    assert duplicate_groups(outcome.merge_proposals) == (("thr-001", "thr-002", "thr-003"),)


def test_grouping_decides_nothing() -> None:
    """It is a convenience for whatever renders the proposals; the proposals stay the record."""
    outcome = validate_threats([a_threat("thr-001"), a_threat("thr-002")], context=a_context())

    assert len(outcome.merge_proposals) == 1
    assert duplicate_groups(()) == ()


# ------------------------------------------------------------------------------------------
# Human-review triggers (agent-design.md section 10)
# ------------------------------------------------------------------------------------------


def test_the_trigger_names_match_the_document() -> None:
    assert len(SECTION_10_TRIGGERS) == 4


def test_triggers_reuse_the_context_validator_s_record() -> None:
    """One `ReviewTrigger`, not two. Section 7's and section 10's triggers are the same thing."""
    from trace_ai.workflow.context_validation import ReviewTrigger

    outcome = validate_threats([a_threat()], context=a_context())

    assert all(isinstance(trigger, ReviewTrigger) for trigger in outcome.triggers)
    assert all(hasattr(trigger, "object_ids") for trigger in outcome.triggers)


def test_a_high_confidence_threat_on_an_assumed_claim_triggers_review() -> None:
    claims = [a_claim("ctx-001", ClaimStatus.ASSUMED)]
    threat = a_threat(
        assumption_ids=["ctx-001"], evidence_ids=["evd-001"], confidence=ConfidenceLevel.HIGH
    )

    outcome = validate_threats([threat], context=a_context(), claims=claims)

    names = {trigger.name for trigger in outcome.triggers}
    assert "critical_threat_depends_on_uncertain_assumption" in names


def test_a_threat_citing_a_contradicted_claim_triggers_review() -> None:
    claims = [a_claim("ctx-001", ClaimStatus.DOCUMENTED)]
    threat = a_threat(assumption_ids=["ctx-001"], evidence_ids=["evd-001"])

    outcome = validate_threats(
        [threat], context=a_context(), claims=claims, contradicted_claim_ids=["ctx-001"]
    )

    names = {trigger.name for trigger in outcome.triggers}
    assert "threats_rely_on_contradictory_context" in names


def test_a_component_no_threat_reaches_triggers_review() -> None:
    outcome = validate_threats([a_threat()], context=a_context())

    (trigger,) = [t for t in outcome.triggers if t.name == "likely_missing_core_component"]
    assert "cmp-002" in trigger.detail
    assert "cmp-003" in trigger.detail


def test_a_thin_architecture_triggers_review() -> None:
    thin = a_context(component_ids=["cmp-001"], data_flow_ids=[])

    outcome = validate_threats([a_threat()], context=thin)

    names = {trigger.name for trigger in outcome.triggers}
    assert "architecture_materially_incomplete" in names


def test_a_trigger_is_not_an_error() -> None:
    """Reasons for a person to look, not statements that anything is wrong."""
    outcome = validate_threats([a_threat()], context=a_context())

    assert outcome.triggers
    assert outcome.valid


# ------------------------------------------------------------------------------------------
# STRIDE coverage baseline (DEC-063): authored, deterministic, warn-only
# ------------------------------------------------------------------------------------------


def _component(component_id: str, component_type: str) -> Any:
    from trace_ai.domain.component import Component

    return Component.model_validate(
        {
            "id": component_id,
            "assessment_id": "asm-001",
            "name": component_id,
            "component_type": component_type,
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "status": ObjectStatus.APPROVED,
        }
    )


def test_classify_maps_known_types_and_defaults_unknown_to_unclassified() -> None:
    from trace_ai.domain.threat import UNCLASSIFIED_KIND, classify_element_kind

    assert classify_element_kind("service") == "process"
    assert classify_element_kind("managed_database") == "data_store"
    assert classify_element_kind("external_service") == "external_actor"
    assert classify_element_kind("quantum_flux_capacitor") == UNCLASSIFIED_KIND


def test_coverage_names_the_uncovered_applicable_categories() -> None:
    from trace_ai.workflow.threat_validation import stride_coverage_gaps

    component = _component("cmp-001", "service")  # a process: all six STRIDE apply
    threat = a_threat(category=["spoofing"], affected_component_ids=["cmp-001"])
    gaps = {gap.component_id: gap for gap in stride_coverage_gaps([component], [threat])}

    assert "spoofing" not in gaps["cmp-001"].uncovered, "a covered category is not a gap"
    assert "tampering" in gaps["cmp-001"].uncovered, "an applicable, unnamed category is a gap"


def test_an_unclassified_component_is_listed_rather_than_read_as_clean() -> None:
    from trace_ai.domain.threat import UNCLASSIFIED_KIND
    from trace_ai.workflow.threat_validation import stride_coverage_gaps

    gaps = {
        gap.component_id: gap for gap in stride_coverage_gaps([_component("cmp-009", "gizmo")], [])
    }
    assert gaps["cmp-009"].kind == UNCLASSIFIED_KIND
    assert gaps["cmp-009"].uncovered == (), "an unclassified component is presented, not judged"


def test_coverage_is_warn_only_and_never_blocks_or_retries() -> None:
    """Acceptance: the run proceeds and no path retries the threat agent against coverage."""
    component = _component("cmp-001", "service")
    outcome = validate_threats([a_threat()], context=a_context(), components=[component])

    assert outcome.valid, "a coverage gap does not block the run"
    assert outcome.coverage_gaps, "the gap is named"
    assert not any(error.retryable for error in outcome.errors), (
        "nothing retries against a coverage gap"
    )
    assert all("coverage" not in error.rule.lower() for error in outcome.errors), (
        "coverage never becomes an error"
    )


def test_an_inapplicable_category_is_a_warn_only_observation() -> None:
    """DEC-063: spoofing whose only element is a data store is flagged, never rejected."""
    store = _component("cmp-001", "managed_database")  # data_store: no spoofing
    threat = a_threat(category=["spoofing"], affected_component_ids=["cmp-001"])
    outcome = validate_threats([threat], context=a_context(), components=[store])

    assert outcome.valid, "an implausible category does not block"
    flagged = {
        (observation.threat_id, observation.category) for observation in outcome.implausible_threats
    }
    assert ("thr-001", "spoofing") in flagged
    assert not any(error.retryable for error in outcome.errors)


def test_a_category_applicable_to_any_affected_element_is_not_flagged() -> None:
    process = _component("cmp-001", "service")  # process admits spoofing
    store = _component("cmp-002", "managed_database")
    threat = a_threat(category=["spoofing"], affected_component_ids=["cmp-001", "cmp-002"])
    outcome = validate_threats([threat], context=a_context(), components=[process, store])
    assert outcome.implausible_threats == (), "plausible against the process element"
