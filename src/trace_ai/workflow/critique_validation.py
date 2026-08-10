"""Critique validation and recommendation routing: the boundary that keeps the critic bounded.

`agent-design.md` section 15 gives the critic recommendation authority only, and section 27 states
the consequence with a worked example that is exactly this node's job: "The critic may recommend
that a threat be reconsidered. It may not automatically start an unlimited threat-generation and
criticism loop."

**A recommendation is recorded, never executed.** A critique produces a `RoutedRecommendation`
against its target and the target is not touched. `data-model.md` section 32 requires the lineage
from threat through mapping and evidence assessment to critique and finding to stay traceable, and
an in-place mutation destroys it: the object a critique was raised against stops existing the
moment the critique is applied to it, so nothing can later say what was criticised.

**Loop prevention is a counter and a routing decision, in plain Python.** A recommendation whose
effect would be to re-enter a phase the run has already passed is a re-invocation. Those are
counted, and past the budget they are routed to human review rather than executed. There is no
orchestration framework to configure — DEC-016 settled that, and DEC-007's LangGraph proposal was
rejected rather than left open — so this survives whatever the orchestrator becomes.

**Volume is checked as a ratio, and it is the one section 15 failure condition that needs a
number.** "Generates large quantities of superficial criticism" cannot be decided per critique;
a single critique is never disproportionate. Measured against the count of objects the critic was
shown, it becomes a question with an answer. The threshold is a parameter with a stated default
rather than a constant nobody chose.

**This node owns the write**, on DEC-048's argument applied again: `workflow/critical_review.py`
contains no store write, so a critique reaches persistence only through validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.critique import (
    SEVERITY_CRITIQUE_TYPES,
    Critique,
    CritiqueSubjectType,
    CritiqueType,
    RecommendedAction,
)
from trace_ai.domain.enums import Severity
from trace_ai.domain.proposals.critical_review import promote_critique
from trace_ai.workflow.context_validation import ReviewTrigger
from trace_ai.workflow.errors import ErrorClass
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.proposals.critical_review import (
        CriticalReviewProposal,
        CritiqueProposal,
    )
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "DEFAULT_MAXIMUM_REINVOCATIONS",
    "DEFAULT_VOLUME_RATIO",
    "REINVOKING_ACTIONS",
    "SECTION_15_TRIGGERS",
    "CritiqueValidationError",
    "CritiqueValidationOutcome",
    "RoutedRecommendation",
    "UnvalidatedWriteError",
    "persist_critiques",
    "validate_critiques",
]

# `agent-design.md` section 15's human-review triggers, in the document's order.
SECTION_15_TRIGGERS: Final[tuple[str, ...]] = (
    "critic_challenges_a_likely_high_severity_conclusion",
    "two_agents_produce_materially_conflicting_interpretations",
    "a_reviewer_decision_would_affect_multiple_findings",
    "the_critic_identifies_a_major_architecture_gap",
)

# The two actions whose effect is to send work back. `keep` changes nothing, and `reject` and
# `merge` are Finding Consolidation's to apply going forward -- neither re-enters a passed phase.
REINVOKING_ACTIONS: Final[frozenset[RecommendedAction]] = frozenset(
    {RecommendedAction.REVISE, RecommendedAction.INVESTIGATE}
)

# Which phase a recommendation about each subject would send work back to. `documentation_gap` and
# `finding` are absent: both are consumed by Finding Consolidation, which runs *after* critical
# review, so a recommendation about one routes forward rather than back.
_PHASE_BY_SUBJECT: Final[dict[CritiqueSubjectType, Phase]] = {
    CritiqueSubjectType.THREAT: Phase.THREAT_GENERATION,
    CritiqueSubjectType.CONTROL: Phase.REQUIREMENT_AND_CONTROL_MAPPING,
    CritiqueSubjectType.CONTROL_MAPPING: Phase.REQUIREMENT_AND_CONTROL_MAPPING,
    CritiqueSubjectType.EVIDENCE_ASSESSMENT: Phase.EVIDENCE_VALIDATION,
}

# How many re-invocations one review may ask for before the rest go to a person. Two, because the
# number's job is to be small: section 27's concern is an unbounded loop, and a review that wants
# three separate phases re-run is a review the reviewer should see rather than one the orchestrator
# should act on.
DEFAULT_MAXIMUM_REINVOCATIONS: Final = 2

# Critiques per reviewed object, above which the volume is reported. One critique per object is
# already a review that found something wrong with everything it was shown, which is what section
# 15's superficial-volume failure condition describes.
DEFAULT_VOLUME_RATIO: Final = 1.0


@dataclass(frozen=True, slots=True)
class CritiqueValidationError:
    """One problem with one proposed critique."""

    position: int
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
        return f"critique {self.position} ({self.subject_id}).{self.field}: {self.message}"


@dataclass(frozen=True, slots=True)
class RoutedRecommendation:
    """One recommendation, recorded against its target and applied to nothing.

    `executable` is the routing decision, not permission: a recommendation is executable when it
    does not re-enter a passed phase, or when it does and the re-invocation budget still has room.
    Past the budget it is `False` and the reviewer decides (section 27).
    """

    position: int
    subject_type: CritiqueSubjectType
    subject_id: str
    action: RecommendedAction
    reinvokes_phase: Phase | None
    executable: bool
    reason: str


@dataclass(frozen=True, slots=True)
class CritiqueValidationOutcome:
    """What validated, what routes where, and why a person should look."""

    errors: tuple[CritiqueValidationError, ...] = ()
    triggers: tuple[ReviewTrigger, ...] = ()
    recommendations: tuple[RoutedRecommendation, ...] = ()
    duplicate_keys: tuple[tuple[str, str], ...] = ()
    volume_ratio: float = 0.0
    volume_exceeded: bool = False

    @property
    def valid(self) -> bool:
        return not self.blocking_errors

    @property
    def blocking_errors(self) -> tuple[CritiqueValidationError, ...]:
        return tuple(
            error
            for error in self.errors
            if error.error_class is not ErrorClass.INSUFFICIENT_EVIDENCE
        )

    @property
    def clean(self) -> bool:
        """Nothing to report. Zero critiques reaches here, and must."""
        return not (self.errors or self.triggers or self.duplicate_keys or self.volume_exceeded)

    @property
    def deferred_to_review(self) -> tuple[RoutedRecommendation, ...]:
        """The recommendations the budget stopped. A person decides these, not the orchestrator."""
        return tuple(
            recommendation
            for recommendation in self.recommendations
            if recommendation.reinvokes_phase is not None and not recommendation.executable
        )

    def retry_instructions(self) -> tuple[str, ...]:
        return tuple(error.retry_instruction() for error in self.errors if error.retryable)


class UnvalidatedWriteError(RuntimeError):
    """Persistence was attempted for a proposal that did not validate."""

    def __init__(self, errors: Sequence[CritiqueValidationError]) -> None:
        super().__init__(
            f"{len(errors)} critique(s) failed validation and none was written. An agent's "
            f"output becomes an authoritative record only after a deterministic node accepts it "
            f"(agent-design.md section 22)."
        )
        self.errors = tuple(errors)


def _target_errors(
    proposed: CritiqueProposal,
    position: int,
    *,
    subjects: dict[str, DomainModel],
    expected: dict[CritiqueSubjectType, type[DomainModel]],
) -> list[CritiqueValidationError]:
    """Section 15's "critiques lack target objects", from both sides."""
    subject = subjects.get(proposed.subject_id)
    if subject is None:
        return [
            CritiqueValidationError(
                position=position,
                subject_id=proposed.subject_id,
                field="subject_id",
                rule="critiques name a target object that exists (agent-design.md section 15)",
                message=(
                    f"{proposed.subject_id!r} is not an object in this assessment. A critique of "
                    f"nothing cannot be traced to a specific issue."
                ),
                error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
            )
        ]

    model = expected.get(proposed.subject_type)
    if model is not None and not isinstance(subject, model):
        return [
            CritiqueValidationError(
                position=position,
                subject_id=proposed.subject_id,
                field="subject_type",
                rule="the target is of the declared type (agent-design.md section 15)",
                message=(
                    f"subject_type is {proposed.subject_type.value!r} but "
                    f"{proposed.subject_id!r} is a {type(subject).__name__}."
                ),
                error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
            )
        ]

    return []


