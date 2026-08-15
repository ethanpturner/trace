"""The Context Extraction node: the first model-assisted step, and the first model call.

`agent-design.md` section 7 specifies the contract and section 26 the retry rule that shapes the
control flow here — retry when the *output* failed, never because the *material* is incomplete.
Incomplete material is designed to produce questions, and a node that retried on it would be asking
the same model the same question until it stopped saying "I don't know", which is fabrication with
extra steps.

**The node produces a context and stops.** It approves nothing, and it cannot: the checkpoint that
follows is a phase in the transition table, not a branch this node could skip. The `SystemContext`
it produces is version 1 with `approved_at` and `approved_by` unset, and every object it converts
arrives `candidate`.

**Every ceiling is checked before the call.** A `maximum_model_calls` of zero stops the node before
it spends anything, which is how a run is made to prove it needs a model rather than assumed to.

**An invalid output is preserved, not discarded** (`data-model.md` section 33). It goes to the
assessment's `traces/` area and the execution record names the file; the error message never carries
it, because a failed attempt's output is model text that can contain a quoted source excerpt or an
echoed prompt.

`agent-design.md` section 38's open question 1 asks whether extraction needs one agent or two. This
is one node, consistent with the six-agent cap in section 36: splitting it into two model-assisted
stages would be a design change requiring a decision-log entry, and the deterministic normalization
half already lives in the validation node.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.base import now
from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.proposals import (
    CONTEXT_EXTRACTION_AGENT,
    ContextExtractionProposal,
    ProposalError,
    convert_proposal,
)
from trace_ai.domain.system_context import FIRST_VERSION, SystemContext
from trace_ai.infrastructure.model.agents import spec_for
from trace_ai.services.context.input_package import assemble_extractor_input
from trace_ai.workflow.errors import ErrorClass
from trace_ai.workflow.limits import resolve_retry_policy
from trace_ai.workflow.model_call import call_model, with_retry_feedback
from trace_ai.workflow.nodes import NodeResult
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.retry import AttemptFailedError, RetryPolicy, run_with_retries

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.proposals.conversion import ConvertedContext
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.services.execution_ledger import ExecutionLedger
    from trace_ai.services.prompts import PromptRegistry
    from trace_ai.workflow.limits import Budget
    from trace_ai.workflow.nodes import NodeContext

__all__ = ["NODE_NAME", "NODE_VERSION", "PROMPT_ID", "PROMPT_VERSION", "ContextExtractionNode"]

NODE_NAME: Final = "context-extraction"
NODE_VERSION: Final = "0.1"
PROMPT_ID: Final = "extract-context"
PROMPT_VERSION: Final = "v1"

# The marker the prompt declares for the application's own exported schema. Substituted at
# composition so the prompt cannot describe a shape the application would reject.
_SCHEMA_MARKER: Final = "schema.context_extraction_proposal"


@dataclass(slots=True)
class ContextExtractionNode:
    """Ask the model for a context proposal, convert what comes back, and record what it cost."""

    ledger: ExecutionLedger
    index: EvidenceIndex
    profile: ModelProfile
    registry: PromptRegistry
    evidence_ids: Sequence[str]
    assessment_name: str
    budget: Budget | None = None
    retry_policy: RetryPolicy | None = None
    """The attempt loop's policy. `None` — the norm under the driver — defers to the
    budget's `retry_policy()`, so the configuration's `maximum_retries_per_node` is the
    operative ceiling (#397); the built-in default applies only when there is neither."""
    structured_input: dict[str, Any] | None = None

    seeded: ConvertedContext | None = None
    """Objects a DEC-070 parser derived and persisted before this node ran, if any.

    They join the version-1 baseline alongside this node's own conversion, and the agent is told
    about them in the trusted region so it extends rather than re-derives — the division of
    labor: parsers own what the artifact states, the agent owns what the documents mean.
    """

    reviewer_feedback: str | None = None
    """Why a reviewer rejected the previous run's context, carried into this attempt.

    DEC-038 makes re-extraction a new `WorkflowRun` rather than a backward transition, and this is
    what connects the two in the prompt: a repeated attempt carries feedback or it is a repetition
    (`agent-design.md` section 26). It goes in the **trusted** half, outside the source-content
    fence, because DEC-013 puts `reviewer_edit` among the origins that are not material under
    review — the reviewer is the operator, not a document being assessed (DEC-040).
    """

    version: str = NODE_VERSION
    execution_type: ExecutionType = field(default=ExecutionType.MODEL, init=False)

    @property
    def name(self) -> str:
        return NODE_NAME

    @property
    def phase(self) -> Phase:
        return Phase.CONTEXT_EXTRACTION

    def run(self, context: NodeContext) -> NodeResult:
        """One extraction: assemble, call, convert, persist, and report what was produced."""
        if context.model is None:
            raise ValueError(
                f"{NODE_NAME} is a model-assisted node and was given no model. A deterministic "
                f"node is classified as one in agent-design.md section 4."
            )

        # Section 29's creativity for this agent, read from the one `AGENTS` table (WS11) rather
        # than declared inline: declaring it per node is how this very value drifted before it was
        # caught, and the table makes the intent one decision the execution record still shows.
        profile = self.profile.with_creativity(spec_for(NODE_NAME).creativity)

        package = assemble_extractor_input(
            context.handle,
            index=self.index,
            evidence_ids=self.evidence_ids,
            profile=self.profile,
            assessment_name=self.assessment_name,
            structured_input=self.structured_input,
        )
        composed = self.registry.compose(
            PROMPT_ID,
            PROMPT_VERSION,
            {
                _SCHEMA_MARKER: _schema_text(),
                **package.substitutions(),
            },
        )
        system = package.trusted
        if self.seeded is not None and self.seeded.all_objects():
            listed = "\n".join(
                f"- {getattr(obj, 'id', '')}: {getattr(obj, 'name', type(obj).__name__)}"
                for obj in self.seeded.all_objects()
            )
            system = (
                f"{system}\n\n## Deterministically parsed context (already recorded)\n\n"
                f"The objects below were parsed mechanically from a machine-readable artifact "
                f"and already exist in the assessment. Extend this context rather than "
                f"re-deriving it: do not re-propose these components or flows.\n\n{listed}"
            )
        if self.reviewer_feedback:
            system = (
                f"{system}\n\n## Reviewer feedback on the previous extraction\n\n"
                f"A reviewer rejected the previous run's context for this reason. It is a "
                f"trusted instruction from the operator, not source material:\n\n"
                f"{self.reviewer_feedback}"
            )

        usages: list[Any] = []
        attempts = 0

        def attempt(state: Any) -> ContextExtractionProposal:
            nonlocal attempts
            attempts += 1
            execution.retry_number = attempts - 1

            prompt = with_retry_feedback(
                composed.text,
                state.feedback,
                instruction="Return a corrected object. Do not restate the previous one.",
            )
            proposal = call_model(
                context.model,
                prompt=prompt,
                schema=ContextExtractionProposal,
                profile=profile,
                system=system,
                budget=self.budget,
                execution=execution,
                usages=usages,
            )
            try:
                proposal.validate_against_evidence(set(package.evidence_ids))
                proposal.validate_references()
            except ProposalError as invalid:
                raise AttemptFailedError(
                    error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
                    message=str(invalid),
                    raw_output=proposal.model_dump_json(indent=2),
                    feedback=str(invalid),
                ) from None
            return proposal

        with self.ledger.record(
            NODE_NAME,
            node_version=self.version,
            execution_type=ExecutionType.MODEL,
            consumes=list(package.evidence_ids),
        ) as execution:
            execution.prompt_version = composed.reference
            proposal = run_with_retries(
                attempt,
                policy=resolve_retry_policy(self.retry_policy, self.budget),
                node_name=NODE_NAME,
                artifacts=context.handle.artifacts,
                on_attempt_failed=lambda number, failure, path: execution.metadata.update(
                    {f"attempt_{number}_failure": failure.error_class.value}
                    | ({f"attempt_{number}_output": path} if path else {})
                ),
            )

            converted = self._persist(context, proposal)
            system_context = self._system_context(context, proposal, converted)

            produced = [str(getattr(obj, "id", "")) for obj in converted.all_objects()]
            execution.produced(*produced)
            for usage in usages:
                execution.record_usage(usage)
            execution.metadata["attempts"] = attempts
            execution.metadata["evidence_excluded"] = len(package.excluded_evidence_ids)
            if package.excluded_evidence_ids:
                # DEC-071: persist the names, not just the count, for the coverage ledger.
                execution.metadata["excluded_evidence_ids"] = sorted(package.excluded_evidence_ids)
            execution.metadata["carried_reviewer_feedback"] = bool(self.reviewer_feedback)

        return NodeResult(
            produced_object_ids=produced,
            consumed_object_ids=list(package.evidence_ids),
            state_changes={
                "component_ids": list(system_context.component_ids),
                "actor_ids": list(system_context.actor_ids),
                "asset_ids": list(system_context.asset_ids),
                "data_flow_ids": list(system_context.data_flow_ids),
                "trust_boundary_ids": list(system_context.trust_boundary_ids),
                "context_claim_ids": list(system_context.context_claim_ids),
                "open_question_ids": [question.id for question in converted.questions],
                "source_observation_ids": [obs.id for obs in converted.observations],
                "system_context_version": system_context.version,
            },
            model_usages=list(usages),
            prompt_version=composed.reference,
            model_name=context.model.name,
            metadata={
                "attempts": attempts,
                "excluded": len(package.excluded_evidence_ids),
                "carried_reviewer_feedback": bool(self.reviewer_feedback),
            },
        )

    # -- persistence -----------------------------------------------------------------------

    def _persist(
        self, context: NodeContext, proposal: ContextExtractionProposal
    ) -> ConvertedContext:
        """Allocate identifiers and store the objects, in one transaction.

        Conversion and persistence share a transaction because DEC-018 assigns an identifier from a
        counter at insert: a converted object that was never saved would have consumed a number,
        and the gap reads as a deleted object.
        """
        repository = context.handle.objects
        with repository.transaction():
            converted = convert_proposal(
                proposal,
                allocator=repository,
                assessment_id=context.handle.assessment_id,
                created_at=now(),
                generated_by=CONTEXT_EXTRACTION_AGENT,
            )
            for obj in converted.all_objects():
                repository.save(obj)
        return converted

    def _system_context(
        self,
        context: NodeContext,
        proposal: ContextExtractionProposal,
        converted: ConvertedContext,
    ) -> SystemContext:
        """The first baseline: version 1, unapproved, holding identifiers and nothing else.

        Unapproved is not a default that could be overridden — `approved_at` and `approved_by` stay
        unset because approval is the reviewer's at the checkpoint that follows (DEC-005), and this
        node has no way to reach it.
        """
        # The baseline lists the seeded objects too: a DEC-070 parser may have persisted
        # components and flows before this node ran, and a baseline that omitted them would put
        # objects in front of checkpoint 1's validation that its own context never named. The
        # union is explicit rather than a repository sweep, so a re-extraction run cannot
        # accidentally adopt a rejected revision's objects.
        seeded = self.seeded
        system = SystemContext.model_validate(
            proposal.system.model_dump()
            | {
                "assessment_id": context.handle.assessment_id,
                "context_claim_ids": [
                    claim.id for claim in (*(seeded.claims if seeded else ()), *converted.claims)
                ],
                "component_ids": [
                    component.id
                    for component in (
                        *(seeded.components if seeded else ()),
                        *converted.components,
                    )
                ],
                "asset_ids": [
                    asset.id for asset in (*(seeded.assets if seeded else ()), *converted.assets)
                ],
                "actor_ids": [
                    actor.id for actor in (*(seeded.actors if seeded else ()), *converted.actors)
                ],
                "data_flow_ids": [
                    flow.id
                    for flow in (*(seeded.data_flows if seeded else ()), *converted.data_flows)
                ],
                "trust_boundary_ids": [
                    boundary.id
                    for boundary in (
                        *(seeded.trust_boundaries if seeded else ()),
                        *converted.trust_boundaries,
                    )
                ],
                "version": FIRST_VERSION,
            }
        )
        with context.handle.objects.transaction():
            context.handle.objects.save(system)
        return system


def _schema_text() -> str:
    """The exported proposal schema, as the prompt embeds it."""
    import json

    return json.dumps(ContextExtractionProposal.model_json_schema(), indent=2)
