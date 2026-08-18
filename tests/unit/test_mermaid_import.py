"""The Mermaid DFD import (#599): the export dialect read back, the family rules held.

The load-bearing assertions: imported objects enter as proposals with `structured_input`
provenance and candidate status, never as authority; the three arrow forms carry their stated
directions and nothing else — the dialect has no protocols, no authentication, no encryption, so
everything unstated stays absent or `unknown`, never a stated negative; actor nodes and their
edges seed nothing; lines outside the export subset yield nothing; a Trace export re-ingests —
the round trip the DEC-120 precedent makes the family's measurement; and a diagram that
disagrees with prose surfaces as a `claim_conflict` observation, never as an override.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.system_context import SystemContext
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.context.mermaid import parse_mermaid
from trace_ai.services.context.parsers import seed_structured_documents
from trace_ai.services.export import export_mermaid
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.workflow.context_validation import validate_context

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

DIAGRAM = """flowchart LR
    subgraph tb-prod["Production"]
        gateway["API Gateway"]
        worker["Analysis #quot;Worker#quot;"]
    end
    queue["Managed Queue"]
    users(["End users"])
    gateway -->|"Forwards jobs"| queue
    queue <-->|"Job status"| worker
    worker -.-|"Diagnostics"| gateway
    users -->|"Submits requests"| gateway
    classDef styled fill:#f9f
    gateway --> queue
"""


def prepared(tmp_path: Path, filename: str, text: str) -> AssessmentHandle:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / filename
    source.write_text(text, encoding="utf-8")
    store = AssessmentStore.at_root(tmp_path / "data")
    service = AssessmentService(store, artifact_root=tmp_path / "data")
    created = service.create(
        "Imported", default_configuration("offline-fake", "stride-scenario-based")
    )
    handle = service.handle(created.id)
    DocumentLoader(handle).load_document(
        source, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
    )
    return handle


def test_a_file_that_is_not_a_flowchart_is_refused() -> None:
    with pytest.raises(ValueError, match="flowchart"):
        parse_mermaid("sequenceDiagram\n    A->>B: hello\n")


def test_seeding_enters_the_proposal_path_as_candidates(tmp_path: Path) -> None:
    """Provenance is `structured_input`, status is `candidate`, labels unescape, and the
    excerpt quotes the node's own line with a hash."""
    handle = prepared(tmp_path, "architecture-abc123.mmd", DIAGRAM)
    seeded = seed_structured_documents(handle)
    assert seeded is not None

    by_name = {component.name: component for component in seeded.components}
    assert set(by_name) == {"API Gateway", 'Analysis "Worker"', "Managed Queue"}
    gateway = by_name["API Gateway"]
    assert gateway.status is ObjectStatus.CANDIDATE
    assert gateway.source_origin is SourceOrigin.STRUCTURED_INPUT

    (cited,) = gateway.evidence_ids
    reference = handle.objects.get(EvidenceReference, cited)
    assert 'gateway["API Gateway"]' in reference.quoted_text


def test_the_three_arrow_forms_carry_their_stated_directions(tmp_path: Path) -> None:
    """The dotted, undirected form imports as direction `unknown` — the claim the diagram
    makes — and nothing carries encryption, authentication, or a protocol."""
    handle = prepared(tmp_path, "flows.mmd", DIAGRAM)
    seed_structured_documents(handle)

    flows = {flow.name: flow for flow in handle.objects.list(DataFlow)}
    assert set(flows) == {"Forwards jobs", "Job status", "Diagnostics"}
    assert str(flows["Forwards jobs"].direction) == "one_way"
    assert str(flows["Job status"].direction) == "bidirectional"
    assert str(flows["Diagnostics"].direction) == "unknown"
    for flow in flows.values():
        assert str(flow.encryption_in_transit) == "unknown"
        assert str(flow.authentication) == "unknown"
        assert flow.protocol is None


def test_actor_nodes_and_lines_outside_the_subset_seed_nothing(tmp_path: Path) -> None:
    """A stadium node is recognized and deliberately not seeded; its edge, a styling line, and
    an unlabelled edge all yield nothing."""
    handle = prepared(tmp_path, "actors.mmd", DIAGRAM)
    seed_structured_documents(handle)

    names = {component.name for component in handle.objects.list(Component)}
    assert "End users" not in names
    flow_names = {flow.name for flow in handle.objects.list(DataFlow)}
    assert "Submits requests" not in flow_names
    assert len(flow_names) == 3, "the unlabelled duplicate edge is outside the subset"


