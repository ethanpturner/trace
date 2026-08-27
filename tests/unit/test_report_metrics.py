"""Report-quality metrics and the reviewer rubric (issue #111).

The acceptance criteria are the spine: the unsupported-claim count comes from the validator and
is stored, invented findings are zero for a passing report, rubric scores are bounded and carry
`evaluator_type: reviewer`, no readability value is computed anywhere, the per-run summary
carries every available count, and the zero-finding assessment summarizes cleanly with the
report recorded as correctly containing no findings.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evaluation_result import EvaluationResult, EvaluatorType
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.finding import Finding
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.proposals.report_sections import LimitationEntry, ReportSections
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evaluation.metrics import compute_metrics
from trace_ai.services.evaluation.report_metrics import (
    RUBRIC_CATEGORIES,
    compute_report_metrics,
    record_rubric,
    write_summary,
)
from trace_ai.services.execution_ledger import start_run
from trace_ai.services.report.input_assembly import assemble_report_input
from trace_ai.workflow.finding_review import approve_finding
from trace_ai.workflow.report_rendering import render_report
from trace_ai.workflow.report_validation import (
    validate_rendered_report,
    validate_report_sections,
)

REVIEWER = "reviewer-local"
STAMP = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)
PASSAGE = "The comment service posts validated analysis output automatically."


@pytest.fixture
def prepared(tmp_path: Any) -> Iterator[dict[str, Any]]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Rubric", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield {"handle": handle, "run": run}


def seed_finding(handle: AssessmentHandle) -> Finding:
    stamped = now()
    with handle.objects.transaction():
        handle.objects.save(
            EvidenceReference.model_validate(
                {
                    "id": "evd-001",
                    "assessment_id": handle.assessment_id,
                    "source_document_id": "src-001",
                    "start_line": 10,
                    "end_line": 12,
                    "quoted_text": PASSAGE,
                    "content_hash": content_hash(PASSAGE.encode()),
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "created_at": stamped,
                }
            )
        )
    finding = Finding.model_validate(
        {
            "id": "fnd-001",
            "assessment_id": handle.assessment_id,
            "title": "AI output is published without adequate review",
            "summary": "Comments are posted automatically after schema validation.",
            "description": "Schema validation does not validate factual correctness.",
            "threat_ids": ["thr-001"],
            "requirement_ids": ["req-AI-002"],
            "control_mapping_ids": ["map-001"],
            "affected_component_ids": ["cmp-001"],
            "affected_asset_ids": ["ast-001"],
            "evidence_ids": ["evd-001"],
            "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
            "severity": Severity.MEDIUM,
            "impact": "Manipulated output reaches customer pull requests.",
            "recommendation": "Add a human approval gate before publication.",
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
    return finding


def validated_report(handle: AssessmentHandle, **section_changes: Any) -> dict[str, Any]:
    assembly = assemble_report_input(
        handle,
        prompt_versions={},
        model="claude-opus-5",
        model_configuration="primary-development",
    )
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
    payload.update(section_changes)
    sections = ReportSections.model_validate(payload)
    markdown = render_report(assembly, sections, generated_at=STAMP)
    return {
        "assembly": assembly,
        "sections_outcome": validate_report_sections(assembly, sections),
        "rendered_outcome": validate_rendered_report(assembly, markdown),
        "markdown": markdown,
    }


def report_metrics(prepared: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    results = compute_report_metrics(
        prepared["handle"],
        prepared["run"],
        sections_outcome=report["sections_outcome"],
        rendered_outcome=report["rendered_outcome"],
        rendered_markdown=report["markdown"],
        approved_count=len(report["assembly"].approved_findings),
    )
    return {result.metric_name: result for result in results}


# ------------------------------------------------------------------------------------------
# Computed report metrics
# ------------------------------------------------------------------------------------------


def test_a_passing_report_scores_zero_invented_and_zero_unsupported(
    prepared: dict[str, Any],
) -> None:
    seed_finding(prepared["handle"])
    named = report_metrics(prepared, validated_report(prepared["handle"]))

    assert named["unsupported_claim_count"].metric_value == 0.0
    assert named["report_invented_finding_count"].metric_value == 0.0
    assert named["report_finding_coverage"].metric_value == 1.0
    assert named["report_severity_inconsistency_count"].metric_value == 0.0
    assert all(result.evaluator_type is EvaluatorType.AUTOMATED for result in named.values())


def test_an_invented_identifier_is_counted_from_the_validator(
    prepared: dict[str, Any],
) -> None:
    seed_finding(prepared["handle"])
    report = validated_report(
        prepared["handle"], risk_summary="The worst weakness is fnd-009, allowing forgery."
    )
    named = report_metrics(prepared, report)

    assert named["unsupported_claim_count"].metric_value == 1.0
    assert named["report_invented_finding_count"].metric_value == 1.0


def test_the_zero_finding_report_is_recorded_as_correct(prepared: dict[str, Any]) -> None:
    report = validated_report(
        prepared["handle"],
        risk_summary="No findings were approved; the gaps record what could not be determined.",
    )
    named = report_metrics(prepared, report)

    # DEC-150: no approved finding means no coverage ratio at all. The report being correct
    # about a zero-finding run is the report validator's business, not a 100% on the page.
    assert "report_finding_coverage" not in named
    assert named["report_invented_finding_count"].metric_value == 0.0


# ------------------------------------------------------------------------------------------
# The rubric: recorded, bounded, and never computed
# ------------------------------------------------------------------------------------------


def full_scores(**changes: int) -> dict[str, int]:
    scores = dict.fromkeys(RUBRIC_CATEGORIES, 4)
    scores.update(changes)
    return scores


def test_rubric_scores_are_stored_retrievable_and_marked_as_reviewer_judgement(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    results = record_rubric(
        handle,
        prepared["run"],
        full_scores(report_quality=3),
        reviewer_id=REVIEWER,
        comments="Readable, but the risk summary repeats the executive summary.",
    )

    assert len(results) == len(RUBRIC_CATEGORIES)
    stored = {result.metric_name: result for result in handle.objects.list(EvaluationResult)}
    quality = stored["rubric_report_quality"]
    assert quality.metric_value == 3.0
    assert quality.evaluator_type is EvaluatorType.REVIEWER
    assert "reviewer-rubric-v1" in quality.evaluation_method
    assert quality.notes is not None and "risk summary repeats" in quality.notes


def test_an_out_of_range_or_partial_rubric_is_refused(prepared: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="one to five"):
        record_rubric(
            prepared["handle"],
            prepared["run"],
            full_scores(report_quality=6),
            reviewer_id=REVIEWER,
        )
    partial = full_scores()
    partial.pop("evidence_quality")
    with pytest.raises(ValueError, match="evidence_quality"):
        record_rubric(prepared["handle"], prepared["run"], partial, reviewer_id=REVIEWER)


def test_readability_and_report_quality_originate_only_from_reviewer_input(
    prepared: dict[str, Any],
) -> None:
    """Section 15: no heuristic readability score wears a measurement's authority."""
    module = PROJECT_ROOT / "src" / "trace_ai" / "services" / "evaluation" / "report_metrics.py"
    source = module.read_text(encoding="utf-8")
    for heuristic in ("flesch", "readability_score", "grade_level"):
        assert heuristic not in source.casefold()

    seed_finding(prepared["handle"])
    named = report_metrics(prepared, validated_report(prepared["handle"]))
    assert not any("readability" in name for name in named)
    assert not any("quality" in name for name in named)


