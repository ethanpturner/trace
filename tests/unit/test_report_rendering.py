"""The deterministic report renderer (issue #106, DEC-035).

The acceptance criteria are the spine: no model client anywhere near the module, byte-identical
output apart from timestamps, approved findings exactly once with resolving citations quoted
byte for byte, the template's authored empty wording for a zero-finding report, gaps rendered as
gaps (the DEC-009 test), unique stable anchors, and output confined to the assessment's own
directory.
"""

from __future__ import annotations

import re
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
from trace_ai.workflow.report_rendering import (
    render_report,
    report_filename,
    write_report,
)

REVIEWER = "reviewer-local"
STAMP = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)
PASSAGE = "The webhook receiver validates the payload structure | before queuing."


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow Security Review",
            default_configuration("primary-development", "stride-scenario-based"),
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
                    "description": "no document states where TLS terminates.",
                    "importance": "Whether transit encryption covers the internal hop is open.",
                    "severity": Severity.MEDIUM,
                    "status": ObjectStatus.APPROVED,
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
                "recommendation": "Verify each event with the platform's signature mechanism.",
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

        rejected = Finding.model_validate(
            {
                **finding.model_dump(),
                "id": "fnd-002",
                "title": "A rejected candidate that must not render",
                "status": ObjectStatus.REJECTED,
            }
        )
        with handle.objects.transaction():
            handle.objects.save(rejected)


def assembled(handle: AssessmentHandle) -> Any:
    return assemble_report_input(
        handle,
        prompt_versions={"generate-report-sections": "generate-report-sections-v1"},
        model="claude-opus-5",
        model_configuration="primary-development",
    )


