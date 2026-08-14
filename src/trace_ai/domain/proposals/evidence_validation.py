"""What the Evidence Validation agent returns, and the promotion that owns it.

The same boundary as everywhere else: `id`, `assessment_id`, `generated_by`, and `created_at` have
no field here, and `extra="forbid"` makes a payload carrying one a validation error rather than a
dropped key.

**Subjects are referenced by identifier, never by key.** This agent evaluates objects that already
exist — a claim, a control, a mapping, a threat — and every one of them was supplied in its input
package. There is nothing for it to invent, so there is no local-key mechanism here at all, and an
identifier the package did not contain is an assessment of something the agent was not given.

**The recommendation is the DEC-009 escape hatch, and it is a recommendation.** Section 14's
outputs include "recommendations to continue, revise, or stop a candidate conclusion", and its
allowed operations include recommending that a candidate be downgraded to a question or given
documentation-gap treatment. Those are proposals: the agent may not create a `Question`, may not
create a `DocumentationGap`, and may not approve anything. `Recommendation` is a field, not an
action, and nothing here writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Self

from pydantic import Field, field_validator, model_validator

from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.enums import ConfidenceLevel, EvidenceStrength, ValidationStatus
from trace_ai.domain.evidence_assessment import (
    EVIDENCED_VALIDATION_STATUSES,
    EvidenceAssessment,
    Recommendation,
    SubjectType,
)
from trace_ai.domain.identifiers import (
    PREFIX_BY_TERM,
    EvidenceReferenceId,
    SourceObservationId,
    parse_id,
)
from trace_ai.domain.proposals.context_extraction import ProposalError

if TYPE_CHECKING:
    from collections.abc import Set
    from datetime import datetime

    from trace_ai.domain.identifiers import AssessmentId, EvidenceAssessmentId

__all__ = [
    "EVIDENCE_VALIDATION_AGENT",
    "EvidenceAssessmentProposal",
    "EvidenceValidationProposal",
    "QuotedEvidence",
    "WeighedEvidence",
    "promote_assessment",
]

# The agent version `agent-design.md` section 33 names for this agent.
EVIDENCE_VALIDATION_AGENT: Final = "evidence-validation-v1"


class WeighedEvidence(DomainModel):
    """One evidence reference and the strength assigned to it (DEC-022).

    A typed pair rather than a mapping entry, because this schema crosses the wire: the
    provider's strict output grammar rewrites an open mapping into an object that accepts only
    `{}` (DEC-083's finding, recurring here as DEC-087), which made the required per-reference
    strengths structurally impossible to emit. Promotion folds the pairs back into the mapping
    the domain object keeps.
    """

    evidence_id: EvidenceReferenceId
    strength: EvidenceStrength


class QuotedEvidence(DomainModel):
    """One evidence reference and the passage text the rationale relies on (DEC-087)."""

    evidence_id: EvidenceReferenceId
    text: str = Field(min_length=1)


class EvidenceAssessmentProposal(DomainModel):
    """One assessment (section 20, minus what the application owns)."""

    subject_type: SubjectType
    subject_id: str

    evidence_ids: list[EvidenceReferenceId]
    evidence_strengths: list[WeighedEvidence]

    validation_status: ValidationStatus
    rationale: str = Field(min_length=1)

    missing_evidence: list[str] = Field(default_factory=list)
    contradictions: list[SourceObservationId] = Field(default_factory=list)

    confidence: ConfidenceLevel

    recommendation: Recommendation
    """What to do with the candidate (DEC-047). Survives promotion; `quoted_text` does not."""

    quoted_text: list[QuotedEvidence] = Field(default_factory=list)
    """Any evidence text the rationale relies on, named per reference.

    Optional, and its purpose is to be *checked*: section 14 makes "the rationale misquotes or
    materially changes evidence" a failure condition, and `data-model.md` section 8 forbids
    modifying an `EvidenceReference` after creation, so any divergence is the agent's. A quotation
    the agent has to write down separately is one the application can compare."""

    # `EvidenceAssessment`'s own rules, applied one step earlier — the same deliberate
    # duplication as `RequirementMappingProposal` and for the same reason (#324): caught here it
    # is a schema failure the retry policy feeds back with the field named; caught at promotion
    # it is a conversion crash after the call is already paid for.

    @field_validator("evidence_strengths", mode="before")
    @classmethod
    def _strengths_accept_the_mapping_form(cls, value: object) -> object:
        """The pre-DEC-087 recordings carry `{evidence_id: strength}`; fold it to pairs.

        The exported schema — what the prompt teaches and the wire grammar compiles — is the
        pair list only. The mapping form exists so the committed recordings stay loadable, not
        as a second shape a model may choose.
        """
        if isinstance(value, dict):
            return [
                {"evidence_id": evidence_id, "strength": strength}
                for evidence_id, strength in value.items()
            ]
        return value

    @field_validator("quoted_text", mode="before")
    @classmethod
    def _quotations_accept_the_mapping_form(cls, value: object) -> object:
        if isinstance(value, dict):
            return [
                {"evidence_id": evidence_id, "text": text} for evidence_id, text in value.items()
            ]
        return value

    @model_validator(mode="after")
    def _subject_id_matches_subject_type(self) -> Self:
        parsed = parse_id(self.subject_id)
        expected = PREFIX_BY_TERM.get(self.subject_type.value)
        if expected is not None and parsed.prefix != expected:
            raise ValueError(
                f"subject_type is {self.subject_type.value!r}, whose identifiers begin "
                f"{expected!r}, but subject_id {self.subject_id!r} names a {parsed.object_type}."
            )
        return self

    @model_validator(mode="after")
    def _asserted_status_cites_evidence(self) -> Self:
        if self.validation_status in EVIDENCED_VALIDATION_STATUSES and not self.evidence_ids:
            raise ValueError(
                f"validation_status {self.validation_status.value!r} cites no evidence. A "
                f"conclusion resting on nothing is 'unsupported', 'requires_confirmation', or "
                f"'not_evaluated' — never 'supported' (agent-design.md section 14)."
            )
        return self

    @model_validator(mode="after")
    def _contradicted_names_a_contradiction(self) -> Self:
        if self.validation_status is ValidationStatus.CONTRADICTED and not self.contradictions:
            raise ValueError(
                "validation_status 'contradicted' records no contradiction. Name the "
                "SourceObservation holding the passages that disagree (DEC-021)."
            )
        return self

    @model_validator(mode="after")
    def _strengths_cover_the_evidence(self) -> Self:
        weighed_ids = [entry.evidence_id for entry in self.evidence_strengths]
        duplicates = sorted({i for i in weighed_ids if weighed_ids.count(i) > 1})
        if duplicates:
            raise ValueError(
                f"these evidence references are weighed more than once: {duplicates}. "
                f"One strength per reference (DEC-022)."
            )
        listed = set(self.evidence_ids)
        weighed = set(weighed_ids)
        unweighed = sorted(listed - weighed)
        if unweighed:
            raise ValueError(
                f"these evidence references carry no strength: {unweighed}. "
                f"evidence_strengths covers every identifier in evidence_ids (DEC-022)."
            )
        unlisted = sorted(weighed - listed)
        if unlisted:
            raise ValueError(
                f"these strengths weigh evidence the assessment does not list: {unlisted}. "
                f"evidence_strengths covers every identifier in evidence_ids (DEC-022)."
            )
        return self


class EvidenceValidationProposal(DomainModel):
    """One model response: the assessments drawn over the conclusions it was given.

    An empty list is valid. A package containing no conclusion that needs testing produces no
    assessment, and a schema demanding output would be asking for assessments to exist.
    """

    assessments: list[EvidenceAssessmentProposal] = Field(default_factory=list)

    def validate_references(self, available: Set[str]) -> None:
        """Every identifier an assessment names must be one the input package supplied."""
        missing = sorted(
            {
                value
                for assessment in self.assessments
                for value in (
                    assessment.subject_id,
                    *assessment.evidence_ids,
                    *assessment.contradictions,
                    *(entry.evidence_id for entry in assessment.quoted_text),
                )
                if value not in available
            }
        )
        if missing:
            raise ProposalError(
                f"these identifiers were not in the input package: {missing}. An assessment may "
                f"only evaluate subjects, evidence, and contradictions it was given."
            )

    def validate_quotations(self, quoted: dict[str, str]) -> None:
        """Every quotation the agent wrote down matches the passage it names (section 14).

        `quoted` maps evidence identifier to the stored `quoted_text`. The comparison is on
        whitespace-collapsed text, so a rewrapped quotation passes and a changed word does not:
        section 14's failure condition is a rationale that "misquotes or materially changes"
        evidence, and re-wrapping changes neither.
        """
        wrong: list[str] = []
        for assessment in self.assessments:
            for entry in assessment.quoted_text:
                evidence_id, text = entry.evidence_id, entry.text
                stored = quoted.get(evidence_id)
                if stored is None:
                    wrong.append(f"{evidence_id} (no such evidence reference)")
                elif " ".join(text.split()) not in " ".join(stored.split()):
                    wrong.append(f"{evidence_id} (quoted text is not in the passage)")

        if wrong:
            raise ProposalError(
                f"these quotations do not match the evidence they name: {sorted(wrong)}. "
                f"Evidence text is fixed at creation (data-model.md section 8), so a rationale "
                f"that quotes something else is quoting something that was not said."
            )


def promote_assessment(
    proposal: EvidenceAssessmentProposal,
    *,
    assessment_id: EvidenceAssessmentId,
    parent_assessment_id: AssessmentId,
    generated_by: str = EVIDENCE_VALIDATION_AGENT,
    created_at: datetime | None = None,
) -> EvidenceAssessment:
    """Turn a proposed assessment into one the application owns.

    `quoted_text` is dropped. It exists to have been *checked* against the stored evidence, and
    persisting a second copy of a passage would create exactly the divergence section 14's
    misquotation rule is about. `recommendation` survives (DEC-047).
    """
    payload = proposal.model_dump()
    payload.pop("quoted_text")
    payload["evidence_strengths"] = {
        entry.evidence_id: entry.strength for entry in proposal.evidence_strengths
    }
    return EvidenceAssessment.model_validate(
        {
            **payload,
            "id": assessment_id,
            "assessment_id": parent_assessment_id,
            "generated_by": generated_by,
            "created_at": created_at if created_at is not None else now(),
        }
    )
