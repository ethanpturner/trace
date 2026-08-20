"""What checkpoint 1 settled, rendered once for every downstream package (DEC-141).

The contradictory-docs live capture is the reproduction this module answers: the reviewer resolved
a retention contradiction at checkpoint 1, and the downstream stages — which received the
conflicting passages in their fences and the settled claims in their trusted regions, but never the
contradiction record or its resolution — re-asked the settled question three times and filed the
subject as a documentation gap. The resolution existed on the authoritative objects
(`SourceObservation.reviewer_notes`, the claims' `user_confirmed` values); no package carried it.

**The entries here are derived from authoritative objects, never from workflow state.** Section 31
keeps `AssessmentState` to identifiers and routing, and this module honors it by reading
`SourceObservation` and `Question` — objects a reviewer's checkpoint-1 actions wrote — rather than
any record of the review itself. `ReviewerDecision` rows stay out: they are the audit trail of how
the objects got their values, and a package that carried them would be a second copy of what the
objects already say.

**Reviewer text is trusted-human, and it renders in the trusted region on that authority.** The
precedent is established twice over: a claim's `rationale` (a DEC-023 edit) renders in the threat
package's trusted region, and a dismissal precedent's `reviewer_rationale` renders in the critic's —
"the one text in the pipeline written by the human whose judgment the critic is meant to
anticipate." A resolution and an answer are the same kind of text. The one edge that needs
handling: a reviewer may paste source-document content into a rationale or an answer, and a pasted
fence marker must not be able to fabricate an excerpt boundary. Every free-text field here passes
through `neutralize_fence` before it renders, so reviewer-quoted source text enters on the
reviewer's authority as inert prose, never as a fence.

**A rejected observation does not travel.** The reviewer decided the contradiction is not real, and
a package that carried it anyway would invite an agent to honor a disagreement nobody stands
behind. An approved-but-unresolved contradiction travels with ``reviewer_resolution: null`` — the
disagreement is real and unsettled, and saying so is the honest rendering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.services.context.input_package import neutralize_fence

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from trace_ai.domain.question import Question

__all__ = [
    "answered_question_entries",
    "answered_questions",
    "contradiction_entry",
    "recorded_contradictions",
]


def contradiction_entry(observation: SourceObservation) -> dict[str, Any]:
    """One recorded contradiction, with its resolution when a reviewer has settled it.

    ``reviewer_resolution`` is `resolve_contradiction`'s rationale — which statement is
    authoritative and why, in the reviewer's words. ``settled_claim_ids`` names the claims that
    carry the chosen value as ``user_confirmed``, so an agent can connect the settlement to the
    objects it already has. A null resolution is a real, unsettled disagreement.
    """
    resolution = (observation.reviewer_notes or "").strip()
    return {
        "id": observation.id,
        "summary": neutralize_fence(observation.summary),
        "evidence_ids": list(observation.evidence_ids),
        "status": observation.status.value,
        "settled_claim_ids": list(observation.subject_claim_ids),
        "reviewer_resolution": neutralize_fence(resolution) if resolution else None,
    }


def recorded_contradictions(
    observations: Iterable[SourceObservation],
) -> list[dict[str, Any]]:
    """Every contradiction a reviewer has not rejected, as entries, in identifier order.

    Rejection is the one status that removes an observation from the pipeline's view of the
    documents: the reviewer decided the disagreement is not real. Everything else travels,
    resolved or not, because a contradiction an agent was never shown is one it cannot be held
    to have addressed.
    """
    return [
        contradiction_entry(observation)
        for observation in sorted(observations, key=lambda entry: entry.id)
        if observation.kind is ObservationKind.CONTRADICTION
        and observation.status is not ObjectStatus.REJECTED
    ]


def answered_questions(questions: Iterable[Question]) -> list[Question]:
    """The questions that carry an answer, in identifier order.

    `Question` enforces that the three answer fields move together, so filtering on `response`
    is filtering on all of them.
    """
    return sorted(
        (question for question in questions if question.response is not None),
        key=lambda question: question.id,
    )


def answered_question_entries(questions: Sequence[Question]) -> list[dict[str, Any]]:
    """Answered questions as entries: the question, the answer, and who answered.

    ``response_origin`` is the provenance label — ``user_response`` marks a reviewer's answer
    (section 4.4) — so a downstream agent can distinguish "the reviewer answered this" from
    anything a document asserts. An open question does not travel: the downstream packages carry
    settlements, and an unanswered question is not one.
    """
    return [
        {
            "id": question.id,
            "question": neutralize_fence(question.question),
            "response": neutralize_fence(question.response or ""),
            "response_origin": question.response_origin.value if question.response_origin else None,
        }
        for question in questions
    ]
