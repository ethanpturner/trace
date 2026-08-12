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
from trace_ai.domain.proposals.catalog_gap import CatalogGapCandidateProposal
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.threat import KNOWN_THREAT_CATEGORIES, Threat
from trace_ai.domain.vocabulary import VocabularyTerm, normalize_term

if TYPE_CHECKING:
    from collections.abc import Set
    from datetime import datetime

    from trace_ai.domain.identifiers import AssessmentId, ThreatId

__all__ = [
    "THREAT_ANALYSIS_AGENT",
    "ThreatAnalysisProposal",
    "ThreatProposal",
    "promote_threat",
]

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


class ThreatAnalysisProposal(DomainModel):
    """One model response: the threats the agent proposes, and nothing else.

    **An empty list is valid.** `agent-design.md` section 10 says quality matters more than volume
    and warns against producing threats to fill categories; a schema requiring at least one would
    apply exactly the pressure the section argues against, and an architecture that genuinely
    supports no threat is a legitimate outcome. What is not valid is a threat that is malformed,
    and every one of those fails individually.

    Section 10 lists two further outputs this schema does not carry -- threat-related `Question`
    objects and coverage metadata. Neither is built here; the linkage exists, in
    `Threat.open_question_ids`, for when they are.
    """

    threats: list[ThreatProposal] = Field(default_factory=list)

    catalog_gap_candidates: list[CatalogGapCandidateProposal] = Field(default_factory=list)
    """Concerns no requirement covers, flagged for the catalog owner (DEC-065). The third path
    between stretching the nearest requirement and dropping the observation. Empty is the
    ordinary case, and nothing rewards count."""

    def validate_specificity(self) -> None:
        """Refuse a threat that is a category label wearing a title.

        `agent-design.md` section 10 says the agent "should not produce six generic threats merely
        to satisfy each STRIDE category", and section 39 lists "Generic STRIDE labels are rejected"
        among the fixture tests. This is that check.

        **It catches the label, not every generic threat.** A threat whose title normalizes to a
        category name -- `Tampering`, `Elevation of Privilege`, `prompt_injection` -- describes
        nothing and is refused. A threat that is merely vague while still naming components,
        assets, and a path is not caught here, and nothing pretends otherwise: the reviewer at
        checkpoint 2 is what catches that, and a heuristic that tried would reject real scenarios.

        The check is deliberately narrow for the same reason `KNOWN_THREAT_CATEGORIES` validates
        nothing (DEC-041): a rule about what a threat may be *called* is a rule this schema can
        state exactly, and a rule about what a threat may *say* is not.
        """
        offenders = [
            threat.title
            for threat in self.threats
            if _reads_as_a_category(threat.title) or _reads_as_a_category(threat.description)
        ]
        if offenders:
            raise ProposalError(
                f"these are category labels rather than scenarios: {sorted(offenders)}. A threat "
                f"names an actor or failure source, its preconditions, an attack path, the "
                f"components and assets it affects, and an impact. Categories are a coverage aid "
                f"and not an output quota (agent-design.md section 10)."
            )

    def validate_references(self, available: Set[str]) -> None:
        """Every identifier a threat names must be one the input package supplied.

        This is `agent-design.md` section 10's "invent nonexistent components" prohibition, checked
        rather than asked for. It lives here rather than on `ThreatProposal` because only the
        caller knows what was in the package, and a schema that guessed would either refuse valid
        references or accept invented ones.

        Every unknown identifier across every threat is collected before raising, so one retry
        carries the whole correction rather than surfacing them one attempt at a time.
        """
        unknown: dict[int, list[str]] = {}
        for position, threat in enumerate(self.threats):
            referenced = [
                *threat.affected_component_ids,
                *threat.affected_asset_ids,
                *threat.threat_actor_ids,
                *threat.related_data_flow_ids,
                *threat.evidence_ids,
            ]
            missing = sorted({value for value in referenced if value not in available})
            if missing:
                unknown[position] = missing

        if unknown:
            detail = "; ".join(
                f"threat {position} ({self.threats[position].title!r}) references {missing}"
                for position, missing in sorted(unknown.items())
            )
            raise ProposalError(
                f"these identifiers were not in the input package: {detail}. A threat may only "
                f"reference components, assets, actors, data flows, and evidence it was given; "
                f"one it was not given describes a system it was not shown."
            )

        ungrounded: dict[int, list[str]] = {}
        for position, candidate in enumerate(self.catalog_gap_candidates):
            missing = sorted({value for value in candidate.evidence_ids if value not in available})
            if missing:
                ungrounded[position] = missing

        if ungrounded:
            detail = "; ".join(
                f"candidate {position} ({self.catalog_gap_candidates[position].concern[:60]!r}) "
                f"cites {missing}"
                for position, missing in sorted(ungrounded.items())
            )
            raise ProposalError(
                f"these evidence identifiers were not in the input package: {detail}. A "
                f"catalog-gap candidate grounds its concern in evidence it was shown (DEC-065)."
            )


def _reads_as_a_category(text: str) -> bool:
    """Whether `text` is a category label rather than a description of anything.

    Normalized and compared to `KNOWN_THREAT_CATEGORIES`, so `Tampering`, `tampering`, and
    `Elevation of Privilege` are all caught. A term that does not normalize is not a bare label
    by definition -- it has punctuation or structure a category name does not.
    """
    try:
        return normalize_term(text) in KNOWN_THREAT_CATEGORIES
    except ValueError:
        return False


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
