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
from trace_ai.infrastructure.model.seam import ModelFailure, ModelSuccess
from trace_ai.services.context.input_package import assemble_extractor_input
from trace_ai.workflow.errors import ErrorClass, classify_model_failure
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
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    structured_input: dict[str, Any] | None = None

    version: str = NODE_VERSION
    execution_type: ExecutionType = field(default=ExecutionType.MODEL, init=False)

    @property
    def name(self) -> str:
        return NODE_NAME

    @property
    def phase(self) -> Phase:
        return Phase.CONTEXT_EXTRACTION

    def _projected_cost(self, prompt: str) -> Any:
        return _projected_cost_for(self.profile, prompt)

    def run(self, context: NodeContext) -> NodeResult:
        """One extraction: assemble, call, convert, persist, and report what was produced."""
        if context.model is None:
            raise ValueError(
                f"{NODE_NAME} is a model-assisted node and was given no model. A deterministic "
                f"node is classified as one in agent-design.md section 4."
            )

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

        usages: list[Any] = []
        attempts = 0

        def attempt(state: Any) -> ContextExtractionProposal:
            nonlocal attempts
            attempts += 1

            prompt = (
                composed.text
                if state.feedback is None
                else (
                    f"{composed.text}\n\n## Validation feedback on your previous attempt\n\n"
                    f"{state.feedback}\n\nReturn a corrected object. Do not restate the previous one."
                )
            )

            if self.budget is not None:
                self.budget.check_model_call(estimated_cost=self._projected_cost(prompt))

            outcome = context.model.generate(  # type: ignore[union-attr]
                prompt=prompt,
                schema=ContextExtractionProposal,
                settings=self.profile.settings,
                system=package.trusted,
            )

            if isinstance(outcome, ModelFailure):
                usages.append(outcome.usage)
                if self.budget is not None:
                    self.budget.spend_model_call(outcome.usage.estimated_cost)
                raise AttemptFailedError(
                    error_class=classify_model_failure(outcome.reason),
                    message=outcome.message,
                    raw_output=outcome.raw_output,
                    feedback=outcome.message,
                )

            if not isinstance(outcome, ModelSuccess):  # pragma: no cover - the union has two arms
                raise AttemptFailedError(
                    error_class=ErrorClass.UNEXPECTED_APPLICATION_FAILURE,
                    message=f"the model seam returned {type(outcome).__name__}",
                )
            usages.append(outcome.usage)
            if self.budget is not None:
                self.budget.spend_model_call(outcome.usage.estimated_cost)

            proposal = outcome.value
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
                policy=self.retry_policy,
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
            metadata={"attempts": attempts, "excluded": len(package.excluded_evidence_ids)},
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
        system = SystemContext.model_validate(
            proposal.system.model_dump()
            | {
                "assessment_id": context.handle.assessment_id,
                "context_claim_ids": [claim.id for claim in converted.claims],
                "component_ids": [component.id for component in converted.components],
                "asset_ids": [asset.id for asset in converted.assets],
                "actor_ids": [actor.id for actor in converted.actors],
                "data_flow_ids": [flow.id for flow in converted.data_flows],
                "trust_boundary_ids": [boundary.id for boundary in converted.trust_boundaries],
                "version": FIRST_VERSION,
            }
        )
        with context.handle.objects.transaction():
            context.handle.objects.save(system)
        return system


def _projected_cost_for(profile: ModelProfile, prompt: str) -> Any:
    """A conservative projection of one call's cost, for the pre-call ceiling check.

    Input is estimated from the prompt's length at roughly four characters per token, and output is
    charged at the full `max_output_tokens` — a call cannot cost more than that, so a ceiling
    enforced against this projection is never crossed. It is deliberately pessimistic: the
    alternative is a ceiling checked after the money is spent, which is a record rather than a
    limit. The tradeoff is that a run can be stopped slightly early.
    """
    return profile.cost_of(
        input_tokens=len(prompt) // 4,
        output_tokens=profile.settings.max_output_tokens,
    )


def _schema_text() -> str:
    """The exported proposal schema, as the prompt embeds it."""
    import json

    return json.dumps(ContextExtractionProposal.model_json_schema(), indent=2)
