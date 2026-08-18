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
from trace_ai.services.context.iac import parse_terraform, parse_terraform_hcl
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


HCL_DECLARATION = """\
# Ticketing datastore, declared in HCL syntax (DEC-121).
resource "aws_db_instance" "tickets_db" {
  engine              = "postgres"
  storage_encrypted   = true
  publicly_accessible = false  # stated, with a trailing comment
}

resource "aws_s3_bucket" "exports" {
  bucket = "exports"
}
"""


def test_hcl_parses_to_the_same_declaration_as_its_json_twin() -> None:
    """The two syntaxes are documented equivalents, and the two readers agree on this pair."""
    from_hcl = parse_terraform_hcl(HCL_DECLARATION)
    from_json = parse_terraform(DECLARATION)
    assert [
        (resource.resource_type, resource.name, resource.stated) for resource in from_hcl.resources
    ] == [
        (resource.resource_type, resource.name, resource.stated) for resource in from_json.resources
    ]


def test_the_subset_reads_literal_booleans_and_nothing_else() -> None:
    """An expression, a commented-out line, and a nested block's attribute are all *not
    stated*: the subset scanner yields nothing for each, which is DEC-009's line — silence,
    never a guessed value."""
    parsed = parse_terraform_hcl(
        """\
resource "aws_db_instance" "conditional" {
  storage_encrypted = var.encrypt_at_rest
  # publicly_accessible = true
  /* deletion_protection = true */
  timeouts {
    encrypted = true
  }
}
resource "aws_ebs_volume" "scratch" {
  encrypted           = false
  deletion_protection = true
}
"""
    )
    by_name = {resource.name: resource for resource in parsed.resources}
    assert by_name["conditional"].stated == ()
    assert dict(by_name["scratch"].stated) == {"encrypted": False, "deletion_protection": True}


def test_a_resource_free_hcl_file_is_an_empty_declaration_not_a_refusal() -> None:
    """`variables.tf` and `outputs.tf` are ordinary in a real corpus; the suffix named the
    format and the file states no resources."""
    parsed = parse_terraform_hcl('variable "region" {\n  default = "us-east-1"\n}\n')
    assert parsed.resources == ()


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


def test_hcl_seeding_holds_the_same_family_rules(tmp_path: Path) -> None:
    """The HCL path enters the same proposal door: `structured_input` provenance, candidate
    status, a documented claim per stated boolean, and an excerpt quoting the resource's own
    lines — trailing comment and all — with a verifying hash."""
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.hashing import content_hash
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader

    declaration = tmp_path / "main.tf"
    declaration.write_text(HCL_DECLARATION, encoding="utf-8")

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
        assert by_name["tickets db"].component_type == "managed_database"
        assert by_name["tickets db"].status is ObjectStatus.CANDIDATE
        assert by_name["tickets db"].source_origin is SourceOrigin.STRUCTURED_INPUT

        claims = {claim.predicate: claim for claim in handle.objects.list(ContextClaim)}
        assert set(claims) == {"storage_encrypted", "publicly_accessible"}
        assert claims["storage_encrypted"].value is True
        assert claims["publicly_accessible"].value is False, "a stated false is documented"

        (cited,) = claims["storage_encrypted"].evidence_ids
        reference = handle.objects.get(EvidenceReference, cited)
        assert "storage_encrypted   = true" in reference.quoted_text
        assert reference.quoted_text.splitlines()[0].startswith('resource "aws_db_instance"')
        assert reference.content_hash == content_hash(reference.quoted_text.encode("utf-8"))


def test_a_resource_free_hcl_file_seeds_nothing_and_refuses_nothing(tmp_path: Path) -> None:
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader

    variables = tmp_path / "variables.tf"
    variables.write_text('variable "region" {\n  default = "us-east-1"\n}\n', encoding="utf-8")

    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Variables only", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        DocumentLoader(handle).load_document(
            variables,
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )
        seeded = seed_structured_documents(handle)
        assert seeded is None or seeded.components == ()
        assert handle.objects.list(Component) == []


def test_a_closed_vocabulary_string_is_as_literal_as_a_stated_boolean() -> None:
    """The widened admission rule (DEC-121 as amended): a stated enum member is read verbatim
    in both syntaxes; an expression or an interpolated string is still not stated."""
    from_hcl = parse_terraform_hcl(
        """\
resource "azurerm_storage_account" "artifacts" {
  minimum_tls_version = "TLS1_2"
}
resource "azurerm_storage_account" "legacy" {
  minimum_tls_version = var.tls_floor
}
resource "azurerm_storage_account" "templated" {
  minimum_tls_version = "${var.tls_floor}"
}
"""
    )
    by_name = {resource.name: resource for resource in from_hcl.resources}
    assert dict(by_name["artifacts"].stated) == {"minimum_tls_version": "TLS1_2"}
    assert by_name["legacy"].stated == ()
    assert by_name["templated"].stated == ()

    from_json = parse_terraform(
        '{"resource": {"azurerm_storage_account": {"artifacts": '
        '{"minimum_tls_version": "TLS1_2"}}}}'
    )
    assert dict(from_json.resources[0].stated) == {"minimum_tls_version": "TLS1_2"}


def test_a_security_group_rule_yields_no_reachability_conclusion() -> None:
    """The must-not-conclude negative: cross-resource is closed, permanently (DEC-121 as
    amended). A world-open ingress rule is a graph judgment away from a reachability claim,
    and the parser makes no part of that judgment — the resource seeds as a component and
    nothing more."""
    parsed = parse_terraform_hcl(
        """\
resource "aws_security_group_rule" "world_open" {
  type        = "ingress"
  cidr_blocks = ["0.0.0.0/0"]
  from_port   = 443
  to_port     = 443
}
"""
    )
    (rule,) = parsed.resources
    assert rule.stated == (), "no reachability, exposure, or any other claim"
