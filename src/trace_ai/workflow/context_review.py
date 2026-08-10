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
`request_more_analysis`, which is what connects the two runs.

This module is at `workflow/` rather than at the `application/` path the issue named: there is no
`application` package, and the two nodes either side of this one — `context_extraction.py` and
`context_validation.py` — are here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.enums import ReviewDisposition
from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.question import Question, QuestionStatus, order_for_review
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.domain.source_document import SourceDocument
from trace_ai.domain.system_context import SystemContext
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.services.evidence.index import EvidenceNotFoundError
from trace_ai.workflow.checkpoint import CheckpointNode, build_review_package
from trace_ai.workflow.nodes import NodeResult
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from trace_ai.domain.base import DomainModel
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
    "QuotedExcerpt",
    "approve_context",
    "build_context_review_package",
    "current_system_context",
    "request_re_extraction",
    "system_context_key",
]

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
    )


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
    """Approve the current context revision, or refuse and say what is outstanding.

    Approval writes two things and they belong together: `approved_at` and `approved_by` on the
    revision, which is what the gate reads, and a `ReviewerDecision`, which is what section 2.5
    requires so the action is recorded rather than applied silently.

    The revision is rebuilt with `model_validate` rather than `model_copy` (DEC-023). This is the
    path a human-supplied value takes into a domain object, so it is the one that least tolerates
    skipping the schema.
    """
    if not package.can_approve:
        raise ApprovalRefusedError(package.approval_blockers)

    timestamp = at if at is not None else now()
    approved = SystemContext.model_validate(
        package.system_context.model_dump() | {"approved_at": timestamp, "approved_by": reviewer_id}
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
