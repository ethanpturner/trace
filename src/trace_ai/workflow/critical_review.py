"""The Critical Review node: the fifth agent, and the one whose value is not yet established.

`agent-design.md` section 15 specifies the contract. `docs/product/roadmap.md` Stage 4 sets a
decision gate on it — "if the critic or another agent does not improve results, remove or defer
it" — and section 40 lists "the critic creates noise" among the simplification triggers. This
module is written so that removing it is deleting a file and a phase entry, not unpicking a
dependency: nothing else imports it, and no other node's behaviour changes if it never runs.

**One review group per call** (DEC-049). The group is one threat's lineage, and section 15's
"unrestricted second full assessment" prohibition is enforced by what the package contains rather
than by an instruction. An agent shown everything re-derives everything.

**It persists nothing.** The same arrangement as evidence validation, and for the same reason
(DEC-048's argument, applied again): section 22's write model gives the write to the deterministic
node behind this one, and this module contains no store write, so the rule is a property of the
import graph rather than a convention. `propose` returns the group and the checked proposal.

**Zero critiques is a success and never a retry.** Section 15 makes "generates large quantities of
superficial criticism" a failure condition and its retry list contains no volume condition. A node
that retried an empty response would be the mechanism by which the critic learned to manufacture
findings, which is the failure the same section names.

**Low-to-moderate creativity** (section 29). The one thing latitude buys here is noticing an
inconsistency nobody specified a check for; the one thing it costs is superficial volume. Moderate
is the reading of "low to moderate" that treats the critic as a search rather than as a checklist,
and it is the setting most worth revisiting at the Stage 4 gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.proposals.critical_review import (
    CRITICAL_REVIEW_AGENT,
    CriticalReviewProposal,
)
from trace_ai.infrastructure.model.seam import Creativity, ModelFailure, ModelSuccess
from trace_ai.services.critique.input_package import ReviewGroup, assemble_review_group
from trace_ai.workflow.errors import ErrorClass, classify_model_failure
from trace_ai.workflow.nodes import NodeResult
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.retry import AttemptFailedError, RetryPolicy, run_with_retries

if TYPE_CHECKING:
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.critique.input_package import SelectedObjects
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.services.execution_ledger import ExecutionLedger
    from trace_ai.services.prompts import PromptRegistry
    from trace_ai.workflow.limits import Budget
    from trace_ai.workflow.nodes import NodeContext

__all__ = [
    "NODE_NAME",
    "NODE_VERSION",
    "PROMPT_ID",
    "PROMPT_VERSION",
    "CriticalReviewNode",
    "CriticalReviewOutcome",
]

NODE_NAME: Final = "critical-review"
NODE_VERSION: Final = "0.1"
PROMPT_ID: Final = "challenge-analysis"
PROMPT_VERSION: Final = "v1"

_SCHEMA_MARKER: Final = "schema.critical_review_proposal"


def _schema_text() -> str:
    """The application's own exported schema, substituted into the prompt."""
    return json.dumps(CriticalReviewProposal.model_json_schema(), indent=2, sort_keys=True)


@dataclass(frozen=True, slots=True)
class CriticalReviewOutcome:
    """What one review call produced: the group, the proposal, and the result."""

    group: ReviewGroup
    proposal: CriticalReviewProposal
    result: NodeResult


@dataclass(slots=True)
class CriticalReviewNode:
    """Challenge one threat's analysis, and record what the challenge cost."""

    ledger: ExecutionLedger
    index: EvidenceIndex
    profile: ModelProfile
    registry: PromptRegistry
    selected: SelectedObjects
    budget: Budget | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    version: str = NODE_VERSION
    execution_type: ExecutionType = field(default=ExecutionType.MODEL, init=False)

    @property
    def name(self) -> str:
        return NODE_NAME

    @property
    def phase(self) -> Phase:
        return Phase.CRITICAL_REVIEW

    def run(self, context: NodeContext) -> NodeResult:
        """The `Node` protocol's entry point. A caller needing the output calls `propose`."""
        return self.propose(context).result

    def propose(self, context: NodeContext) -> CriticalReviewOutcome:
        """One review pass over one group: assemble, call, check, and report. Persists nothing."""
        if context.model is None:
            raise ValueError(
                f"{NODE_NAME} is a model-assisted node and was given no model. A deterministic "
                f"node is classified as one in agent-design.md section 4."
            )

        profile = self.profile.with_creativity(Creativity.MODERATE)

        group = assemble_review_group(
            assessment_id=context.handle.assessment_id,
            selected=self.selected,
            index=self.index,
            profile=profile,
        )
        composed = self.registry.compose(
            PROMPT_ID,
            PROMPT_VERSION,
            {_SCHEMA_MARKER: _schema_text(), **group.substitutions()},
        )
        available = group.referenceable_ids()

        usages: list[Any] = []
        attempts = 0

        def attempt(state: Any) -> CriticalReviewProposal:
            nonlocal attempts
            attempts += 1

            prompt = (
                composed.text
                if state.feedback is None
                else (
                    f"{composed.text}\n\n## Validation feedback on your previous attempt\n\n"
                    f"{state.feedback}\n\nReturn a corrected object. Do not restate the previous "
                    f"one, and do not add critiques to compensate — an empty list is a valid "
                    f"answer."
                )
            )

            if self.budget is not None:
                self.budget.check_model_call(
                    estimated_cost=profile.cost_of(
                        input_tokens=len(prompt) // 4,
                        output_tokens=profile.settings.max_output_tokens,
                    )
                )

            outcome = context.model.generate(  # type: ignore[union-attr]
                prompt=prompt,
                schema=CriticalReviewProposal,
                settings=profile.settings,
                system=group.trusted,
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

            # Section 15's retry conditions. References first: a critique of something outside the
            # group is the scope error, and correcting it is different from correcting a shallow
            # critique of something inside it.
            try:
                proposal.validate_references(available)
            except ProposalError as invalid:
                raise AttemptFailedError(
                    error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
                    message=str(invalid),
                    raw_output=proposal.model_dump_json(indent=2),
                    feedback=str(invalid),
                ) from None

            try:
                proposal.validate_distinctness()
            except ProposalError as repeated:
                raise AttemptFailedError(
                    error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
                    message=str(repeated),
                    raw_output=proposal.model_dump_json(indent=2),
                    feedback=str(repeated),
                ) from None

            return proposal

        with self.ledger.record(
            NODE_NAME,
            node_version=self.version,
            execution_type=ExecutionType.MODEL,
            consumes=group.input_object_ids(),
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

            for usage in usages:
                execution.record_usage(usage)
            execution.metadata["attempts"] = attempts
            execution.metadata["threat_id"] = group.threat_id
            execution.metadata["critiques"] = len(proposal.critiques)
            execution.metadata["reviewed_objects"] = group.reviewed_object_count

        return CriticalReviewOutcome(
            group=group,
            proposal=proposal,
            result=NodeResult(
                produced_object_ids=[],
                consumed_object_ids=list(group.input_object_ids()),
                state_changes={},
                model_usages=list(usages),
                prompt_version=composed.reference,
                model_name=context.model.name,
                metadata={
                    "attempts": attempts,
                    "threat_id": group.threat_id,
                    "critiques": len(proposal.critiques),
                    "reviewed_objects": group.reviewed_object_count,
                    "agent": CRITICAL_REVIEW_AGENT,
                },
            ),
        )
