"""The Evidence Validation node: the step that separates supported from merely asserted.

`agent-design.md` section 14 specifies the contract, and section 35 Phase 3 groups this agent with
the mapper under one success condition: Trace distinguishes among satisfied, unverified, and unmet
requirements without treating missing documentation as proof of weakness. The mapper draws the
conclusion; this step decides whether the documents carry it.

The shape follows `RequirementControlMappingNode` — retry, ceilings, and preserve-the-failed-output
are the same rules everywhere. Three things are specific.

**The misquotation check is deterministic, and it is the one failure condition here that can be.**
Section 14 makes "the rationale misquotes or materially changes evidence" invalid output, and
`data-model.md` section 8 forbids modifying an `EvidenceReference` after creation — so any
divergence between what the agent wrote down and what the passage says is the agent's. The proposal
carries `quoted_text` for exactly this comparison. Whitespace is collapsed before comparing, so a
rewrapped quotation passes and a changed word does not.

**Section 14's four retry conditions are its four, and no more.** Schema failure, omitted evidence
references, failing to distinguish support from inference, and unaddressed contradictions. A
classification of `unsupported` is *not* among them: retrying it would ask the agent to find
support that does not exist, which section 26 describes in the general case as inviting fabrication
on the third attempt. An assessment set with no `unsupported` classification is a success, and so
is one with nothing else.

**A contradiction in the input must be addressed by some assessment.** Section 14 makes
"contradictory evidence is ignored" a failure condition, and ignoring is only detectable against
the set as a whole: no individual assessment is wrong for not mentioning a contradiction that
another one handles. The check is that every contradiction the package carried is named by at least
one assessment.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.proposals.evidence_validation import (
    EVIDENCE_VALIDATION_AGENT,
    EvidenceValidationProposal,
)
from trace_ai.infrastructure.model.seam import Creativity, ModelFailure, ModelSuccess
from trace_ai.services.evidence.validation_package import (
    EvidenceValidationInput,
    assemble_evidence_input,
)
from trace_ai.workflow.errors import ErrorClass, classify_model_failure
from trace_ai.workflow.limits import resolve_retry_policy
from trace_ai.workflow.nodes import NodeResult
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.retry import AttemptFailedError, RetryPolicy, run_with_retries

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.source_observation import SourceObservation
    from trace_ai.infrastructure.model.profiles import ModelProfile
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
    "EvidenceValidationNode",
    "EvidenceValidationOutcome",
    "unaddressed_contradictions",
]

NODE_NAME: Final = "evidence-validation"
NODE_VERSION: Final = "0.1"
PROMPT_ID: Final = "validate-evidence"
PROMPT_VERSION: Final = "v1"

_SCHEMA_MARKER: Final = "schema.evidence_validation_proposal"


def _schema_text() -> str:
    """The application's own exported schema, substituted into the prompt."""
    return json.dumps(EvidenceValidationProposal.model_json_schema(), indent=2, sort_keys=True)


def unaddressed_contradictions(
    proposal: EvidenceValidationProposal, supplied: Sequence[str]
) -> tuple[str, ...]:
    """Contradictions the package carried that no assessment named (section 14).

    A set-level check, because no individual assessment is wrong for staying silent about a
    contradiction another one handles. What is wrong is the whole response passing over one.
    """
    named = {
        contradiction
        for assessment in proposal.assessments
        for contradiction in assessment.contradictions
    }
    return tuple(sorted(set(supplied) - named))


@dataclass(frozen=True, slots=True)
class EvidenceValidationOutcome:
    """What one evidence-validation call produced: the package, the proposal, and the result.

    Three things rather than one because they have three consumers. `result` is what the
    orchestrator records; `proposal` is what the deterministic node validates and persists; and
    `package` is what that node needs in order to check the proposal against what was actually
    supplied. `NodeResult` cannot carry any of it -- it holds identifiers, counts, and costs and
    never an object, which is `data-model.md` section 31's state-design rule.
    """

    package: EvidenceValidationInput
    proposal: EvidenceValidationProposal
    result: NodeResult


