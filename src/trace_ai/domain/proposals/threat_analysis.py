"""`ThreatProposal`: what the Threat Analysis agent returns, and the promotion that owns it.

`agent-design.md` section 22 and DEC-006 put the boundary in the same place from two directions:
the agent proposes, the application validates and persists. This schema is that boundary for a
threat, and the omissions are the whole point -- `id`, `assessment_id`, `status`, `generated_by`,
and `created_at` have no field here, and `extra="forbid"` on `DomainModel` turns a payload
carrying one into a validation error rather than a field silently dropped.

**Referenced objects are identifiers, not local keys.** This is the one structural difference from
`ContextExtractionProposal`, and it follows from what the agent is given. The extractor invents
components and cannot know the identifiers they will be allocated, so it names them by local key.
The threat agent selects from an approved context that already exists, so the identifiers are
supplied to it in the input package and echoed back. A threat naming a component the package never
mentioned is a hallucinated component -- `agent-design.md` section 10 lists inventing one among the
prohibited operations -- and checking that is the validation node's job, because only the node
knows what was in the package.

**The prohibitions are structural.** Section 10 forbids the agent to generate findings, assert that
a control is missing, or assign final severity. None of the three has a field here. `likelihood` is
preliminary and free text; it is not a severity and nothing derives one from it (DEC-030).

**Promotion sets `status` to `candidate` and never anything else.** An agent that could propose
`approved` would be approving its own work, which is what two structural checkpoints exist to
prevent (DEC-005). `promote_threat` takes the identifier from the caller rather than minting one,
because DEC-018 allocates at insert from a store-held counter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import Field

from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus
from trace_ai.domain.identifiers import (
    ActorId,
    AssetId,
    ComponentId,
    ContextClaimId,
    DataFlowId,
    EvidenceReferenceId,
    QuestionId,
)
from trace_ai.domain.threat import Threat
from trace_ai.domain.vocabulary import VocabularyTerm

if TYPE_CHECKING:
    from datetime import datetime

    from trace_ai.domain.identifiers import AssessmentId, ThreatId

__all__ = ["THREAT_ANALYSIS_AGENT", "ThreatProposal", "promote_threat"]

# The agent version `agent-design.md` section 33 names for this agent, and the value
# `data-model.md` section 16's own worked example carries in `generated_by`.
THREAT_ANALYSIS_AGENT: Final = "threat-analysis-v1"


class ThreatProposal(DomainModel):
    """One threat the agent proposes (section 16, minus everything the application owns).

    Every field the application owns is absent rather than optional. Optional would mean an agent
    could supply it and be ignored; absent means supplying it fails.
    """

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)

    methodology: str = Field(min_length=1)
    """How the scenario was arrived at. Free text for the MVP (DEC-041)."""

    category: list[VocabularyTerm] = Field(default_factory=list)
    """Open vocabulary, normalized on the way in (DEC-041). `KNOWN_THREAT_CATEGORIES` in
    `domain/threat.py` lists what the corpus uses and rejects nothing. An uncategorisable threat
    is proposed uncategorised; forcing it into the nearest STRIDE bucket is worse than leaving the
    list empty, because a wrong category is read as a right one."""

    threat_actor_ids: list[ActorId] = Field(default_factory=list)

    affected_component_ids: list[ComponentId] = Field(min_length=1)
    affected_asset_ids: list[AssetId] = Field(min_length=1)
    """Both non-empty: section 10 makes a threat identifying neither an invalid output."""

    related_data_flow_ids: list[DataFlowId] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    attack_path: list[str] = Field(default_factory=list)

    impact: str = Field(min_length=1)
    """Non-empty: section 10 makes a threat lacking plausible security impact an invalid output."""

    likelihood: str | None = None
    confidence: ConfidenceLevel

    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    assumption_ids: list[ContextClaimId] = Field(default_factory=list)
    open_question_ids: list[QuestionId] = Field(default_factory=list)


def promote_threat(
    proposal: ThreatProposal,
    *,
    threat_id: ThreatId,
    assessment_id: AssessmentId,
    generated_by: str = THREAT_ANALYSIS_AGENT,
    created_at: datetime | None = None,
) -> Threat:
    """Turn a validated proposal into a `Threat` the application owns.

    `threat_id` is supplied by the caller and comes from `repository.allocate('thr')`: DEC-018
    assigns an identifier at insert from a monotonic per-`(assessment_id, prefix)` counter, and a
    function that minted its own would be a second source of numbers.

    `status` is `candidate` and is not a parameter. There is no argument that would make it
    anything else, which is the point -- DEC-005's checkpoints are structural, and a promotion
    that could produce an approved object would route around one of them.
    """
    return Threat.model_validate(
        {
            **proposal.model_dump(),
            "id": threat_id,
            "assessment_id": assessment_id,
            "status": ObjectStatus.CANDIDATE,
            "generated_by": generated_by,
            "created_at": created_at if created_at is not None else now(),
        }
    )
