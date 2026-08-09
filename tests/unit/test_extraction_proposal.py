"""Tests for the context-extraction proposal schema and its conversion to domain objects.

`agent-design.md` section 22 states the write model: agents return proposed structured objects and
do not write authoritative records. This file is where that stops being a rule someone remembers and
becomes a property of a schema — so most of these tests assert what the schema **cannot** express.

Four prohibitions come straight from section 7's list, and each has its own test rather than being
folded into one: they fail for the same reason today (`extra="forbid"`) and would stop doing so
independently if a field were ever added.

The conversion tests are about the other half of the boundary. Identifiers are allocated by the
application (DEC-018), local keys are resolved to them, and an unresolved key stops the conversion
by name — before any identifier is allocated, because a monotonic counter leaves gaps that read as
deleted objects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain.context_claim import ClaimStatus
from trace_ai.domain.data_flow import FlowDirection
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus
from trace_ai.domain.identifiers import InMemoryAllocator, parse_id
from trace_ai.domain.proposals import (
    CONTEXT_EXTRACTION_AGENT,
    ContextExtractionProposal,
    GenerationMetadata,
    ProposalError,
    ProposedComponent,
    convert_proposal,
)
from trace_ai.domain.question import QuestionStatus
from trace_ai.domain.source_observation import ObservationKind

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
EVIDENCE = {"evd-001", "evd-002", "evd-003"}


def proposal(**changes: Any) -> ContextExtractionProposal:
    payload: dict[str, Any] = {
        "system": {"system_name": "ForgeFlow", "deployment_model": "SaaS"},
        "components": [
            {"key": "webhook", "name": "Webhook Receiver", "component_type": "service"},
            {"key": "worker", "name": "Analysis Worker", "component_type": "service"},
        ],
        "actors": [{"key": "developer", "name": "Developer", "actor_type": "developer"}],
        "assets": [
            {
                "key": "source-code",
                "name": "Customer Source Code",
                "asset_type": "source_code",
                "component_keys": ["worker"],
            }
        ],
        "trust_boundaries": [
            {
                "key": "github-boundary",
                "name": "GitHub Boundary",
                "boundary_type": "organization_to_third_party",
            }
        ],
        "data_flows": [
            {
                "key": "webhook-delivery",
                "name": "Webhook delivery",
                "source_component_key": "webhook",
                "destination_component_key": "worker",
                "direction": FlowDirection.ONE_WAY,
                "crosses_trust_boundary_keys": ["github-boundary"],
                "evidence_ids": ["evd-001"],
            }
        ],
        "claims": [
            {
                "key": "auth-provider",
                "subject_type": "system",
                "predicate": "authentication_provider",
                "value": "GitHub OAuth",
                "status": ClaimStatus.DOCUMENTED,
                "confidence": ConfidenceLevel.HIGH,
                "evidence_ids": ["evd-001"],
            }
        ],
        "questions": [
            {
                "key": "hmac",
                "question": "Does webhook validation include HMAC signature verification?",
                "rationale": "Without it the receiver accepts forged deliveries.",
                "priority": "high",
                "blocking": False,
            }
        ],
        "observations": [],
        **changes,
    }
    return ContextExtractionProposal.model_validate(payload)


# ------------------------------------------------------------------------------------------
# Coverage of section 7's outputs
# ------------------------------------------------------------------------------------------


def test_the_schema_covers_every_output_section_7_lists() -> None:
    """SystemContext, claims, components, actors, assets, data flows, trust boundaries, questions,
    and `SourceObservation` records (DEC-021)."""
    assert set(ContextExtractionProposal.model_fields) == {
        "system",
        "claims",
        "components",
        "actors",
        "assets",
        "data_flows",
        "trust_boundaries",
        "questions",
        "observations",
    }


def test_a_full_proposal_validates() -> None:
    built = proposal()
    assert built.system.system_name == "ForgeFlow"
    assert len(built.components) == 2


# ------------------------------------------------------------------------------------------
# What the schema cannot express
# ------------------------------------------------------------------------------------------


def test_no_proposed_object_carries_an_identifier() -> None:
    """DEC-018 allocates at insert from a store-held counter. An agent-chosen `cmp-001` would be a
    number the store may already have used, and the collision is invisible until it happens."""
    for model in (ProposedComponent,):
        assert "id" not in model.model_fields
        assert "key" in model.model_fields

    with pytest.raises(ValidationError, match="id"):
        ProposedComponent.model_validate(
            {"key": "webhook", "id": "cmp-001", "name": "W", "component_type": "service"}
        )


@pytest.mark.parametrize("identifier", ["cmp-001", "ast-014", "req-AUTH-001", "evd-1000"])
def test_a_local_key_that_looks_like_an_identifier_is_refused(identifier: str) -> None:
    """Refusing the *shape* matters as much as refusing the field: a key of `cmp-001` would read as
    an allocated identifier everywhere it appeared."""
    with pytest.raises(ValidationError, match="local key"):
        ProposedComponent.model_validate(
            {"key": identifier, "name": "W", "component_type": "service"}
        )


def test_a_proposal_carrying_a_severity_is_refused() -> None:
    """`agent-design.md` section 7, Prohibited operations: "Assign vulnerability severity". DEC-030
    gives severity to the reviewer at checkpoint 2, and no node proposes one."""
    with pytest.raises(ValidationError):
        proposal(
            assets=[{"key": "a", "name": "A", "asset_type": "customer_data", "severity": "high"}]
        )


def test_a_proposal_carrying_a_finding_is_refused() -> None:
    """Section 7: "Generate final findings". A finding is a downstream object with its own
    checkpoint, and an extractor that could propose one would be skipping both."""
    with pytest.raises(ValidationError):
        proposal(findings=[{"key": "f", "title": "Unvalidated webhook"}])


@pytest.mark.parametrize("field", ["approved_at", "approved_by"])
def test_a_proposal_carrying_an_approval_field_is_refused(field: str) -> None:
    """Approval is the reviewer's (DEC-005). An agent that could set it would approve its own
    work, which is what two structural checkpoints exist to prevent."""
    with pytest.raises(ValidationError):
        proposal(system={"system_name": "ForgeFlow", field: "2026-08-09T12:00:00Z"})


def test_a_proposal_carrying_a_status_is_refused() -> None:
    """Status is set at conversion: everything arrives `candidate`, because the objects exist and
    nobody has approved them."""
    with pytest.raises(ValidationError):
        proposal(
            components=[
                {"key": "w", "name": "W", "component_type": "service", "status": "approved"}
            ]
        )


@pytest.mark.parametrize("field", ["tool", "tools", "prompt", "model_profile", "configuration"])
def test_a_proposal_naming_a_tool_prompt_or_configuration_is_refused(field: str) -> None:
    """`agent-design.md` section 22: agents do not select tools, and section 2.7 forbids them
    modifying system configuration. A response that could name one is a response that could try."""
    with pytest.raises(ValidationError):
        proposal(**{field: "anything"})


# ------------------------------------------------------------------------------------------
# Evidence discipline
# ------------------------------------------------------------------------------------------


def test_a_documented_claim_without_evidence_is_refused() -> None:
    with pytest.raises(ValidationError, match="must cite evidence"):
        proposal(
            claims=[
                {
                    "key": "c",
                    "subject_type": "system",
                    "predicate": "p",
                    "value": "v",
                    "status": ClaimStatus.DOCUMENTED,
                    "confidence": ConfidenceLevel.HIGH,
                    "evidence_ids": [],
                }
            ]
        )


@pytest.mark.parametrize("status", [ClaimStatus.ASSUMED, ClaimStatus.UNKNOWN])
def test_a_claim_about_a_silence_needs_no_evidence(status: ClaimStatus) -> None:
    """DEC-009. Requiring evidence here would leave an extractor choosing between dropping a claim
    and mislabelling it, and mislabelling is how missing documentation becomes a vulnerability."""
    built = proposal(
        claims=[
            {
                "key": "c",
                "subject_type": "system",
                "predicate": "database_encryption",
                "value": None,
                "status": status,
                "confidence": ConfidenceLevel.LOW,
                "rationale": "The documentation does not state whether the database is encrypted.",
                "evidence_ids": [],
            }
        ]
    )
    assert built.claims[0].evidence_ids == []


def test_a_proposal_citing_evidence_that_was_not_supplied_is_rejected() -> None:
    """`agent-design.md` section 14 lists nonexistent evidence references among the failure
    conditions. An unresolvable citation reads exactly like one that checks out."""
    built = proposal(
        components=[
            {
                "key": "webhook",
                "name": "Webhook Receiver",
                "component_type": "service",
                "evidence_ids": ["evd-999"],
            },
            {"key": "worker", "name": "Analysis Worker", "component_type": "service"},
        ]
    )
    with pytest.raises(ProposalError, match="evd-999"):
        built.validate_against_evidence(EVIDENCE)


def test_a_proposal_citing_only_supplied_evidence_passes() -> None:
    proposal().validate_against_evidence(EVIDENCE)


def test_an_injection_attempt_is_an_observation_carrying_its_passage() -> None:
    """DEC-021: one object with a `kind`, not a claim and not a security event of its own."""
    built = proposal(
        observations=[
            {
                "key": "override-block",
                "kind": ObservationKind.INJECTION_ATTEMPT,
                "summary": "A block instructs its reader to ignore prior instructions.",
                "evidence_ids": ["evd-003"],
            }
        ]
    )
    assert built.observations[0].kind is ObservationKind.INJECTION_ATTEMPT
    assert "severity" not in built.observations[0].model_dump()


def test_a_contradiction_needs_two_passages() -> None:
    with pytest.raises(ValidationError, match="at least 2"):
        proposal(
            observations=[
                {
                    "key": "retention",
                    "kind": ObservationKind.CONTRADICTION,
                    "summary": "Two documents disagree about retention.",
                    "evidence_ids": ["evd-001"],
                }
            ]
        )


# ------------------------------------------------------------------------------------------
# Local references
# ------------------------------------------------------------------------------------------


def test_two_objects_may_not_share_a_key() -> None:
    with pytest.raises(ValidationError, match="a key names"):
        proposal(
            actors=[{"key": "webhook", "name": "Developer", "actor_type": "developer"}],
        )


def test_a_flow_whose_source_key_is_not_a_proposed_component_fails_by_name() -> None:
    built = proposal(
        data_flows=[
            {
                "key": "delivery",
                "name": "Delivery",
                "source_component_key": "absent-service",
                "destination_component_key": "worker",
                "direction": FlowDirection.ONE_WAY,
            }
        ]
    )
    with pytest.raises(ProposalError, match="absent-service"):
        built.validate_references()


def test_a_flow_from_a_component_to_itself_is_refused() -> None:
    with pytest.raises(ValidationError, match="between two components"):
        proposal(
            data_flows=[
                {
                    "key": "loop",
                    "name": "Loop",
                    "source_component_key": "worker",
                    "destination_component_key": "worker",
                    "direction": FlowDirection.ONE_WAY,
                }
            ]
        )


# ------------------------------------------------------------------------------------------
# Conversion
# ------------------------------------------------------------------------------------------


def convert(built: ContextExtractionProposal) -> Any:
    return convert_proposal(
        built,
        allocator=InMemoryAllocator(),
        assessment_id="asm-001",
        created_at=NOW,
        generated_by=CONTEXT_EXTRACTION_AGENT,
    )


def test_conversion_allocates_identifiers_under_the_scheme() -> None:
    converted = convert(proposal())
    for component in converted.components:
        assert parse_id(component.id).prefix == "cmp"
    for flow in converted.data_flows:
        assert parse_id(flow.id).prefix == "df"
    assert parse_id(converted.actors[0].id).prefix == "act"
    assert parse_id(converted.assets[0].id).prefix == "ast"


def test_conversion_resolves_local_keys_to_allocated_identifiers() -> None:
    converted = convert(proposal())
    (flow,) = converted.data_flows
    assert flow.source_component_id == converted.identifiers["webhook"]
    assert flow.destination_component_id == converted.identifiers["worker"]
    assert flow.crosses_trust_boundary_ids == [converted.identifiers["github-boundary"]]


def test_everything_arrives_as_a_candidate() -> None:
    """An agent that could propose `approved` would be approving its own work."""
    converted = convert(proposal())
    for obj in [*converted.components, *converted.assets, *converted.data_flows]:
        assert obj.status is ObjectStatus.CANDIDATE
    assert converted.questions[0].status is QuestionStatus.OPEN


def test_conversion_stops_before_allocating_anything_when_a_key_is_unresolved() -> None:
    """A monotonic counter leaves gaps that read as deleted objects, so a half-converted proposal
    is worse than a refused one."""
    allocator = InMemoryAllocator()
    built = proposal(
        assets=[
            {
                "key": "source-code",
                "name": "Customer Source Code",
                "asset_type": "source_code",
                "component_keys": ["absent"],
            }
        ]
    )
    with pytest.raises(ProposalError, match="absent"):
        convert_proposal(
            built,
            allocator=allocator,
            assessment_id="asm-001",
            created_at=NOW,
            generated_by=CONTEXT_EXTRACTION_AGENT,
        )
    assert allocator.issued("cmp") == 0


def test_conversion_stamps_the_agent_version_on_generated_objects() -> None:
    converted = convert(proposal())
    assert converted.claims[0].generated_by == CONTEXT_EXTRACTION_AGENT
    assert converted.questions[0].generated_by == CONTEXT_EXTRACTION_AGENT


# ------------------------------------------------------------------------------------------
# Generation metadata and the exported schema
# ------------------------------------------------------------------------------------------


def test_generation_metadata_matches_section_34_field_for_field() -> None:
    assert set(GenerationMetadata.model_fields) == {
        "generated_by",
        "workflow_run_id",
        "execution_record_id",
        "model_name",
        "prompt_version",
        "generated_at",
    }


def test_the_agent_version_is_the_one_section_33_names() -> None:
    """Agent version and model are different things: the same agent can run against a different
    model, and an evaluation comparing two runs needs to tell which changed."""
    assert CONTEXT_EXTRACTION_AGENT == "context-extraction-v1"
    metadata = GenerationMetadata(
        generated_by=CONTEXT_EXTRACTION_AGENT,
        workflow_run_id="run-001",
        execution_record_id="exe-014",
        model_name="claude-opus-5",
        prompt_version="extract-context-v1",
        generated_at=NOW,
    )
    assert metadata.generated_by != metadata.model_name


def test_the_json_schema_is_exportable_and_stable() -> None:
    """The prompt embeds this schema rather than restating it, so the two cannot drift — which only
    works if the export does not move between runs."""
    first = ContextExtractionProposal.model_json_schema()
    second = ContextExtractionProposal.model_json_schema()
    assert first == second
    assert "properties" in first
    assert set(first["properties"]) == set(ContextExtractionProposal.model_fields)


def test_the_exported_schema_offers_no_identifier_field() -> None:
    """The prompt is built from this. A schema advertising `id` would invite the agent to fill it."""
    schema = ContextExtractionProposal.model_json_schema()
    component = schema["$defs"]["ProposedComponent"]["properties"]
    assert "id" not in component
    assert "key" in component
