"""`CatalogGapCandidateProposal`: the typed channel for a concern no requirement covers (DEC-065).

The RaD-TM discipline, transplanted: never stretch the nearest requirement over a concern it does
not cover, and never drop the observation — flag it as catalog-maintenance input. The Threat
Analysis and Mapping agents may return this proposal; no new model call exists and the agent cap
inventory is unchanged.

Proposal rules apply unchanged (`agent-design.md` section 22, DEC-006): no identifier, no status,
nothing authoritative, `extra="forbid"`. What this schema additionally *omits* is the DEC-009
pressure point answered structurally: no severity, no validation status, no recommendation — a
candidate is about the catalog's coverage, not the system's controls, and a shape that could read
as a finding is unrepresentable rather than discouraged.

The named-nearest-requirements field is the quality gate: an empty list is a validation failure,
because "no requirement covers this" is only falsifiable when the near-misses are named.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.catalog_gap_candidate import CatalogGapCandidate, NearestRequirement
from trace_ai.domain.identifiers import EvidenceReferenceId, RequirementId
from trace_ai.domain.vocabulary import VocabularyTerm

if TYPE_CHECKING:
    from datetime import datetime

    from trace_ai.domain.identifiers import AssessmentId, CatalogGapCandidateId

__all__ = [
    "CatalogGapCandidateProposal",
    "NearestRequirementConsidered",
    "promote_catalog_gap_candidate",
]


class NearestRequirementConsidered(DomainModel):
    """One requirement the agent considered and found not to fit, with the reason."""

    requirement_id: RequirementId
    why_not: str = Field(min_length=1)


class CatalogGapCandidateProposal(DomainModel):
    """A concern the catalog does not cover, as the agent proposes it (section 23a)."""

    concern: str = Field(min_length=1)
    suggested_category: VocabularyTerm

    nearest_requirements: list[NearestRequirementConsidered] = Field(min_length=1)
    """The quality gate (DEC-065): the nearest requirements considered and why each does not
    fit. `min_length=1` makes an unjustified candidate a schema failure, not a style problem."""

    evidence_ids: list[EvidenceReferenceId] = Field(min_length=1)
    """What grounds the concern. Non-empty: a candidate claims the analysis met this concern in
    the material, and an ungrounded candidate is exactly the junk DEC-065's tradeoffs warn
    about."""


def promote_catalog_gap_candidate(
    proposal: CatalogGapCandidateProposal,
    *,
    candidate_id: CatalogGapCandidateId,
    assessment_id: AssessmentId,
    generated_by: str,
    created_at: datetime | None = None,
) -> CatalogGapCandidate:
    """Turn a proposed candidate into the routed artifact the application owns.

    There is no status to fix because the object carries none: a candidate is never decided,
    approved, or consolidated — it is read by the catalog owner and feeds a DEC-057 authoring
    decision, or it does not.
    """
    return CatalogGapCandidate.model_validate(
        {
            "id": candidate_id,
            "assessment_id": assessment_id,
            "concern": proposal.concern,
            "suggested_category": proposal.suggested_category,
            "nearest_requirements": [
                NearestRequirement.model_validate(considered.model_dump())
                for considered in proposal.nearest_requirements
            ],
            "evidence_ids": list(proposal.evidence_ids),
            "generated_by": generated_by,
            "created_at": created_at if created_at is not None else now(),
        }
    )
