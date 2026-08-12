"""`CatalogGapCandidate`: a credible concern no requirement covers, routed to the catalog owner.

`data-model.md` section 23a is authoritative for the fields. DEC-065 is the decision: the RaD-TM
discipline transplanted — never stretch the nearest requirement over a concern it does not cover,
and never drop the observation. The candidate is the third path, and it is catalog-maintenance
input, not an assessment conclusion.

**The shape that must not happen is unrepresentable.** A candidate is about the *catalog's*
coverage, not the system's controls, so the schema carries no severity, no validation status, no
recommendation, and no finding-shaped field, and `extra="forbid"` makes adding one a validation
error. No report section renders it (the DEC-035 ownership table is unchanged), finding
consolidation never reads it, and it is not a checkpoint subject — it appears in the checkpoint 2
package as an informational block because under DEC-004 the reviewer and the catalog owner are
the same person.

**The nearest-requirements justification is the quality gate.** DEC-024's whole-catalog posture
is what makes "no requirement covers this" a claim the agent can actually make; naming the
nearest requirements considered and why each does not fit is what makes it falsifiable. An empty
list is a validation failure, here and at the proposal boundary.

**A candidate feeds the next catalog version through a human** (DEC-057). It carries no
authority: the catalog grows by an authoring decision, not by an agent inventing requirements
mid-assessment.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.identifiers import (
    AssessmentId,
    CatalogGapCandidateId,
    EvidenceReferenceId,
    RequirementId,
)
from trace_ai.domain.vocabulary import VocabularyTerm

__all__ = ["CatalogGapCandidate", "NearestRequirement"]


class NearestRequirement(DomainModel):
    """One requirement considered and found not to fit, with the reason.

    The pair is what makes a coverage claim checkable: a reader can open `requirement_id` and
    weigh `why_not` against its text. A candidate naming no near-misses is refused outright.
    """

    requirement_id: RequirementId
    why_not: str = Field(min_length=1)
    """Why this requirement does not cover the concern. Non-empty: a named requirement with no
    stated misfit is a claim nobody can weigh."""


class CatalogGapCandidate(DomainModel):
    """A concern the catalog does not cover, persisted for the catalog owner (DEC-065)."""

    id: CatalogGapCandidateId
    assessment_id: AssessmentId

    concern: str = Field(min_length=1)
    """The security concern the analysis met and the catalog does not cover, in prose."""

    suggested_category: VocabularyTerm
    """Where in the catalog the concern would live — a primary-category suggestion, open
    vocabulary (DEC-036), normalized on the way in. A suggestion for the 0.2 authoring decision,
    not a placement."""

    nearest_requirements: list[NearestRequirement] = Field(min_length=1)
    """The requirements considered and why each does not fit. Non-empty by schema: this list is
    the DEC-065 quality gate, and a candidate without it is unfalsifiable."""

    evidence_ids: list[EvidenceReferenceId] = Field(min_length=1)
    """The evidence grounding the concern. Non-empty: a candidate is a claim the analysis *met*
    this concern in the material, and meeting it means being able to point at it."""

    generated_by: str = Field(min_length=1)
    created_at: datetime