def _severity_error(
    proposed: CritiqueProposal, position: int, *, subject: DomainModel | None
) -> CritiqueValidationError | None:
    """DEC-049's rule, applied where the subject's severity can be looked up."""
    if proposed.critique_type not in SEVERITY_CRITIQUE_TYPES:
        return None

    severity = getattr(subject, "severity", None)
    if isinstance(severity, Severity) and severity is not Severity.UNASSIGNED:
        return None

    stated = "no severity" if severity is None else f"severity {Severity.UNASSIGNED.value!r}"
    return CritiqueValidationError(
        position=position,
        subject_id=proposed.subject_id,
        field="critique_type",
        rule="a severity critique needs a severity somebody assigned (DEC-030, DEC-049)",
        message=(
            f"critique_type {proposed.critique_type.value!r} against {proposed.subject_id!r}, "
            f"which carries {stated}. The reviewer assigns a finding's severity at checkpoint 2, "
            f"which runs after critical review, so there is nothing here to overstate."
        ),
    )


def _route(
    proposed: CritiqueProposal, position: int, *, budget_remaining: int
) -> RoutedRecommendation:
    """Where one recommendation goes, and whether the budget lets it go there (section 27)."""
    phase = (
        _PHASE_BY_SUBJECT.get(proposed.subject_type)
        if proposed.recommended_action in REINVOKING_ACTIONS
        else None
    )

    if phase is None:
        return RoutedRecommendation(
            position=position,
            subject_type=proposed.subject_type,
            subject_id=proposed.subject_id,
            action=proposed.recommended_action,
            reinvokes_phase=None,
            executable=True,
            reason=(
                "the recommendation is applied going forward, by Finding Consolidation or the "
                "reviewer, and re-enters no phase this run has passed."
            ),
        )

    within = budget_remaining > 0
    return RoutedRecommendation(
        position=position,
        subject_type=proposed.subject_type,
        subject_id=proposed.subject_id,
        action=proposed.recommended_action,
        reinvokes_phase=phase,
        executable=within,
        reason=(
            f"acting on this would re-enter {phase.value}, which this run has passed. "
            + (
                "The re-invocation budget has room."
                if within
                else "The re-invocation budget is spent, so a reviewer decides rather than the "
                "orchestrator (agent-design.md section 27)."
            )
        ),
    )