# ------------------------------------------------------------------------------------------
# The per-run summary
# ------------------------------------------------------------------------------------------


def test_the_summary_contains_every_available_count(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    seed_finding(handle)
    report = validated_report(handle)
    results = [
        *compute_metrics(handle, prepared["run"]),
        *compute_report_metrics(
            handle,
            prepared["run"],
            sections_outcome=report["sections_outcome"],
            rendered_outcome=report["rendered_outcome"],
            rendered_markdown=report["markdown"],
            approved_count=1,
        ),
    ]
    path = write_summary(handle, prepared["run"], results)

    assert path.parent == handle.artifacts.area("evaluation")
    summary = json.loads(path.read_text(encoding="utf-8"))
    counts = summary["counts"]
    for field in (
        "findings_proposed",
        "findings_approved",
        "findings_rejected",
        "findings_edited",
        "questions_generated",
        "documentation_gaps",
        "model_calls",
        "input_tokens",
        "output_tokens",
        "failures",
        "retries",
    ):
        assert field in counts, f"the summary is missing {field}"
    assert counts["findings_approved"] == 1
    assert summary["metrics"]["finding_evidence_coverage"] == 1.0
    assert summary["metrics"]["unsupported_claim_count"] == 0.0


def test_a_zero_finding_assessment_summarizes_cleanly(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    report = validated_report(
        handle,
        risk_summary="No findings were approved; the gaps record what could not be determined.",
    )
    results = [
        *compute_metrics(handle, prepared["run"]),
        *compute_report_metrics(
            handle,
            prepared["run"],
            sections_outcome=report["sections_outcome"],
            rendered_outcome=report["rendered_outcome"],
            rendered_markdown=report["markdown"],
            approved_count=0,
        ),
    ]
    path = write_summary(handle, prepared["run"], results)

    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["counts"]["findings_proposed"] == 0
    assert summary["counts"]["findings_approved"] == 0
    assert list(handle.artifacts.area("outputs").iterdir()) == [], (
        "the summary lives in evaluation/, never in the report directory"
    )


def test_computation_makes_no_model_call() -> None:
    module = PROJECT_ROOT / "src" / "trace_ai" / "services" / "evaluation" / "report_metrics.py"
    source = module.read_text(encoding="utf-8")
    assert "StructuredModel" not in source
    assert "anthropic" not in source
    assert "generate(" not in source
