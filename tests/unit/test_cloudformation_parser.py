"""The CloudFormation parser (#593): the IaC family's shape, held for a new dialect.

The load-bearing assertions: only literal booleans at a resource's `Properties` top level are
read, in either direction — a stated `false` is a documented negative — and an intrinsic yields
nothing, because an expression is *not stated* (DEC-009's line, the DEC-113 posture); the same
stated fact makes the same family predicate whichever dialect declared it; parsed output enters
as proposals with `structured_input` provenance and candidate status; and the syntax boundary is
the loader's own — a short-form-tagged YAML template is refused at ingestion, and this parser
adds nothing to admit it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.source_document import MediaType
from trace_ai.services.context.cloudformation import parse_cloudformation
from trace_ai.services.context.parsers import seed_structured_documents

if TYPE_CHECKING:
    from pathlib import Path

JSON_TEMPLATE = """{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Resources": {
    "TicketsDb": {
      "Type": "AWS::RDS::DBInstance",
      "Properties": {
        "Engine": "postgres",
        "StorageEncrypted": true,
        "PubliclyAccessible": false,
        "DBName": {"Ref": "DatabaseName"}
      }
    },
    "Exports": {
      "Type": "AWS::S3::Bucket",
      "Properties": {
        "BucketName": "exports"
      }
    }
  }
}
"""

YAML_TEMPLATE = """\
AWSTemplateFormatVersion: "2010-09-09"
Resources:
  TicketsDb:
    Type: AWS::RDS::DBInstance
    Properties:
      Engine: postgres
      StorageEncrypted: true
      PubliclyAccessible: false
      DBName:
        Ref: DatabaseName
  Exports:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: exports
"""


def test_parse_reads_literal_booleans_under_the_family_predicates() -> None:
    parsed = parse_cloudformation(JSON_TEMPLATE, media_type=MediaType.JSON)
    by_id = {resource.logical_id: resource for resource in parsed.resources}
    assert set(by_id) == {"TicketsDb", "Exports"}
    assert dict(by_id["TicketsDb"].stated) == {
        "storage_encrypted": True,
        "publicly_accessible": False,
    }
    # The bucket states neither admitted property, and the `Ref` intrinsic on the database is
    # not a literal boolean: silence, and silence yields nothing.
    assert by_id["Exports"].stated == ()


def test_a_document_without_a_resources_block_is_refused() -> None:
    with pytest.raises(ValueError, match="Resources"):
        parse_cloudformation('{"Parameters": {"Env": {}}}', media_type=MediaType.JSON)


def test_tag_free_yaml_parses_to_the_same_template_as_its_json_twin() -> None:
    """Long-form intrinsics parse as mappings and yield nothing; the two spellings agree."""
    from_yaml = parse_cloudformation(YAML_TEMPLATE, media_type=MediaType.YAML)
    from_json = parse_cloudformation(JSON_TEMPLATE, media_type=MediaType.JSON)
    assert [
        (resource.logical_id, resource.resource_type, resource.stated)
        for resource in from_yaml.resources
    ] == [
        (resource.logical_id, resource.resource_type, resource.stated)
        for resource in from_json.resources
    ]


def test_a_short_form_tagged_template_is_refused_at_ingestion(tmp_path: Path) -> None:
    """`!Ref` fails `yaml.safe_load`, and the loader refuses YAML that does not safe-parse —
    the syntax boundary is the ingestion rule, and the parser adds no tag handling."""
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader, MalformedDocumentError

    template = tmp_path / "tagged.cfn.yaml"
    template.write_text(
        "Resources:\n  Db:\n    Type: AWS::RDS::DBInstance\n    Properties:\n"
        "      DBName: !Ref DatabaseName\n",
        encoding="utf-8",
    )

    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Tagged", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        with pytest.raises(MalformedDocumentError):
            DocumentLoader(handle).load_document(
                template,
                origin=SourceOrigin.UPLOADED_DOCUMENT,
                trust_level=TrustLevel.UNTRUSTED,
            )


def test_seeding_enters_the_proposal_path_as_candidates(tmp_path: Path) -> None:
    """Provenance is `structured_input`, status is `candidate`, a stated false is a documented
    negative, and the excerpt quotes the resource's own lines with a verifying hash."""
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.hashing import content_hash
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader

    template = tmp_path / "stack.cfn.json"
    template.write_text(JSON_TEMPLATE, encoding="utf-8")

    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Declared", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        DocumentLoader(handle).load_document(
            template,
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
        assert claims["storage_encrypted"].subject_id == database.id

        (cited,) = claims["storage_encrypted"].evidence_ids
        reference = handle.objects.get(EvidenceReference, cited)
        assert '"StorageEncrypted": true' in reference.quoted_text
        assert reference.section_title == "AWS::RDS::DBInstance.TicketsDb"
        assert reference.content_hash == content_hash(reference.quoted_text.encode("utf-8"))

        # Family idempotence, checked once for the whole family (DEC-038).
        again = seed_structured_documents(handle)
        assert again is not None
        assert len(handle.objects.list(Component)) == 2


def test_yaml_seeding_quotes_the_resources_own_lines(tmp_path: Path) -> None:
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader

    template = tmp_path / "stack.cfn.yaml"
    template.write_text(YAML_TEMPLATE, encoding="utf-8")

    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Declared", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        DocumentLoader(handle).load_document(
            template,
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )

        seeded = seed_structured_documents(handle)
        assert seeded is not None

        claims = {claim.predicate: claim for claim in handle.objects.list(ContextClaim)}
        (cited,) = claims["storage_encrypted"].evidence_ids
        reference = handle.objects.get(EvidenceReference, cited)
        assert "StorageEncrypted: true" in reference.quoted_text
        assert reference.quoted_text.splitlines()[0].strip() == "TicketsDb:"
        assert "Exports" not in reference.quoted_text


def test_a_closed_vocabulary_string_property_reads_verbatim() -> None:
    """The widened admission rule, in CloudFormation's spelling: a stated `SslPolicy` is read
    verbatim at `Properties`' top level; an intrinsic is a mapping and yields nothing."""
    parsed = parse_cloudformation(
        """{
  "Resources": {
    "Listener": {
      "Type": "AWS::ElasticLoadBalancingV2::Listener",
      "Properties": {
        "SslPolicy": "ELBSecurityPolicy-TLS13-1-2-2021-06"
      }
    },
    "Templated": {
      "Type": "AWS::ElasticLoadBalancingV2::Listener",
      "Properties": {
        "SslPolicy": {"Ref": "PolicyName"}
      }
    }
  }
}
""",
        media_type=MediaType.JSON,
    )
    by_id = {resource.logical_id: resource for resource in parsed.resources}
    assert dict(by_id["Listener"].stated) == {"ssl_policy": "ELBSecurityPolicy-TLS13-1-2-2021-06"}
    assert by_id["Templated"].stated == ()
