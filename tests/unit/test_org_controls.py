"""The org-controls catalog and its parser (#528, DEC-115).

The load-bearing properties: the loader is the catalog's one reader and refuses drift,
disagreement, and duplicates; the parser verifies an assertion against the central catalog
before seeding anything and seeds documented claims with catalog provenance as checkpoint-1
candidates; and a failed verification seeds nothing rather than partially.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.org_control import OrganizationalControl
from trace_ai.services.context.parsers import seed_structured_documents
from trace_ai.services.org_controls import OrgCatalogError, load_org_controls

if TYPE_CHECKING:
    from pathlib import Path


def test_the_committed_catalog_loads_and_verifies() -> None:
    catalog = load_org_controls("0.1")
    assert len(catalog) >= 2
    assert "enterprise-idp-mfa" in catalog.by_name()
    assert catalog.content_hash.startswith("sha256:")


def test_an_unknown_version_is_refused_with_the_known_ones_named() -> None:
    with pytest.raises(OrgCatalogError, match="known versions"):
        load_org_controls("9.9")


def test_a_control_name_must_be_a_slug_not_an_identifier() -> None:
    with pytest.raises(ValueError, match="lowercase slug"):
        OrganizationalControl.model_validate(
            {
                "name": "Central Logging",
                "title": "t",
                "statement": "s",
                "mechanism": "m",
                "catalog_version": "0.1",
            }
        )
    with pytest.raises(ValueError, match="identifier"):
        OrganizationalControl.model_validate(
            {
                "name": "ctl-core",
                "title": "t",
                "statement": "s",
                "mechanism": "m",
                "catalog_version": "0.1",
            }
        )


def _handle_with(tmp_path: Path, assertion: str) -> tuple[Any, Any]:
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader

    path = tmp_path / "org-controls.yaml"
    path.write_text(assertion, encoding="utf-8")
    store = AssessmentStore.at_root(tmp_path / "data")
    store.__enter__()
    service = AssessmentService(store, artifact_root=tmp_path / "data")
    created = service.create("Org", default_configuration("offline-fake", "stride-scenario-based"))
    handle = service.handle(created.id)
    DocumentLoader(handle).load_document(
        path, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
    )
    return store, handle


def test_the_zero_two_catalog_carries_the_operator_fact_set_with_references() -> None:
    """0.2 is the operator fact set DEC-115's v0 waited for (#568, DEC-122): the 0.1 entries
    carried forward plus the wider set, each entry pointing at the organizational
    documentation that evidences it. 0.1 stays untouched — a version's content never moves."""
    catalog = load_org_controls("0.2")
    names = set(catalog.by_name())
    assert {"enterprise-idp-mfa", "central-logging", "secrets-vault"} <= names
    for control in catalog.controls:
        assert control.references, f"{control.name} carries no reference (DEC-122)"
    # 0.1 predates the field and stays reference-free.
    for control in load_org_controls("0.1").controls:
        assert control.references == []


def test_a_seeded_claim_carries_the_references_as_text(tmp_path: Path) -> None:
    """References are pointers a reviewer can check, riding in the claim's value (DEC-122).
    They never become evidence objects: the referenced documents are not in the store."""
    store, handle = _handle_with(
        tmp_path,
        'org_controls_catalog:\n  version: "0.2"\n  asserted:\n    - secrets-vault\n',
    )
    try:
        seed_structured_documents(handle)
        (claim,) = handle.objects.list(ContextClaim)
        assert "secrets-vault (org-controls catalog 0.2)" in str(claim.value)
        assert "References: Platform Security Standard PS-4" in str(claim.value)
        # The claim's only evidence is the assertion document itself.
        assert len(claim.evidence_ids) == 1
    finally:
        store.__exit__(None, None, None)


def test_a_verified_assertion_seeds_documented_claims_with_provenance(tmp_path: Path) -> None:
    store, handle = _handle_with(
        tmp_path,
        'org_controls_catalog:\n  version: "0.1"\n  asserted:\n    - enterprise-idp-mfa\n',
    )
    try:
        seeded = seed_structured_documents(handle)
        assert seeded is not None
        (claim,) = handle.objects.list(ContextClaim)
        assert claim.predicate == "organizational_control"
        assert claim.status.value == "documented"
        assert claim.source_origin is SourceOrigin.STRUCTURED_INPUT
        assert claim.generated_by == "org-controls-parser-v1"
        assert "enterprise-idp-mfa (org-controls catalog 0.1)" in str(claim.value)
        assert claim.evidence_ids, "a documented claim cites the assertion it came from"
    finally:
        store.__exit__(None, None, None)


def test_an_unverifiable_assertion_seeds_nothing(tmp_path: Path) -> None:
    """An unknown control name is an unverifiable claim about the organization: the parser
    raises with the reason and nothing is seeded — no partial claim survives a typo."""
    store, handle = _handle_with(
        tmp_path,
        'org_controls_catalog:\n  version: "0.1"\n  asserted:\n    - nonexistent-control\n',
    )
    try:
        with pytest.raises(ValueError, match="nonexistent-control"):
            seed_structured_documents(handle)
        assert handle.objects.list(ContextClaim) == []
    finally:
        store.__exit__(None, None, None)


def test_seeded_claims_are_candidates_for_checkpoint_one(tmp_path: Path) -> None:
    store, handle = _handle_with(
        tmp_path,
        'org_controls_catalog:\n  version: "0.1"\n  asserted:\n    - central-logging\n',
    )
    try:
        seed_structured_documents(handle)
        (claim,) = handle.objects.list(ContextClaim)
        assert claim.status.value == "documented"
        # Candidate objects await checkpoint 1; approval is a reviewer's, never the parser's.
        components_and_claims_pending = [
            obj
            for obj in handle.objects.list(ContextClaim)
            if getattr(obj, "status", None) is not ObjectStatus.APPROVED
        ]
        assert components_and_claims_pending
    finally:
        store.__exit__(None, None, None)