@dataclass(slots=True)
class EvidenceValidationNode:
    """Ask the model whether the evidence carries the conclusions, and record what it cost."""

    ledger: ExecutionLedger
    index: EvidenceIndex
    profile: ModelProfile
    registry: PromptRegistry
    subjects: Sequence[DomainModel]
    observations: Sequence[SourceObservation] = ()
    budget: Budget | None = None
    retry_policy: RetryPolicy | None = None
    """The attempt loop's policy. `None` — the norm under the driver — defers to the
    budget's `retry_policy()`, so the configuration's `maximum_retries_per_node` is the
    operative ceiling (#397); the built-in default applies only when there is neither."""

    version: str = NODE_VERSION
    execution_type: ExecutionType = field(default=ExecutionType.MODEL, init=False)

    @property
    def name(self) -> str:
        return NODE_NAME

    @property
    def phase(self) -> Phase:
        return Phase.EVIDENCE_VALIDATION

    def run(self, context: NodeContext) -> NodeResult:
        """The `Node` protocol's entry point. A caller needing the output calls `propose`."""
        return self.propose(context).result

    def propose(self, context: NodeContext) -> EvidenceValidationOutcome:
        """One evidence-validation pass: assemble, call, check, and report.

        **It persists nothing.** `agent-design.md` section 22's write model gives the write to the
        deterministic step behind this one, so what comes back is a checked proposal and the
        package it was checked against. This module contains no store write at all.
        """
        if context.model is None:
            raise ValueError(
                f"{NODE_NAME} is a model-assisted node and was given no model. A deterministic "
                f"node is classified as one in agent-design.md section 4."
            )

        # Section 29's low creativity. Latitude here would mean a looser reading of what a passage
        # supports, which is the one judgment this step exists to make strictly.
        profile = self.profile.with_creativity(Creativity.LOW)

        package = assemble_evidence_input(
            assessment_id=context.handle.assessment_id,
            subjects=self.subjects,
            index=self.index,
            observations=self.observations,
            profile=profile,
        )
        composed = self.registry.compose(
            PROMPT_ID,
            PROMPT_VERSION,
            {_SCHEMA_MARKER: _schema_text(), **package.substitutions()},
        )
        available = package.referenceable_ids()

        usages: list[Any] = []
        attempts = 0

        def attempt(state: Any) -> EvidenceValidationProposal:
            nonlocal attempts
            attempts += 1
            execution.retry_number = attempts - 1

            prompt = (
                composed.text
                if state.feedback is None
                else (
                    f"{composed.text}\n\n## Validation feedback on your previous attempt\n\n"
                    f"{state.feedback}\n\nReturn a corrected object. Do not restate the previous "
                    f"one, and do not raise a classification to make the correction easier."
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
                schema=EvidenceValidationProposal,
                settings=profile.settings,
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

            # Section 29: the conditions the call actually ran at, recorded where a reader of the
            # ExecutionRecord can find them -- a wrong effort mapping is otherwise invisible (#401).
            for condition_key in ("effort", "creativity"):
                if condition_key in outcome.metadata:
                    execution.metadata[condition_key] = outcome.metadata[condition_key]
            if self.budget is not None:
                self.budget.spend_model_call(outcome.usage.estimated_cost)

            proposal = outcome.value

            # Section 14's four retry conditions, in the order that makes each correction the most
            # useful one to receive. References first: an assessment about something that was not
            # supplied cannot be judged on anything else.
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
                proposal.validate_quotations(package.quoted_text)
            except ProposalError as misquoted:
                raise AttemptFailedError(
                    error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
                    message=str(misquoted),
                    raw_output=proposal.model_dump_json(indent=2),
                    feedback=str(misquoted),
                ) from None

            ignored = unaddressed_contradictions(proposal, package.contradiction_ids)
            if ignored:
                message = (
                    f"these contradictions were supplied and no assessment addresses them: "
                    f"{list(ignored)}. Contradictory evidence may not be passed over "
                    f"(agent-design.md section 14). Name the record on the assessment it bears on."
                )
                raise AttemptFailedError(
                    error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
                    message=message,
                    raw_output=proposal.model_dump_json(indent=2),
                    feedback=message,
                )

            return proposal

        with self.ledger.record(
            NODE_NAME,
            node_version=self.version,
            execution_type=ExecutionType.MODEL,
            consumes=package.input_object_ids(),
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

            for usage in usages:
                execution.record_usage(usage)
            execution.metadata["attempts"] = attempts
            execution.metadata["subjects"] = len(package.subject_ids)
            execution.metadata["assessments"] = len(proposal.assessments)
            execution.metadata["contradictions"] = len(package.contradiction_ids)

        return EvidenceValidationOutcome(
            package=package,
            proposal=proposal,
            result=NodeResult(
                produced_object_ids=[],
                consumed_object_ids=list(package.input_object_ids()),
                state_changes={},
                model_usages=list(usages),
                prompt_version=composed.reference,
                model_name=context.model.name,
                metadata={
                    "attempts": attempts,
                    "subjects": len(package.subject_ids),
                    "assessments": len(proposal.assessments),
                    "contradictions": len(package.contradiction_ids),
                    "agent": EVIDENCE_VALIDATION_AGENT,
                },
            ),
        )
