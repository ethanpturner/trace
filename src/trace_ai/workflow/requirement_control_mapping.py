"""The Requirement and Control Mapping node: the step where the assessment starts narrowing.

`agent-design.md` section 12 specifies the contract, and `docs/product/roadmap.md` Stage 3 names
this the core false-positive-reduction mechanism. Section 35 Phase 3 states the success condition:
"Trace distinguishes among satisfied, unverified, and unmet requirements without treating missing
documentation as proof of weakness."

The shape follows `ThreatAnalysisNode` closely — retry, ceilings, and preserve-the-failed-output
are the same everywhere and a second interpretation of any of them would be a second thing to keep
right. Four things are specific to this step.

**One agent, not two.** DEC-024 removed the deterministic requirement matcher the backlog put in
front of this node. There is nothing to filter on: `applicable_technologies` is populated on zero
of the twenty-three requirements, and the remaining candidate fields are free text by decision. The
whole catalog goes in every call, and the discrimination constraint is enforced on the output.

**Low creativity** (section 29). This is the one agent whose latitude would directly damage its
purpose: breadth here means marking more requirements applicable, and undiscriminated applicability
is section 12's named failure condition.

**A requirement remaining `unverified` never triggers a retry.** Section 12 says so directly, and
section 26 gives the general reason: retrying an analysis condition invites the agent to fabricate
an answer on the third attempt, because producing one is the only way to stop being retried. What
*is* retried is shape — a schema failure, a missing applicability rationale, a reference to
something the package did not contain. A mapping run producing zero `unmet` statuses is a success.

**Suppressions are carried, never dropped.** DEC-025 puts a declined negative conclusion on the
mapping that declined it, and this node promotes both halves unchanged. `evaluation-plan.md`
section 8 makes false-negative rate a primary metric, and a suppression that leaves no trace is
invisible to exactly the measurement meant to catch over-suppression.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.proposals.mapping import (
    MAPPING_AGENT,
    MappingProposal,
    promote_control,
    promote_documentation_gap,
    promote_mapping,
)
from trace_ai.infrastructure.model.seam import Creativity, ModelFailure, ModelSuccess
from trace_ai.services.mapping.input_package import assemble_mapping_input
from trace_ai.workflow.errors import ErrorClass, classify_model_failure
from trace_ai.workflow.nodes import NodeResult
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.retry import AttemptFailedError, RetryPolicy, run_with_retries

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.control import Control
    from trace_ai.domain.control_mapping import ControlMapping
    from trace_ai.domain.documentation_gap import DocumentationGap
    from trace_ai.domain.system_context import SystemContext
    from trace_ai.domain.threat import Threat
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.services.execution_ledger import ExecutionLedger
    from trace_ai.services.prompts import PromptRegistry
    from trace_ai.services.requirements.loader import LoadedCatalog
    from trace_ai.workflow.limits import Budget
    from trace_ai.workflow.nodes import NodeContext

__all__ = [
    "NODE_NAME",
    "NODE_VERSION",
    "PROMPT_ID",
    "PROMPT_VERSION",
    "MappingOutcome",
    "RequirementControlMappingNode",
]

NODE_NAME: Final = "requirement-and-control-mapping"
NODE_VERSION: Final = "0.1"
PROMPT_ID: Final = "map-requirements-controls"
PROMPT_VERSION: Final = "v1"

_SCHEMA_MARKER: Final = "schema.mapping_proposal"


def _schema_text() -> str:
    """The application's own exported schema, substituted into the prompt.

    Exported rather than restated: a copy pasted into the prompt file drifts until a test notices,
    and this cannot drift at all.
    """
    return json.dumps(MappingProposal.model_json_schema(), indent=2, sort_keys=True)


@dataclass(frozen=True, slots=True)
class MappingOutcome:
    """What one mapping call produced, after promotion and persistence."""

    controls: tuple[Control, ...]
    mappings: tuple[ControlMapping, ...]
    documentation_gaps: tuple[DocumentationGap, ...]

    @property
    def object_ids(self) -> list[str]:
        return [
            *(control.id for control in self.controls),
            *(mapping.id for mapping in self.mappings),
            *(gap.id for gap in self.documentation_gaps),
        ]


@dataclass(slots=True)
class RequirementControlMappingNode:
    """Map one threat against the catalog, and record what the answer cost."""

    ledger: ExecutionLedger
    index: EvidenceIndex
    profile: ModelProfile
    registry: PromptRegistry
    context: SystemContext
    catalog: LoadedCatalog
    threat: Threat
    evidence_ids: Sequence[str]
    budget: Budget | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    version: str = NODE_VERSION
    execution_type: ExecutionType = field(default=ExecutionType.MODEL, init=False)

    @property
    def name(self) -> str:
        return NODE_NAME

    @property
    def phase(self) -> Phase:
        return Phase.REQUIREMENT_AND_CONTROL_MAPPING

    def run(self, context: NodeContext) -> NodeResult:
        """One mapping pass over one threat: assemble, call, promote, persist, and report."""
        if context.model is None:
            raise ValueError(
                f"{NODE_NAME} is a model-assisted node and was given no model. A deterministic "
                f"node is classified as one in agent-design.md section 4."
            )

        # Section 29's low creativity, applied to a copy. Breadth here means marking more
        # requirements applicable, which is the failure condition rather than the goal.
        profile = self.profile.with_creativity(Creativity.LOW)

        package = assemble_mapping_input(
            context.handle,
            context=self.context,
            threat=self.threat,
            catalog=self.catalog,
            index=self.index,
            evidence_ids=self.evidence_ids,
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

        def attempt(state: Any) -> MappingProposal:
            nonlocal attempts
            attempts += 1

            prompt = (
                composed.text
                if state.feedback is None
                else (
                    f"{composed.text}\n\n## Validation feedback on your previous attempt\n\n"
                    f"{state.feedback}\n\nReturn a corrected object. Do not restate the previous "
                    f"one, and do not change a satisfaction status to make the correction easier."
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
                schema=MappingProposal,
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
            # Keys first: an unresolved control key and an unknown identifier are different
            # corrections, and reporting the reference problem for a key would send the agent
            # looking for an object that was never supposed to exist yet.
            try:
                proposal.validate_keys()
            except ProposalError as unresolved:
                raise AttemptFailedError(
                    error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
                    message=str(unresolved),
                    raw_output=proposal.model_dump_json(indent=2),
                    feedback=str(unresolved),
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
            try:
                proposal.validate_threat(self.threat.id)
            except ProposalError as wrong_threat:
                raise AttemptFailedError(
                    error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
                    message=str(wrong_threat),
                    raw_output=proposal.model_dump_json(indent=2),
                    feedback=str(wrong_threat),
                ) from None
            # Last, because it is the correction most likely to be right when the others pass:
            # the shape is fine and one status asserts more than its citations support.
            try:
                proposal.validate_evidence_policy()
            except ProposalError as unsupported:
                raise AttemptFailedError(
                    error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
                    message=str(unsupported),
                    raw_output=proposal.model_dump_json(indent=2),
                    feedback=str(unsupported),
                ) from None
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
                policy=self.retry_policy,
                node_name=NODE_NAME,
                artifacts=context.handle.artifacts,
                on_attempt_failed=lambda number, failure, path: execution.metadata.update(
                    {f"attempt_{number}_failure": failure.error_class.value}
                    | ({f"attempt_{number}_output": path} if path else {})
                ),
            )

            outcome = self._persist(context, proposal)
            produced = outcome.object_ids
            execution.produced(*produced)
            for usage in usages:
                execution.record_usage(usage)
            execution.metadata["attempts"] = attempts
            execution.metadata["catalog_version"] = package.catalog_version
            execution.metadata["threat_id"] = package.threat_id
            execution.metadata["mappings"] = len(outcome.mappings)
            execution.metadata["controls"] = len(outcome.controls)
            execution.metadata["documentation_gaps"] = len(outcome.documentation_gaps)
            execution.metadata["suppressions"] = sum(
                1 for mapping in outcome.mappings if mapping.suppressed_by
            )

        return NodeResult(
            produced_object_ids=produced,
            consumed_object_ids=list(package.input_object_ids()),
            # Section 31's state carries identifiers and routing only. There is no control list
            # here because there is no field for one: `Control` is reached through the mappings
            # that cite it, and a state field would be a second place the set was recorded.
            state_changes={
                "control_mapping_ids": [mapping.id for mapping in outcome.mappings],
                "documentation_gap_ids": [gap.id for gap in outcome.documentation_gaps],
            },
            model_usages=list(usages),
            prompt_version=composed.reference,
            model_name=context.model.name,
            metadata={
                "attempts": attempts,
                "threat_id": package.threat_id,
                "catalog_version": package.catalog_version,
                "mappings": len(outcome.mappings),
                "controls": len(outcome.controls),
                "documentation_gaps": len(outcome.documentation_gaps),
                "requirements_offered": len(package.requirement_ids),
            },
        )

    def _persist(self, context: NodeContext, proposal: MappingProposal) -> MappingOutcome:
        """Allocate identifiers and store everything, in one transaction.

        Controls are allocated first because a mapping's `control_keys` resolve to their
        identifiers, and `promote_mapping` refuses before allocating anything when a key is
        unresolved (DEC-018). Order follows the proposal, so a re-run over the same response
        numbers them the same way.
        """
        repository = context.handle.objects
        assessment_id = context.handle.assessment_id

        controls: list[Control] = []
        mappings: list[ControlMapping] = []
        gaps: list[DocumentationGap] = []

        with repository.transaction():
            allocated: dict[str, str] = {}
            for proposed_control in proposal.controls:
                control = promote_control(
                    proposed_control,
                    control_id=repository.allocate("ctl"),
                    assessment_id=assessment_id,
                    generated_by=MAPPING_AGENT,
                )
                repository.save(control)
                controls.append(control)
                allocated[proposed_control.key] = control.id

            for proposed_mapping in proposal.mappings:
                mapping = promote_mapping(
                    proposed_mapping,
                    mapping_id=repository.allocate("map"),
                    assessment_id=assessment_id,
                    control_ids=allocated,
                    generated_by=MAPPING_AGENT,
                )
                repository.save(mapping)
                mappings.append(mapping)

            for proposed_gap in proposal.documentation_gaps:
                gap = promote_documentation_gap(
                    proposed_gap,
                    gap_id=repository.allocate("gap"),
                    assessment_id=assessment_id,
                    generated_by=MAPPING_AGENT,
                )
                repository.save(gap)
                gaps.append(gap)

        return MappingOutcome(
            controls=tuple(controls),
            mappings=tuple(mappings),
            documentation_gaps=tuple(gaps),
        )
