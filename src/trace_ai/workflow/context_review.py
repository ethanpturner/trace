"""Checkpoint 1: the context approval gate, and the package a reviewer decides from.

`current-architecture.md` section 8 gives the purpose — prevent downstream analysis from being
built on incorrect architecture assumptions — and `agent-design.md` section 9 states the workflow
rule without qualification: threat analysis does not begin until the context checkpoint is
approved. `workflow/checkpoint.py` supplies the machinery both checkpoints share; this module
supplies what is specific to the first one, which is the content of the package and the gate.

**The gate is not a check that could be skipped; it is the node's return value.**
`ContextReviewNode.run` names the `SystemContext` among the objects awaiting a decision whenever
`is_approved` is false, and the orchestrator advances only when nothing is awaiting one. There is no
flag, no configuration field (DEC-012 removed the one that existed), and no argument — and because
the guard reads `approved_at`/`approved_by` rather than counting decisions, a `ReviewerDecision`
written directly against the context does not get past it either. That is DEC-005's "structural"
expressed as a control flow with nowhere to put an exception.

**Evidence travels with the claim.** `data-model.md` section 2.2 requires conclusions to link to
specific source locations, and a reviewer cannot confirm a claim without reading the passage it
rests on. Every documented and inferred claim carries its excerpts, and every excerpt is labelled
`quoted untrusted source content` — so a reviewer meeting the ForgeFlow injection fixture meets it
framed as data. The text itself is verbatim: a reviewer deciding whether a document tries to
instruct its reader needs to see what it actually says.

**What is documented is kept apart from what is not.** `current-architecture.md` section 5.5 says
the system does not silently convert an interpretation into a confirmed fact, and this is the
checkpoint where that distinction earns its keep: `claims_by_status` groups by `ClaimStatus`, and
the package reports the four non-documented groups separately rather than presenting one
undifferentiated list a tired reviewer approves in a block.

**Approval is refused, never deferred, while something blocking is outstanding.** A blocking
question is one the extraction said the analysis cannot proceed without; a blocking validation error
is one the application already knows makes an object wrong. Approving over either would record a
reviewer confirming objects nobody could confirm, and the refusal names what is outstanding rather
than saying no.

**Rejection stops the run; it does not route backwards.** DEC-038 settles what "request
re-extraction" means: a new `WorkflowRun` for the same assessment, not a transition from
`human_context_review` back to `context_extraction`. The decision is recorded here with disposition
`request_more_analysis`, which is what connects the two runs — and `re_extraction_feedback` is how
the reviewer's rationale reaches the next attempt, in the trusted half of the prompt, because
DEC-013 puts `reviewer_edit` among the origins that are not material under review.

**Every mutating action leaves a record, and the record carries the delta.** `data-model.md`
section 2.5 forbids *silently* overwriting generated content — the load-bearing word is *silently* —
so an edit mutates the object in place under the same identifier and writes a `ReviewerDecision`
carrying only the fields that changed, before and after (DEC-023). That is what keeps the generated
value recoverable after the object has moved on, and what makes reviewer edit rate computable per
field rather than per object. `supersedes_id` is not used here: it records a generated object
replacing a generated one, and its case is re-extraction.

**Approval mints the revision** (DEC-040). Version 1 is the generated baseline and is never
approved; version 2 is the baseline a person approved, and its membership is recomputed from the
store — so a reviewer-added object reaches it and a reviewer-rejected one does not. Nothing else in
the model is versioned.

This module is at `workflow/` rather than at the `application/` path the issue named: there is no
`application` package, and the two nodes either side of this one — `context_extraction.py` and
`context_validation.py` — are here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.enums import ObjectStatus, ReviewDisposition, SourceOrigin
from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.identifiers import PREFIXES, parse_id
from trace_ai.domain.question import Question, QuestionStatus, order_for_review
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.domain.source_document import SourceDocument
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.domain.system_context import SystemContext
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.services.evidence.index import EvidenceNotFoundError
from trace_ai.workflow.checkpoint import CheckpointNode, build_review_package
from trace_ai.workflow.nodes import NodeResult
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from pydantic import JsonValue

    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.workflow.checkpoint import ReviewPackage
    from trace_ai.workflow.context_validation import (
        ContextValidationOutcome,
        ReviewTrigger,
        ValidationError,
    )
    from trace_ai.workflow.nodes import NodeContext

__all__ = [
    "CONTEXT_OBJECT_TYPES",
    "NODE_NAME",
    "UNTRUSTED_LABEL",
    "ApprovalRefusedError",
    "ClaimPresentation",
    "ContextReviewNode",
    "ContextReviewPackage",
    "ContradictionResolution",
    "QuotedExcerpt",
    "ReviewerActionError",
    "add_context_object",
    "answer_question",
    "apply_edit",
    "approve_context",
    "approved_membership",
    "attach_evidence",
    "build_context_review_package",
    "confirm_assumption",
    "current_system_context",
    "decide_object",
    "re_extraction_feedback",
    "request_re_extraction",
    "resolve_contradiction",
    "system_context_key",
]

# Which `SystemContext` identifier list each presentation group fills. One mapping, so the package
# and the approved revision cannot disagree about which objects belong to which list.
_LIST_BY_GROUP: Final[dict[str, str]] = {
    "components": "component_ids",
    "actors": "actor_ids",
    "assets": "asset_ids",
    "data_flows": "data_flow_ids",
    "trust_boundaries": "trust_boundary_ids",
}

NODE_NAME: Final = "human-context-review"

# How every excerpt in the package is labelled. A reviewer reading
# `demo/forgeflow/input/sample-repository-notes.md` meets a block that addresses them directly; what
# stops it being read as instruction is that it arrives inside something that says what it is.
UNTRUSTED_LABEL: Final = "quoted untrusted source content"

# The five object types the extractor produces, in the order the package presents them. Grouped by
# type because that is how a reviewer checks an architecture — all the components, then all the
# flows — rather than in allocation order, which interleaves them.
CONTEXT_OBJECT_TYPES: Final[tuple[tuple[str, type[Any]], ...]] = (
    ("components", Component),
    ("actors", Actor),
    ("assets", Asset),
    ("data_flows", DataFlow),
    ("trust_boundaries", TrustBoundary),
)

# The statuses that carry an assertion the documents support. Everything else is an interpretation,
# and section 5.5 is about not letting the two blur.
_DOCUMENTED: Final = frozenset({ClaimStatus.DOCUMENTED})


class ApprovalRefusedError(RuntimeError):
    """Approval attempted while something blocking is outstanding, with what named.

    A refusal rather than a warning: an approval recorded over a blocking error is a reviewer
    confirming an object the application already knows is wrong, and the record would not say so.
    """

    def __init__(self, blockers: Sequence[str]) -> None:
        listed = "\n  - ".join(blockers)
        super().__init__(
            f"the context cannot be approved while {len(blockers)} item(s) are outstanding:\n"
            f"  - {listed}"
        )
        self.blockers = tuple(blockers)


def system_context_key(context: SystemContext) -> str:
    """How a `SystemContext` is named where an identifier is expected.

    It has none: DEC-034 keys it by `(assessment_id, version)` because it is addressed by its
    position in a sequence. This renders that pair, the same way the store's row key does, so a
    `ReviewerDecision` about a context and the row it concerns agree on what they are talking about.
    """
    return f"{context.assessment_id}@v{context.version}"


def current_system_context(handle: AssessmentHandle) -> SystemContext:
    """The latest revision. A checkpoint is always about the most recent one."""
    revisions = sorted(handle.objects.list(SystemContext), key=lambda item: item.version)
    if not revisions:
        raise ValueError(
            "this assessment has no extracted context, so there is nothing to review. A run that "
            "reached the checkpoint produced one."
        )
    return revisions[-1]


@dataclass(frozen=True, slots=True)
class QuotedExcerpt:
    """One source passage, labelled as what it is.

    The text is verbatim. Neutralising it would be the wrong trade here: the prompt fence exists
    because a model may act on what it reads, and a reviewer deciding whether a document tries to
    instruct its reader has to see the instruction.
    """

    evidence_id: str
    document: str | None
    location: str
    text: str
    label: str = UNTRUSTED_LABEL

    def rendered(self) -> str:
        """The excerpt with its label and provenance, for whatever renders the package."""
        where = " ".join(part for part in (self.document, self.location) if part)
        heading = f"[{self.label} — {self.evidence_id}{f', {where}' if where else ''}]"
        return f"{heading}\n{self.text}"


@dataclass(frozen=True, slots=True)
class ClaimPresentation:
    """One claim with the passages it rests on.

    A claim and its evidence are one thing to a reviewer and two objects to the store, and the
    package is where they are put back together. `excerpts` is empty for an `assumed` or `unknown`
    claim, which is correct and not a gap: DEC-009 makes those the statuses that cite nothing.
    """

    claim: ContextClaim
    excerpts: tuple[QuotedExcerpt, ...] = ()

    @property
    def id(self) -> str:
        return self.claim.id

    @property
    def status(self) -> ClaimStatus:
        return self.claim.status

    @property
    def is_documented(self) -> bool:
        return self.claim.status in _DOCUMENTED

    @property
    def cites_evidence(self) -> bool:
        return bool(self.excerpts)


@dataclass(frozen=True, slots=True)
class ContextReviewPackage:
    """Everything checkpoint 1 shows, derived from the run and stored nowhere.

    Section 31 makes the point: the package is derived, so the pause mechanism presupposes no
    interface. A stored package would be a second copy of objects that already exist and would go
    stale the moment a reviewer edited one.
    """

    package: ReviewPackage[DomainModel]
    system_context: SystemContext
    objects_by_type: dict[str, tuple[DomainModel, ...]]
    claims: tuple[ClaimPresentation, ...]
    questions: tuple[Question, ...]
    """Open questions, blocking first, then by priority (`order_for_review`)."""

    triggers: tuple[ReviewTrigger, ...] = ()
    outstanding_errors: tuple[ValidationError, ...] = ()
    injection_attempts: tuple[SourceObservation, ...] = ()
    """Injection attempts the extraction recorded about the supplied documents (DEC-075).

    Surfacing them is detection made visible: the reviewer is told which document tried to inject
    and what it attempted, framed as an observation about the document rather than an instruction
    to anyone. An attempt here does not block approval — it triages attention — but a subject
    extracted from a flagged document also carries an `injection_flag` reason."""

    reasons_by_object_id: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Routing reasons per subject (DEC-062), derived from persisted state and stored nowhere.

    A subject absent from this map has no reasons, which is routine, not exempt: it still needs a
    decision. The values are `ReasonCode` strings, kept as strings so the package carries no
    import an interface has to resolve."""

    def reasons_for(self, object_id: str) -> tuple[str, ...]:
        return self.reasons_by_object_id.get(object_id, ())

    def claims_by_status(self) -> dict[ClaimStatus, tuple[ClaimPresentation, ...]]:
        """The claims grouped by what kind of assertion each is.

        Every status the extraction produced gets a key, and only those: a group nobody is in is
        not shown as an empty heading, because a reviewer scanning for what needs attention should
        not have to read past four empty sections to find the one that does not.
        """
        grouped: dict[ClaimStatus, list[ClaimPresentation]] = {}
        for presented in self.claims:
            grouped.setdefault(presented.status, []).append(presented)
        return {status: tuple(items) for status, items in grouped.items()}

    @property
    def documented_claims(self) -> tuple[ClaimPresentation, ...]:
        return tuple(presented for presented in self.claims if presented.is_documented)

    @property
    def interpreted_claims(self) -> tuple[ClaimPresentation, ...]:
        """Inferred, assumed, unknown, contradicted — everything that is not a documented fact.

        Named as its own group because section 5.5's rule is about this boundary specifically: an
        interpretation presented alongside a documented fact, in one list, is an interpretation
        being silently converted into a confirmed fact by layout.
        """
        return tuple(presented for presented in self.claims if not presented.is_documented)

    @property
    def blocking_questions(self) -> tuple[Question, ...]:
        return tuple(question for question in self.questions if question.blocking)

    @property
    def approval_blockers(self) -> tuple[str, ...]:
        """What stands between this package and an approval, each named well enough to act on."""
        blockers = [
            f"question {question.id} is blocking and unanswered: {question.question}"
            for question in self.blocking_questions
        ] + [
            f"validation error on {error.object_id}.{error.field}: {error.message}"
            for error in self.outstanding_errors
        ]
        return tuple(blockers)

    @property
    def can_approve(self) -> bool:
        return not self.approval_blockers

    def counts(self) -> dict[str, int]:
        """Identifiers and counts only, for a log line or a command-line summary.

        Never content: source-derived text in a log record is what `trace_ai.observability` exists
        to prevent, and every excerpt in this package is source-derived by construction.
        """
        return {
            **{name: len(items) for name, items in self.objects_by_type.items()},
            "claims": len(self.claims),
            "documented_claims": len(self.documented_claims),
            "interpreted_claims": len(self.interpreted_claims),
            "open_questions": len(self.questions),
            "blocking_questions": len(self.blocking_questions),
            "triggers": len(self.triggers),
            "outstanding_errors": len(self.outstanding_errors),
        }


