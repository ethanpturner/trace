"""The TM-BOM import (#573, DEC-120): DEC-072's open question answered, the family rules held.

The load-bearing assertions: imported objects enter as proposals with `structured_input`
provenance and candidate status, never as authority; `encrypted: false` yields nothing, because
the schema's boolean cannot distinguish a stated negative from the exporter's conservative
default for silence (DEC-009); an `assumed` control imports as an `assumed` claim rather than an
existence assertion; `suggested` controls, threats, personas, and the `extensions` block import
as nothing at all; and a Trace export re-ingests — the round trip DEC-072 asked about — without
its approved findings laundering into documented claims.
"""

from __future__ import annotations

import json
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
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.context.parsers import seed_structured_documents
from trace_ai.services.context.tm_bom import parse_tm_bom
from trace_ai.services.export import export_tm_bom
from trace_ai.services.ingestion.loader import DocumentLoader

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

MODEL = json.dumps(
    {
        "version": "1",
        "scope": {"title": "Ticketing platform"},
        "components": [
            {
                "symbolic_name": "api",
                "title": "Ticket API",
                "description": "Serves the ticket UI.",
                "trust_zone": "internal",
            },
            {"symbolic_name": "db", "title": "Ticket Database", "trust_zone": "zone-unspecified"},
        ],
        "data_flows": [
            {
                "symbolic_name": "api-to-db",
                "title": "Queries",
                "source": {"type": "component", "object": "api"},
                "destination": {"type": "component", "object": "db"},
                "encrypted": True,
            },
            {
                "symbolic_name": "db-to-api",
                "title": "Results",
                "source": {"type": "component", "object": "db"},
                "destination": {"type": "component", "object": "api"},
                "encrypted": False,
            },
        ],
        "assumptions": [
            {"description": "Backups are encrypted at rest.", "validity": "unconfirmed"}
        ],
        "threats": [{"symbolic_name": "spoofing", "title": "Spoofed API calls", "event": "spoof"}],
        "controls": [
            {"symbolic_name": "waf", "title": "Web application firewall", "status": "active"},
            {"symbolic_name": "mfa", "title": "Administrator MFA", "status": "assumed"},
            {"symbolic_name": "rate", "title": "Rate limiting", "status": "suggested"},
        ],
        "extensions": {"trace-ai.local/findings": [{"title": "A finding that must not import"}]},
    },
    indent=2,
)


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


def test_a_document_without_a_scope_is_refused() -> None:
    with pytest.raises(ValueError, match="scope"):
        parse_tm_bom('{"components": []}')


def test_seeding_enters_the_proposal_path_as_candidates(tmp_path: Path) -> None:
    """Provenance is `structured_input`, status is `candidate`, and the exporter's marker zone
    for "none stated" does not become a stated deployment zone."""
    handle = prepared(tmp_path, "tm-bom-roundtrip-fixture.json", MODEL)
    seeded = seed_structured_documents(handle)
    assert seeded is not None

    by_name = {component.name: component for component in seeded.components}
    assert set(by_name) == {"Ticket API", "Ticket Database"}
    api = by_name["Ticket API"]
    assert api.status is ObjectStatus.CANDIDATE
    assert api.source_origin is SourceOrigin.STRUCTURED_INPUT
    assert api.deployment_zone == "internal"
    assert by_name["Ticket Database"].deployment_zone is None

    # The excerpt quotes the component's own lines and carries a hash.
    (cited,) = api.evidence_ids
    reference = handle.objects.get(EvidenceReference, cited)
    assert '"symbolic_name": "api"' in reference.quoted_text


def test_the_boolean_asymmetry_holds_for_flows(tmp_path: Path) -> None:
    """`encrypted: true` is a stated fact; `encrypted: false` is indistinguishable from the
    exporter's conservative default for silence, so it yields `unknown`, not a negative."""
    handle = prepared(tmp_path, "tm-bom-flows.json", MODEL)
    seed_structured_documents(handle)

    flows = {flow.name: flow for flow in handle.objects.list(DataFlow)}
    assert set(flows) == {"Queries", "Results"}
    assert str(flows["Queries"].encryption_in_transit) == "encrypted"
    assert str(flows["Results"].encryption_in_transit) == "unknown"


def test_control_statuses_map_to_honest_claim_statuses(tmp_path: Path) -> None:
    handle = prepared(tmp_path, "tm-bom-controls.json", MODEL)
    seed_structured_documents(handle)

    claims = {str(claim.value): claim for claim in handle.objects.list(ContextClaim)}
    active = claims["Web application firewall"]
    assert active.predicate == "declared_control_active"
    assert active.status is ClaimStatus.DOCUMENTED
    assert active.evidence_ids

    assumed = claims["Administrator MFA"]
    assert assumed.predicate == "declared_control_assumed"
    assert assumed.status is ClaimStatus.ASSUMED
    assert assumed.rationale is not None

    assert "Rate limiting" not in claims, "a suggestion asserts nothing"


def test_assumptions_import_as_assumed_and_conclusions_do_not_import(tmp_path: Path) -> None:
    handle = prepared(tmp_path, "tm-bom-assumptions.json", MODEL)
    seed_structured_documents(handle)

    assumption = next(
        claim
        for claim in handle.objects.list(ContextClaim)
        if claim.predicate == "Backups are encrypted at rest."
    )
    assert assumption.status is ClaimStatus.ASSUMED

    names = {component.name for component in handle.objects.list(Component)}
    assert "A finding that must not import" not in names
    predicates = " ".join(claim.predicate for claim in handle.objects.list(ContextClaim))
    assert "must not import" not in predicates, "the extensions block is ignored"
    assert "Spoofed API calls" not in names, "threats are conclusions, not context"


def test_a_trace_export_round_trips(tmp_path: Path) -> None:
    """DEC-072's question, answered by running it: export an approved context, re-ingest the
    export, and the context re-enters as candidates — with the approved findings riding the
    extensions block left behind."""
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

    for cid, name, zone in (
        ("cmp-001", "Webhook Receiver", "public"),
        ("cmp-002", "Analysis Worker", "private"),
    ):
        save(
            Component.model_validate(
                {
                    "id": cid,
                    "assessment_id": handle.assessment_id,
                    "name": name,
                    "component_type": "service",
                    "deployment_zone": zone,
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
                "encryption_in_transit": "tls",
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
                "trust_boundary_ids": [],
                "approved_at": stamped,
                "approved_by": "reviewer-local",
                "version": 1,
            }
        )
    )

    exported = json.dumps(export_tm_bom(handle), indent=2)
    second = prepared(tmp_path / "again", "tm-bom-reimport.json", exported)
    seeded = seed_structured_documents(second)
    assert seeded is not None

    names = {component.name for component in seeded.components}
    assert names == {"Webhook Receiver", "Analysis Worker"}
    (flow,) = second.objects.list(DataFlow)
    assert str(flow.encryption_in_transit) == "encrypted"
    assert flow.status is ObjectStatus.CANDIDATE
