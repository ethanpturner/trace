"""The Evidence Assessment Validation node: the one section 3 used to leave out.

`agent-design.md` section 3 gave every other reasoning agent a deterministic node behind it —
Context Extraction has Context Validation, Threat Analysis has Threat Validation, Requirement and
Control Mapping has Mapping Validation — and evidence validation ran straight into Critical Review.
DEC-048 records that this was an omission rather than an intent, and that a node was built anyway
on the strength of two rules a diagram does not override: `data-model.md` section 33 requires
validation after model-generated structured output, and `agent-design.md` section 22 states that
agents never write authoritative records. Section 3 now draws it, and section 4 classifies it.

**This node owns the write.** `workflow/evidence_validation.py` contains no store write at all, so
persistence is unreachable except through here. That is the arrangement section 22's write model
describes, and it is the only one of the four validators for which it is literally true — the other
three validate objects their agents already persisted.

**It reports and routes; it corrects nothing.** Unlike Mapping Validation, which DEC-013 authorises
to downgrade an unsupported `unmet`, nothing here is authorised to change a classification. An
assessment that fails validation is refused and preserved, not adjusted into one that passes:
re-labelling a `supported` assessment as `unsupported` would turn a conclusion the agent asserted
into one nobody asserted, with a clean validation record.

**Four of section 14's six failure conditions are checkable here, and the two that are not are
named.** Evidence references that do not exist, unsupported claims marked supported, model-generated
text treated as source evidence, and contradictions present in the input and absent from the output
are all decidable. "The rationale misquotes or materially changes evidence" is decidable too and is
checked at the agent node, where the raw output still exists for `traces/`. "Evidence quantity is
mistaken for evidence quality" is a judgment about reasoning and no deterministic rule can catch it;
`evaluation-plan.md` section 7's classification accuracy is what would.

**A status transition is a table, not a write.** Section 14 lists "updated validation statuses"
among the agent's outputs, and applying one is the only state change this node makes to an object it
did not create. `PERMITTED_TRANSITIONS` names which moves are allowed; anything else is an error
rather than a silent overwrite, because a settled classification changing quietly is exactly what
this node exists to stop happening by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.base import now
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.control import Control
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.enums import SourceOrigin, ValidationStatus
from trace_ai.domain.evidence_assessment import (
    EVIDENCED_VALIDATION_STATUSES,
    EvidenceAssessment,
    SubjectType,
)
from trace_ai.domain.proposals.evidence_validation import promote_assessment
from trace_ai.domain.threat import Threat
from trace_ai.workflow.context_validation import ReviewTrigger
from trace_ai.workflow.errors import ErrorClass

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.evidence import EvidenceReference
    from trace_ai.domain.proposals.evidence_validation import (
        EvidenceAssessmentProposal,
        EvidenceValidationProposal,
    )
    from trace_ai.domain.source_observation import SourceObservation
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "PERMITTED_TRANSITIONS",
    "SECTION_14_TRIGGERS",
    "AssessmentValidationError",
    "EvidenceAssessmentValidationOutcome",
    "StatusTransition",
    "persist_assessments",
    "validate_assessments",
]

# `agent-design.md` section 14's human-review triggers, in the document's order.
SECTION_14_TRIGGERS: Final[tuple[str, ...]] = (
    "high_impact_conclusion_remains_contradictory",
    "evidence_is_sensitive_or_hard_to_interpret",
    "high_severity_finding_is_only_partially_supported",
    "inherited_control_needs_reviewer_knowledge",
)

# Which validation-status moves this node may apply. `not_evaluated` is where every object starts,
# so the first evaluation is unrestricted. A status may be re-applied unchanged, because a second
# run reaching the same conclusion is not a transition. `requires_confirmation` may go anywhere,
# because a confirmation arriving is precisely the event that resolves it.
#
# Everything else is refused. A settled classification moving to a different settled one is a
# reversal, and a reversal that happens silently is indistinguishable from the first classification
# never having been made.
PERMITTED_TRANSITIONS: Final[dict[ValidationStatus, frozenset[ValidationStatus]]] = {
    ValidationStatus.NOT_EVALUATED: frozenset(ValidationStatus),
    ValidationStatus.REQUIRES_CONFIRMATION: frozenset(ValidationStatus),
    ValidationStatus.SUPPORTED: frozenset({ValidationStatus.SUPPORTED}),
    ValidationStatus.PARTIALLY_SUPPORTED: frozenset({ValidationStatus.PARTIALLY_SUPPORTED}),
    ValidationStatus.UNSUPPORTED: frozenset({ValidationStatus.UNSUPPORTED}),
    ValidationStatus.CONTRADICTED: frozenset({ValidationStatus.CONTRADICTED}),
}

# The origins that mark a passage as material under review. Anything else was produced by the
# system rather than found in a document, and section 14 makes treating it as source evidence a
# failure condition.
SOURCE_ORIGINS: Final[frozenset[SourceOrigin]] = frozenset(
    {
        SourceOrigin.UPLOADED_DOCUMENT,
        SourceOrigin.STRUCTURED_INPUT,
        SourceOrigin.USER_RESPONSE,
        SourceOrigin.REQUIREMENTS_CATALOG,
    }
)

# Which model holds each subject type. Read once here rather than in each check, so a new subject
# type is one line rather than three branches.
_SUBJECT_MODELS: Final[dict[SubjectType, type[DomainModel]]] = {
    SubjectType.CONTEXT_CLAIM: ContextClaim,
    SubjectType.CONTROL: Control,
    SubjectType.CONTROL_MAPPING: ControlMapping,
    SubjectType.THREAT: Threat,
}


@dataclass(frozen=True, slots=True)
class AssessmentValidationError:
    """One problem with one proposed assessment, named precisely enough to fix."""

    position: int
    """Where in the response it appeared. Proposals carry no identifier, so this is the only
    handle on an assessment that has not been promoted."""

    subject_id: str
    field: str
    rule: str
    message: str
    error_class: ErrorClass = ErrorClass.SCHEMA_VALIDATION_FAILURE

    @property
    def retryable(self) -> bool:
        from trace_ai.workflow.errors import RETRYABLE

        return self.error_class in RETRYABLE

    def retry_instruction(self) -> str:
        return f"assessment {self.position} ({self.subject_id}).{self.field}: {self.message}"


@dataclass(frozen=True, slots=True)
class StatusTransition:
    """One object's validation status, before and after.

    Produced by validation and applied by `persist_assessments`. A transition the table does not
    permit never becomes one of these; it becomes an error.
    """

    subject_type: SubjectType
    subject_id: str
    from_status: ValidationStatus
    to_status: ValidationStatus


@dataclass(frozen=True, slots=True)
class EvidenceAssessmentValidationOutcome:
    """What validated, what did not, what statuses move, and why a person should look."""

    errors: tuple[AssessmentValidationError, ...] = ()
    triggers: tuple[ReviewTrigger, ...] = ()
    transitions: tuple[StatusTransition, ...] = ()
    ignored_contradiction_ids: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.blocking_errors

    @property
    def blocking_errors(self) -> tuple[AssessmentValidationError, ...]:
        return tuple(
            error
            for error in self.errors
            if error.error_class is not ErrorClass.INSUFFICIENT_EVIDENCE
        )

    @property
    def clean(self) -> bool:
        """Nothing to report. The expected shape when the documents settle what they settle."""
        return not (self.errors or self.triggers or self.ignored_contradiction_ids)

    def retry_instructions(self) -> tuple[str, ...]:
        return tuple(error.retry_instruction() for error in self.errors if error.retryable)


def _subject_errors(
    proposed: EvidenceAssessmentProposal,
    position: int,
    *,
    subjects: dict[str, DomainModel],
) -> list[AssessmentValidationError]:
    """The subject exists, and it is of the type the assessment declares.

    Both halves named in one message when the type is wrong, because "there is no such object" and
    "that object is something else" call for different corrections and the identifier alone does
    not say which one happened.
    """
    subject = subjects.get(proposed.subject_id)
    if subject is None:
        return [
            AssessmentValidationError(
                position=position,
                subject_id=proposed.subject_id,
                field="subject_id",
                rule="the subject resolves to an existing object (agent-design.md section 14)",
                message=(
                    f"{proposed.subject_id!r} is not an object in this assessment. An assessment "
                    f"of something that does not exist is an assessment of nothing."
                ),
                error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
            )
        ]

    expected = _SUBJECT_MODELS.get(proposed.subject_type)
    if expected is not None and not isinstance(subject, expected):
        return [
            AssessmentValidationError(
                position=position,
                subject_id=proposed.subject_id,
                field="subject_type",
                rule="the subject is of the declared type (agent-design.md section 14)",
                message=(
                    f"subject_type is {proposed.subject_type.value!r} but "
                    f"{proposed.subject_id!r} is a {type(subject).__name__}."
                ),
                error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
            )
        ]

    return []


def _evidence_errors(
    proposed: EvidenceAssessmentProposal,
    position: int,
    *,
    references: dict[str, EvidenceReference],
) -> list[AssessmentValidationError]:
    """Section 14's "evidence references do not exist", and its model-generated-text sibling."""
    errors: list[AssessmentValidationError] = []

    missing = sorted(set(proposed.evidence_ids) - set(references))
    if missing:
        errors.append(
            AssessmentValidationError(
                position=position,
                subject_id=proposed.subject_id,
                field="evidence_ids",
                rule="evidence references exist (agent-design.md section 14)",
                message=(
                    f"these evidence references are not in this assessment: {missing}. A citation "
                    f"nobody can resolve reads exactly like one that checks out."
                ),
                error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
            )
        )

    generated = sorted(
        evidence_id
        for evidence_id in proposed.evidence_ids
        if (reference := references.get(evidence_id)) is not None
        and reference.source_origin not in SOURCE_ORIGINS
    )
    if generated:
        errors.append(
            AssessmentValidationError(
                position=position,
                subject_id=proposed.subject_id,
                field="evidence_ids",
                rule="model-generated text is not source evidence "
                "(agent-design.md section 14, Failure conditions)",
                message=(
                    f"these references were produced by the system rather than found in the "
                    f"material under review: {generated}. Citing one is the assessment "
                    f"corroborating itself."
                ),
            )
        )

    return errors