def _triggers(
    proposal: CriticalReviewProposal, *, recommendations: Sequence[RoutedRecommendation]
) -> list[ReviewTrigger]:
    """Section 15's human-review triggers, for the ones a rule can detect."""
    triggers: list[ReviewTrigger] = []

    severity_challenges = sorted(
        {
            critique.subject_id
            for critique in proposal.critiques
            if critique.critique_type in SEVERITY_CRITIQUE_TYPES
        }
    )
    if severity_challenges:
        triggers.append(
            ReviewTrigger(
                name=SECTION_15_TRIGGERS[0],
                object_ids=tuple(severity_challenges),
                detail=(
                    "The critic disagrees with a severity. Severity is the reviewer's judgment "
                    "(DEC-030), so a disagreement about one is theirs to settle."
                ),
            )
        )

    conflicting = sorted(
        {
            critique.subject_id
            for critique in proposal.critiques
            if critique.critique_type
            in {CritiqueType.CONTRADICTORY_ANALYSIS, CritiqueType.UNSUPPORTED_CLAIM}
        }
    )
    if conflicting:
        triggers.append(
            ReviewTrigger(
                name=SECTION_15_TRIGGERS[1],
                object_ids=tuple(conflicting),
                detail=(
                    "The critic and an earlier agent read the same evidence differently. No rule "
                    "here decides which reading is right."
                ),
            )
        )

    deferred = sorted(
        {
            recommendation.subject_id
            for recommendation in recommendations
            if recommendation.reinvokes_phase is not None and not recommendation.executable
        }
    )
    if deferred:
        triggers.append(
            ReviewTrigger(
                name=SECTION_15_TRIGGERS[2],
                object_ids=tuple(deferred),
                detail=(
                    "A recommendation would re-run an earlier phase and the re-invocation budget "
                    "is spent. Whether the work is worth redoing is a person's call."
                ),
            )
        )

    architecture_gaps = sorted(
        {
            critique.subject_id
            for critique in proposal.critiques
            if critique.critique_type is CritiqueType.MISSING_EVIDENCE
        }
    )
    if architecture_gaps:
        triggers.append(
            ReviewTrigger(
                name=SECTION_15_TRIGGERS[3],
                object_ids=tuple(architecture_gaps),
                detail=(
                    "The critic says the analysis rests on evidence that is not there. That is "
                    "either a gap in the documentation or a gap in the assessment."
                ),
            )
        )

    return triggers


