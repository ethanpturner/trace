"""`ContextClaim`: one assertion about the reviewed system, carrying its own epistemic status.

`data-model.md` section 10 is authoritative for the fields. This object carries the distinction the
project exists to defend: section 2.3 says a documented fact, an inference, an assumption, and an
unknown are four different things, and `status` is where the difference is recorded. DEC-009 depends
on that field being honest — silence in a document resolves to `unknown` or `assumed` and never to a
claim that a control is absent.

**The evidence rules follow the status, and they are asymmetric on purpose.** A `documented` claim
must cite evidence, because "documented" is a statement about a document and an uncited one is an
assertion wearing a fact's label. An `inferred` claim must cite the evidence it reasoned from and
say why. An `assumed` or `unknown` claim must **not** be required to cite anything — that is the
DEC-009 path, and a schema that demanded evidence there would leave an extractor with a choice
between dropping the claim and mislabelling it, which is exactly the pressure that turns missing
documentation into a finding.

**`rationale` is the agent's field, not the reviewer's** (DEC-022). `reviewer_notes` belongs to the
human; an inferred or assumed claim carries its reasoning in `rationale`, and the model requires it
there rather than letting the two blur.

**`contradicted` is set by something else.** A claim is contradicted when a `SourceObservation` of
kind `contradiction` names it in `subject_claim_ids` (DEC-021). The reference is one-directional, so
this object carries no field naming what contradicts it and the two cannot disagree about whether
they disagree.

**`value` is `JsonValue`**, which is Pydantic's recursive JSON union: scalars, lists, and
string-keyed mappings, to whatever depth. Section 10 types the field `any`, which strict typing
cannot express, and JSON-compatibility is the real constraint — DEC-020 persists these objects as
JSON payloads, so a value that will not serialize is a value that cannot be stored. This is a typing
decision and not an answer to section 39's open question 1, which asks whether claims should use
this subject-predicate-value shape at all or move to typed models. That stays open.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final, Self

from pydantic import Field, JsonValue, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ConfidenceLevel, SourceOrigin
from trace_ai.domain.identifiers import (
    PREFIX_BY_TERM,
    AssessmentId,
    ContextClaimId,
    EvidenceReferenceId,
    parse_id,
)
from trace_ai.domain.vocabulary import VocabularyTerm

__all__ = ["ClaimStatus", "ContextClaim"]


class ClaimStatus(StrEnum):
    """What kind of assertion a claim is (section 10, "Status values").

    Seven values, and the first five are the epistemic ladder section 2.3 describes. The last two
    are outcomes rather than kinds: `contradicted` is set when a `SourceObservation` names the claim
    (DEC-021), and `rejected` when a reviewer discards it.

    This vocabulary lives here rather than in `domain/enums.py` because section 10 defines it on the
    object, the way section 7 defines `trust_level`. Section 4's members are the shared ones.
    """

    DOCUMENTED = "documented"
    """The source documents say it. Requires evidence."""

    INFERRED = "inferred"
    """Reasoned from evidence that does not say it outright. Requires evidence and a rationale."""

    USER_CONFIRMED = "user_confirmed"
    """The reviewer confirmed it. The reviewer is the evidence."""

    ASSUMED = "assumed"
    """Taken as true without support, and labelled as such. Requires a rationale, not evidence."""

    UNKNOWN = "unknown"
    """The documentation does not settle it. The DEC-009 resting place, and it cites nothing."""

    CONTRADICTED = "contradicted"
    """A `SourceObservation` of kind `contradiction` names this claim (DEC-021)."""

    REJECTED = "rejected"
    """A reviewer discarded it."""


# A claim of this kind asserts something about a document, so it must be able to point at the text.
_REQUIRES_EVIDENCE: Final = frozenset({ClaimStatus.DOCUMENTED, ClaimStatus.INFERRED})

# A claim of this kind rests on reasoning rather than on text, so it must say what the reasoning was
# (DEC-022). `documented` needs no rationale: the quotation is the reasoning.
_REQUIRES_RATIONALE: Final = frozenset({ClaimStatus.INFERRED, ClaimStatus.ASSUMED})

# The DEC-009 statuses. Nothing may require evidence of these, and the test that pins it is the
# reason this set is named rather than written as a negation of the one above.
_NEEDS_NO_EVIDENCE: Final = frozenset({ClaimStatus.ASSUMED, ClaimStatus.UNKNOWN})


class ContextClaim(DomainModel):
    """One architectural or business assertion about the reviewed system (section 10)."""

    id: ContextClaimId
    assessment_id: AssessmentId

    subject_type: VocabularyTerm
    """What kind of thing the claim is about — `component`, `asset`, the system itself.

    Normalized like the other type fields (DEC-036), because a claim about a `Component` and one
    about a `component` are claims about the same kind of thing and nothing downstream should have
    to know that.
    """

    subject_id: str | None = None
    """The object the claim is about, when it is about one. Validated as an identifier, and
    required to agree with `subject_type` when that names a known object type."""

    predicate: str = Field(min_length=1)
    """What is being asserted about the subject. Free text deliberately: the vocabulary is worth
    observing before it is fixed, the same reasoning `requirements/README.md` records for
    applicability conditions."""

    value: JsonValue
    """The asserted value. Any JSON-compatible shape; see the module docstring."""

    status: ClaimStatus
    confidence: ConfidenceLevel
    """Categorical only. DEC-022 removed `confidence_score`, and there is no numeric equivalent."""

    rationale: str | None = None
    """Why the claim holds. Required when `status` is `inferred` or `assumed` (DEC-022)."""

    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    source_origin: SourceOrigin
    generated_by: str | None = None
    reviewer_notes: str | None = None
    created_at: datetime
    updated_at: datetime

    supersedes_id: ContextClaimId | None = None
    """The claim this one replaces on **re-extraction**. Not used for reviewer edits (DEC-023)."""

    @model_validator(mode="after")
    def _evidence_matches_the_claimed_status(self) -> Self:
        """A claim about a document cites the document; a claim about a silence cites nothing.

        The second half is the one that matters. `assumed` and `unknown` are where DEC-009 sends a
        claim the documentation does not support, and requiring evidence there would make the
        honest label the expensive one.
        """
        if self.status in _REQUIRES_EVIDENCE and not self.evidence_ids:
            raise ValueError(
                f"a {self.status} claim must cite at least one evidence reference in evidence_ids. "
                f"A claim the documentation does not support is {ClaimStatus.ASSUMED} or "
                f"{ClaimStatus.UNKNOWN} (DEC-009), not an uncited {self.status} one."
            )
        return self

    @model_validator(mode="after")
    def _reasoned_claims_say_why(self) -> Self:
        """DEC-022: `inferred` and `assumed` carry a rationale, and it is the agent's field."""
        if self.status in _REQUIRES_RATIONALE and not (self.rationale or "").strip():
            raise ValueError(
                f"a {self.status} claim must carry a rationale saying why it holds (DEC-022). "
                f"reviewer_notes is the reviewer's field and is not a substitute."
            )
        return self

    @model_validator(mode="after")
    def _subject_reference_is_coherent(self) -> Self:
        """`subject_id` is an identifier, and it names the kind of thing `subject_type` says.

        A claim about a component pointing at an asset validates field by field and is wrong as a
        whole, and nothing downstream would notice: it would simply describe the wrong object.
        """
        if self.subject_id is None:
            return self

        parsed = parse_id(self.subject_id)
        expected = PREFIX_BY_TERM.get(self.subject_type)
        if expected is not None and parsed.prefix != expected:
            raise ValueError(
                f"subject_type is {self.subject_type!r} but subject_id {self.subject_id!r} names "
                f"{parsed.object_type}. A claim describes one object."
            )
        return self
