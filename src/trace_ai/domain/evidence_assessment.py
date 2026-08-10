"""`EvidenceAssessment`: the only structured record of supported versus merely repeated.

`data-model.md` section 20 is authoritative for the fields. `agent-design.md` section 14 makes
"treat repeated model claims as independent corroboration" a prohibited operation, and without a
first-class assessment object that prohibition has nowhere to live: a conclusion asserted three
times by three steps looks, in the absence of this object, exactly like a conclusion three passages
support.

**Strength is relational, and this is where it is recorded** (DEC-022). `evidence_strengths` maps
each identifier in `evidence_ids` to how it bears on *this* subject. The same passage is direct
evidence about authentication and contextual evidence about session handling, so the strength
cannot live on `EvidenceReference`. DEC-022's own tradeoffs note that the map can drift from the
list in both directions and that nothing structural prevents it; `_strengths_cover_the_evidence`
is that rule.

**A contradiction is a `SourceObservation`, referenced by identifier** (DEC-021). Free text here
would mean a contradiction that could not be joined back to the passages that disagree, which is
the whole content of the record. `SourceObservation.evidence_ids` is where the disagreeing
passages are, and it already requires at least two.

**`subject_type` is a closed enum, and it is section 20's own list.** Section 20's purpose names
what may be assessed — "a claim, control, mapping, threat, or finding" — which is the
`DataFlow.direction` case rather than the `component_type` case (DEC-036): the document names the
values rather than illustrating them. A free string would make an assessment unjoinable to its
subject, and the prefix check below would have nothing to check against.

**The evidence hierarchy is a vocabulary, not a score.** Section 14 states in its own words that
the ranking "is guidance, not a universal scoring formula". `EVIDENCE_HIERARCHY` is an ordered
tuple a rationale can cite by name. Nothing here converts a level to a number, compares two
levels, or combines them, because the moment one does, the caveat in the document stops being
true and `design-principles.md` section 15's warning about metrics that make output look precise
applies directly.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final, Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ConfidenceLevel, EvidenceStrength, ValidationStatus
from trace_ai.domain.identifiers import (
    PREFIX_BY_TERM,
    AssessmentId,
    EvidenceAssessmentId,
    EvidenceReferenceId,
    SourceObservationId,
    parse_id,
)

__all__ = [
    "EVIDENCED_VALIDATION_STATUSES",
    "EVIDENCE_HIERARCHY",
    "EvidenceAssessment",
    "EvidenceHierarchyLevel",
    "Recommendation",
    "SubjectType",
]


class Recommendation(StrEnum):
    """What section 14 says to do with the candidate conclusion (DEC-047).

    Closed: section 14 names the three -- continue, revise, stop -- rather than illustrating them,
    and adds the two DEC-009 outlets under allowed operations. All five are *recommendations* that
    a later step acts on; none of them is something this agent does. DEC-013's outcome table is
    what actually decides, and storing the recommendation beside it is what makes the two
    comparable.
    """

    CONTINUE = "continue"
    REVISE = "revise"
    STOP = "stop"

    DOWNGRADE_TO_QUESTION = "downgrade_to_question"
    """The answer is obtainable and would change the assessment (DEC-009, section 16)."""

    DOCUMENTATION_GAP = "documentation_gap"
    """The primary issue is inability to verify, and no weakness is yet supported."""


class SubjectType(StrEnum):
    """What an assessment may be about (section 20's purpose, in the document's order).

    Closed. `DocumentationGap` is deliberately absent: section 14 lists gap candidates among the
    agent's *outputs*, not among what it evaluates, and an assessment of a gap would be an
    evaluation of whether the evidence supports the claim that there is no evidence.
    """

    CONTEXT_CLAIM = "context_claim"
    CONTROL = "control"
    CONTROL_MAPPING = "control_mapping"
    THREAT = "threat"
    FINDING = "finding"
    """Section 20 names it. `Finding` arrives with Finding Consolidation in M4, so nothing
    produces this value yet; the vocabulary is the document's rather than what is built."""


class EvidenceHierarchyLevel(StrEnum):
    """Section 14's seven levels, as labels a rationale cites (see the module docstring)."""

    REVIEWER_CONFIRMED_FACT = "reviewer_confirmed_fact"
    DIRECT_IMPLEMENTATION_OR_CONFIGURATION = "direct_implementation_or_configuration"
    EXPLICIT_ARCHITECTURE_DOCUMENTATION = "explicit_architecture_documentation"
    STRUCTURED_PROJECT_INPUT = "structured_project_input"
    MULTIPLE_CONSISTENT_CONTEXTUAL_REFERENCES = "multiple_consistent_contextual_references"
    REASONABLE_INFERENCE = "reasonable_inference"
    UNSUPPORTED_ASSUMPTION = "unsupported_assumption"


# Section 14's hierarchy in the document's order, strongest first. Ordered so a prompt can present
# it as the document does, and for no other purpose: nothing maps a level to a number.
EVIDENCE_HIERARCHY: Final[tuple[EvidenceHierarchyLevel, ...]] = (
    EvidenceHierarchyLevel.REVIEWER_CONFIRMED_FACT,
    EvidenceHierarchyLevel.DIRECT_IMPLEMENTATION_OR_CONFIGURATION,
    EvidenceHierarchyLevel.EXPLICIT_ARCHITECTURE_DOCUMENTATION,
    EvidenceHierarchyLevel.STRUCTURED_PROJECT_INPUT,
    EvidenceHierarchyLevel.MULTIPLE_CONSISTENT_CONTEXTUAL_REFERENCES,
    EvidenceHierarchyLevel.REASONABLE_INFERENCE,
    EvidenceHierarchyLevel.UNSUPPORTED_ASSUMPTION,
)

