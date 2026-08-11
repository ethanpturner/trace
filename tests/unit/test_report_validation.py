"""The report consistency validator (issue #107).

The acceptance criteria are the spine: an invented finding fails, severity drift fails, an
omitted limitation fails, a gap presented as a weakness fails in a test named for DEC-009, a
question presented as a vulnerability fails, an altered quote fails, the empty-findings report
passes, the unsupported-statement count is a section 28 metric, and no model is called.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.finding import Finding
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.proposals.report_sections import LimitationEntry, ReportSections
from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus
from trace_ai.domain.source_document import (
    IngestionStatus,
    MediaType,
    SourceDocument,
    TrustLevel,
)
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.report.input_assembly import assemble_report_input
from trace_ai.workflow.finding_review import approve_finding
from trace_ai.workflow.report_rendering import render_report
from trace_ai.workflow.report_validation import (
    validate_rendered_report,
    validate_report_sections,
)
from trace_ai.workflow.retry import preserve_failed_output

REVIEWER = "reviewer-local"
STAMP = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)
PASSAGE = "The webhook receiver validates the payload structure before queuing analysis jobs."


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Validation", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


def seed(handle: AssessmentHandle, *, with_finding: bool = True) -> None:
    asm = handle.assessment_id
    stamped = now()
    with handle.objects.transaction():
        handle.objects.save(
            SourceDocument.model_validate(
                {
                    "id": "src-001",
                    "assessment_id": asm,
                    "filename": "architecture-overview.md",
                    "media_type": MediaType.MARKDOWN,
                    "origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "content_hash": content_hash(PASSAGE.encode()),
                    "created_at": stamped,
                    "ingestion_status": IngestionStatus.INGESTED,
                    "ingested_at": stamped,
                    "normalized_path": "normalized/architecture-overview.md",
                    "trust_level": TrustLevel.UNTRUSTED,
                }
            )
        )
        handle.objects.save(
            EvidenceReference.model_validate(
                {
                    "id": "evd-001",
                    "assessment_id": asm,
                    "source_document_id": "src-001",
                    "section_title": "Webhook receiver",
                    "start_line": 41,
                    "end_line": 46,
                    "quoted_text": PASSAGE,
                    "content_hash": content_hash(PASSAGE.encode()),
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "created_at": stamped,
                }
            )
        )
        handle.objects.save(
            DocumentationGap.model_validate(
                {
                    "id": "gap-001",
                    "assessment_id": asm,
                    "title": "TLS termination is not described",
                    "description": "No document states where TLS terminates.",
                    "importance": "Whether transit encryption covers the internal hop is open.",
                    "severity": Severity.MEDIUM,
                    "status": ObjectStatus.APPROVED,
                    "generated_by": "finding-consolidation-v1",
                }
            )
        )
        handle.objects.save(
            Question.model_validate(
                {
                    "id": "qst-001",
                    "assessment_id": asm,
                    "question": "Which service verifies webhook signatures?",
                    "rationale": "The answer decides whether req-WEBHOOK-001 is met.",
                    "related_object_type": "threat",
                    "related_object_id": "thr-001",
                    "priority": QuestionPriority.HIGH,
                    "blocking": False,
                    "status": QuestionStatus.OPEN,
                    "generated_by": "finding-consolidation-v1",
                }
            )
        )

    if with_finding:
        finding = Finding.model_validate(
            {
                "id": "fnd-001",
                "assessment_id": asm,
                "title": "Webhook requests may be processed without verified authenticity",
                "summary": "The receiver may accept events without verifying their origin.",
                "description": "The documents describe validation as structural.",
                "threat_ids": ["thr-001"],
                "requirement_ids": ["req-WEBHOOK-001"],
                "control_mapping_ids": ["map-001"],
                "affected_component_ids": ["cmp-001"],
                "affected_asset_ids": ["ast-001"],
                "evidence_ids": ["evd-001"],
                "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
                "severity": Severity.HIGH,
                "impact": "Unauthorized job execution.",
                "recommendation": "Verify each event with the signature mechanism.",
                "assumptions": ["No undocumented signature validation exists."],
                "limitations": ["The receiver's configuration was not available."],
                "confidence": ConfidenceLevel.MEDIUM,
                "status": ObjectStatus.CANDIDATE,
                "generated_by": "finding-consolidation-v1",
                "created_at": stamped,
                "updated_at": stamped,
            }
        )
        with handle.objects.transaction():
            handle.objects.save(finding)
        approve_finding(handle, finding, reviewer_id=REVIEWER)


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
        "risk_summary": "The approved finding fnd-001 concerns unverified event ingestion.",
        "limitations": [
            LimitationEntry.model_validate(
                {"limitation_id": limitation.limitation_id, "text": limitation.facts}
            )
            for limitation in assembly.required_limitations
        ],
    }
    payload.update(changes)
    return ReportSections.model_validate(payload)


# ------------------------------------------------------------------------------------------
# Section checks
# ------------------------------------------------------------------------------------------


def test_a_valid_section_set_passes(handle: AssessmentHandle) -> None:
    seed(handle)
    assembly = assembled(handle)
    outcome = validate_report_sections(assembly, sections(assembly))
    assert outcome.valid
    assert outcome.unsupported_statement_count == 0


def test_a_finding_absent_from_the_approved_set_fails(handle: AssessmentHandle) -> None:
    seed(handle)
    assembly = assembled(handle)
    invented = sections(
        assembly, risk_summary="The most severe weakness is fnd-009, allowing forgery."
    )
    outcome = validate_report_sections(assembly, invented)
    assert not outcome.valid
    assert outcome.violations[0].check == "unknown_identifier"
    assert "fnd-009" in outcome.violations[0].message


def test_a_severity_differing_from_the_approved_finding_fails(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    assembly = assembled(handle)
    drifted = sections(
        assembly, risk_summary="fnd-001 is assessed at severity: low and can be deferred."
    )
    outcome = validate_report_sections(assembly, drifted)
    assert any(violation.check == "severity_drift" for violation in outcome.violations)


def test_an_ordinary_use_of_a_severity_word_is_not_a_violation(
    handle: AssessmentHandle,
) -> None:
    """ "Low confidence" is not a severity statement; a validator that flagged it would train
    the agent to avoid plain words."""
    seed(handle)
    assembly = assembled(handle)
    ordinary = sections(
        assembly, risk_summary="fnd-001 rests on low confidence in the supplied documents."
    )
    assert validate_report_sections(assembly, ordinary).valid


def test_an_omitted_recorded_limitation_fails(handle: AssessmentHandle) -> None:
    seed(handle)
    assembly = assembled(handle)
    omitting = sections(assembly, limitations=[])
    outcome = validate_report_sections(assembly, omitting)
    assert any(violation.check == "limitation_set" for violation in outcome.violations)


def test_dec_009_a_gap_described_as_a_confirmed_weakness_fails(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    assembly = assembled(handle)
    collapsed = sections(
        assembly,
        risk_summary="gap-001 shows the internal hop is exploitable and vulnerable.",
    )
    outcome = validate_report_sections(assembly, collapsed)
    assert any(violation.check == "dec_009_gap_as_weakness" for violation in outcome.violations)


def test_an_open_question_presented_as_a_vulnerability_fails(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    assembly = assembled(handle)
    asserted = sections(
        assembly,
        risk_summary="qst-001 demonstrates the system is vulnerable to forged events.",
    )
    outcome = validate_report_sections(assembly, asserted)
    assert any(violation.check == "question_as_vulnerability" for violation in outcome.violations)


def test_an_altered_quote_fails(handle: AssessmentHandle) -> None:
    seed(handle)
    assembly = assembled(handle)
    altered = PASSAGE[:45] + " and then rejects everything else."
    quoting = sections(
        assembly, risk_summary=f'The documentation states "{altered}" about the receiver.'
    )
    outcome = validate_report_sections(assembly, quoting)
    assert any(violation.check == "altered_quote" for violation in outcome.violations)


def test_failures_preserve_the_offending_output_and_do_not_rewrite_it(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    assembly = assembled(handle)
    invented = sections(assembly, risk_summary="fnd-009 allows forgery.")
    before = invented.model_dump()

    outcome = validate_report_sections(assembly, invented)
    assert not outcome.valid
    assert invented.model_dump() == before, "the validator never repairs prose"

    preserved = preserve_failed_output(
        handle.artifacts,
        node_name="report-validation",
        attempt_number=1,
        raw_output=invented.model_dump_json(indent=2),
    )
    assert (handle.artifacts.assessment_root / preserved).is_file()


def test_the_unsupported_statement_count_is_a_section_28_metric(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    assembly = assembled(handle)
    invented = sections(
        assembly, risk_summary="fnd-009 and fnd-010 allow forgery of analysis jobs."
    )
    outcome = validate_report_sections(assembly, invented)
    assert outcome.unsupported_statement_count == 2
    assert outcome.metrics() == {"unsupported_claim_count": 2}


# ------------------------------------------------------------------------------------------
# Rendered-document checks
# ------------------------------------------------------------------------------------------


def rendered(handle: AssessmentHandle) -> tuple[Any, str]:
    assembly = assembled(handle)
    return assembly, render_report(assembly, sections(assembly), generated_at=STAMP)


def test_a_faithful_rendered_document_passes(handle: AssessmentHandle) -> None:
    seed(handle)
    assembly, markdown = rendered(handle)
    assert validate_rendered_report(assembly, markdown).valid


def test_zero_approved_findings_with_the_empty_wording_passes(
    handle: AssessmentHandle,
) -> None:
    seed(handle, with_finding=False)
    assembly = assembled(handle)
    empty_case = sections(
        assembly,
        risk_summary=(
            "No findings were approved; the documentation gaps and open questions record "
            "what could not be determined."
        ),
    )
    markdown = render_report(assembly, empty_case, generated_at=STAMP)
    assert "No findings were approved" in markdown
    assert validate_rendered_report(assembly, markdown).valid
    assert validate_report_sections(assembly, empty_case).valid


def test_a_rejected_identifier_in_the_document_fails(handle: AssessmentHandle) -> None:
    seed(handle)
    assembly, markdown = rendered(handle)
    tampered = markdown + "\nSee also fnd-002 for a related weakness.\n"
    outcome = validate_rendered_report(assembly, tampered)
    assert any(
        violation.check == "unapproved_finding_identifier" for violation in outcome.violations
    )


def test_a_severity_edit_in_the_document_fails(handle: AssessmentHandle) -> None:
    seed(handle)
    assembly, markdown = rendered(handle)
    tampered = markdown.replace("- Severity: high", "- Severity: low")
    outcome = validate_rendered_report(assembly, tampered)
    assert any(violation.check == "severity_drift" for violation in outcome.violations)


def test_a_removed_limitation_in_the_document_fails(handle: AssessmentHandle) -> None:
    seed(handle)
    assembly, markdown = rendered(handle)
    tampered = markdown.replace("The receiver's configuration was not available.", "")
    outcome = validate_rendered_report(assembly, tampered)
    assert any(violation.check == "omitted_limitation" for violation in outcome.violations)


def test_an_altered_quote_in_the_document_fails(handle: AssessmentHandle) -> None:
    seed(handle)
    assembly, markdown = rendered(handle)
    tampered = markdown.replace(PASSAGE, PASSAGE.replace("validates", "verifies"))
    outcome = validate_rendered_report(assembly, tampered)
    assert any(violation.check == "altered_quote" for violation in outcome.violations)


def test_the_validator_makes_no_model_call() -> None:
    module = PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "report_validation.py"
    source = module.read_text(encoding="utf-8")
    assert "StructuredModel" not in source
    assert "anthropic" not in source
    assert "context.model" not in source
