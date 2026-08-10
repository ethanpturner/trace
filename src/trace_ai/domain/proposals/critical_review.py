"""What the Critical Review agent returns, and the promotion that owns it.

The same boundary as everywhere else: `id`, `assessment_id`, `status`, and `generated_by` have no
field here, and `extra="forbid"` makes a payload carrying one a validation error rather than a
dropped key.

**Every target is an identifier the review group supplied.** The critic challenges objects that
already exist and invents nothing, so there is no local-key mechanism here at all. That absence is
the schema half of section 15's "create criticism without identifying the target object"
prohibition; `validate_references` is the other half.

**The proposal cannot say what happened.** There is no approval, no resulting status, and no
outcome field — only a `recommended_action`. Section 15 prohibits directly approving findings and
DEC-005 reserves approval for the human checkpoint, so the shape refuses it rather than the prompt
asking it not to.

**An empty response is the good outcome as often as not.** `agent-design.md` section 15 makes
"generates large quantities of superficial criticism" a failure condition and roadmap Stage 4 sets
a decision gate on whether the critic improves results at all. A schema requiring at least one
critique would be an instruction to find something.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.critique import (
    Critique,
    CritiqueSubjectType,
    CritiqueType,
    RecommendedAction,
)
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus
from trace_ai.domain.identifiers import EvidenceReferenceId
from trace_ai.domain.proposals.context_extraction import ProposalError

if TYPE_CHECKING:
    from collections.abc import Set

    from trace_ai.domain.identifiers import AssessmentId, CritiqueId

__all__ = [
    "CRITICAL_REVIEW_AGENT",
    "CriticalReviewProposal",
    "CritiqueProposal",
    "promote_critique",
]

# The agent version `agent-design.md` section 33 names for this agent.
CRITICAL_REVIEW_AGENT: Final = "critical-review-v1"


class CritiqueProposal(DomainModel):
    """One critique (section 24, minus what the application owns)."""

    subject_type: CritiqueSubjectType
    subject_id: str

    critique_type: CritiqueType
    description: str = Field(min_length=1)
    rationale: str = Field(min_length=1)

    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    recommended_action: RecommendedAction
    confidence: ConfidenceLevel


class CriticalReviewProposal(DomainModel):
    """One model response: the challenges the critic raised over one review group."""

    critiques: list[CritiqueProposal] = Field(default_factory=list)

    def validate_references(self, available: Set[str]) -> None:
        """Every target and every citation is something the review group contained.

        Section 23 gives this agent "a bounded group of related objects", and DEC-049 fixes the
        bound. A critique of an object outside the group is a critique of something the critic was
        not shown, which is section 15's unrestricted-second-assessment prohibition arriving one
        object at a time.
        """
        missing = sorted(
            {
                value
                for critique in self.critiques
                for value in (critique.subject_id, *critique.evidence_ids)
                if value not in available
            }
        )
        if missing:
            raise ProposalError(
                f"these identifiers were not in the review group: {missing}. A critique names an "
                f"object it was given; criticism of something else is a second assessment."
            )

    def validate_distinctness(self) -> None:
        """No two critiques make the same challenge against the same object.

        Section 15's "generates large quantities of superficial criticism" failure condition has a
        cheap structural corner: the same type against the same target twice is one criticism
        counted twice, whatever the descriptions say. The node's volume check covers the rest,
        which is not structural and cannot be.
        """
        seen: dict[tuple[str, str], int] = {}
        for critique in self.critiques:
            key = (critique.subject_id, critique.critique_type.value)
            seen[key] = seen.get(key, 0) + 1

        repeated = sorted(key for key, count in seen.items() if count > 1)
        if repeated:
            raise ProposalError(
                f"these target-and-type pairs appear more than once: {repeated}. One challenge "
                f"per kind per object; a second is the same criticism counted twice."
            )


def promote_critique(
    proposal: CritiqueProposal,
    *,
    critique_id: CritiqueId,
    assessment_id: AssessmentId,
    generated_by: str = CRITICAL_REVIEW_AGENT,
) -> Critique:
    """Turn a proposed critique into one the application owns.

    `status` is `candidate` and is not a parameter, for the reason every promotion fixes it: an
    agent that could propose `approved` would be approving its own work (DEC-005) — and for this
    agent section 15 says so twice, since approving findings is among its prohibited operations.
    """
    return Critique.model_validate(
        {
            **proposal.model_dump(),
            "id": critique_id,
            "assessment_id": assessment_id,
            "generated_by": generated_by,
            "status": ObjectStatus.CANDIDATE,
        }
    )
