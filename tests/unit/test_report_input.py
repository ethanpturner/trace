"""`ReportSections` and the report input assembly (issue #104, DEC-035).

The acceptance criteria are the spine: one field per model-written section and none for a
renderer-owned one, findings solely from the approved-set accessor, every evaluation-plan
section 3 version identifier present, equal assemblies over identical state, the empty case as
an explicit value, limitations and assumptions carried through, and no model call anywhere.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    ValidationStatus,
)
from trace_ai.domain.finding import Finding
from trace_ai.domain.proposals.report_sections import (
    MODEL_WRITTEN_SECTIONS,
    LimitationEntry,
    ReportSections,
)
from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.report.input_assembly import (
    REPORT_TEMPLATE,
    assemble_report_input,
)
from trace_ai.workflow.finding_review import approve_finding, reject_finding

REVIEWER = "reviewer-local"


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Report", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


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
        "assumptions": ["No undocumented signature validation exists."],
        "limitations": ["The receiver's configuration was not available."],
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


def assemble(handle: AssessmentHandle, **overrides: Any) -> Any:
    options: dict[str, Any] = {
        "prompt_versions": {"generate-report": "generate-report-v1"},
        "model": "claude-opus-5",
        "model_configuration": "primary-development",
        **overrides,
    }
    return assemble_report_input(handle, **options)


# ------------------------------------------------------------------------------------------
# ReportSections: four fields, prose only, limitations by identifier
# ------------------------------------------------------------------------------------------


def sections_payload(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "executive_summary": "The assessment reviewed the webhook processing path.",
        "system_overview": "The system accepts repository events and queues analysis jobs.",
        "risk_summary": "The findings concern unverified event ingestion.",
        "limitations": [
            {
                "limitation_id": "lim-empty-findings",
                "text": "No candidate weakness reached the assessment's bar.",
            }
        ],
    }
    payload.update(changes)
    return payload


def test_report_sections_has_exactly_the_dec_035_fields() -> None:
    assert tuple(ReportSections.model_fields) == MODEL_WRITTEN_SECTIONS
    assert MODEL_WRITTEN_SECTIONS == (
        "executive_summary",
        "system_overview",
        "risk_summary",
        "limitations",
    )


def test_a_renderer_owned_section_is_refused_as_a_field() -> None:
    """Section 8 belongs to the renderer; an agent returning it fails validation."""
    with pytest.raises(ValidationError):
        ReportSections.model_validate(
            sections_payload(approved_findings="The findings are as follows.")
        )


@pytest.mark.parametrize(
    "structure",
    [
        "# A heading\nProse after it.",
        "A table follows.\n| col | col |",
        "A [link](https://example.invalid) in prose.",
        'An anchor <a id="s08"> in prose.',
    ],
)
def test_document_structure_in_a_prose_field_is_refused(structure: str) -> None:
    with pytest.raises(ValidationError, match="belongs to the renderer"):
        ReportSections.model_validate(sections_payload(risk_summary=structure))


def test_limitations_are_checked_by_identifier() -> None:
    sections = ReportSections.model_validate(sections_payload())
    sections.check_required(["lim-empty-findings"])

    with pytest.raises(ValueError, match="missing"):
        sections.check_required(["lim-empty-findings", "lim-blocking-qst-001"])
    with pytest.raises(ValueError, match="not required"):
        sections.check_required([])


def test_a_limitation_with_document_structure_is_refused() -> None:
    with pytest.raises(ValidationError, match="belongs to the renderer"):
        ReportSections.model_validate(
            sections_payload(
                limitations=[
                    LimitationEntry.model_construct(
                        limitation_id="lim-x", text="# Limitations\nSome text."
                    )
                ]
            )
        )


# ------------------------------------------------------------------------------------------
# The assembly: approved-only, versioned, deterministic
# ------------------------------------------------------------------------------------------


def test_findings_come_solely_from_the_approved_set(handle: AssessmentHandle) -> None:
    approved = a_finding(handle)
    rejected = a_finding(handle, id="fnd-002", control_mapping_ids=["map-002"])
    approve_finding(handle, approved, reviewer_id=REVIEWER)
    reject_finding(handle, rejected, reviewer_id=REVIEWER, rationale="Not supported.")

    assembled = assemble(handle)
    assert [finding.id for finding in assembled.approved_findings] == ["fnd-001"]
    assert assembled.zero_approved_findings is False


def test_a_rejected_finding_never_appears_anywhere_in_the_input(
    handle: AssessmentHandle,
) -> None:
    rejected = a_finding(handle)
    reject_finding(handle, rejected, reviewer_id=REVIEWER, rationale="Not supported.")

    assembled = assemble(handle)
    assert assembled.approved_findings == ()
    assert "fnd-001" not in [
        limitation.limitation_id for limitation in assembled.required_limitations
    ]


def test_every_evaluation_plan_version_identifier_is_present(
    handle: AssessmentHandle,
) -> None:
    versions = assemble(handle).versions
    assert versions.architecture_version
    assert versions.workflow_version
    assert versions.prompt_versions == (("generate-report", "generate-report-v1"),)
    assert versions.requirements_catalog_version
    assert versions.model == "claude-opus-5"
    assert versions.model_configuration == "primary-development"


def test_two_assemblies_over_identical_state_are_equal(handle: AssessmentHandle) -> None:
    finding = a_finding(handle)
    approve_finding(handle, finding, reviewer_id=REVIEWER)
    assert assemble(handle) == assemble(handle)


def test_zero_approved_findings_is_explicit_and_required_as_a_limitation(
    handle: AssessmentHandle,
) -> None:
    assembled = assemble(handle)
    assert assembled.approved_findings == ()
    assert assembled.zero_approved_findings is True
    assert "lim-empty-findings" in [
        limitation.limitation_id for limitation in assembled.required_limitations
    ]


def test_finding_assumptions_and_limitations_are_carried_through(
    handle: AssessmentHandle,
) -> None:
    finding = a_finding(handle)
    approve_finding(handle, finding, reviewer_id=REVIEWER)

    assembled = assemble(handle)
    carried = assembled.approved_findings[0]
    assert carried.assumptions == ["No undocumented signature validation exists."]
    assert carried.limitations == ["The receiver's configuration was not available."]
    assert "lim-assumptions-fnd-001" in [
        limitation.limitation_id for limitation in assembled.required_limitations
    ]


def test_a_blocking_open_question_becomes_a_required_limitation(
    handle: AssessmentHandle,
) -> None:
    question = Question.model_validate(
        {
            "id": "qst-001",
            "assessment_id": handle.assessment_id,
            "question": "Which service verifies webhook signatures, if any?",
            "rationale": "The answer decides whether req-WEBHOOK-001 is met.",
            "related_object_type": "threat",
            "related_object_id": "thr-001",
            "priority": QuestionPriority.HIGH,
            "blocking": True,
            "status": QuestionStatus.OPEN,
            "generated_by": "finding-consolidation-v1",
        }
    )
    with handle.objects.transaction():
        handle.objects.save(question)

    assembled = assemble(handle)
    assert [question.id for question in assembled.open_questions] == ["qst-001"]
    assert "lim-blocking-qst-001" in [
        limitation.limitation_id for limitation in assembled.required_limitations
    ]


def test_a_non_authoritative_run_is_a_required_limitation(handle: AssessmentHandle) -> None:
    assembled = assemble(handle, authoritative=False)
    assert assembled.authoritative is False
    assert "lim-non-authoritative" in [
        limitation.limitation_id for limitation in assembled.required_limitations
    ]


def test_the_template_identifier_is_dec_035s(handle: AssessmentHandle) -> None:
    assert assemble(handle).template == REPORT_TEMPLATE == "report-v1"


def test_assembly_makes_no_model_call() -> None:
    module = PROJECT_ROOT / "src" / "trace_ai" / "services" / "report" / "input_assembly.py"
    source = module.read_text(encoding="utf-8")
    assert "StructuredModel" not in source
    assert "anthropic" not in source


def a_threat(handle: AssessmentHandle, identifier: str) -> None:
    from trace_ai.domain.threat import Threat

    stamped = now()
    threat = Threat.model_validate(
        {
            "id": identifier,
            "assessment_id": handle.assessment_id,
            "title": f"Threat {identifier} exercises the receiver",
            "description": "An attacker submits forged events the receiver processes.",
            "methodology": "stride-scenario-based",
            "category": ["spoofing"],
            "affected_component_ids": ["cmp-001"],
            "affected_asset_ids": ["ast-001"],
            "impact": "Unauthorized work is performed.",
            "confidence": ConfidenceLevel.MEDIUM,
            "status": ObjectStatus.CANDIDATE,
            "generated_by": "threat-analysis-v1",
            "created_at": stamped,
        }
    )
    with handle.objects.transaction():
        handle.objects.save(threat)


def test_section_seven_carries_the_approved_findings_threats(handle: AssessmentHandle) -> None:
    """DEC-083: threats have no approval verb; the set the reviewer transitively validated by
    approving the findings is what renders — and only that set."""
    a_threat(handle, "thr-001")
    a_threat(handle, "thr-002")
    approved = a_finding(handle)  # references thr-001
    approve_finding(handle, approved, reviewer_id=REVIEWER)

    assembled = assemble(handle)
    assert [threat.id for threat in assembled.threats] == ["thr-001"]


def test_a_zero_finding_assembly_carries_no_threats(handle: AssessmentHandle) -> None:
    a_threat(handle, "thr-001")
    assembled = assemble(handle)
    assert assembled.threats == ()
    assert assembled.zero_approved_findings is True