def _status_errors(
    proposed: EvidenceAssessmentProposal, position: int
) -> list[AssessmentValidationError]:
    """Section 14's "unsupported claims are marked supported", enforced structurally.

    `EvidenceAssessment` refuses this at construction too. It is checked here because the proposal
    has not been promoted yet, so the refusal arrives as a named error with a position rather than
    as a pydantic traceback from inside the transaction that was about to write it.
    """
    if proposed.validation_status in EVIDENCED_VALIDATION_STATUSES and not proposed.evidence_ids:
        return [
            AssessmentValidationError(
                position=position,
                subject_id=proposed.subject_id,
                field="validation_status",
                rule="a status that asserts something cites a passage "
                "(agent-design.md section 14; DEC-009)",
                message=(
                    f"validation_status {proposed.validation_status.value!r} cites no evidence. "
                    f"A conclusion resting on nothing is 'unsupported', not 'supported'."
                ),
            )
        ]
    return []


def _contradiction_errors(
    proposed: EvidenceAssessmentProposal,
    position: int,
    *,
    observations: dict[str, SourceObservation],
) -> list[AssessmentValidationError]:
    """A named contradiction resolves, and it names the passages the assessment cites."""
    missing = sorted(set(proposed.contradictions) - set(observations))
    if missing:
        return [
            AssessmentValidationError(
                position=position,
                subject_id=proposed.subject_id,
                field="contradictions",
                rule="contradictions resolve to recorded observations (DEC-021)",
                message=f"these contradictions are not recorded in this assessment: {missing}.",
                error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
            )
        ]
    return []