def test_a_subgraph_becomes_a_documented_membership_claim(tmp_path: Path) -> None:
    handle = prepared(tmp_path, "boundary.mmd", DIAGRAM)
    seed_structured_documents(handle)

    claim = next(
        claim
        for claim in handle.objects.list(ContextClaim)
        if claim.predicate == "trust boundary members: Production"
    )
    assert claim.status is ClaimStatus.DOCUMENTED
    assert claim.value == 'API Gateway, Analysis "Worker"'
    (cited,) = claim.evidence_ids
    reference = handle.objects.get(EvidenceReference, cited)
    assert reference.quoted_text.startswith("    subgraph")


def test_a_diagram_that_contradicts_prose_yields_an_observation_not_an_override(
    tmp_path: Path,
) -> None:
    """The #526 machinery carries the disagreement: two asserted statements about one boundary's
    membership disagree, an observation names both, and neither claim is altered."""
    handle = prepared(tmp_path, "conflict.mmd", DIAGRAM)
    seed_structured_documents(handle)
    diagram_claim = next(
        claim
        for claim in handle.objects.list(ContextClaim)
        if claim.predicate.startswith("trust boundary members")
    )

    prose_claim = ContextClaim.model_validate(
        {
            "id": "ctx-900",
            "assessment_id": handle.assessment_id,
            "subject_type": "system",
            "subject_id": None,
            "predicate": "Trust Boundary Members: Production",
            "value": "API Gateway",
            "status": "documented",
            "confidence": "medium",
            "evidence_ids": [diagram_claim.evidence_ids[0]],
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "created_at": now(),
            "updated_at": now(),
        }
    )
    context = SystemContext.model_validate(
        {
            "assessment_id": handle.assessment_id,
            "system_name": "Imported",
            "context_claim_ids": [diagram_claim.id, prose_claim.id],
            "component_ids": [],
            "asset_ids": [],
            "actor_ids": [],
            "data_flow_ids": [],
            "trust_boundary_ids": [],
            "version": 1,
        }
    )
    outcome = validate_context(context, [diagram_claim, prose_claim])
    (observation,) = [
        entry for entry in outcome.cross_claim_observations if entry.kind == "claim_conflict"
    ]
    assert set(observation.object_ids) == {diagram_claim.id, "ctx-900"}


def test_a_trace_export_round_trips(tmp_path: Path) -> None:
    """Export an approved context, re-ingest the export, and the architecture re-enters as
    candidates: names, direction, and boundary membership — everything the dialect carries."""
    stamped = now()
    store = AssessmentStore.at_root(tmp_path / "first")
    service = AssessmentService(store, artifact_root=tmp_path / "first")
    created = service.create(
        "Original", default_configuration("offline-fake", "stride-scenario-based")
    )
    handle = service.handle(created.id)

    def save(obj: Any) -> None:
        with handle.objects.transaction():
            handle.objects.save(obj)

    for cid, name in (("cmp-001", "Webhook Receiver"), ("cmp-002", "Analysis Worker")):
        save(
            Component.model_validate(
                {
                    "id": cid,
                    "assessment_id": handle.assessment_id,
                    "name": name,
                    "component_type": "service",
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "status": ObjectStatus.APPROVED,
                }
            )
        )
    save(
        DataFlow.model_validate(
            {
                "id": "df-001",
                "assessment_id": handle.assessment_id,
                "name": "Events to worker",
                "source_component_id": "cmp-001",
                "destination_component_id": "cmp-002",
                "direction": "one_way",
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
    )
    save(
        TrustBoundary.model_validate(
            {
                "id": "tb-001",
                "assessment_id": handle.assessment_id,
                "name": "Production",
                "boundary_type": "network",
                "inside_component_ids": ["cmp-001", "cmp-002"],
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
    )
    save(
        SystemContext.model_validate(
            {
                "assessment_id": handle.assessment_id,
                "system_name": "Original",
                "context_claim_ids": [],
                "component_ids": ["cmp-001", "cmp-002"],
                "asset_ids": [],
                "actor_ids": [],
                "data_flow_ids": ["df-001"],
                "trust_boundary_ids": ["tb-001"],
                "approved_at": stamped,
                "approved_by": "reviewer-local",
                "version": 1,
            }
        )
    )

    exported = export_mermaid(handle)
    second = prepared(tmp_path / "again", "architecture-roundtrip.mmd", exported)
    seeded = seed_structured_documents(second)
    assert seeded is not None

    names = {component.name for component in seeded.components}
    assert names == {"Webhook Receiver", "Analysis Worker"}
    (flow,) = second.objects.list(DataFlow)
    assert str(flow.direction) == "one_way"
    assert flow.status is ObjectStatus.CANDIDATE
    membership = next(
        claim
        for claim in second.objects.list(ContextClaim)
        if claim.predicate == "trust boundary members: Production"
    )
    assert membership.value == "Analysis Worker, Webhook Receiver"
