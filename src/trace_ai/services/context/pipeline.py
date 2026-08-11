"""Running the context slice: extract, validate, and stop at the checkpoint.

`current-architecture.md` section 5.2 puts the pipeline in the application service, and this module
is the context slice's half of that. The command line calls it; so would anything else. A CLI that
composed the nodes itself would be a second place the pipeline lives, and the two would drift.

**This is deliberately the narrow path.** `services/driver.py` drives all fourteen phases through
the orchestrator; this module remains the context slice alone — extraction through checkpoint 1 —
for the caller that wants exactly that and nothing after it (`trace context extract`). It stays a
hand-rolled walk of four phases because a second orchestrator composition for a strict prefix of
the same table would be the drift the paragraph above warns about, in the other direction.

**The run stops at the checkpoint because the checkpoint is a phase.** Nothing here decides to
pause: the transition table's successor to `context_validation` is `human_context_review`, and the
state written at the end of this function is the paused one. `run_context_slice` cannot be asked to
continue past it, because there is no argument that would mean that (DEC-005, DEC-012).

**Validation reports; it does not gate the pause.** A context with blocking errors still reaches
the reviewer — they are the person who decides what an error means, and a run that refused to pause
would leave them with nothing to look at. What blocking errors stop is *approval*, which is
`workflow/context_review.py`'s refusal and not this module's.

**The state is written before the function returns** (DEC-017). Pausing is stopping: the state file
in `traces/` is what a later invocation reads, and a run that paused without writing one would be a
run nobody could resume.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.prompts import PromptRegistry
from trace_ai.workflow.checkpoint import save_state
from trace_ai.workflow.context_extraction import ContextExtractionNode
from trace_ai.workflow.context_review import (
    ContextReviewNode,
    build_context_review_package,
    re_extraction_feedback,
)
from trace_ai.workflow.context_validation import validate_context
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.state import AssessmentState

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.execution import WorkflowRun
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.infrastructure.model.seam import StructuredModel
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.workflow.context_review import ContextReviewPackage
    from trace_ai.workflow.context_validation import ContextValidationOutcome
    from trace_ai.workflow.limits import Budget

__all__ = ["ContextSliceOutcome", "context_objects", "run_context_slice"]

WORKFLOW_VERSION = "0.1"


@dataclass(frozen=True, slots=True)
class ContextSliceOutcome:
    """What one run of the context slice produced, and where it stopped."""

    run: WorkflowRun
    state: AssessmentState
    validation: ContextValidationOutcome
    package: ContextReviewPackage
    produced_object_ids: tuple[str, ...]
    state_path: str
    """Where the paused state was written, relative to the assessment root."""

    @property
    def paused_at(self) -> Phase:
        return self.state.current_phase


def context_objects(handle: AssessmentHandle) -> list[DomainModel]:
    """Every context object an assessment holds, in the order the review package presents them."""
    return [
        obj
        for model in (Component, Actor, Asset, DataFlow, TrustBoundary, ContextClaim)
        for obj in handle.objects.list(model)
    ]


def run_context_slice(
    handle: AssessmentHandle,
    *,
    model: StructuredModel,
    profile: ModelProfile,
    assessment_name: str,
    evidence_ids: Sequence[str] | None = None,
    structured_input: dict[str, Any] | None = None,
    budget: Budget | None = None,
    carry_reviewer_feedback: bool = True,
) -> ContextSliceOutcome:
    """Extract a context, validate it, and stop at checkpoint 1.

    `evidence_ids` defaults to everything the assessment has indexed. It is a parameter rather than
    always being everything because what the extractor sees is a decision worth making in one place
    (`agent-design.md` section 23), and a caller narrowing it is making that decision explicitly.

    `carry_reviewer_feedback` picks up a previous run's rejection rationale, which is what makes
    this a *re*-extraction rather than a repetition (DEC-038, DEC-040). It is on by default because
    forgetting it is the failure mode: an identical second attempt is a second roll of the same
    dice.
    """
    available = (
        list(evidence_ids)
        if evidence_ids is not None
        else sorted(reference.id for reference in handle.objects.list(EvidenceReference))
    )
    if not available:
        raise ValueError(
            "this assessment has no indexed evidence, so there is nothing to extract a context "
            "from. Register and index source documents first."
        )

    run = start_run(handle, workflow_version=WORKFLOW_VERSION, model_profile=profile.name)
    ledger = ExecutionLedger(handle, run)
    state = (
        AssessmentState.begin(assessment_id=handle.assessment_id, workflow_run_id=run.id)
        .advance(Phase.DOCUMENT_INGESTION)
        .advance(Phase.CONTEXT_EXTRACTION)
    )

    extraction = ContextExtractionNode(
        ledger=ledger,
        index=EvidenceIndex(handle),
        profile=profile,
        registry=PromptRegistry(),
        evidence_ids=available,
        assessment_name=assessment_name,
        structured_input=structured_input,
        budget=budget,
        reviewer_feedback=re_extraction_feedback(handle) if carry_reviewer_feedback else None,
    )
    result = extraction.run(NodeContext(handle=handle, state=state, model=model))
    state = state.advance(Phase.CONTEXT_VALIDATION, **result.state_changes)

    from trace_ai.workflow.context_review import current_system_context

    context = current_system_context(handle)
    validation = validate_context(
        context, context_objects(handle), available_evidence=set(available)
    )
    package = build_context_review_package(
        handle, index=EvidenceIndex(handle), validation=validation
    )

    state = state.advance(Phase.HUMAN_CONTEXT_REVIEW)
    checkpoint = ContextReviewNode().run(NodeContext(handle=handle, state=state))
    state = state.paused_for(Phase.HUMAN_CONTEXT_REVIEW, checkpoint.awaiting_review)
    path = save_state(handle, state)
    ledger.pause(current_node=Phase.HUMAN_CONTEXT_REVIEW.value)

    return ContextSliceOutcome(
        run=handle.objects.get(type(run), run.id),
        state=state,
        validation=validation,
        package=package,
        produced_object_ids=tuple(result.produced_object_ids),
        state_path=path,
    )
