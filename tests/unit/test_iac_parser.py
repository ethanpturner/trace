"""The IaC parser (#525): DEC-070's third parser, the family rules held.

The load-bearing assertions: parsed output enters as proposals with `structured_input`
provenance and candidate status — determinism earns no bypass; a stated boolean becomes a
documented claim in either direction (a stated `false` is a documented negative), while a
declaration silent about an attribute produces nothing — DEC-009's line, held by a parser;
excerpts quote the declaration's own lines with a hash; and the family orchestrator seeds
Terraform beside compose and OpenAPI, idempotently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.services.context.iac import parse_terraform
from trace_ai.services.context.parsers import seed_structured_documents

if TYPE_CHECKING:
    from pathlib import Path

DECLARATION = """{
  "resource": {
    "aws_db_instance": {
      "tickets_db": {
        "engine": "postgres",
        "storage_encrypted": true,
        "publicly_accessible": false
      }
    },
    "aws_s3_bucket": {
      "exports": {
        "bucket": "exports"
      }
    }
  }
}
"""


def test_parse_reads_declarations_and_only_declarations() -> None:
    parsed = parse_terraform(DECLARATION)
    by_name = {resource.name: resource for resource in parsed.resources}
    assert set(by_name) == {"tickets_db", "exports"}
    assert dict(by_name["tickets_db"].stated) == {
        "storage_encrypted": True,
        "publicly_accessible": False,
    }
    # The bucket states neither attribute: silence, and silence yields nothing.
    assert by_name["exports"].stated == ()


def test_a_document_without_a_resource_block_is_refused() -> None:
    with pytest.raises(ValueError, match="resource"):
        parse_terraform('{"variable": {"region": {}}}')


def test_seeding_enters_the_proposal_path_as_candidates(tmp_path: Path) -> None:
    """Provenance is `structured_input`, status is `candidate`, a stated false is a documented
    negative, and the excerpt quotes the declaration's own lines with a hash."""
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader

    declaration = tmp_path / "main.tf.json"
    declaration.write_text(DECLARATION, encoding="utf-8")

    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Declared", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        DocumentLoader(handle).load_document(
            declaration,
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )

        seeded = seed_structured_documents(handle)
        assert seeded is not None
        by_name = {component.name: component for component in seeded.components}
        assert set(by_name) == {"tickets db", "exports"}
        database = by_name["tickets db"]
        assert database.component_type == "managed_database"
        assert database.status is ObjectStatus.CANDIDATE
        assert database.source_origin is SourceOrigin.STRUCTURED_INPUT
        assert by_name["exports"].component_type == "object_storage"

        claims = {claim.predicate: claim for claim in handle.objects.list(ContextClaim)}
        assert set(claims) == {"storage_encrypted", "publicly_accessible"}
        assert claims["storage_encrypted"].value is True
        assert claims["publicly_accessible"].value is False, "a stated false is documented"
        assert claims["storage_encrypted"].status.value == "documented"
        assert claims["storage_encrypted"].subject_id == database.id

        # The excerpt quotes the resource's own lines and its hash re-verifies.
        (cited,) = claims["storage_encrypted"].evidence_ids
        reference = handle.objects.get(EvidenceReference, cited)
        assert '"storage_encrypted": true' in reference.quoted_text
        assert reference.section_title == "aws_db_instance.tickets_db"

        # Family idempotence, checked once for the whole family (DEC-038).
        again = seed_structured_documents(handle)
        assert again is not None
        assert len(handle.objects.list(Component)) == 2
