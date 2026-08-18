"""The Mermaid DFD export (#503): DEC-072's third serializer, family rules held.

The load-bearing assertions: approved objects only; byte-determinism (two exports of the same
approved state are identical, which is what makes the artifact content-addressable); labels are
escaped so an approved name cannot become diagram syntax; an unknown flow direction renders
undirected rather than drawing a claim nobody made; and an unapproved context is refused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from trace_ai.domain.actor import Actor
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.system_context import SystemContext
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.export import ExportError, export_mermaid, write_mermaid

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

REVIEWER = "mermaid-test-reviewer"


def save(handle: AssessmentHandle, obj: Any) -> Any:
    with handle.objects.transaction():
        handle.objects.save(obj)
    return obj


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        stamped = now()

        def component(cid: str, name: str, status: ObjectStatus) -> None:
            save(
                handle,
                Component.model_validate(
                    {
                        "id": cid,
                        "assessment_id": handle.assessment_id,
                        "name": name,
                        "component_type": "service",
                        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                        "status": status,
                    }
                ),
            )

        component("cmp-001", 'Webhook "Receiver"', ObjectStatus.APPROVED)
        component("cmp-002", "Analysis Worker", ObjectStatus.APPROVED)
        component("cmp-003", "Rejected Candidate", ObjectStatus.CANDIDATE)
        save(
            handle,
            Actor.model_validate(
                {
                    "id": "act-001",
                    "assessment_id": handle.assessment_id,
                    "name": "Payment provider",
                    "actor_type": "external_service",
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                }
            ),
        )
        save(
            handle,
            DataFlow.model_validate(
                {
                    "id": "df-001",
                    "assessment_id": handle.assessment_id,
                    "name": "Webhook events",
                    "source_component_id": "cmp-001",
                    "destination_component_id": "cmp-002",
                    "direction": "one_way",
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "status": ObjectStatus.APPROVED,
                }
            ),
        )
        save(
            handle,
            DataFlow.model_validate(
                {
                    "id": "df-002",
                    "assessment_id": handle.assessment_id,
                    "name": "Sync of unknown direction",
                    "source_component_id": "cmp-002",
                    "destination_component_id": "cmp-001",
                    "direction": "unknown",
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "status": ObjectStatus.APPROVED,
                }
            ),
        )
        save(
            handle,
            TrustBoundary.model_validate(
                {
                    "id": "tb-001",
                    "assessment_id": handle.assessment_id,
                    "name": "Internet boundary",
                    "boundary_type": "internet_to_application",
                    "inside_component_ids": ["cmp-001"],
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "status": ObjectStatus.APPROVED,
                }
            ),
        )
        save(
            handle,
            SystemContext.model_validate(
                {
                    "assessment_id": handle.assessment_id,
                    "system_name": "ForgeFlow",
                    "system_purpose": "AI-assisted review",
                    "context_claim_ids": [],
                    "component_ids": ["cmp-001", "cmp-002", "cmp-003"],
                    "asset_ids": [],
                    "actor_ids": ["act-001"],
                    "data_flow_ids": ["df-001", "df-002"],
                    "trust_boundary_ids": ["tb-001"],
                    "approved_at": stamped,
                    "approved_by": REVIEWER,
                    "version": 1,
                }
            ),
        )
        yield handle


def test_the_diagram_holds_approved_objects_only(handle: AssessmentHandle) -> None:
    source = export_mermaid(handle)
    assert source.startswith("flowchart LR\n")
    assert "cmp-001" in source and "cmp-002" in source
    assert "Rejected Candidate" not in source, "candidates leave no trace (DEC-072)"
    assert '(["Payment provider"])' in source
    assert 'subgraph tb-001["Internet boundary"]' in source


def test_labels_are_escaped_not_trusted(handle: AssessmentHandle) -> None:
    source = export_mermaid(handle)
    assert "Webhook #quot;Receiver#quot;" in source
    assert '"Webhook "Receiver""' not in source


def test_an_unknown_direction_renders_undirected(handle: AssessmentHandle) -> None:
    source = export_mermaid(handle)
    assert 'cmp-001 -->|"Webhook events"| cmp-002' in source
    assert 'cmp-002 -.-|"Sync of unknown direction"| cmp-001' in source


def test_the_export_is_byte_deterministic(handle: AssessmentHandle) -> None:
    assert export_mermaid(handle) == export_mermaid(handle)


def test_an_unapproved_context_is_refused(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Unapproved", default_configuration("offline-fake", "stride-scenario-based")
        )
        with pytest.raises(ExportError, match="context"):
            export_mermaid(service.handle(created.id))


def test_the_export_writes_to_the_outputs_area(handle: AssessmentHandle) -> None:
    written = write_mermaid(handle)
    assert written.name.startswith("architecture-")
    assert written.name.endswith(".mmd")
    assert written.is_file()
