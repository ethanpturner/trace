"""`SourceObservation`: something observed about the source material, not about the system.

`data-model.md` section 10a is authoritative for the fields, and DEC-021 is why there is one object
here rather than two. A `ContextClaim` asserts that authentication is delegated; a
`SourceObservation` asserts that two documents disagree, or that a passage tries to instruct its
reader. The distinction is categorical — one describes the system, the other describes the
documents — and it is the reason a contradiction cannot quietly become a finding.

**There is no severity field, and its absence is a rule rather than an omission.** An observation
says something about a document. A `Finding` asserts a weakness in the reviewed system. Giving an
observation a severity would be the first step of a path from "these two paragraphs disagree" to "a
vulnerability exists", and the whole point of the object is that no such path exists.

**Evidence counts differ by kind, and the numbers mean something.** A contradiction is a claim about
a relationship between two passages, so it takes two: one reference proves nothing about a
disagreement. An injection attempt is a claim about one passage, so it takes one.

**A contradiction does not resolve itself.** Section 10a says so explicitly, and this module holds
no logic that picks the safer statement. Where the answer would change the assessment, a `Question`
is raised alongside — which is a workflow step, not a field.

**The link to `ContextClaim` runs one way.** A claim is `contradicted` when an observation names it
in `subject_claim_ids`. The claim carries no field naming what contradicts it, so the two cannot
disagree about whether they disagree. That direction is also why a claim cannot enforce its own
`contradicted` status: nothing on the claim can see the observations. `unsupported_contradictions`
is how that inconsistency is *detected*, and the Context Validation node is where it is checked.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.context_claim import ClaimStatus
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.identifiers import (
    AssessmentId,
    ContextClaimId,
    EvidenceReferenceId,
    SourceObservationId,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from trace_ai.domain.context_claim import ContextClaim

__all__ = ["ObservationKind", "SourceObservation", "unsupported_contradictions"]


class ObservationKind(StrEnum):
    """What was observed about the source material (section 10a, "Kind values").

    Two values, and DEC-021 is the decision that they belong to one object. They share a shape —
    an assertion about documents rather than about the system, resting on quoted passages, carrying
    no severity — and separating them would have produced two objects with one field different.

    The vocabulary lives here rather than in `domain/enums.py` because section 10a defines it on the
    object, the way section 10 defines `ContextClaim`'s statuses.
    """

    CONTRADICTION = "contradiction"
    """Two passages disagree. Requires at least two evidence references."""

    INJECTION_ATTEMPT = "injection_attempt"
    """A passage attempts to instruct its reader. Requires at least one."""


# Section 10a's evidence rule, by kind. A contradiction is an assertion about a relationship
# between passages, so one reference cannot establish it.
_MINIMUM_EVIDENCE: Final[dict[ObservationKind, int]] = {
    ObservationKind.CONTRADICTION: 2,
    ObservationKind.INJECTION_ATTEMPT: 1,
}


class SourceObservation(DomainModel):
    """Something observed about the source material (section 10a, DEC-021)."""

    id: SourceObservationId
    assessment_id: AssessmentId

    kind: ObservationKind
    summary: str = Field(min_length=1)
    """What was observed, in the reviewer's terms."""

    evidence_ids: list[EvidenceReferenceId] = Field(min_length=1)
    """The passages the observation rests on. Required, and the minimum count depends on `kind`."""

    subject_claim_ids: list[ContextClaimId] = Field(default_factory=list)
    """The claims this observation bears on. What makes a claim `contradicted`, one-directionally."""

    status: ObjectStatus
    generated_by: str | None = None
    reviewer_notes: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _evidence_meets_the_minimum_for_its_kind(self) -> Self:
        """Section 10a's first two validation rules, as schema rather than as convention."""
        required = _MINIMUM_EVIDENCE[self.kind]
        if len(self.evidence_ids) < required:
            raise ValueError(
                f"a {self.kind} observation requires at least {required} evidence "
                f"{'reference' if required == 1 else 'references'}, got {len(self.evidence_ids)}. "
                f"A contradiction is an assertion about two passages disagreeing, and one passage "
                f"cannot establish it."
            )
        return self


def unsupported_contradictions(
    claims: Iterable[ContextClaim],
    observations: Iterable[SourceObservation],
) -> list[str]:
    """Identifiers of claims marked `contradicted` that no observation contradicts.

    The link between the two objects runs one way by design, which means a claim cannot enforce its
    own `contradicted` status — nothing on the claim can see the observations. So the inconsistency
    is detected rather than made impossible, and this is the detection: the Context Validation node
    calls it, and a non-empty result is a validation failure rather than something to repair
    silently.

    Repairing it silently would be the worse option in both directions. Clearing the status would
    discard a contradiction someone recorded; inventing an observation would fabricate evidence.
    """
    contradicted_by = {
        claim_id
        for observation in observations
        if observation.kind is ObservationKind.CONTRADICTION
        for claim_id in observation.subject_claim_ids
    }
    return [
        claim.id
        for claim in claims
        if claim.status is ClaimStatus.CONTRADICTED and claim.id not in contradicted_by
    ]