# The statuses that say something about a passage, and therefore need one. `unsupported` is
# absent: "no passage supports this" is a statement about the evidence set rather than about a
# passage, and requiring a citation for it would leave nowhere to record the ordinary case where
# a conclusion rests on nothing. `requires_confirmation` and `not_evaluated` are absent for the
# same reason -- neither asserts anything the reader could check against a quotation.
EVIDENCED_VALIDATION_STATUSES: Final[frozenset[ValidationStatus]] = frozenset(
    {
        ValidationStatus.SUPPORTED,
        ValidationStatus.PARTIALLY_SUPPORTED,
        ValidationStatus.CONTRADICTED,
    }
)


class EvidenceAssessment(DomainModel):
    """Whether the evidence supports one claim, control, mapping, threat, or finding."""

    id: EvidenceAssessmentId
    assessment_id: AssessmentId

    subject_type: SubjectType
    subject_id: str
    """The object evaluated. Its prefix must match `subject_type`; whether the object exists is
    checked where the assessment's objects are known, not here."""

    evidence_ids: list[EvidenceReferenceId]
    """The evidence evaluated. Required, and empty only for a status that asserts nothing."""

    evidence_strengths: dict[str, EvidenceStrength]
    """Per-evidence strength for *this* subject (DEC-022). Keys are exactly `evidence_ids`."""

    validation_status: ValidationStatus
    rationale: str = Field(min_length=1)
    """Why the evidence does or does not support the subject. Required: a classification with no
    argument behind it is the model's confidence wearing the shape of a finding."""

    missing_evidence: list[str] = Field(default_factory=list)
    contradictions: list[SourceObservationId] = Field(default_factory=list)
    """The `SourceObservation` records naming passages that disagree (DEC-021)."""

    confidence: ConfidenceLevel

    recommendation: Recommendation
    """Continue, revise, stop, downgrade to a question, or treat as a documentation gap
    (DEC-047). A recommendation and not an action: DEC-013's outcome table decides what actually
    happens, and this is stored beside it so the two can be compared."""

    generated_by: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def _subject_id_matches_subject_type(self) -> Self:
        """`subject_id` names an object of the type `subject_type` declares.

        Checked by prefix, which is what makes the closed enum worth having: `parse_id` already
        knows which prefix belongs to which object type, so a mismatch is caught before the
        assessment is stored against something it is not about.
        """
        parsed = parse_id(self.subject_id)
        expected = PREFIX_BY_TERM.get(self.subject_type.value)
        if expected is not None and parsed.prefix != expected:
            raise ValueError(
                f"subject_type is {self.subject_type.value!r}, whose identifiers begin "
                f"{expected!r}, but subject_id {self.subject_id!r} names a "
                f"{parsed.object_type}."
            )
        return self

    @model_validator(mode="after")
    def _asserted_status_cites_evidence(self) -> Self:
        """A status that says something about a passage names one (section 14).

        Section 14 makes "unsupported claims are marked supported" a failure condition, and this
        is the structural half of it. The other half — whether the cited passage actually supports
        the subject — is a judgment, and no schema can hold it.
        """
        if self.validation_status in EVIDENCED_VALIDATION_STATUSES and not self.evidence_ids:
            raise ValueError(
                f"validation_status {self.validation_status.value!r} cites no evidence. A "
                f"conclusion resting on nothing is 'unsupported', 'requires_confirmation', or "
                f"'not_evaluated' — never 'supported' (agent-design.md section 14)."
            )
        return self

    @model_validator(mode="after")
    def _contradicted_names_a_contradiction(self) -> Self:
        """`contradicted` names the observation recording the disagreement (DEC-021).

        Without it the status says two passages conflict and points at neither, which is the
        `forgeflow-scenario.md` section 16.1 failure: Trace must not silently choose the safer
        statement, and a contradiction with no record is indistinguishable from a choice.
        """
        if self.validation_status is ValidationStatus.CONTRADICTED and not self.contradictions:
            raise ValueError(
                "validation_status 'contradicted' records no contradiction. Name the "
                "SourceObservation holding the passages that disagree (DEC-021)."
            )
        return self

    @model_validator(mode="after")
    def _strengths_cover_the_evidence(self) -> Self:
        """`evidence_strengths` has exactly one entry per `evidence_ids` entry (DEC-022).

        Both directions, because both are drift DEC-022 named and neither is visible downstream:
        a listed identifier with no strength reads as evidence nobody weighed, and a strength for
        an unlisted identifier reads as evidence that was weighed and then dropped.
        """
        listed = set(self.evidence_ids)
        weighed = set(self.evidence_strengths)

        unweighed = sorted(listed - weighed)
        if unweighed:
            raise ValueError(
                f"these evidence references carry no strength: {unweighed}. "
                f"evidence_strengths covers every identifier in evidence_ids (DEC-022)."
            )

        unlisted = sorted(weighed - listed)
        if unlisted:
            raise ValueError(
                f"these identifiers carry a strength and are not in evidence_ids: {unlisted}. "
                f"A strength for evidence the assessment does not cite weighs nothing."
            )
        return self