def _transition_error(
    proposed: EvidenceAssessmentProposal,
    position: int,
    *,
    current: ValidationStatus,
) -> AssessmentValidationError | None:
    """Whether the status move the assessment implies is one the table permits."""
    if proposed.validation_status in PERMITTED_TRANSITIONS[current]:
        return None
    return AssessmentValidationError(
        position=position,
        subject_id=proposed.subject_id,
        field="validation_status",
        rule="validation-status transitions are a permitted set, not a write "
        "(agent-design.md section 14, Outputs)",
        message=(
            f"{proposed.subject_id} is {current.value!r} and this assessment would make it "
            f"{proposed.validation_status.value!r}. A settled classification is not reversed "
            f"here: that is a reviewer's decision or a later run's, and a silent reversal is "
            f"indistinguishable from the first classification never having been made."
        ),
    )


def _triggers(
    proposal: EvidenceValidationProposal, *, subjects: dict[str, DomainModel]
) -> list[ReviewTrigger]:
    """Section 14's human-review triggers, for the ones a rule can detect."""
    triggers: list[ReviewTrigger] = []

    contradictory = sorted(
        {
            assessed.subject_id
            for assessed in proposal.assessments
            if assessed.validation_status is ValidationStatus.CONTRADICTED
        }
    )
    if contradictory:
        triggers.append(
            ReviewTrigger(
                name=SECTION_14_TRIGGERS[0],
                object_ids=tuple(contradictory),
                detail=(
                    "Passages disagree and no rule here chooses between them. Which statement is "
                    "authoritative is a question for someone who can ask."
                ),
            )
        )

    partial = sorted(
        {
            assessed.subject_id
            for assessed in proposal.assessments
            if assessed.validation_status is ValidationStatus.PARTIALLY_SUPPORTED
        }
    )
    if partial:
        triggers.append(
            ReviewTrigger(
                name=SECTION_14_TRIGGERS[2],
                object_ids=tuple(partial),
                detail=(
                    "A conclusion is only partly carried by its evidence. Whether the supported "
                    "part is enough is a judgment, and severity is the reviewer's (DEC-030)."
                ),
            )
        )

    inherited = sorted(
        {
            assessed.subject_id
            for assessed in proposal.assessments
            if isinstance(subject := subjects.get(assessed.subject_id), Control)
            and subject.control_type.value == "inherited"
            and not subject.is_documented_inheritance
        }
    )
    if inherited:
        triggers.append(
            ReviewTrigger(
                name=SECTION_14_TRIGGERS[3],
                object_ids=tuple(inherited),
                detail=(
                    "An inherited control the documentation does not establish (DEC-026). "
                    "Confirming it needs knowledge of the platform, not of the documents."
                ),
            )
        )

    return triggers