def _excerpts(index: EvidenceIndex, evidence_ids: Sequence[str]) -> tuple[QuotedExcerpt, ...]:
    """The passages behind one claim, labelled. An unresolvable citation is reported, not dropped.

    A citation that resolves to nothing is `agent-design.md` section 14's named failure condition,
    and the package is the last place it can be seen before a reviewer confirms the claim it
    supports.
    """
    rendered: list[QuotedExcerpt] = []
    for evidence_id in evidence_ids:
        try:
            reference = index.get(evidence_id)
        except EvidenceNotFoundError:
            rendered.append(
                QuotedExcerpt(
                    evidence_id=evidence_id,
                    document=None,
                    location="unresolved",
                    text=(
                        f"{evidence_id} does not resolve to a stored passage. The claim it "
                        f"supports cannot be confirmed from it."
                    ),
                )
            )
            continue

        document = index.handle.objects.find(SourceDocument, reference.source_document_id)
        parts = []
        if reference.section_title:
            parts.append(reference.section_title)
        if reference.start_line is not None:
            end = reference.end_line if reference.end_line is not None else reference.start_line
            parts.append(f"lines {reference.start_line}-{end}")
        rendered.append(
            QuotedExcerpt(
                evidence_id=reference.id,
                document=getattr(document, "filename", None),
                location=", ".join(parts),
                text=reference.quoted_text,
            )
        )
    return tuple(rendered)


