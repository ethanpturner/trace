"""The Threat Analysis node: the second model-assisted step, and the first that reasons.

`agent-design.md` section 10 specifies the contract. The node's shape follows
`ContextExtractionNode` closely, because the retry rule, the ceiling checks, and the
preserve-the-failed-output rule are the same everywhere and a second interpretation of any of them
would be a second thing to keep right. What is specific to this step is below.

**It reasons from the approved baseline, and refuses anything else.** `current-architecture.md`
section 5.6 has threat analysis work from the approved context rather than reinterpreting the
documents. `assemble_threat_input` raises `UnapprovedContextError` on an unapproved revision, and
this node does not catch it: a run that produced threats against a context nobody signed off would
leave artifacts indistinguishable from a correct one.

**Moderate creativity, and only here.** Section 29 gives this agent the one non-`low` creativity
setting in the MVP, because threat generation benefits from breadth -- subject to that section's
constraint that creativity must not override architectural grounding. The grounding is enforced by
`validate_references`, not by the setting: a threat naming a component that was not supplied fails
validation whatever latitude produced it.

**A reference to something the package did not contain is a retryable schema failure.** Section 10
prohibits inventing components, and DEC-016's error taxonomy classifies a bad reference as
`missing_required_relationship`, which is retryable because it is a shape error the agent can be
told about. The correction carries every unknown identifier at once.

**Zero threats is a success.** Section 10 puts quality above volume, and a node that retried a
low threat count would be asking a model to produce threats until it produced some, which is the
fabrication `agent-design.md` section 26 describes in the general case. `insufficient_evidence` is
not retryable and neither is a small answer, which is not an error at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.base import now
from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.proposals.catalog_gap import promote_catalog_gap_candidate
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.proposals.threat_analysis import (
    THREAT_ANALYSIS_AGENT,
    ThreatAnalysisProposal,
    promote_threat,
)
from trace_ai.infrastructure.model.seam import Creativity, ModelFailure, ModelSuccess
from trace_ai.services.threats.input_package import assemble_threat_input
from trace_ai.workflow.errors import ErrorClass, classify_model_failure
from trace_ai.workflow.nodes import NodeResult
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.retry import AttemptFailedError, RetryPolicy, run_with_retries

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.catalog_gap_candidate import CatalogGapCandidate
    from trace_ai.domain.system_context import SystemContext
    from trace_ai.domain.threat import Threat
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.services.execution_ledger import ExecutionLedger
    from trace_ai.services.prompts import PromptRegistry
    from trace_ai.workflow.limits import Budget
    from trace_ai.workflow.nodes import NodeContext

__all__ = ["NODE_NAME", "NODE_VERSION", "PROMPT_ID", "PROMPT_VERSION", "ThreatAnalysisNode"]

NODE_NAME: Final = "threat-analysis"
NODE_VERSION: Final = "0.1"
PROMPT_ID: Final = "generate-scenario-threats"
PROMPT_VERSION: Final = "v1"

_SCHEMA_MARKER: Final = "schema.threat_analysis_proposal"


def _schema_text() -> str:
    """The application's own exported schema, substituted into the prompt.

    Exported rather than restated, for the reason the registry's docstring gives: a copy pasted
    into the prompt file drifts until a test notices, and this cannot drift at all.
    """
    return json.dumps(ThreatAnalysisProposal.model_json_schema(), indent=2, sort_keys=True)


@dataclass(slots=True)
class ThreatAnalysisNode:
    """Ask the model for threats against an approved context, and record what they cost."""

    ledger: ExecutionLedger
    index: EvidenceIndex
    profile: ModelProfile
    registry: PromptRegistry
    context: SystemContext
    evidence_ids: Sequence[str]
    assessment_name: str
    threat_methodology: str
    budget: Budget | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    version: str = NODE_VERSION
    execution_type: ExecutionType = field(default=ExecutionType.MODEL, init=False)

    @property
    def name(self) -> str:
        return NODE_NAME

    @property
    def phase(self) -> Phase:
        return Phase.THREAT_GENERATION

    def run(self, context: NodeContext) -> NodeResult:
        """One threat-analysis pass: assemble, call, promote, persist, and report."""
        if context.model is None:
            raise ValueError(
                f"{NODE_NAME} is a model-assisted node and was given no model. A deterministic "
                f"node is classified as one in agent-design.md section 4."
            )

        # Section 29's moderate creativity. Applied to a copy: the profile carries the run's model
        # and limits, and the latitude belongs to the agent rather than to the run.
        profile = self.profile.with_creativity(Creativity.MODERATE)

        package = assemble_threat_input(
            context.handle,
            context=self.context,
            index=self.index,
            evidence_ids=self.evidence_ids,
            profile=profile,
            assessment_name=self.assessment_name,
            threat_methodology=self.threat_methodology,
        )
        composed = self.registry.compose(
            PROMPT_ID,
            PROMPT_VERSION,
            {_SCHEMA_MARKER: _schema_text(), **package.substitutions()},
        )
        available = package.referenceable_ids()

        usages: list[Any] = []
        attempts = 0

        def attempt(state: Any) -> ThreatAnalysisProposal:
            nonlocal attempts
            attempts += 1

            prompt = (
                composed.text
                if state.feedback is None
                else (
                    f"{composed.text}\n\n## Validation feedback on your previous attempt\n\n"
                    f"{state.feedback}\n\nReturn a corrected object. Do not restate the previous "
                    f"one, and do not add threats to compensate."
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
                schema=ThreatAnalysisProposal,
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
            if self.budget is not None:
                self.budget.spend_model_call(outcome.usage.estimated_cost)

            proposal = outcome.value
            # Specificity first: a set of category labels referencing nothing would otherwise be
            # reported as a reference problem, which is the less useful of the two corrections.
            try:
                proposal.validate_specificity()
            except ProposalError as generic:
                raise AttemptFailedError(
                    error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
                    message=str(generic),
                    raw_output=proposal.model_dump_json(indent=2),
                    feedback=str(generic),
                ) from None
            try:
                proposal.validate_references(available)
            except ProposalError as invalid:
                raise AttemptFailedError(
                    error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
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

            threats, candidates = self._persist(context, proposal)
            threat_ids = [threat.id for threat in threats]
            produced = [*threat_ids, *(candidate.id for candidate in candidates)]
            execution.produced(*produced)
            for usage in usages:
                execution.record_usage(usage)
            execution.metadata["attempts"] = attempts
            execution.metadata["threats"] = len(threats)
            execution.metadata["catalog_gap_candidates"] = len(candidates)
            execution.metadata["evidence_excluded"] = len(package.excluded_evidence_ids)
            if package.excluded_evidence_ids:
                # DEC-071: the fence rule names what a budget excluded; persisting the names is
                # what lets the coverage ledger carry them to the reader instead of a count
                # dying inside the run.
                execution.metadata["excluded_evidence_ids"] = sorted(package.excluded_evidence_ids)

        return NodeResult(
            produced_object_ids=produced,
            consumed_object_ids=list(package.evidence_ids),
            # Candidates are not in the state: section 31 keeps identifiers and *routing*, and a
            # candidate routes nowhere — no later phase consumes it (DEC-065).
            state_changes={"candidate_threat_ids": threat_ids},
            model_usages=list(usages),
            prompt_version=composed.reference,
            model_name=context.model.name,
            metadata={
                "attempts": attempts,
                "threats": len(threats),
                "catalog_gap_candidates": len(candidates),
                "excluded": len(package.excluded_evidence_ids),
                "context_version": self.context.version,
            },
        )

    def _persist(
        self, context: NodeContext, proposal: ThreatAnalysisProposal
    ) -> tuple[list[Threat], list[CatalogGapCandidate]]:
        """Allocate identifiers and store the threats and candidates, in one transaction.

        Allocation and insert share a transaction because DEC-018 takes the number from a counter
        at insert: a promoted threat that was never saved would have consumed one, and the gap
        reads as a deleted object. Order follows the proposal, so a re-run over the same response
        numbers them the same way. Catalog-gap candidates persist beside the threats as routed
        artifacts (DEC-065): allocated like anything else, consumed by no later phase.
        """
        repository = context.handle.objects
        stamped = now()
        threats: list[Threat] = []
        candidates: list[CatalogGapCandidate] = []
        with repository.transaction():
            for proposed in proposal.threats:
                threat = promote_threat(
                    proposed,
                    threat_id=repository.allocate("thr"),
                    assessment_id=context.handle.assessment_id,
                    generated_by=THREAT_ANALYSIS_AGENT,
                    created_at=stamped,
                )
                repository.save(threat)
                threats.append(threat)
            for proposed_candidate in proposal.catalog_gap_candidates:
                candidate = promote_catalog_gap_candidate(
                    proposed_candidate,
                    candidate_id=repository.allocate("cgc"),
                    assessment_id=context.handle.assessment_id,
                    generated_by=THREAT_ANALYSIS_AGENT,
                    created_at=stamped,
                )
                repository.save(candidate)
                candidates.append(candidate)
        return threats, candidates