def validate_assessments(
    proposal: EvidenceValidationProposal,
    *,
    subjects: Sequence[DomainModel],
    references: Sequence[EvidenceReference],
    observations: Sequence[SourceObservation] = (),
    supplied_contradiction_ids: Sequence[str] = (),
) -> EvidenceAssessmentValidationOutcome:
    """Validate a proposed assessment set. Returns problems, transitions, and triggers.

    Nothing is written and nothing is corrected. `persist_assessments` applies the result, and it
    refuses to run against an outcome that did not validate.
    """
    by_id: dict[str, DomainModel] = {str(getattr(obj, "id", "")): obj for obj in subjects}
    reference_by_id = {reference.id: reference for reference in references}
    observation_by_id = {observation.id: observation for observation in observations}

    errors: list[AssessmentValidationError] = []
    transitions: list[StatusTransition] = []

    for position, proposed in enumerate(proposal.assessments):
        subject_problems = _subject_errors(proposed, position, subjects=by_id)
        errors.extend(subject_problems)
        errors.extend(_evidence_errors(proposed, position, references=reference_by_id))
        errors.extend(_status_errors(proposed, position))
        errors.extend(_contradiction_errors(proposed, position, observations=observation_by_id))

        if subject_problems:
            continue

        subject = by_id[proposed.subject_id]
        current = getattr(subject, "validation_status", None)
        if not isinstance(current, ValidationStatus):
            # Only `Control` carries a validation status today. A subject without one has no
            # transition to check and no status to update, which is a fact about the schema
            # rather than a problem with the assessment.
            continue

        problem = _transition_error(proposed, position, current=current)
        if problem is not None:
            errors.append(problem)
        elif current is not proposed.validation_status:
            transitions.append(
                StatusTransition(
                    subject_type=proposed.subject_type,
                    subject_id=proposed.subject_id,
                    from_status=current,
                    to_status=proposed.validation_status,
                )
            )

    named = {
        contradiction
        for assessed in proposal.assessments
        for contradiction in assessed.contradictions
    }
    ignored = tuple(sorted(set(supplied_contradiction_ids) - named))

    return EvidenceAssessmentValidationOutcome(
        errors=tuple(errors),
        triggers=tuple(_triggers(proposal, subjects=by_id)),
        transitions=tuple(transitions),
        ignored_contradiction_ids=ignored,
    )


class UnvalidatedWriteError(RuntimeError):
    """Persistence was attempted for a proposal that did not validate."""

    def __init__(self, errors: Sequence[AssessmentValidationError]) -> None:
        super().__init__(
            f"{len(errors)} assessment(s) failed validation and none was written. An agent's "
            f"output becomes an authoritative record only after a deterministic node accepts it "
            f"(agent-design.md section 22; data-model.md section 33)."
        )
        self.errors = tuple(errors)


def persist_assessments(
    handle: AssessmentHandle,
    proposal: EvidenceValidationProposal,
    outcome: EvidenceAssessmentValidationOutcome,
) -> tuple[list[EvidenceAssessment], list[Control]]:
    """Write the validated assessments and apply their status transitions.

    Refuses outright when validation failed, rather than writing the assessments that happened to
    pass: a partial write leaves the run reporting a mixture nobody decided on, and the retry that
    follows would re-propose the failed ones against a store that already holds their siblings.

    Allocation and insert share one transaction, because DEC-018 takes the identifier from a
    counter at insert and a promoted assessment that was never saved would consume one.
    """
    if not outcome.valid:
        raise UnvalidatedWriteError(outcome.blocking_errors)

    repository = handle.objects
    stamped = now()
    written: list[EvidenceAssessment] = []
    updated: list[Control] = []

    moves = {transition.subject_id: transition for transition in outcome.transitions}

    with repository.transaction():
        for proposed in proposal.assessments:
            assessed = promote_assessment(
                proposed,
                assessment_id=repository.allocate("eas"),
                parent_assessment_id=handle.assessment_id,
                created_at=stamped,
            )
            repository.save(assessed)
            written.append(assessed)

        for subject_id, transition in sorted(moves.items()):
            if transition.subject_type is not SubjectType.CONTROL:
                continue
            control = repository.get(Control, subject_id)
            # `model_validate` rather than `model_copy`: domain objects are frozen, and this is
            # the path on which a computed value re-enters the schema (`CLAUDE.md`).
            revised = Control.model_validate(
                {**control.model_dump(), "validation_status": transition.to_status}
            )
            repository.save(revised)
            updated.append(revised)

    return written, updated
