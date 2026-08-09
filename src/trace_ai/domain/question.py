"""`Question`: what Trace asks when the documentation cannot settle something.

`data-model.md` section 22 is authoritative for the fields. This object is DEC-009's first-named
outlet: where the material does not establish whether a control exists, the output is a question,
not a finding. `agent-design.md` section 7 makes it the extractor's response to incomplete context —
"incomplete context should produce questions" — rather than a reason to retry.

A `Question` is not a `DocumentationGap` (section 23). A question asks a person for an answer the
documents do not contain; a gap records that the documentation itself is insufficient. The two are
often raised together and they are answered by different people doing different things.

**`blocking` is required and has no default.** Whether the workflow pauses for an answer is a
property of the question, and a default would let an unset field decide it — quietly, in the
direction whoever wrote the default happened to choose.

**An answered question carries all three answer fields or none.** A question with a `response` and
no `answered_at`, or an `answered` status and no response, reads as resolved from every angle a
consumer looks at it, which is worse than one that still reads as open.

**Ordering is a product property, not a display detail.** `demo/forgeflow/forgeflow-scenario.md`
section 20 says questions should be prioritized by their ability to change findings, so
`order_for_review` lives here with the object rather than in whatever renders it: the checkpoint
review package and the command line both need the same order, and two implementations of it would
eventually disagree about which question a reviewer sees first.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.identifiers import AssessmentId, QuestionId, parse_id
from trace_ai.domain.vocabulary import VocabularyTerm

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["Question", "QuestionPriority", "QuestionStatus", "order_for_review"]


class QuestionPriority(StrEnum):
    """How much the answer matters (section 22).

    Closed, because section 22 names the values — "Low, medium, high" — rather than illustrating
    them (DEC-036). Priority is about the answer's ability to change a finding, not about how
    interesting the question is.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QuestionStatus(StrEnum):
    """Where a question has got to (section 22)."""

    OPEN = "open"
    """Asked and unanswered. The only status `order_for_review` returns."""

    ANSWERED = "answered"
    """A response was recorded, with its origin and timestamp."""

    DISMISSED = "dismissed"
    """The reviewer decided the answer would not change the assessment."""


# The three fields that record an answer. Present together or absent together.
_ANSWER_FIELDS: Final = ("response", "response_origin", "answered_at")

# Highest first, so the reviewer sees what can change a finding before what cannot.
_PRIORITY_ORDER: Final[dict[QuestionPriority, int]] = {
    QuestionPriority.HIGH: 0,
    QuestionPriority.MEDIUM: 1,
    QuestionPriority.LOW: 2,
}


class Question(DomainModel):
    """Missing information that could materially affect the assessment (section 22)."""

    id: QuestionId
    assessment_id: AssessmentId

    question: str = Field(min_length=1)
    """What is being asked, phrased for a person to answer."""

    rationale: str = Field(min_length=1)
    """Why the answer matters. Required: a question nobody can justify is one nobody will answer."""

    related_object_type: VocabularyTerm | None = None
    related_object_id: str | None = None

    priority: QuestionPriority
    blocking: bool
    """Whether the workflow pauses for an answer. Required, and deliberately undefaulted."""

    response: str | None = None
    response_origin: SourceOrigin | None = None
    """`user_response` for a reviewer's answer (section 4.4)."""

    answered_at: datetime | None = None
    status: QuestionStatus
    generated_by: str

    @model_validator(mode="after")
    def _an_answer_is_complete_or_absent(self) -> Self:
        """Section 22's answer fields move together, and `answered` means all three are set.

        A half-answered question is worse than an open one. It reads as resolved to anything that
        checks `status`, as unanswered to anything that checks `response`, and the disagreement
        surfaces wherever the two are read together rather than here.
        """
        present = [name for name in _ANSWER_FIELDS if getattr(self, name) is not None]

        if self.status is QuestionStatus.ANSWERED and len(present) != len(_ANSWER_FIELDS):
            missing = [name for name in _ANSWER_FIELDS if name not in present]
            raise ValueError(
                f"status is {QuestionStatus.ANSWERED} but {', '.join(missing)} "
                f"{'is' if len(missing) == 1 else 'are'} unset. An answered question records the "
                f"response, where it came from, and when."
            )
        if self.status is not QuestionStatus.ANSWERED and present:
            raise ValueError(
                f"status is {self.status} but {', '.join(present)} "
                f"{'is' if len(present) == 1 else 'are'} set. A question carrying an answer is "
                f"{QuestionStatus.ANSWERED}."
            )
        return self

    @model_validator(mode="after")
    def _related_reference_is_coherent(self) -> Self:
        """`related_object_id` is an identifier, and it names what `related_object_type` says."""
        if self.related_object_id is None:
            return self

        parsed = parse_id(self.related_object_id)
        if self.related_object_type is not None:
            expected = parsed.object_type.casefold()
            if self.related_object_type != expected:
                raise ValueError(
                    f"related_object_type is {self.related_object_type!r} but "
                    f"related_object_id {self.related_object_id!r} names {parsed.object_type}"
                )
        return self


def order_for_review(questions: Iterable[Question]) -> list[Question]:
    """The open questions, blocking first, then by priority, then by identifier.

    Scenario section 20 asks for questions ordered by their ability to change findings. Blocking
    comes first because a blocking question stops the workflow — nothing else can be worked on
    until it is answered — and priority orders the rest. The identifier is the final tiebreak so
    the order is total: two runs over the same questions produce the same list, which is what makes
    a review package comparable with the one a reviewer saw yesterday.

    Answered and dismissed questions are not returned. They are not what a reviewer is being asked
    for, and the record of them lives on the objects themselves.
    """
    return sorted(
        (question for question in questions if question.status is QuestionStatus.OPEN),
        key=lambda question: (
            not question.blocking,
            _PRIORITY_ORDER[question.priority],
            question.id,
        ),
    )
