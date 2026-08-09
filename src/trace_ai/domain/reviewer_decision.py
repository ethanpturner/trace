"""`ReviewerDecision`: what a human did, recorded rather than applied silently.

`data-model.md` section 25 is authoritative for the fields. Section 2.5 requires reviewer actions to
be recorded rather than silently overwriting generated content, and this object is that record. Both
structural checkpoints write them — context approval and finding approval — so the model belongs to
neither and is shared.

**`prior_value` and `updated_value` hold the delta, not a snapshot** (DEC-023). Reviewer edit rate
is a primary evaluation metric, and "the reviewer changed the severity and left everything else" is
a measurement; "the reviewer changed this finding" is not. `capture_edit` builds the pair from the
object before and after, so the delta is computed once rather than assembled by hand at each call
site — and so it cannot be captured after the edit has already been applied, which is the mistake
that turns an audit record into a record of nothing.

**"Request re-extraction" is `request_more_analysis`.** `agent-design.md` section 9 lists it among
the reviewer's actions at the context checkpoint and section 4.6 has no matching disposition. The
mapping is recorded here rather than in a new enum member, for the reason DEC-030 gives for the same
situation with severity: section 4.6 names the dispositions the *system records*, and section 9
names the actions a *reviewer takes*; the two do not correspond one to one, and adding a member for
every phrasing of an action would make the vocabulary a list of verbs. What re-extraction produces
is separately recorded — DEC-023 gives the re-extracted claims `supersedes_id`, so the decision and
its consequence are both traceable.

**`reviewer_id` is not authentication.** It is a configured local string, defaulting to the
operating-system username, recorded so evaluation can attribute decisions when more than one person
reviews the same benchmark. DEC-004 has no authentication to draw from, and treating this field as
though it did would be the kind of mistake that is invisible until it matters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Self

from pydantic import JsonValue, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ReviewDisposition
from trace_ai.domain.identifiers import (
    AssessmentId,
    ReviewerDecisionId,
    WorkflowRunId,
    parse_id,
)
from trace_ai.domain.vocabulary import VocabularyTerm

__all__ = ["ReviewerDecision", "changed_fields"]

# An edit says what changed, so both halves of the delta are required. The other dispositions
# record a judgment about an object rather than a change to it.
_REQUIRES_DELTA: Final = frozenset({ReviewDisposition.EDIT})

# Dispositions that change nothing about the object's content. A delta on one of these would be a
# record of a change that did not happen.
_FORBIDS_DELTA: Final = frozenset({ReviewDisposition.APPROVE, ReviewDisposition.REJECT})


def changed_fields(
    before: DomainModel, after: DomainModel
) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
    """The fields that differ between two states of one object, before and after.

    Returns the two halves of a DEC-023 delta. Comparison is over the serialized forms, so what is
    recorded is what would be persisted rather than what the objects hold in memory — an enum and
    its value compare equal in the record, which is the comparison a later reader makes.
    """
    old = before.model_dump(mode="json")
    new = after.model_dump(mode="json")
    names = [name for name in new if name in old and old[name] != new[name]]
    return ({name: old[name] for name in names}, {name: new[name] for name in names})


class ReviewerDecision(DomainModel):
    """A human decision affecting an assessment object (section 25)."""

    id: ReviewerDecisionId
    assessment_id: AssessmentId

    subject_type: VocabularyTerm
    """The kind of object reviewed. Normalized (DEC-036) and checked against `subject_id`."""

    subject_id: str
    disposition: ReviewDisposition

    prior_value: dict[str, JsonValue] | None = None
    """The changed fields as they were. The delta only, never a whole-object snapshot (DEC-023)."""

    updated_value: dict[str, JsonValue] | None = None
    """The same fields as they became."""

    rationale: str | None = None
    reviewer_id: str | None = None
    """A configured local string, not an authenticated identity (DEC-023)."""

    created_at: datetime
    workflow_run_id: WorkflowRunId | None = None

    @model_validator(mode="after")
    def _the_delta_matches_the_disposition(self) -> Self:
        """An edit says what changed; an approval says nothing changed.

        A recorded edit that cannot say what it changed is not an audit record — it is the silent
        overwrite section 2.5 forbids, with a row next to it.
        """
        if self.disposition in _REQUIRES_DELTA:
            missing = [
                name
                for name, value in (
                    ("prior_value", self.prior_value),
                    ("updated_value", self.updated_value),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"an {ReviewDisposition.EDIT} decision must carry {' and '.join(missing)}. "
                    f"An edit that cannot say what changed records that something was overwritten "
                    f"and nothing else (DEC-023)."
                )
        elif self.disposition in _FORBIDS_DELTA and (self.prior_value or self.updated_value):
            raise ValueError(
                f"a {self.disposition} decision changes no field, so it carries no delta. "
                f"A change to the object is an {ReviewDisposition.EDIT}."
            )
        return self

    @model_validator(mode="after")
    def _the_delta_describes_one_change(self) -> Self:
        """Both halves name the same fields. Otherwise the record says a field appeared or vanished,
        which is not something a reviewer edit can do to a frozen, schema-validated object."""
        if (
            self.prior_value is not None
            and self.updated_value is not None
            and set(self.prior_value) != set(self.updated_value)
        ):
            raise ValueError(
                f"prior_value names {sorted(self.prior_value)} and updated_value names "
                f"{sorted(self.updated_value)}; a delta describes the same fields on both sides"
            )
        return self

    @model_validator(mode="after")
    def _subject_reference_is_coherent(self) -> Self:
        """`subject_id` is an identifier naming the kind of object `subject_type` says.

        `SystemContext` is the exception the scheme already documents: it has no identifier, so a
        decision about a context names it some other way and this check does not apply.
        """
        if self.subject_type == "system_context":
            return self

        parsed = parse_id(self.subject_id)
        if self.subject_type != parsed.object_term:
            raise ValueError(
                f"subject_type is {self.subject_type!r} but subject_id {self.subject_id!r} names "
                f"{parsed.object_type}"
            )
        return self

    @classmethod
    def capture_edit(
        cls,
        *,
        decision_id: ReviewerDecisionId,
        before: DomainModel,
        after: DomainModel,
        subject_type: str,
        subject_id: str,
        created_at: datetime,
        assessment_id: AssessmentId | None = None,
        rationale: str | None = None,
        reviewer_id: str | None = None,
        workflow_run_id: WorkflowRunId | None = None,
    ) -> Self:
        """Record an edit by comparing the object before and after it.

        The delta is computed here rather than at the call site, because a call site that assembles
        it by hand can assemble it wrongly in a way nothing detects: after the edit is applied, the
        generated state is gone, and a `prior_value` copied from the edited object records that
        nothing changed. One implementation, taking both states, cannot be used that way.

        `assessment_id` defaults to the object's own, which is where it always comes from — passing
        it separately would be an opportunity to pass a different one.
        """
        prior, updated = changed_fields(before, after)
        if not prior:
            raise ValueError(
                "before and after are identical; there is no edit to record. A decision that "
                "changed nothing is an approval, not an edit."
            )
        owner = (
            assessment_id if assessment_id is not None else getattr(after, "assessment_id", None)
        )
        return cls.model_validate(
            {
                "id": decision_id,
                "assessment_id": owner,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "disposition": ReviewDisposition.EDIT,
                "prior_value": prior,
                "updated_value": updated,
                "rationale": rationale,
                "reviewer_id": reviewer_id,
                "created_at": created_at,
                "workflow_run_id": workflow_run_id,
            }
        )
