"""`TrustBoundary`: a place where trust, ownership, privilege, or control changes.

`data-model.md` section 15 is authoritative for the fields.

`inside_component_ids` and `outside_component_ids` are both optional and both may be empty, which
is deliberate rather than lax. A boundary extracted from a sentence like "the webhook receiver is
internet facing" is a real boundary before anyone has worked out which components sit on each side
of it, and refusing to record it until the sides are known would lose the boundary and keep the
silence. Whether a boundary with no components on either side is useful is a question for the
Context Validation node, which can see the rest of the context; it is not a reason for the schema to
reject one.

`controls` is a list of free-text control names, not `Control` identifiers. Section 15 types it
`list[string]` and describes it as "Known controls at boundary" -- the extracted `Control` objects
come later in the pipeline and are linked from their own object.
"""

from __future__ import annotations

from typing import Final

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.identifiers import (
    AssessmentId,
    ComponentId,
    EvidenceReferenceId,
    TrustBoundaryId,
)
from trace_ai.domain.vocabulary import VocabularyTerm

__all__ = ["KNOWN_BOUNDARY_TYPES", "TrustBoundary"]

# Section 15's examples. Documentation, not a validation rule (DEC-036).
KNOWN_BOUNDARY_TYPES: Final[frozenset[str]] = frozenset(
    {
        "internet_to_application",
        "user_to_administration",
        "application_to_data_store",
        "organization_to_third_party",
        "human_to_service_identity",
        "low_privilege_to_high_privilege",
        "tenant_boundary",
        "assessment_data_boundary",
    }
)


class TrustBoundary(DomainModel):
    """A change in trust, ownership, privilege, or control (section 15)."""

    id: TrustBoundaryId
    assessment_id: AssessmentId

    name: str = Field(min_length=1)
    boundary_type: VocabularyTerm
    """Open vocabulary; see `KNOWN_BOUNDARY_TYPES`."""

    description: str | None = None
    inside_component_ids: list[ComponentId] = Field(default_factory=list)
    outside_component_ids: list[ComponentId] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    """Control names as documented, not `Control` identifiers."""

    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    status: ObjectStatus
