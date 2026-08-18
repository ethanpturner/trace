"""The Report Generation node: the sixth and last capped agent, and the narrowest.

`agent-design.md` section 19 specifies the contract. The agent writes four passages —
`executive_summary`, `system_overview`, `risk_summary`, and one limitation entry per required
limitation — and nothing else: per-object prose is the renderer's, the document is the renderer's,
and the template is not even an input (DEC-035). Its output is handed to the validator and the
renderer; nothing here writes a report to disk.

**Low creativity** (section 29, resolved by DEC-085). Everything this agent may legitimately do —
summarize, reorder, explain relationships — is grounded in approved objects, and the one thing
latitude buys is the failure condition list: invented conclusions, flattened uncertainty. The
critic runs at moderate because it is a search; this agent is a restatement, and restatement
takes the low reading.

**The failure conditions section 19 makes retryable are checked here**, before the proposal
leaves the node: a limitation set that does not match the required list, and an identifier in
prose the input did not carry — which is how "the report invents conclusions" is detectable by a
deterministic check rather than by judgment. Deeper consistency checking is the report validator's
(#107). A failed attempt's raw output goes to `traces/` (section 33) and the retry carries the
validation feedback forward.

**Zero approved findings is a successful report.** The input states the empty case explicitly and
requires the `lim-empty-findings` limitation; the agent writes it. Nothing here retries an answer
for being about nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.proposals.report_sections import ReportSections
from trace_ai.infrastructure.model.agents import spec_for
from trace_ai.services.report.prompt_input import (
    IDENTIFIER_SHAPE,
    assemble_report_prompt_input,
)
from trace_ai.workflow.errors import ErrorClass
from trace_ai.workflow.limits import resolve_retry_policy
from trace_ai.workflow.model_call import cache_prefix_of, call_model, with_retry_feedback
from trace_ai.workflow.nodes import NodeResult
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.retry import AttemptFailedError, RetryPolicy, run_with_retries

if TYPE_CHECKING:
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.execution_ledger import ExecutionLedger
    from trace_ai.services.prompts import PromptRegistry
    from trace_ai.services.report.input_assembly import ReportInput
    from trace_ai.workflow.limits import Budget
    from trace_ai.workflow.nodes import NodeContext

__all__ = [
    "NODE_NAME",
    "NODE_VERSION",
    "PROMPT_ID",
    "PROMPT_VERSION",
    "REPORT_GENERATION_AGENT",
    "ReportGenerationNode",
    "ReportGenerationOutcome",
]

NODE_NAME: Final = "report-generation"
NODE_VERSION: Final = "0.1"
PROMPT_ID: Final = "generate-report-sections"
PROMPT_VERSION: Final = "v1"

# The agent version (`agent-design.md` section 33's convention). Not the model.
REPORT_GENERATION_AGENT: Final = "report-generation-v1"

_SCHEMA_MARKER: Final = "schema.report_sections"


def _schema_text() -> str:
    return json.dumps(ReportSections.model_json_schema(), indent=2, sort_keys=True)


def _unknown_identifiers(sections: ReportSections, referenceable: frozenset[str]) -> list[str]:
    """Identifier-shaped tokens in the prose that the input did not carry (section 19).

    A fabricated `fnd-009` in the executive summary is the checkable form of an invented
    conclusion. `limitation_id` values are checked separately by `check_required`, so this scan
    covers the prose fields and the limitation texts.
    """
    prose = [
        sections.executive_summary,
        sections.system_overview,
        sections.risk_summary,
        *(entry.text for entry in sections.limitations),
    ]
    mentioned = {match for text in prose for match in IDENTIFIER_SHAPE.findall(text)}
    return sorted(mentioned - referenceable)


@dataclass(frozen=True, slots=True)
class ReportGenerationOutcome:
    """What one generation call produced: the sections and the run record. No document."""

    sections: ReportSections
    result: NodeResult


@dataclass(slots=True)
class ReportGenerationNode:
    """Write the four model-written sections from the assembled approved input."""

    ledger: ExecutionLedger
    profile: ModelProfile
    registry: PromptRegistry
    assembled: ReportInput
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
        return Phase.REPORT_GENERATION

    def run(self, context: NodeContext) -> NodeResult:
        """The `Node` protocol's entry point. A caller needing the sections calls `generate`."""
        return self.generate(context).result

    def generate(self, context: NodeContext) -> ReportGenerationOutcome:
        """One generation pass: render the input, call, check, and report. Persists nothing."""
        if context.model is None:
            raise ValueError(
                f"{NODE_NAME} is a model-assisted node and was given no model. A deterministic "
                f"node is classified as one in agent-design.md section 4."
            )

        # Section 29's creativity for this agent, read from the one `AGENTS` table (WS11).
        profile = self.profile.with_creativity(spec_for(NODE_NAME).creativity)
        package = assemble_report_prompt_input(self.assembled)
        composed = self.registry.compose(
            PROMPT_ID,
            PROMPT_VERSION,
            {_SCHEMA_MARKER: _schema_text(), **package.substitutions()},
        )
        required_ids = [
            limitation.limitation_id for limitation in self.assembled.required_limitations
        ]

        cache_prefix = cache_prefix_of(composed.text, package.substitutions()["input.report"])
        usages: list[Any] = []
        attempts = 0

        def attempt(state: Any) -> ReportSections:
            nonlocal attempts
            attempts += 1
            execution.retry_number = attempts - 1

            prompt = with_retry_feedback(
                composed.text,
                state.feedback,
                instruction=(
                    "Return a corrected object. Write only from the approved input above; do not "
                    "add material to compensate."
                ),
            )
            sections = call_model(
                context.model,
                prompt=prompt,
                schema=ReportSections,
                profile=profile,
                system=None,
                budget=self.budget,
                execution=execution,
                usages=usages,
                cache_prefix=cache_prefix,
            )

            # Section 19's retry conditions, in checkable form. The limitation set first: an
            # omitted limitation is the failure DEC-035's mechanism exists to make structural.
            try:
                sections.check_required(required_ids)
            except ValueError as mismatch:
                raise AttemptFailedError(
                    error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
                    message=str(mismatch),
                    raw_output=sections.model_dump_json(indent=2),
                    feedback=str(mismatch),
                ) from None

            unknown = _unknown_identifiers(sections, package.referenceable)
            if unknown:
                message = (
                    f"the response mentions {unknown}, which the approved input does not "
                    f"carry. A statement about an object the input did not supply is an "
                    f"invented conclusion (agent-design.md section 19)."
                )
                raise AttemptFailedError(
                    error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
                    message=message,
                    raw_output=sections.model_dump_json(indent=2),
                    feedback=message,
                )

            return sections

        with self.ledger.record(
            NODE_NAME,
            node_version=self.version,
            execution_type=ExecutionType.MODEL,
            consumes=package.input_object_ids,
        ) as execution:
            execution.prompt_version = composed.reference
            sections = run_with_retries(
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
            execution.metadata["approved_findings"] = len(self.assembled.approved_findings)
            execution.metadata["required_limitations"] = len(required_ids)
            execution.metadata["zero_approved_findings"] = self.assembled.zero_approved_findings

        return ReportGenerationOutcome(
            sections=sections,
            result=NodeResult(
                produced_object_ids=[],
                consumed_object_ids=list(package.input_object_ids),
                state_changes={},
                model_usages=list(usages),
                prompt_version=composed.reference,
                model_name=context.model.name,
                metadata={
                    "attempts": attempts,
                    "approved_findings": len(self.assembled.approved_findings),
                    "required_limitations": len(required_ids),
                    "zero_approved_findings": self.assembled.zero_approved_findings,
                    "agent": REPORT_GENERATION_AGENT,
                },
            ),
        )