def validate_critiques(
    proposal: CriticalReviewProposal,
    *,
    subjects: Sequence[DomainModel],
    subject_models: dict[CritiqueSubjectType, type[DomainModel]],
    reviewed_object_count: int,
    maximum_reinvocations: int = DEFAULT_MAXIMUM_REINVOCATIONS,
    volume_ratio: float = DEFAULT_VOLUME_RATIO,
) -> CritiqueValidationOutcome:
    """Validate a proposed critique set and route its recommendations. Nothing is executed.

    `subject_models` maps each subject type to the model that holds it, supplied by the caller so
    this module imports no domain object it does not otherwise need and a subject type added later
    is one entry rather than a branch.
    """
    by_id: dict[str, DomainModel] = {str(getattr(obj, "id", "")): obj for obj in subjects}

    errors: list[CritiqueValidationError] = []
    recommendations: list[RoutedRecommendation] = []
    reinvocations = 0

    for position, proposed in enumerate(proposal.critiques):
        target_problems = _target_errors(
            proposed, position, subjects=by_id, expected=subject_models
        )
        errors.extend(target_problems)

        problem = _severity_error(proposed, position, subject=by_id.get(proposed.subject_id))
        if problem is not None:
            errors.append(problem)

        routed = _route(proposed, position, budget_remaining=maximum_reinvocations - reinvocations)
        if routed.reinvokes_phase is not None and routed.executable:
            reinvocations += 1
        recommendations.append(routed)

    seen: dict[tuple[str, str], int] = {}
    for critique in proposal.critiques:
        key = (critique.subject_id, critique.critique_type.value)
        seen[key] = seen.get(key, 0) + 1
    duplicates = tuple(sorted(key for key, count in seen.items() if count > 1))

    # Zero reviewed objects would divide by zero, and it is not a state the critic can be in: the
    # review group always contains at least the threat. Guarded rather than assumed.
    ratio = len(proposal.critiques) / reviewed_object_count if reviewed_object_count else 0.0

    return CritiqueValidationOutcome(
        errors=tuple(errors),
        triggers=tuple(_triggers(proposal, recommendations=recommendations)),
        recommendations=tuple(recommendations),
        duplicate_keys=duplicates,
        volume_ratio=ratio,
        volume_exceeded=ratio > volume_ratio,
    )


def persist_critiques(
    handle: AssessmentHandle,
    proposal: CriticalReviewProposal,
    outcome: CritiqueValidationOutcome,
) -> list[Critique]:
    """Write the validated critiques. Targets are read and never written.

    Refuses outright when validation failed, for the reason `persist_assessments` does: a partial
    write leaves a mixture nobody decided on, and the retry re-proposes the failures against a
    store already holding their siblings.

    Nothing in this function loads a target object, and that is the enforcement of section 15's
    no-rewrite prohibition: lineage from a critique to what it criticises is a reference, and a
    mutation would replace the thing the reference points at.
    """
    if not outcome.valid:
        raise UnvalidatedWriteError(outcome.blocking_errors)

    repository = handle.objects
    written: list[Critique] = []

    with repository.transaction():
        for proposed in proposal.critiques:
            critique = promote_critique(
                proposed,
                critique_id=repository.allocate("crq"),
                assessment_id=handle.assessment_id,
            )
            repository.save(critique)
            written.append(critique)

    return written