def build_context_review_package(
    handle: AssessmentHandle,
    *,
    index: EvidenceIndex,
    validation: ContextValidationOutcome,
) -> ContextReviewPackage:
    """Assemble checkpoint 1's package from the validated objects and the validation result."""
    context = current_system_context(handle)

    objects_by_type: dict[str, tuple[DomainModel, ...]] = {
        name: tuple(handle.objects.list(model)) for name, model in CONTEXT_OBJECT_TYPES
    }
    claims = tuple(
        ClaimPresentation(claim=claim, excerpts=_excerpts(index, claim.evidence_ids))
        for claim in handle.objects.list(ContextClaim)
    )
    questions = tuple(
        order_for_review(
            question
            for question in handle.objects.list(Question)
            if question.status is QuestionStatus.OPEN
        )
    )

    presented: list[DomainModel] = [obj for items in objects_by_type.values() for obj in items] + [
        presentation.claim for presentation in claims
    ]

    return ContextReviewPackage(
        package=build_review_package(
            handle,
            checkpoint_type=Phase.HUMAN_CONTEXT_REVIEW,
            objects=presented,
            validation_findings=tuple(error.message for error in validation.errors),
            triggers=tuple(trigger.name for trigger in validation.triggers),
        ),
        system_context=context,
        objects_by_type=objects_by_type,
        claims=claims,
        questions=questions,
        triggers=validation.triggers,
        outstanding_errors=validation.blocking_errors,
        injection_attempts=tuple(
            observation
            for observation in handle.objects.list(SourceObservation)
            if observation.kind is ObservationKind.INJECTION_ATTEMPT
        ),
        reasons_by_object_id=_routing_reasons(handle),
    )


