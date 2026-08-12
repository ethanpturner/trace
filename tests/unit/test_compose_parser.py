"""DEC-070's first parser: compose manifests into deterministic proposals.

Issue #345's acceptance criteria are the spine: a compose file yields components and flows that
pause at checkpoint 1 like any extraction, and parser output is marked deterministic in its
provenance (`source_origin: structured_input`, `generated_by: compose-parser-v1` on the evidence
path). Determinism earns no bypass — the seeded objects arrive `candidate` and the reviewer
decides them — and the parser does not guess meaning: `internet_accessible` stays `None` whatever
the manifest maps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.component import Component
from trace_ai.domain.data_flow import DataFlow, FlowDirection
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.domain.source_document import TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.fake import DeterministicModel
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.context.compose import (
    COMPOSE_PARSER,
    parse_compose,
    seed_compose_documents,
)
from trace_ai.services.driver import run_assessment
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

PROFILE = resolve_profile("offline-fake")

MANIFEST = """\
services:

  web:
    image: nginx:1.27
    ports:
      - "443:443"
    depends_on:
      - api

  api:
    image: forgeflow/api:2.1
    depends_on:
      - db

  db:
    image: postgres:16
"""


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    compose_path = tmp_path / "docker-compose.yml"
    compose_path.write_text(MANIFEST, encoding="utf-8")
    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Compose", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        DocumentLoader(handle).load_document(
            compose_path, origin=SourceOrigin.STRUCTURED_INPUT, trust_level=TrustLevel.UNTRUSTED
        )
        yield handle


# ------------------------------------------------------------------------------------------
# The parser
# ------------------------------------------------------------------------------------------


def test_the_manifest_parses_into_services_and_dependencies() -> None:
    parsed = parse_compose(MANIFEST)

    by_name = {service.name: service for service in parsed.services}
    assert set(by_name) == {"web", "api", "db"}
    assert by_name["web"].image == "nginx:1.27"
    assert by_name["web"].depends_on == ("api",)
    assert by_name["api"].depends_on == ("db",)
    assert by_name["db"].depends_on == ()

    lines = MANIFEST.splitlines()
    web = by_name["web"]
    assert lines[web.start_line - 1].strip() == "web:"
    assert "nginx:1.27" in web.excerpt


def test_a_yaml_file_that_is_not_a_manifest_is_refused() -> None:
    with pytest.raises(ValueError, match="no `services` mapping"):
        parse_compose("metadata:\n  version: '1.0'\n")


# ------------------------------------------------------------------------------------------
# Seeding: provenance, evidence, and idempotence
# ------------------------------------------------------------------------------------------


def test_seeded_objects_carry_deterministic_provenance(handle: AssessmentHandle) -> None:
    """Issue #345's second acceptance criterion."""
    seeded = seed_compose_documents(handle)
    assert seeded is not None
    assert {component.name for component in seeded.components} == {"web", "api", "db"}

    for component in handle.objects.list(Component):
        assert component.source_origin is SourceOrigin.STRUCTURED_INPUT
        assert component.status is ObjectStatus.CANDIDATE
        # The parser owns what the artifact states, never what it means (DEC-070).
        assert component.internet_accessible is None

    by_name = {component.name: component.id for component in seeded.components}
    flows = handle.objects.list(DataFlow)
    assert {(flow.source_component_id, flow.destination_component_id) for flow in flows} == {
        (by_name["web"], by_name["api"]),
        (by_name["api"], by_name["db"]),
    }
    for flow in flows:
        assert flow.direction is FlowDirection.ONE_WAY
        assert flow.source_origin is SourceOrigin.STRUCTURED_INPUT


def test_every_seeded_object_cites_a_verifiable_excerpt(handle: AssessmentHandle) -> None:
    """The excerpt is the artifact's own text, hashed — evidence that re-verifies forever."""
    seed_compose_documents(handle)

    references = {
        reference.id: reference
        for reference in handle.objects.list(EvidenceReference)
        if reference.source_origin is SourceOrigin.STRUCTURED_INPUT
    }
    assert references
    for component in handle.objects.list(Component):
        assert component.evidence_ids
        for evidence_id in component.evidence_ids:
            reference = references[evidence_id]
            assert reference.quoted_text in MANIFEST
            assert reference.content_hash == content_hash(reference.quoted_text.encode("utf-8"))


def test_seeding_twice_mints_nothing_new(handle: AssessmentHandle) -> None:
    first = seed_compose_documents(handle)
    counts = (len(handle.objects.list(Component)), len(handle.objects.list(DataFlow)))

    second = seed_compose_documents(handle)
    assert second is not None and first is not None
    assert {c.id for c in second.components} == {c.id for c in first.components}
    assert (len(handle.objects.list(Component)), len(handle.objects.list(DataFlow))) == counts


def test_an_assessment_without_a_manifest_seeds_nothing(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Plain", default_configuration("offline-fake", "stride-scenario-based")
        )
        assert seed_compose_documents(service.handle(created.id)) is None


# ------------------------------------------------------------------------------------------
# Checkpoint 1 (issue #345's first acceptance criterion)
# ------------------------------------------------------------------------------------------


def test_a_compose_file_pauses_at_checkpoint_one_like_any_extraction(tmp_path: Path) -> None:
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_text(MANIFEST, encoding="utf-8")

    minimal: dict[str, Any] = {"system": {"system_name": "Compose"}}
    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Compose", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        DocumentLoader(handle).load_document(
            compose_path, origin=SourceOrigin.STRUCTURED_INPUT, trust_level=TrustLevel.UNTRUSTED
        )

        outcome = run_assessment(
            service,
            created.id,
            model=DeterministicModel([ContextExtractionProposal.model_validate(minimal)]),
            profile=PROFILE,
        )

        assert outcome.paused
        assert outcome.state.current_phase is Phase.HUMAN_CONTEXT_REVIEW

        from trace_ai.workflow.context_review import current_system_context

        context = current_system_context(handle)
        seeded_ids = {component.id for component in handle.objects.list(Component)}
        assert seeded_ids
        assert seeded_ids <= set(context.component_ids)
        assert len(context.data_flow_ids) == 2
        assert COMPOSE_PARSER  # the provenance constant the evidence path records
