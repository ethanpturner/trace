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

from typing import TYPE_CHECKING, Final

from pydantic import Field

from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.enums import ConfidenceLevel, EvidenceStrength, ValidationStatus
from trace_ai.domain.evidence_assessment import (
    EvidenceAssessment,
    Recommendation,
    SubjectType,
)
from trace_ai.domain.identifiers import EvidenceReferenceId, SourceObservationId
from trace_ai.domain.proposals.context_extraction import ProposalError

if TYPE_CHECKING:
    from collections.abc import Set
    from datetime import datetime

    from trace_ai.domain.identifiers import AssessmentId, EvidenceAssessmentId

__all__ = [
    "EVIDENCE_VALIDATION_AGENT",
    "EvidenceAssessmentProposal",
    "EvidenceValidationProposal",
    "promote_assessment",
]

# The agent version `agent-design.md` section 33 names for this agent.
EVIDENCE_VALIDATION_AGENT: Final = "evidence-validation-v1"


class EvidenceAssessmentProposal(DomainModel):
    """One assessment (section 20, minus what the application owns)."""

    subject_type: SubjectType
    subject_id: str

    evidence_ids: list[EvidenceReferenceId]
    evidence_strengths: dict[str, EvidenceStrength]

    validation_status: ValidationStatus
    rationale: str = Field(min_length=1)

    missing_evidence: list[str] = Field(default_factory=list)
    contradictions: list[SourceObservationId] = Field(default_factory=list)

    confidence: ConfidenceLevel

    recommendation: Recommendation
    """What to do with the candidate (DEC-047). Survives promotion; `quoted_text` does not."""

    quoted_text: dict[str, str] = Field(default_factory=dict)
    """Any evidence text the rationale relies on, keyed by evidence identifier.

    Optional, and its purpose is to be *checked*: section 14 makes "the rationale misquotes or
    materially changes evidence" a failure condition, and `data-model.md` section 8 forbids
    modifying an `EvidenceReference` after creation, so any divergence is the agent's. A quotation
    the agent has to write down separately is one the application can compare."""


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
            for evidence_id, text in assessment.quoted_text.items():
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
    return EvidenceAssessment.model_validate(
        {
            **payload,
            "id": assessment_id,
            "assessment_id": parent_assessment_id,
            "generated_by": generated_by,
            "created_at": created_at if created_at is not None else now(),
        }
    )
