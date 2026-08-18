"""DEC-068: sensitivity, personas, entry points, the access model, and the two checks.

Issue #343's acceptance criteria are the spine: the ForgeFlow structured input's material
round-trips through the proposal boundary into domain objects where it supplies the new fields,
and absence renders as `unknown` — never `False`, never `None` — for the one field where absence
would otherwise read as an answer.

The two checks are asserted to be exactly what DEC-068 made them: the zone-mismatch check is
warn-only by construction (outside `errors`, so it can neither block nor be retried against), and
the privilege-extremes check names the unrepresented extreme without blocking anything.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from trace_ai.domain.component import Component
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.proposals.context_extraction import (
    ContextExtractionProposal,
    ProposalError,
)
from trace_ai.domain.proposals.conversion import convert_proposal
from trace_ai.domain.system_context import AccessModel, SystemContext
from trace_ai.workflow.context_validation import validate_context


def proposal_payload(**changes: Any) -> dict[str, Any]:
    """A proposal shaped from what the ForgeFlow structured input actually supplies.

    `internet_facing: [Webhook Receiver]` grounds a webhook entry point, the administrative
    identity paragraph grounds a privileged administrator, and the asset classifications
    (`Restricted`, `Confidential`) ground normalized sensitivity values.
    """
    payload: dict[str, Any] = {
        "system": {
            "system_name": "ForgeFlow",
            "system_purpose": "AI-assisted pull request review platform",
        },
        "claims": [],
        "components": [
            {
                "key": "webhook",
                "name": "Webhook Receiver",
                "component_type": "service",
                "deployment_zone": "public",
                "internet_accessible": True,
                "entry_point_types": ["Webhook", "API"],
            },
            {
                "key": "db",
                "name": "Managed Database",
                "component_type": "managed_database",
                "deployment_zone": "private",
            },
        ],
        "actors": [
            {
                "key": "admin",
                "name": "Platform Administrator",
                "actor_type": "administrator",
                "access_level": "Privileged",
                "skill_level": "skilled",
            }
        ],
        "assets": [
            {
                "key": "tokens",
                "name": "GitHub App installation tokens",
                "asset_type": "access_token",
                "data_classification": "Restricted",
                "component_keys": ["webhook", "db"],
                "stored_in_component_keys": ["db"],
            }
        ],
        "data_flows": [],
        "trust_boundaries": [],
        "questions": [],
        "observations": [],
    }
    payload.update(changes)
    return payload


def converted(**changes: Any) -> Any:
    from trace_ai.domain.base import now
    from trace_ai.domain.identifiers import InMemoryAllocator

    proposal = ContextExtractionProposal.model_validate(proposal_payload(**changes))
    return convert_proposal(
        proposal,
        allocator=InMemoryAllocator(),
        assessment_id="asm-001",
        created_at=now(),
        generated_by="context-extraction-v1",
    )


# ------------------------------------------------------------------------------------------
# Round-trip: the material's values survive the proposal boundary (issue #343)
# ------------------------------------------------------------------------------------------


def test_the_forgeflow_material_round_trips_through_conversion() -> None:
    outcome = converted()

    webhook = next(c for c in outcome.components if c.name == "Webhook Receiver")
    assert webhook.entry_point_types == ["webhook", "api"]  # normalized on the way in

    admin = outcome.actors[0]
    assert admin.access_level == "privileged"
    assert admin.skill_level == "skilled"

    tokens = outcome.assets[0]
    assert tokens.data_classification == "restricted"
    database = next(c for c in outcome.components if c.name == "Managed Database")
    assert tokens.stored_in_component_ids == [database.id]
    assert set(tokens.stored_in_component_ids) <= set(tokens.component_ids)


def test_stored_in_must_be_a_subset_of_holds_or_processes() -> None:
    proposal = ContextExtractionProposal.model_validate(
        proposal_payload(
            assets=[
                {
                    "key": "tokens",
                    "name": "GitHub App installation tokens",
                    "asset_type": "access_token",
                    "component_keys": ["webhook"],
                    "stored_in_component_keys": ["db"],
                }
            ]
        )
    )
    with pytest.raises(ProposalError, match="subset"):
        proposal.validate_references()


# ------------------------------------------------------------------------------------------
# Absence renders as unknown, never False, never None (issue #343)
# ------------------------------------------------------------------------------------------


def test_an_unstated_access_model_is_unknown() -> None:
    """On the proposal and on the domain object alike: absence is `unknown`, an explicit value."""
    proposal = ContextExtractionProposal.model_validate(proposal_payload())
    assert proposal.system.access_model is AccessModel.UNKNOWN
    assert a_context().access_model is AccessModel.UNKNOWN
    assert a_context().access_model.value == "unknown"


def test_a_stated_access_model_survives_the_proposal_boundary() -> None:
    """The extraction node builds the context from `proposal.system.model_dump()`, so the field
    passes through by name; this pins both ends of that hand-off."""
    proposal = ContextExtractionProposal.model_validate(
        proposal_payload(system={"system_name": "ForgeFlow", "access_model": "deny_by_default"})
    )
    assert proposal.system.access_model is AccessModel.DENY_BY_DEFAULT
    rebuilt = a_context(**{"access_model": proposal.system.model_dump()["access_model"]})
    assert rebuilt.access_model is AccessModel.DENY_BY_DEFAULT


def test_the_access_model_is_a_closed_enum() -> None:
    """Named values, like `DataFlow.direction` — an invented posture is refused, not normalized."""
    with pytest.raises(PydanticValidationError):
        ContextExtractionProposal.model_validate(
            proposal_payload(system={"system_name": "X", "access_model": "mostly_deny"})
        )


def test_a_boolean_persona_is_refused_as_a_non_answer() -> None:
    with pytest.raises(PydanticValidationError, match="nobody gave"):
        ContextExtractionProposal.model_validate(
            proposal_payload(
                actors=[
                    {
                        "key": "admin",
                        "name": "Platform Administrator",
                        "actor_type": "administrator",
                        "access_level": False,
                    }
                ]
            )
        )


def test_unstated_personas_stay_none_rather_than_defaulting() -> None:
    outcome = converted(actors=[{"key": "user", "name": "Developer", "actor_type": "end_user"}])
    assert outcome.actors[0].skill_level is None
    assert outcome.actors[0].access_level is None


# ------------------------------------------------------------------------------------------
# The zone-mismatch check: warn-only by construction (DEC-068)
# ------------------------------------------------------------------------------------------


def component(component_id: str, name: str, zone: str | None) -> Component:
    return Component.model_validate(
        {
            "id": component_id,
            "assessment_id": "asm-001",
            "name": name,
            "component_type": "service",
            "deployment_zone": zone,
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "status": ObjectStatus.CANDIDATE,
        }
    )


def flow(flow_id: str, source: str, destination: str, crossings: list[str]) -> DataFlow:
    return DataFlow.model_validate(
        {
            "id": flow_id,
            "assessment_id": "asm-001",
            "name": "events",
            "source_component_id": source,
            "destination_component_id": destination,
            "direction": "one_way",
            "crosses_trust_boundary_ids": crossings,
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "status": ObjectStatus.CANDIDATE,
        }
    )


def a_context(**changes: Any) -> SystemContext:
    payload: dict[str, Any] = {
        "assessment_id": "asm-001",
        "system_name": "ForgeFlow",
        "context_claim_ids": [],
        "component_ids": [],
        "asset_ids": [],
        "actor_ids": [],
        "data_flow_ids": [],
        "trust_boundary_ids": [],
        "version": 1,
    }
    payload.update(changes)
    return SystemContext.model_validate(payload)


def test_a_zone_crossing_flow_with_no_boundary_is_reported_and_blocks_nothing() -> None:
    objects = [
        component("cmp-001", "Webhook Receiver", "public"),
        component("cmp-002", "Managed Database", "private"),
        flow("df-001", "cmp-001", "cmp-002", crossings=[]),
    ]
    outcome = validate_context(
        a_context(component_ids=["cmp-001", "cmp-002"], data_flow_ids=["df-001"]), objects
    )

    assert [mismatch.flow_id for mismatch in outcome.zone_mismatches] == ["df-001"]
    assert "df-001" in outcome.zone_mismatches[0].detail
    # Warn-only, structurally: nothing about the mismatch is an error, blocks, or retries.
    assert not any("zone" in error.rule for error in outcome.errors)
    assert outcome.ready_for_review
    assert not outcome.retry_instructions()


# ------------------------------------------------------------------------------------------
# The cross-claim consistency checks: DEC-070's residual, the same warn-only posture (#526)
# ------------------------------------------------------------------------------------------


def _flow_stating(flow_id: str, **changes: Any) -> DataFlow:
    payload: dict[str, Any] = {
        "id": flow_id,
        "assessment_id": "asm-001",
        "name": "events",
        "source_component_id": "cmp-001",
        "destination_component_id": "cmp-002",
        "direction": "one_way",
        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
        "status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return DataFlow.model_validate(payload)


def _claim(claim_id: str, predicate: str, value: Any, *, status: str = "documented") -> Any:
    from trace_ai.domain.context_claim import ContextClaim

    payload: dict[str, Any] = {
        "id": claim_id,
        "assessment_id": "asm-001",
        "subject_type": "component",
        "subject_id": "cmp-001",
        "predicate": predicate,
        "value": value,
        "status": status,
        "confidence": "medium",
        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
        "created_at": "2026-08-17T00:00:00Z",
        "updated_at": "2026-08-17T00:00:00Z",
    }
    if status == "documented":
        payload["evidence_ids"] = ["evd-001"]
    if status in ("inferred", "assumed"):
        payload["evidence_ids"] = ["evd-001"] if status == "inferred" else []
        payload["rationale"] = "stated for the test"
    return ContextClaim.model_validate(payload)


def test_an_exposure_conflict_between_a_flow_and_its_destination_is_reported() -> None:
    objects = [
        component("cmp-001", "Webhook Receiver", None),
        Component.model_validate(
            {
                "id": "cmp-002",
                "assessment_id": "asm-001",
                "name": "Internal Worker",
                "component_type": "service",
                "internet_accessible": False,
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.CANDIDATE,
            }
        ),
        _flow_stating("df-001", internet_exposed=True),
    ]
    outcome = validate_context(
        a_context(component_ids=["cmp-001", "cmp-002"], data_flow_ids=["df-001"]), objects
    )

    (observation,) = [
        entry for entry in outcome.cross_claim_observations if entry.kind == "exposure_conflict"
    ]
    assert observation.object_ids == ("df-001", "cmp-002")
    # Warn-only, structurally, like the zone check.
    assert outcome.ready_for_review
    assert not outcome.retry_instructions()


def test_a_tls_protocol_stating_no_encryption_is_a_transport_conflict() -> None:
    objects = [
        component("cmp-001", "Webhook Receiver", None),
        component("cmp-002", "Managed Database", None),
        _flow_stating("df-001", protocol="HTTPS", encryption_in_transit="none"),
    ]
    outcome = validate_context(
        a_context(component_ids=["cmp-001", "cmp-002"], data_flow_ids=["df-001"]), objects
    )
    (observation,) = [
        entry for entry in outcome.cross_claim_observations if entry.kind == "transport_conflict"
    ]
    assert "HTTPS" in observation.detail


def test_silence_is_never_a_side_of_a_conflict() -> None:
    """DEC-009 held by the checks themselves: an unstated value conflicts with nothing."""
    quiet = [
        component("cmp-001", "Webhook Receiver", None),
        component("cmp-002", "Managed Database", None),
        # No exposure statement on the destination; unknown transport on the flow.
        _flow_stating("df-001", internet_exposed=True, protocol="https"),
    ]
    outcome = validate_context(
        a_context(component_ids=["cmp-001", "cmp-002"], data_flow_ids=["df-001"]), quiet
    )
    assert outcome.cross_claim_observations == ()


def test_two_asserting_claims_on_one_fact_with_different_values_conflict() -> None:
    objects = [
        component("cmp-001", "Webhook Receiver", None),
        _claim("ctx-001", "operation_authentication", "bearer"),
        _claim("ctx-002", "operation_authentication", "none"),
    ]
    outcome = validate_context(
        a_context(component_ids=["cmp-001"], context_claim_ids=["ctx-001", "ctx-002"]), objects
    )
    (observation,) = [
        entry for entry in outcome.cross_claim_observations if entry.kind == "claim_conflict"
    ]
    assert observation.object_ids == ("ctx-001", "ctx-002")


def test_an_assumed_claim_never_conflicts_and_agreement_never_conflicts() -> None:
    assumed_side = [
        component("cmp-001", "Webhook Receiver", None),
        _claim("ctx-001", "operation_authentication", "bearer"),
        _claim("ctx-002", "operation_authentication", "none", status="assumed"),
    ]
    agreeing = [
        component("cmp-001", "Webhook Receiver", None),
        _claim("ctx-001", "operation_authentication", "bearer"),
        _claim("ctx-002", "Operation Authentication", "bearer"),
    ]
    for objects in (assumed_side, agreeing):
        outcome = validate_context(a_context(component_ids=["cmp-001"]), objects)
        assert not [
            entry for entry in outcome.cross_claim_observations if entry.kind == "claim_conflict"
        ]


def test_a_declared_crossing_or_a_silent_zone_is_no_mismatch() -> None:
    declared = [
        component("cmp-001", "Webhook Receiver", "public"),
        component("cmp-002", "Managed Database", "private"),
        flow("df-001", "cmp-001", "cmp-002", crossings=["tb-001"]),
    ]
    silent = [
        component("cmp-001", "Webhook Receiver", "public"),
        component("cmp-002", "Managed Database", None),
        flow("df-001", "cmp-001", "cmp-002", crossings=[]),
    ]
    matching_case = [
        component("cmp-001", "Webhook Receiver", "Public"),
        component("cmp-002", "Managed Database", "public"),
        flow("df-001", "cmp-001", "cmp-002", crossings=[]),
    ]
    shared = a_context(component_ids=["cmp-001", "cmp-002"], data_flow_ids=["df-001"])
    for objects in (declared, silent, matching_case):
        assert validate_context(shared, objects).zone_mismatches == ()


# ------------------------------------------------------------------------------------------
# The privilege-extremes check (DEC-068)
# ------------------------------------------------------------------------------------------


def actor(actor_id: str, actor_type: str, access_level: str | None = None) -> Any:
    from trace_ai.domain.actor import Actor

    return Actor.model_validate(
        {
            "id": actor_id,
            "assessment_id": "asm-001",
            "name": actor_id,
            "actor_type": actor_type,
            "access_level": access_level,
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
        }
    )


def test_both_extremes_missing_yields_both() -> None:
    outcome = validate_context(a_context(actor_ids=["act-001"]), [actor("act-001", "developer")])
    assert [extreme.extreme for extreme in outcome.privilege_extremes] == [
        "anonymous_or_external",
        "administrative_or_privileged",
    ]
    assert outcome.ready_for_review


def test_represented_extremes_yield_nothing() -> None:
    objects = [
        actor("act-001", "external_attacker"),
        actor("act-002", "administrator"),
    ]
    outcome = validate_context(a_context(actor_ids=["act-001", "act-002"]), objects)
    assert outcome.privilege_extremes == ()


def test_a_persona_satisfies_an_extreme_its_type_does_not() -> None:
    """An anonymous end user is the anonymous extreme; a privileged service identity the other."""
    objects = [
        actor("act-001", "end_user", access_level="anonymous"),
        actor("act-002", "service_identity", access_level="privileged"),
    ]
    outcome = validate_context(a_context(actor_ids=["act-001", "act-002"]), objects)
    assert outcome.privilege_extremes == ()


# ------------------------------------------------------------------------------------------
# Unfamiliar terms cover the new vocabularies (DEC-036)
# ------------------------------------------------------------------------------------------


def test_unfamiliar_new_vocabulary_terms_are_reported_never_rejected() -> None:
    unusual = Component.model_validate(
        {
            "id": "cmp-001",
            "assessment_id": "asm-001",
            "name": "Kiosk",
            "component_type": "service",
            "entry_point_types": ["nfc_tap"],
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "status": ObjectStatus.CANDIDATE,
        }
    )
    outcome = validate_context(a_context(component_ids=["cmp-001"]), [unusual])
    assert "entry_point_types=nfc_tap" in outcome.unfamiliar_terms
    assert outcome.ready_for_review