def _routing_reasons(handle: AssessmentHandle) -> dict[str, tuple[str, ...]]:
    """The per-subject routing reasons (DEC-062), derived from persisted state at build time.

    Only `injection_flag` is derived here (issue #274); the other codes attach as their inputs
    are built. The reasons are computed, never read from storage.
    """
    from trace_ai.workflow.reason_codes import ReasonCode, injection_flagged_subjects

    reasons: dict[str, list[str]] = {}
    for object_id in injection_flagged_subjects(handle):
        reasons.setdefault(object_id, []).append(ReasonCode.INJECTION_FLAG.value)
    return {object_id: tuple(codes) for object_id, codes in reasons.items()}


def context_review_subjects(context: NodeContext) -> list[str]:
    """What checkpoint 1 waits on: every extracted object, in presentation order.

    Read from the state rather than from the store, because the state is what the run carries
    across the pause (DEC-017) and a resumed invocation must wait on the same list the paused one
    named. Questions are not subjects — a question is answered, not decided, and answering one is
    recorded on the `Question` rather than as a `ReviewerDecision`.
    """
    state = context.state
    return [
        *state.component_ids,
        *state.actor_ids,
        *state.asset_ids,
        *state.data_flow_ids,
        *state.trust_boundary_ids,
        *state.context_claim_ids,
    ]


@dataclass(slots=True)
class ContextReviewNode:
    """Checkpoint 1 as a workflow node: the shared checkpoint, plus the approval gate.

    The shared `CheckpointNode` is configured here for `human_context_review` and does the part
    both checkpoints share — which subjects are outstanding, and which already have a
    `ReviewerDecision`. What this class adds is the one thing that is specific to the first
    checkpoint: `run` names the `SystemContext` among the objects awaiting a decision whenever
    `is_approved` is false.

    That is the whole gate. The orchestrator advances only on an empty `awaiting_review`, so there
    is no path to threat generation that does not pass an approved context. The only constructor
    field is `version`; there is no `skip`, no `enabled`, and nothing to pass that changes the
    condition.

    Reading `is_approved` rather than counting decisions matters. A checkpoint that advanced once
    every subject had a `ReviewerDecision` would advance for a run whose decisions were written by
    something other than `approve_context` — an evaluation harness replaying rows, say — leaving
    `approved_at` unset and the record unable to say a reviewer ever saw the context.
    """

    version: str = "0.1"
    checkpoint: CheckpointNode = field(init=False, repr=False)
    execution_type: ExecutionType = field(default=ExecutionType.HUMAN_CHECKPOINT, init=False)

    def __post_init__(self) -> None:
        self.checkpoint = CheckpointNode(
            checkpoint_type=Phase.HUMAN_CONTEXT_REVIEW,
            subjects=context_review_subjects,
            version=self.version,
        )

    @property
    def name(self) -> str:
        return self.checkpoint.name

    @property
    def phase(self) -> Phase:
        return Phase.HUMAN_CONTEXT_REVIEW

    def run(self, context: NodeContext) -> NodeResult:
        shared = self.checkpoint.run(context)
        awaiting = list(shared.awaiting_review)

        system_context = current_system_context(context.handle)
        if not system_context.is_approved:
            awaiting.append(system_context_key(system_context))

        return NodeResult(
            awaiting_review=awaiting,
            consumed_object_ids=shared.consumed_object_ids,
            metadata={
                **shared.metadata,
                "context_approved": system_context.is_approved,
                "system_context_version": system_context.version,
            },
        )


def _record(
    handle: AssessmentHandle,
    *,
    context: SystemContext,
    disposition: ReviewDisposition,
    reviewer_id: str,
    rationale: str | None,
    workflow_run_id: str | None,
    at: datetime,
) -> ReviewerDecision:
    """One decision about a `SystemContext`, allocated and persisted in a single transaction."""
    with handle.objects.transaction() as repository:
        decision = ReviewerDecision.model_validate(
            {
                "id": repository.allocate("dec"),
                "assessment_id": context.assessment_id,
                "subject_type": "system_context",
                "subject_id": system_context_key(context),
                "disposition": disposition,
                "rationale": rationale,
                "reviewer_id": reviewer_id,
                "created_at": at,
                "workflow_run_id": workflow_run_id,
            }
        )
        repository.save(decision)
    return decision


