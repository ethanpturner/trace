"""The output manifest and the publish step (issue #108, DEC-035).

The acceptance criteria are the spine: a manifest beside every successfully rendered report with
every DEC-035 field and all six evaluation-plan section 3 version identifiers, a content hash
that matches the file, `final_report_path` set on success and untouched on failure, no manifest
for a report that failed validation, a zero-finding render recorded as a success, and one
deterministic `ExecutionRecord` with no model name.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import Assessment, default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import ExecutionRecord, ExecutionStatus, ExecutionType
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
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.report.input_assembly import assemble_report_input
from trace_ai.workflow.finding_review import approve_finding
from trace_ai.workflow.report_manifest import (
    ReportValidationFailedError,
    manifest_filename,
    publish_report,
)
from trace_ai.workflow.report_rendering import NODE_NAME, NODE_VERSION

REVIEWER = "reviewer-local"
STAMP = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)
PASSAGE = "The webhook receiver validates the payload structure before queuing analysis jobs."


@pytest.fixture
def prepared(tmp_path: Any) -> Iterator[dict[str, Any]]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Manifest", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield {"handle": handle, "ledger": ExecutionLedger(handle, run), "run_id": run.id}


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


def publish(prepared: dict[str, Any], **changes: Any) -> Any:
    handle = prepared["handle"]
    assembly = assembled(handle)
    return publish_report(
        handle,
        assembly,
        changes.pop("sections", sections(assembly)),
        ledger=prepared["ledger"],
        workflow_run_id=prepared["run_id"],
        generated_at=STAMP,
        **changes,
    )


# ------------------------------------------------------------------------------------------
# Success: report, manifest, final_report_path, record
# ------------------------------------------------------------------------------------------


def test_a_manifest_is_written_beside_the_report_with_every_dec_035_field(
    prepared: dict[str, Any],
) -> None:
    seed(prepared["handle"])
    published = publish(prepared)

    assert published.manifest_path.name == manifest_filename(prepared["run_id"])
    assert published.manifest_path.parent == published.report_path.parent

    manifest = json.loads(published.manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == "1"
    assert manifest["assessment_id"] == prepared["handle"].assessment_id
    assert manifest["workflow_run_id"] == prepared["run_id"]
    assert manifest["report"]["format"] == "markdown"
    assert manifest["report"]["template_version"] == "report-v1"
    versions = manifest["versions"]
    for field in (
        "architecture",
        "data_model",
        "workflow",
        "requirements_catalog",
        "prompts",
        "model",
        "model_profile",
        "model_configuration",
    ):
        assert field in versions, f"the manifest is missing versions.{field}"
    counts = manifest["counts"]
    for field in (
        "approved_findings",
        "findings_by_severity",
        "documentation_gaps",
        "open_questions",
        "assumptions",
        "confirmed_controls",
        "threats",
        "evidence_references",
    ):
        assert field in counts, f"the manifest is missing counts.{field}"
    assert manifest["authoritative"] is True
    assert manifest["ablations"] == []


def test_the_recorded_hash_matches_a_fresh_hash_of_the_report_file(
    prepared: dict[str, Any],
) -> None:
    seed(prepared["handle"])
    published = publish(prepared)
    manifest = json.loads(published.manifest_path.read_text(encoding="utf-8"))
    assert manifest["report"]["content_hash"] == content_hash(published.report_path.read_bytes())


def test_final_report_path_points_at_the_written_report(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    seed(handle)
    published = publish(prepared)

    stored = handle.objects.get(Assessment, handle.assessment_id)
    assert stored.final_report_path == f"outputs/report-{prepared['run_id']}.md"
    assert (handle.artifacts.assessment_root / stored.final_report_path).is_file()
    assert stored.updated_at > published.assessment.created_at


def test_the_render_is_recorded_as_a_deterministic_execution(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    seed(handle)
    publish(prepared)

    records = [
        record for record in handle.objects.list(ExecutionRecord) if record.node_name == NODE_NAME
    ]
    assert len(records) == 1
    record = records[0]
    assert record.node_version == NODE_VERSION
    assert record.execution_type is ExecutionType.DETERMINISTIC
    assert record.model_name is None, "rendering uses no model, and the record says so"
    assert record.status is ExecutionStatus.COMPLETED
    assert "fnd-001" in record.input_object_ids


# ------------------------------------------------------------------------------------------
# Failure: nothing published
# ------------------------------------------------------------------------------------------


def test_a_failed_validation_produces_no_manifest_and_leaves_the_path_unchanged(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    seed(handle)
    assembly = assembled(handle)
    invented = sections(assembly, risk_summary="The worst weakness is fnd-009.")

    with pytest.raises(ReportValidationFailedError) as failure:
        publish(prepared, sections=invented)

    outputs = handle.artifacts.area("outputs")
    assert list(outputs.iterdir()) == [], "no report and no manifest were written"
    assert handle.objects.get(Assessment, handle.assessment_id).final_report_path is None
    preserved = handle.artifacts.assessment_root / failure.value.preserved
    assert preserved.is_file(), "the offending output is preserved for debugging"


# ------------------------------------------------------------------------------------------
# The empty case is a success
# ------------------------------------------------------------------------------------------


def test_zero_approved_findings_publishes_with_a_zero_count(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    seed(handle, with_finding=False)
    published = publish(prepared)

    manifest = json.loads(published.manifest_path.read_text(encoding="utf-8"))
    assert manifest["counts"]["approved_findings"] == 0
    assert manifest["counts"]["findings_by_severity"] == {}

    records = [
        record for record in handle.objects.list(ExecutionRecord) if record.node_name == NODE_NAME
    ]
    assert records[0].status is ExecutionStatus.COMPLETED


def test_manifest_generation_makes_no_model_call() -> None:
    module = PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "report_manifest.py"
    source = module.read_text(encoding="utf-8")
    assert "StructuredModel" not in source
    assert "anthropic" not in source
    assert "context.model" not in source