def sections(assembly: Any) -> ReportSections:
    return ReportSections.model_validate(
        {
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
    )


def rendered(handle: AssessmentHandle) -> str:
    assembly = assembled(handle)
    return render_report(assembly, sections(assembly), generated_at=STAMP)


# ------------------------------------------------------------------------------------------
# No model, deterministic output
# ------------------------------------------------------------------------------------------


def test_the_module_imports_no_model_client() -> None:
    module = PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "report_rendering.py"
    source = module.read_text(encoding="utf-8")
    assert "infrastructure.model" not in source
    assert "StructuredModel" not in source
    assert "anthropic" not in source
    assert "context.model" not in source


def test_two_renders_over_identical_state_are_byte_identical(handle: AssessmentHandle) -> None:
    seed(handle)
    assert rendered(handle) == rendered(handle)


def test_the_scope_names_the_run_profile_not_the_configured_default(
    handle: AssessmentHandle,
) -> None:
    """The report is the run's record, and the run's profile comes from the caller that ran —
    `assemble_report_input`'s `model_configuration`. The configured default differs on every
    offline replay, and rendering it would put a profile nobody used into the one document that
    exists to carry provenance (#322)."""
    seed(handle)
    assembly = assemble_report_input(
        handle,
        prompt_versions={"generate-report-sections": "generate-report-sections-v1"},
        model="deterministic-fake",
        model_configuration="offline-fake",
    )
    assert assembly.assessment.configuration.model_profile != "offline-fake"
    report = render_report(assembly, sections(assembly), generated_at=STAMP)
    assert "- Model profile: offline-fake" in report
    assert f"- Model profile: {assembly.assessment.configuration.model_profile}" not in report


# ------------------------------------------------------------------------------------------
# Findings: approved exactly once, cited, quoted verbatim
# ------------------------------------------------------------------------------------------


def test_every_approved_finding_appears_exactly_once(handle: AssessmentHandle) -> None:
    seed(handle)
    report = rendered(handle)
    assert report.count("### fnd-001:") == 1
    assert "fnd-002" not in report
    assert "A rejected candidate that must not render" not in report


def test_a_rendered_finding_cites_document_location_and_quoted_text(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    report = rendered(handle)
    assert "[evd-001 — architecture-overview.md, Webhook receiver, lines 41-46]" in report
    assert PASSAGE in report, "quoted text is reproduced byte for byte"


def test_recommended_actions_order_by_severity_then_identifier(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    report = rendered(handle)
    assert "- [high] fnd-001: Verify each event" in report


# ------------------------------------------------------------------------------------------
# The empty case is a correct report
# ------------------------------------------------------------------------------------------


def test_zero_approved_findings_renders_the_authored_empty_wording(
    handle: AssessmentHandle,
) -> None:
    seed(handle, with_finding=False)
    report = rendered(handle)
    assert "No findings were approved in this assessment." in report
    assert "This is a defined outcome and not a failure." in report
    assert "not a statement that the reviewed system is secure" in report
    assert '<a id="s08-approved-findings"></a>' in report, "the section is never omitted"


def test_all_sixteen_sections_render_whatever_the_content(handle: AssessmentHandle) -> None:
    seed(handle, with_finding=False)
    report = rendered(handle)
    for number in range(1, 17):
        assert f'<a id="s{number:02d}-' in report, f"section {number} is missing"


# ------------------------------------------------------------------------------------------
# DEC-009: a gap renders as a gap
# ------------------------------------------------------------------------------------------


def test_dec_009_a_documentation_gap_is_never_presented_as_a_confirmed_weakness(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    report = rendered(handle)

    gaps_section = report.split('<a id="s09-documentation-gaps"></a>', 1)[1].split(
        '<a id="s10-', 1
    )[0]
    assert "It could not be determined from the documentation provided" in gaps_section
    assert "vulnerab" not in gaps_section.casefold()
    assert "weakness" not in gaps_section.casefold()

    findings_section = report.split('<a id="s08-approved-findings"></a>', 1)[1].split(
        '<a id="s09-', 1
    )[0]
    assert "gap-001" not in findings_section, "a gap never renders among the findings"


# ------------------------------------------------------------------------------------------
# Anchors
# ------------------------------------------------------------------------------------------


def test_anchors_are_unique_and_stable_across_runs(handle: AssessmentHandle) -> None:
    seed(handle)
    first = rendered(handle)
    second = rendered(handle)

    anchors = re.findall(r'<a id="([^"]+)"></a>', first)
    assert len(anchors) == len(set(anchors)), "anchors are unique within the document"
    assert anchors == re.findall(r'<a id="([^"]+)"></a>', second)
    assert "fnd-001" in anchors and "gap-001" in anchors and "evd-001" in anchors


# ------------------------------------------------------------------------------------------
# Output confinement
# ------------------------------------------------------------------------------------------


def test_output_is_confined_to_the_assessments_own_directory(
    handle: AssessmentHandle,
) -> None:
    seed(handle)
    assembly = assembled(handle)
    report, path = write_report(
        handle,
        assembly,
        sections(assembly),
        workflow_run_id="run-001",
        generated_at=STAMP,
    )

    assert report.filename == report_filename("run-001") == "report-run-001.md"
    assert path.is_relative_to(handle.artifacts.assessment_root)
    assert path.parent == handle.artifacts.area("outputs")
    assert path.read_text(encoding="utf-8") == report.markdown


def test_a_filename_that_escapes_the_assessment_is_refused(handle: AssessmentHandle) -> None:
    from trace_ai.infrastructure.filesystem.artifact_store import ArtifactStoreError

    with pytest.raises(ArtifactStoreError):
        handle.artifacts.store_output("../outside.md", b"escaped")


# ------------------------------------------------------------------------------------------
# The coverage ledger (DEC-071, issue #346)
# ------------------------------------------------------------------------------------------


def _register(handle: AssessmentHandle, document_id: str, status: IngestionStatus) -> None:
    stamped = now()
    payload: dict[str, Any] = {
        "id": document_id,
        "assessment_id": handle.assessment_id,
        "filename": f"{document_id}.md",
        "media_type": MediaType.MARKDOWN,
        "origin": SourceOrigin.UPLOADED_DOCUMENT,
        "content_hash": content_hash(document_id.encode()),
        "created_at": stamped,
        "ingestion_status": status,
        "trust_level": TrustLevel.UNTRUSTED,
    }
    if status is IngestionStatus.INGESTED:
        payload |= {"ingested_at": stamped, "normalized_path": f"normalized/{document_id}.md"}
    with handle.objects.transaction():
        handle.objects.save(SourceDocument.model_validate(payload))


def test_the_ledger_accounts_for_every_registered_document(handle: AssessmentHandle) -> None:
    """Issue #346's acceptance criterion: ledger rows equal registered documents."""
    seed(handle)
    _register(handle, "src-002", IngestionStatus.FAILED)
    _register(handle, "src-003", IngestionStatus.REGISTERED)

    assembly = assembled(handle)
    assert len(assembly.coverage) == len(assembly.source_documents) == 3

    report = render_report(assembly, sections(assembly), generated_at=STAMP)
    section_14 = report.split('<a id="s14-methodology"></a>')[1].split('<a id="s15-')[0]
    assert "### Source coverage" in section_14
    for document in assembly.source_documents:
        assert document.id in section_14

    by_id = {entry.document_id: entry for entry in assembly.coverage}
    assert by_id["src-001"].bucket.value == "reviewed"
    assert by_id["src-002"].bucket.value == "could_not_process"
    assert by_id["src-003"].bucket.value == "excluded_by_rule"
    assert "--no-index" in by_id["src-003"].justification


def test_budget_exclusions_reach_the_ledger_with_names(handle: AssessmentHandle) -> None:
    """The fence rule's naming obligation, carried through to the reader (DEC-071)."""
    from trace_ai.domain.execution import ExecutionType
    from trace_ai.services.execution_ledger import ExecutionLedger, start_run

    seed(handle)
    run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    ledger = ExecutionLedger(handle, run)
    with ledger.record(
        "threat-analysis", node_version="0.1", execution_type=ExecutionType.MODEL
    ) as execution:
        execution.metadata["excluded_evidence_ids"] = ["evd-001"]

    assembly = assembled(handle)
    entry = next(item for item in assembly.coverage if item.document_id == "src-001")
    assert entry.bucket.value == "reviewed_with_exclusions"
    assert entry.excluded_evidence_ids == ("evd-001",)
    assert "evd-001" in entry.justification

    report = render_report(assembly, sections(assembly), generated_at=STAMP)
    assert "reviewed_with_exclusions" in report


def test_an_unaccounted_document_refuses_to_render(handle: AssessmentHandle) -> None:
    """A loud failure over a quiet omission: the renderer checks the ledger is total."""
    from dataclasses import replace as dc_replace

    seed(handle)
    assembly = dc_replace(assembled(handle), coverage=())
    with pytest.raises(ValueError, match="does not account"):
        render_report(assembly, sections(assembly), generated_at=STAMP)


def test_the_agent_receives_the_ledger_as_input(handle: AssessmentHandle) -> None:
    """DEC-071: limitations prose may interpret the ledger, so the agent must see it."""
    from trace_ai.services.report.prompt_input import assemble_report_prompt_input

    seed(handle)
    _register(handle, "src-002", IngestionStatus.REGISTERED)

    prompt_input = assemble_report_prompt_input(assembled(handle))
    text = prompt_input.substitutions()["input.report"]
    assert "### Source coverage" in text
    assert "excluded_by_rule" in text
    assert "never restate" in text