def approve_context(
    handle: AssessmentHandle,
    package: ContextReviewPackage,
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[SystemContext, ReviewerDecision]:
    """Mint the approved revision, or refuse and say what is outstanding.

    **Approval increments the version** (DEC-023: `SystemContext.version` increments on approval,
    alongside `approved_at` and `approved_by`; DEC-040 states what that means in practice). The
    revision the extractor produced is left exactly as it was, so the generated baseline and the
    approved one sit side by side and the difference between them is readable. Nothing else in the
    model is versioned — a reviewer edit to a `Component` mutates it in place and records its delta
    on a `ReviewerDecision`.

    **The new revision's membership is recomputed from the store**, not copied. That is how a
    reviewer-added object reaches the approved baseline and how a reviewer-rejected one stays out
    of it: threat analysis reasons from this object, and an object the reviewer rejected is not
    something to reason from.

    The revision is built with `model_validate` rather than `model_copy` (DEC-023). This is the
    path a human-supplied value takes into a domain object, so it is the one that least tolerates
    skipping the schema.
    """
    if not package.can_approve:
        raise ApprovalRefusedError(package.approval_blockers)

    timestamp = at if at is not None else now()
    approved = SystemContext.model_validate(
        package.system_context.next_version().model_dump()
        | approved_membership(handle)
        | {"approved_at": timestamp, "approved_by": reviewer_id}
    )
    with handle.objects.transaction() as repository:
        repository.save(approved)
    decision = _record(
        handle,
        context=approved,
        disposition=ReviewDisposition.APPROVE,
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=timestamp,
    )
    return approved, decision


def request_re_extraction(
    handle: AssessmentHandle,
    package: ContextReviewPackage,
    *,
    reviewer_id: str,
    rationale: str,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> ReviewerDecision:
    """Reject the extracted context and ask for another one.

    DEC-038: this stops the run rather than routing it backwards. The transition table declares a
    sequence and `successor` returns one phase; an edge from `human_context_review` back to
    `context_extraction` would make the pipeline branch and would be the loop `agent-design.md`
    section 27 requires the orchestrator to prevent. Re-extraction is the assessment's next
    `WorkflowRun`, which DEC-031 already allows for, and this decision is what connects the two.

    A rationale is required rather than optional. "Do it again" with no reason is an instruction
    the next extraction cannot act on, and the retry rule in section 26 is that a repeated attempt
    carries feedback or it is a repetition.
    """
    if not rationale.strip():
        raise ValueError(
            "a re-extraction request must say what was wrong. A repeated attempt carries feedback "
            "or it is a repetition (agent-design.md section 26)."
        )
    return _record(
        handle,
        context=package.system_context,
        disposition=ReviewDisposition.REQUEST_MORE_ANALYSIS,
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=at if at is not None else now(),
    )


# ------------------------------------------------------------------------------------------
# The mutating reviewer actions (`agent-design.md` section 9)
# ------------------------------------------------------------------------------------------


class ReviewerActionError(ValueError):
    """A reviewer action the application refuses, with the reason in the corpus's terms."""


def _object_term(obj: DomainModel) -> str:
    """The vocabulary term for an object's type, agreeing with its identifier's prefix."""
    identifier = getattr(obj, "id", None)
    if isinstance(identifier, str):
        return parse_id(identifier).object_term
    return "system_context"


def _persist(handle: AssessmentHandle, obj: DomainModel, decision: ReviewerDecision) -> None:
    """The object and the record of who changed it, in one transaction.

    Section 2.5 forbids *silently* overwriting generated content. An overwrite that committed while
    its decision failed would be exactly that, and nothing afterwards could tell the difference
    between a reviewer edit and a bug.
    """
    with handle.objects.transaction() as repository:
        repository.save(obj)
        repository.save(decision)


def _decision_about(
    handle: AssessmentHandle,
    obj: DomainModel,
    *,
    disposition: ReviewDisposition,
    reviewer_id: str,
    rationale: str | None,
    workflow_run_id: str | None,
    at: datetime,
) -> ReviewerDecision:
    """A decision carrying no delta — approval, rejection, or an addition."""
    return ReviewerDecision.model_validate(
        {
            "id": handle.objects.allocate("dec"),
            "assessment_id": getattr(obj, "assessment_id", handle.assessment_id),
            "subject_type": _object_term(obj),
            "subject_id": getattr(obj, "id", ""),
            "disposition": disposition,
            "rationale": rationale,
            "reviewer_id": reviewer_id,
            "created_at": at,
            "workflow_run_id": workflow_run_id,
        }
    )


def _edited[ModelT: DomainModel](obj: ModelT, changes: dict[str, Any]) -> ModelT:
    """The object with `changes` applied, built through the schema.

    `model_validate`, never `model_copy` (DEC-023). The copy API validates nothing: an invalid enum
    value survives it and serializes into the DEC-020 payload, and `extra="forbid"` is bypassed.
    This is the one path on which a human-supplied value enters a domain object, so it is the one
    that least tolerates skipping the schema.
    """
    payload = obj.model_dump() | changes
    if "updated_at" in type(obj).model_fields and "updated_at" not in changes:
        payload["updated_at"] = now()
    return type(obj).model_validate(payload)


def _context_objects(handle: AssessmentHandle) -> list[DomainModel]:
    """Every context object in the assessment, for a referential check."""
    return [obj for _, model in CONTEXT_OBJECT_TYPES for obj in handle.objects.list(model)]


def _refuse_new_reference_problems(
    handle: AssessmentHandle, before: DomainModel, after: DomainModel
) -> None:
    """Refuse an edit that makes a reference dangle, with the validation node's own message.

    The check runs against `SystemContext.validate_against`, which is what the Context Validation
    node calls, so the reviewer is refused in the same words the pipeline would have reported later.
    Comparing before and after rather than checking the result outright matters: a context that was
    already inconsistent is not made the reviewer's fault by an unrelated edit.
    """
    identifier = getattr(after, "id", None)
    if not isinstance(identifier, str):
        return

    context = current_system_context(handle)
    objects = [obj for obj in _context_objects(handle) if getattr(obj, "id", None) != identifier]
    existing = set(context.validate_against([*objects, before]))
    introduced = [
        problem
        for problem in context.validate_against([*objects, after])
        if problem not in existing
    ]
    if introduced:
        raise ReviewerActionError(
            "this edit would leave a reference that does not resolve:\n  - "
            + "\n  - ".join(introduced)
            + "\nA reviewer correction cannot introduce a dangling endpoint; add the object it "
            "names first."
        )


def apply_edit[ModelT: DomainModel](
    handle: AssessmentHandle,
    obj: ModelT,
    changes: dict[str, Any],
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[ModelT, ReviewerDecision]:
    """Edit an object in place and record what changed.

    DEC-023's first mechanism. The object keeps its identifier, its fields change, and the decision
    carries `prior_value` and `updated_value` holding **only the changed fields** — which is what
    makes reviewer edit rate computable per field rather than per object, and what makes the
    generated value recoverable after the object has moved on.

    The delta is captured by `ReviewerDecision.capture_edit`, which takes both states rather than
    being assembled here. A `prior_value` copied from the already-edited object records that
    nothing changed, and that is not a mistake any call site should be able to make.
    """
    timestamp = at if at is not None else now()
    edited = _edited(obj, changes)
    _refuse_new_reference_problems(handle, obj, edited)

    with handle.objects.transaction() as repository:
        decision = ReviewerDecision.capture_edit(
            decision_id=repository.allocate("dec"),
            before=obj,
            after=edited,
            subject_type=_object_term(obj),
            subject_id=str(getattr(obj, "id", "")),
            created_at=timestamp,
            rationale=rationale,
            reviewer_id=reviewer_id,
            workflow_run_id=workflow_run_id,
        )
        repository.save(edited)
        repository.save(decision)
    return edited, decision


def _has_status(obj: DomainModel) -> bool:
    """Whether a decision changes anything on this object besides writing the record.

    A `ContextClaim` has a `status`, and it is a `ClaimStatus` — what kind of assertion the claim
    is, not where it sits in a workflow. An approval has no value to set there.
    """
    if isinstance(obj, ContextClaim):
        return False
    return "status" in type(obj).model_fields


def _status_for(obj: DomainModel, disposition: ReviewDisposition) -> ObjectStatus:
    return (
        ObjectStatus.APPROVED if disposition is ReviewDisposition.APPROVE else ObjectStatus.REJECTED
    )


def decide_object[ModelT: DomainModel](
    handle: AssessmentHandle,
    obj: ModelT,
    disposition: ReviewDisposition,
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[ModelT, ReviewerDecision]:
    """Approve or reject one extracted object.

    The status change and the disposition say the same thing, which is why the decision carries no
    delta: `ReviewerDecision` refuses one on an approval or a rejection, because a change to the
    object's *content* is an edit and this is not one.

    `Actor` has no `status` field — `data-model.md` section 13's table has none and DEC-037 declined
    to add one — so an actor's decision is the whole record of it.

    **`ContextClaim.status` is not a lifecycle** and is not set to `approved` here. Section 10's
    status values are epistemic — what kind of assertion the claim is — and there is no `approved`
    among them. Approving a claim therefore changes nothing on the object and the decision is the
    whole record; a reviewer who wants to raise a claim's *authority* is confirming it, which is
    `confirm_assumption` and a different status. Rejection does have a value, and it means what it
    says: the reviewer discarded the claim.
    """
    if disposition not in {ReviewDisposition.APPROVE, ReviewDisposition.REJECT}:
        raise ReviewerActionError(
            f"{disposition} is not an approve-or-reject decision. An edit goes through "
            f"`apply_edit`, which records what changed."
        )

    timestamp = at if at is not None else now()
    if _has_status(obj):
        decided = _edited(obj, {"status": _status_for(obj, disposition)})
    elif isinstance(obj, ContextClaim) and disposition is ReviewDisposition.REJECT:
        decided = _edited(obj, {"status": ClaimStatus.REJECTED})
    else:
        decided = obj
    decision = _decision_about(
        handle,
        decided,
        disposition=disposition,
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=timestamp,
    )
    _persist(handle, decided, decision)
    return decided, decision


def add_context_object[ModelT: DomainModel](
    handle: AssessmentHandle,
    model: type[ModelT],
    fields: dict[str, Any],
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[ModelT, ReviewerDecision]:
    """Add a component, actor, asset, data flow, or trust boundary the extractor missed.

    The object carries `source_origin` of `reviewer_edit` (DEC-039), which is what distinguishes it
    from an extracted one without joining to the decision log. It is `approved` from birth: nobody
    needs to approve what they just wrote, and leaving it `candidate` would make the checkpoint wait
    on a decision about the reviewer's own object.

    The identifier is allocated by the store like every other one (DEC-018). A reviewer-supplied
    identifier could collide with a number the counter has not reached yet.
    """
    known = {name for name, candidate in CONTEXT_OBJECT_TYPES if candidate is model}
    if not known:
        raise ReviewerActionError(
            f"{model.__name__} is not one of the context object types a reviewer may add: "
            f"{', '.join(name for name, _ in CONTEXT_OBJECT_TYPES)}."
        )

    timestamp = at if at is not None else now()
    prefix = next(candidate for candidate, name in PREFIXES.items() if name == model.__name__)

    with handle.objects.transaction() as repository:
        payload: dict[str, Any] = {
            "id": repository.allocate(prefix),
            "assessment_id": handle.assessment_id,
            "source_origin": SourceOrigin.REVIEWER_EDIT,
            **fields,
        }
        if "status" in model.model_fields:
            payload.setdefault("status", ObjectStatus.APPROVED)
        added = model.model_validate(payload)
        decision = _decision_about(
            handle,
            added,
            disposition=ReviewDisposition.APPROVE,
            reviewer_id=reviewer_id,
            rationale=rationale,
            workflow_run_id=workflow_run_id,
            at=timestamp,
        )
        repository.save(added)
        repository.save(decision)

    _refuse_new_reference_problems(handle, added, added)
    return added, decision


def confirm_assumption(
    handle: AssessmentHandle,
    claim: ContextClaim,
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[ContextClaim, ReviewerDecision]:
    """Move a claim to `user_confirmed`: the top of `agent-design.md` section 14's hierarchy.

    The transition is recorded rather than inferred, because it is the one status change that adds
    authority without adding evidence — the reviewer *is* the evidence. A claim that arrived
    `assumed` and leaves `user_confirmed` has been promoted by a person, and the decision is where
    that person is named.
    """
    if claim.status is ClaimStatus.USER_CONFIRMED:
        raise ReviewerActionError(f"{claim.id} is already user_confirmed")
    return apply_edit(
        handle,
        claim,
        {"status": ClaimStatus.USER_CONFIRMED},
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=at,
    )


@dataclass(frozen=True, slots=True)
class ContradictionResolution:
    """What resolving one contradiction produced: the observation, the claims, and the records."""

    observation: SourceObservation
    claims: tuple[ContextClaim, ...]
    decisions: tuple[ReviewerDecision, ...]


def resolve_contradiction(
    handle: AssessmentHandle,
    observation: SourceObservation,
    *,
    resolution: JsonValue,
    rationale: str,
    reviewer_id: str,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> ContradictionResolution:
    """Record which statement is authoritative, and why, without discarding the other.

    `demo/forgeflow/forgeflow-scenario.md` section 16 states the requirement negatively — do not
    quietly choose the safer statement — and this is the positive form of it. The observation keeps
    **every** evidence reference it was created with, so the statement the reviewer did not select
    stays retrievable; what changes is that the observation now carries a rationale and the claims
    it bears on carry the chosen value as `user_confirmed`.

    A rationale is required. A resolution with no reasoning is indistinguishable from the silent
    choice the scenario exists to catch.
    """
    if observation.kind is not ObservationKind.CONTRADICTION:
        raise ReviewerActionError(
            f"{observation.id} is a {observation.kind} observation; only a contradiction is "
            f"resolved by choosing between statements"
        )
    if not rationale.strip():
        raise ReviewerActionError(
            "a contradiction resolution must carry a rationale. Without one it is "
            "indistinguishable from quietly choosing the safer statement "
            "(forgeflow-scenario.md section 16)."
        )
    if not observation.subject_claim_ids:
        raise ReviewerActionError(
            f"{observation.id} names no claim, so there is nothing for a resolution to settle"
        )

    timestamp = at if at is not None else now()
    resolved, observation_decision = apply_edit(
        handle,
        observation,
        {"reviewer_notes": rationale, "status": ObjectStatus.APPROVED},
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=timestamp,
    )

    claims: list[ContextClaim] = []
    decisions: list[ReviewerDecision] = [observation_decision]
    for claim_id in observation.subject_claim_ids:
        claim = handle.objects.find(ContextClaim, claim_id)
        if claim is None:
            raise ReviewerActionError(
                f"{observation.id} names claim {claim_id}, which this assessment does not hold"
            )
        settled, decision = apply_edit(
            handle,
            claim,
            {
                "value": resolution,
                "status": ClaimStatus.USER_CONFIRMED,
                "rationale": rationale,
            },
            reviewer_id=reviewer_id,
            rationale=rationale,
            workflow_run_id=workflow_run_id,
            at=timestamp,
        )
        claims.append(settled)
        decisions.append(decision)

    return ContradictionResolution(
        observation=resolved, claims=tuple(claims), decisions=tuple(decisions)
    )


def answer_question(
    handle: AssessmentHandle,
    question: Question,
    *,
    response: str,
    reviewer_id: str,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Question, ReviewerDecision]:
    """Record a reviewer's answer, which is what takes a question out of the blocking set.

    `data-model.md` section 22's three answer fields move together and `Question` enforces it: a
    response with no origin is an answer nobody is accountable for, and an origin with no timestamp
    is an answer that cannot be placed in the review.
    """
    if question.status is not QuestionStatus.OPEN:
        raise ReviewerActionError(f"{question.id} is {question.status}, not open")
    if not response.strip():
        raise ReviewerActionError(
            f"{question.id} needs an answer, not an empty one. A question the reviewer cannot "
            f"answer is dismissed, which is a different status and a different record."
        )

    timestamp = at if at is not None else now()
    return apply_edit(
        handle,
        question,
        {
            "response": response,
            "response_origin": SourceOrigin.USER_RESPONSE,
            "answered_at": timestamp,
            "status": QuestionStatus.ANSWERED,
        },
        reviewer_id=reviewer_id,
        rationale=None,
        workflow_run_id=workflow_run_id,
        at=timestamp,
    )


def attach_evidence[ModelT: DomainModel](
    handle: AssessmentHandle,
    obj: ModelT,
    evidence_ids: Sequence[str],
    *,
    index: EvidenceIndex,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[ModelT, ReviewerDecision]:
    """Link an existing `EvidenceReference` to an object.

    **Evidence text is never edited.** `data-model.md` section 8 requires a correction to create a
    new evidence reference, because DEC-019 hashes `quoted_text` and the indexer records the line
    range it came from — editing it in place would leave the stored text disagreeing with both its
    own hash and its own location, and the disagreement would surface as an unverifiable citation
    rather than as the edit that caused it. So this function links; it does not write.

    Each reference is resolved before it is linked, so a reviewer cannot attach a citation that
    resolves to nothing — the failure `agent-design.md` section 14 names.
    """
    if "evidence_ids" not in type(obj).model_fields:
        raise ReviewerActionError(f"{type(obj).__name__} carries no evidence references")

    unknown = [
        evidence_id
        for evidence_id in evidence_ids
        if handle.objects.find(_reference(), evidence_id) is None
    ]
    if unknown:
        raise ReviewerActionError(
            f"{', '.join(unknown)} do not resolve to stored evidence. Section 8 requires a "
            f"correction to create a new evidence reference; a citation nobody can follow is the "
            f"failure agent-design.md section 14 names."
        )

    existing: list[str] = list(getattr(obj, "evidence_ids"))  # noqa: B009 - the name is dynamic
    added = [evidence_id for evidence_id in evidence_ids if evidence_id not in existing]
    if not added:
        raise ReviewerActionError(
            f"{getattr(obj, 'id', type(obj).__name__)} already cites "
            f"{', '.join(evidence_ids)}; there is no change to record"
        )
    index.resolve(added)

    return apply_edit(
        handle,
        obj,
        {"evidence_ids": [*existing, *added]},
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=at,
    )


def _reference() -> type[Any]:
    from trace_ai.domain.evidence import EvidenceReference

    return EvidenceReference


def approved_membership(handle: AssessmentHandle) -> dict[str, list[str]]:
    """The identifier lists an approved revision carries: every context object not rejected.

    Recomputed from the store rather than copied from the previous revision, so a reviewer-added
    object reaches the baseline and a reviewer-rejected one does not. Threat analysis reasons from
    this object; an object the reviewer rejected is not something to reason from (DEC-040).
    """
    lists: dict[str, list[str]] = {}
    for name, model in CONTEXT_OBJECT_TYPES:
        field_name = _LIST_BY_GROUP[name]
        lists[field_name] = [
            obj.id
            for obj in handle.objects.list(model)
            if getattr(obj, "status", None) is not ObjectStatus.REJECTED
        ]
    lists["context_claim_ids"] = [
        claim.id
        for claim in handle.objects.list(ContextClaim)
        if claim.status is not ClaimStatus.REJECTED
    ]
    return lists


def re_extraction_feedback(handle: AssessmentHandle) -> str | None:
    """The most recent re-extraction rationale, for the next run's extraction node to carry.

    Reviewer text is trusted input and does not go inside the source-content fence: DEC-013's
    trust levels put `reviewer_edit` among the origins that are *not* material under review, and
    the reviewer is the operator rather than a document being assessed. This closes DEC-038's open
    question about whether the rationale may reach a prompt.
    """
    requests = [
        decision
        for decision in handle.objects.list(ReviewerDecision)
        if decision.disposition is ReviewDisposition.REQUEST_MORE_ANALYSIS
        and decision.subject_type == "system_context"
    ]
    if not requests:
        return None
    return max(requests, key=lambda decision: (decision.created_at, decision.id)).rationale
