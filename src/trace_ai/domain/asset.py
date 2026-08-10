"""`Asset`: something in the reviewed system that requires protection.

`data-model.md` section 12 is authoritative for the fields.

The three impact fields -- `confidentiality_impact`, `integrity_impact`, `availability_impact` --
are free text and optional, and they are **not severity**. Severity is assigned by the reviewer at
checkpoint 2 and lives on `Finding` (DEC-030); these describe what would happen to this asset if a
property were lost, which is context a finding's severity draws on rather than a rating anything
computes from. Nothing in the pipeline derives one from the other.
"""

from __future__ import annotations

from typing import Final

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.identifiers import AssessmentId, AssetId, ComponentId, EvidenceReferenceId
from trace_ai.domain.vocabulary import VocabularyTerm

__all__ = ["KNOWN_ASSET_TYPES", "Asset"]

# Section 12's examples. Documentation, not a validation rule (DEC-036).
KNOWN_ASSET_TYPES: Final[frozenset[str]] = frozenset(
    {
        "customer_data",
        "source_code",
        "repository_metadata",
        "access_token",
        "api_key",
        "user_identity",
        "audit_log",
        "model_output",
        "service_availability",
        "business_process",
        "organizational_reputation",
    }
)


class Asset(DomainModel):
    """Something requiring protection (section 12)."""

    id: AssetId
    assessment_id: AssessmentId

    name: str = Field(min_length=1)
    asset_type: VocabularyTerm
    """Open vocabulary; see `KNOWN_ASSET_TYPES`."""

    description: str | None = None

    confidentiality_impact: str | None = None
    """What disclosure would cost. Prose context for severity, never a rating (DEC-030)."""

    integrity_impact: str | None = None
    availability_impact: str | None = None

    data_classification: str | None = None
    owner: str | None = None
    component_ids: list[ComponentId] = Field(default_factory=list)
    """Components that hold or process this asset."""

    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)

    source_origin: SourceOrigin
    """Where this object came from (section 4.4). `uploaded_document` for something the extractor
    read out of a document, `reviewer_edit` for something a person added at the checkpoint. Required
    rather than defaulted, because a default would make the extractor's provenance the answer given
    when nobody supplied one (DEC-039)."""

    status: ObjectStatus
