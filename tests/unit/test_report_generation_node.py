"""The Report Generation node against the deterministic fake (issue #105).

Nothing here proves a model writes a good report. What the tests prove is that the application
bounds it: the input carries only approved objects, a limitation set that does not match the
required list is retried with feedback, an identifier the input did not carry is rejected, a
zero-finding assessment succeeds, invalid output is preserved, and the record carries the prompt
and node versions.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    ValidationStatus,
)
from trace_ai.domain.execution import ExecutionRecord
from trace_ai.domain.finding import Finding
from trace_ai.domain.proposals.report_sections import LimitationEntry, ReportSections
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import DeterministicModel, ModelUsage
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.seam import Creativity
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.prompts import PromptRegistry
from trace_ai.services.report.input_assembly import assemble_report_input
from trace_ai.workflow.errors import WorkflowError
from trace_ai.workflow.finding_review import approve_finding, reject_finding
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.report_generation import (
    NODE_NAME,
    NODE_VERSION,
    ReportGenerationNode,
)
from trace_ai.workflow.retry import RetryPolicy
from trace_ai.workflow.state import AssessmentState

PROFILE = resolve_profile("primary-development")
REVIEWER = "reviewer-local"

USAGE = ModelUsage(
    model="claude-opus-5",
    input_tokens=9_000,
    output_tokens=1_200,
    estimated_cost=Decimal("0.08"),
)


class Usable(DeterministicModel):
    """The fake, with usage attached so the ledger has something to record."""

    def generate(self, **kwargs: Any) -> Any:
        outcome = super().generate(**kwargs)
        if hasattr(outcome, "usage") and outcome.usage.input_tokens == 0:
            return type(outcome)(
                **{**{f: getattr(outcome, f) for f in outcome.__slots__}, "usage": USAGE}
            )
        return outcome


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[dict[str, Any]]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Report", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield {"handle": handle, "ledger": ExecutionLedger(handle, run)}


def a_finding(handle: AssessmentHandle, **changes: Any) -> Finding:
    stamped = now()
    payload: dict[str, Any] = {
        "id": "fnd-001",
        "assessment_id": handle.assessment_id,
        "title": "Webhook requests may be processed without verified authenticity",
        "summary": "The receiver may accept events without verifying their origin.",
        "description": "The documents describe validation as structural, not cryptographic.",
        "threat_ids": ["thr-001"],
        "requirement_ids": ["req-WEBHOOK-001"],
        "control_mapping_ids": ["map-001"],
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "evidence_ids": ["evd-001"],
        "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
        "severity": Severity.HIGH,
        "impact": "Unauthorized job execution and resource exhaustion.",
        "recommendation": "Verify each event with the platform's signature mechanism.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "finding-consolidation-v1",
        "created_at": stamped,
        "updated_at": stamped,
    }
    payload.update(changes)
    finding = Finding.model_validate(payload)
    with handle.objects.transaction():
        handle.objects.save(finding)
    return finding


def assembled(handle: AssessmentHandle) -> Any:
    return assemble_report_input(
        handle,
        prompt_versions={"generate-report-sections": "generate-report-sections-v1"},
        model="claude-opus-5",
        model_configuration="primary-development",
    )


def sections(assembly: Any, **changes: Any) -> ReportSections:
    payload: dict[str, Any] = {
        "executive_summary": "The assessment reviewed the webhook processing path.",
        "system_overview": "The system accepts repository events and queues analysis jobs.",
        "risk_summary": "The approved findings concern unverified event ingestion.",
        "limitations": [
            LimitationEntry.model_validate(
                {"limitation_id": limitation.limitation_id, "text": limitation.facts}
            )
            for limitation in assembly.required_limitations
        ],
    }
    payload.update(changes)
    return ReportSections.model_validate(payload)


def node(prepared: dict[str, Any], assembly: Any, **changes: Any) -> ReportGenerationNode:
    options: dict[str, Any] = {
        "ledger": prepared["ledger"],
        "profile": PROFILE,
        "registry": PromptRegistry(),
        "assembled": assembly,
        **changes,
    }
    return ReportGenerationNode(**options)


def node_context(prepared: dict[str, Any], model: Any) -> NodeContext:
    handle = prepared["handle"]
    return NodeContext(
        handle=handle,
        state=AssessmentState.begin(
            assessment_id=handle.assessment_id, workflow_run_id=prepared["ledger"].run.id
        ),
        model=model,
    )


# ------------------------------------------------------------------------------------------
# The input the agent sees
# ------------------------------------------------------------------------------------------


def test_a_rejected_finding_never_appears_in_the_prompt(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    approved = a_finding(handle)
    rejected = a_finding(
        handle, id="fnd-002", title="A rejected candidate title", control_mapping_ids=["map-002"]
    )
    approve_finding(handle, approved, reviewer_id=REVIEWER)
    reject_finding(handle, rejected, reviewer_id=REVIEWER, rationale="Not supported.")

    assembly = assembled(handle)
    model = Usable([sections(assembly)])
    node(prepared, assembly).generate(node_context(prepared, model))

    prompt = model.calls[0].prompt
    assert "fnd-001" in prompt
    assert "fnd-002" not in prompt
    assert "A rejected candidate title" not in prompt


def test_a_valid_response_succeeds_in_one_attempt(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    approve_finding(handle, a_finding(handle), reviewer_id=REVIEWER)
    assembly = assembled(handle)
    model = Usable([sections(assembly)])

    outcome = node(prepared, assembly).generate(node_context(prepared, model))

    assert len(model.calls) == 1
    assert outcome.result.metadata["attempts"] == 1
    assert outcome.sections.executive_summary


def test_the_call_uses_low_creativity(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    assembly = assembled(handle)
    model = Usable([sections(assembly)])
    node(prepared, assembly).generate(node_context(prepared, model))

    expected = PROFILE.with_creativity(Creativity.LOW).settings
    assert model.calls[0].settings == expected


# ------------------------------------------------------------------------------------------
# Retry conditions (section 19)
# ------------------------------------------------------------------------------------------


def test_a_missing_required_limitation_is_retried_with_feedback(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    assembly = assembled(handle)
    incomplete = sections(assembly, limitations=[])
    model = Usable([incomplete, sections(assembly)])

    outcome = node(prepared, assembly).generate(node_context(prepared, model))

    assert len(model.calls) == 2
    assert "missing" in model.calls[1].prompt
    assert outcome.result.metadata["attempts"] == 2


def test_an_identifier_the_input_did_not_carry_is_rejected(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    assembly = assembled(handle)
    invented = sections(
        assembly,
        risk_summary="The most severe weakness is fnd-009, which allows job forgery.",
    )
    model = Usable([invented, sections(assembly)])

    outcome = node(prepared, assembly).generate(node_context(prepared, model))

    assert len(model.calls) == 2
    assert "fnd-009" in model.calls[1].prompt
    assert outcome.result.metadata["attempts"] == 2


def test_retries_are_bounded_and_invalid_output_is_preserved(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    assembly = assembled(handle)
    model = Usable([sections(assembly, limitations=[]), sections(assembly, limitations=[])])

    with pytest.raises(WorkflowError):
        node(prepared, assembly, retry_policy=RetryPolicy(maximum_retries_per_node=1)).generate(
            node_context(prepared, model)
        )

    traces = handle.artifacts.area("traces")
    preserved = list(traces.glob("*report-generation*"))
    assert preserved, "a failed attempt's raw output goes to traces/ (section 33)"


# ------------------------------------------------------------------------------------------
# The empty case is a successful report
# ------------------------------------------------------------------------------------------


def test_zero_approved_findings_generates_a_complete_valid_section_set(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    assembly = assembled(handle)
    assert assembly.zero_approved_findings is True

    model = Usable([sections(assembly)])
    outcome = node(prepared, assembly).generate(node_context(prepared, model))

    assert outcome.result.metadata["zero_approved_findings"] is True
    written = {entry.limitation_id for entry in outcome.sections.limitations}
    assert "lim-empty-findings" in written
    assert "No candidate weakness reached" in model.calls[0].prompt


# ------------------------------------------------------------------------------------------
# The record, and what the node does not do
# ------------------------------------------------------------------------------------------


def test_prompt_and_node_versions_are_recorded(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    assembly = assembled(handle)
    model = Usable([sections(assembly)])
    node(prepared, assembly).generate(node_context(prepared, model))

    (record,) = handle.objects.list(ExecutionRecord)
    assert record.node_name == NODE_NAME
    assert record.node_version == NODE_VERSION
    assert record.prompt_version == "generate-report-sections-v1"
    assert record.model_name == "claude-opus-5"


def test_the_output_is_not_written_to_disk_as_the_report(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    assembly = assembled(handle)
    model = Usable([sections(assembly)])
    node(prepared, assembly).generate(node_context(prepared, model))

    outputs = handle.artifacts.area("outputs")
    assert list(outputs.iterdir()) == [], "the sections go to the validator and the renderer"


def test_the_node_module_contains_no_store_write() -> None:
    module = PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "report_generation.py"
    source = module.read_text(encoding="utf-8")
    assert ".save(" not in source
    assert "transaction(" not in source


def test_the_node_declares_the_report_generation_phase(prepared: dict[str, Any]) -> None:
    assembly = assembled(prepared["handle"])
    built = node(prepared, assembly)
    assert built.phase is Phase.REPORT_GENERATION
    assert built.name == NODE_NAME


def test_a_deterministic_node_context_without_a_model_is_refused(
    prepared: dict[str, Any],
) -> None:
    assembly = assembled(prepared["handle"])
    with pytest.raises(ValueError, match="model-assisted"):
        node(prepared, assembly).generate(node_context(prepared, None))
