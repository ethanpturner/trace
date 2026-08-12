"""The output manifest, and the publish step that writes it only after validation passes.

`agent-design.md` section 20 makes the manifest the rendering node's responsibility, and DEC-035
fixes its shape: JSON, one per report, sitting beside it, carrying what a later reader needs to
know that two reports are comparable — the artifact and its DEC-019 hash, every version identifier
`evaluation-plan.md` section 3 requires, the counts, and whether the run was authoritative.

**No manifest without a valid report.** `publish_report` runs the consistency validator (#107)
over the sections and again over the rendered document, and a violation stops everything: no
report file, no manifest, `Assessment.final_report_path` unchanged, and the offending output
preserved under `traces/`. A report that failed validation never becomes the assessment's final
report.

**The render is an execution like any other.** The publish records one `ExecutionRecord` with
`execution_type` deterministic and no model name — rendering uses no model, and the record is
what says so rather than the absence of a row.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.assessment import Assessment
from trace_ai.domain.base import now
from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.hashing import content_hash
from trace_ai.workflow.report_rendering import (
    NODE_NAME,
    NODE_VERSION,
    RenderedReport,
    render_report,
    report_filename,
)
from trace_ai.workflow.report_validation import (
    ReportValidationOutcome,
    validate_rendered_report,
    validate_report_sections,
)
from trace_ai.workflow.retry import preserve_failed_output

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from trace_ai.domain.proposals.report_sections import ReportSections
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.execution_ledger import ExecutionLedger
    from trace_ai.services.report.input_assembly import ReportInput

__all__ = [
    "MANIFEST_VERSION",
    "PublishedReport",
    "ReportValidationFailedError",
    "build_manifest",
    "manifest_filename",
    "publish_report",
]

MANIFEST_VERSION: Final = "1"


class ReportValidationFailedError(RuntimeError):
    """The report failed the consistency validator; nothing was published.

    Carries both validation outcomes so the caller can route by error class (section 26) or show
    the violations. The offending output is preserved under `traces/` before this is raised.
    """

    def __init__(
        self,
        sections_outcome: ReportValidationOutcome,
        rendered_outcome: ReportValidationOutcome,
        preserved: str,
    ) -> None:
        violations = [*sections_outcome.violations, *rendered_outcome.violations]
        super().__init__(
            f"{len(violations)} report validation violation(s); no manifest was written and "
            f"final_report_path is unchanged. The offending output is preserved at {preserved}."
        )
        self.sections_outcome = sections_outcome
        self.rendered_outcome = rendered_outcome
        self.preserved = preserved


@dataclass(frozen=True, slots=True)
class PublishedReport:
    """A validated report on disk, with its manifest and the updated assessment.

    The two validation outcomes ride along so the caller can compute the report-quality
    metrics (#329) from the same passes that gated publication, rather than re-validating.
    """

    report: RenderedReport
    report_path: Path
    manifest: dict[str, Any]
    manifest_path: Path
    assessment: Assessment
    sections_outcome: ReportValidationOutcome
    rendered_outcome: ReportValidationOutcome


def manifest_filename(workflow_run_id: str) -> str:
    return f"report-{workflow_run_id}.manifest.json"


def build_manifest(
    assembled: ReportInput,
    *,
    workflow_run_id: str,
    report_path: str,
    report_hash: str,
    generated_at: datetime,
    ablations: tuple[str, ...] = (),
) -> dict[str, Any]:
    """DEC-035's manifest, field for field. Deterministic; no model."""
    findings = assembled.approved_findings
    by_severity: dict[str, int] = {}
    for finding in findings:
        by_severity[finding.severity.value] = by_severity.get(finding.severity.value, 0) + 1

    versions = assembled.versions
    return {
        "manifest_version": MANIFEST_VERSION,
        "assessment_id": assembled.assessment.id,
        "workflow_run_id": workflow_run_id,
        "generated_at": generated_at.isoformat(),
        "report": {
            "path": report_path,
            "content_hash": report_hash,
            "format": "markdown",
            "template_version": assembled.template,
        },
        "versions": {
            "architecture": versions.architecture_version,
            "data_model": assembled.assessment.data_model_version,
            "workflow": versions.workflow_version,
            "requirements_catalog": versions.requirements_catalog_version,
            "prompts": dict(versions.prompt_versions),
            "model": versions.model,
            "model_profile": assembled.assessment.configuration.model_profile,
            "model_configuration": versions.model_configuration,
        },
        "counts": {
            "approved_findings": len(findings),
            "findings_by_severity": dict(sorted(by_severity.items())),
            "documentation_gaps": len(assembled.approved_documentation_gaps),
            "open_questions": len(assembled.open_questions),
            "assumptions": len(assembled.assumption_claims),
            "confirmed_controls": len(assembled.confirmed_controls),
            "threats": len(assembled.threats),
            "evidence_references": len(assembled.evidence_references),
        },
        "authoritative": assembled.authoritative,
        "ablations": list(ablations),
    }


def publish_report(
    handle: AssessmentHandle,
    assembled: ReportInput,
    sections: ReportSections,
    *,
    ledger: ExecutionLedger,
    workflow_run_id: str,
    generated_at: datetime | None = None,
    ablations: tuple[str, ...] = (),
) -> PublishedReport:
    """Validate, render, validate again, and only then write everything (DEC-035, #107, #108).

    The order is the guarantee: a violation at either pass raises before a byte reaches
    `outputs/`, so a failed render produces no manifest and leaves `final_report_path` exactly as
    it was. On success the report and its manifest are stored, `Assessment.final_report_path` is
    set to the report's path relative to the assessment root, `updated_at` moves, and one
    deterministic `ExecutionRecord` names the render.
    """
    stamp = generated_at if generated_at is not None else now()

    with ledger.record(
        NODE_NAME,
        node_version=NODE_VERSION,
        execution_type=ExecutionType.DETERMINISTIC,
        consumes=[finding.id for finding in assembled.approved_findings],
    ) as execution:
        sections_outcome = validate_report_sections(assembled, sections)
        markdown = render_report(assembled, sections, generated_at=stamp)
        rendered_outcome = validate_rendered_report(assembled, markdown)

        if not (sections_outcome.valid and rendered_outcome.valid):
            preserved = preserve_failed_output(
                handle.artifacts,
                node_name=NODE_NAME,
                attempt_number=1,
                raw_output=json.dumps(
                    {"sections": sections.model_dump(), "rendered": markdown},
                    indent=2,
                    default=str,
                ),
            )
            execution.metadata["violations"] = len(sections_outcome.violations) + len(
                rendered_outcome.violations
            )
            raise ReportValidationFailedError(sections_outcome, rendered_outcome, preserved)

        report = RenderedReport(markdown=markdown, filename=report_filename(workflow_run_id))
        report_path = handle.artifacts.store_output(
            report.filename, report.markdown.encode("utf-8")
        )
        relative = str(report_path.relative_to(handle.artifacts.assessment_root))
        report_hash = content_hash(report.markdown.encode("utf-8"))

        manifest = build_manifest(
            assembled,
            workflow_run_id=workflow_run_id,
            report_path=relative,
            report_hash=report_hash,
            generated_at=stamp,
            ablations=ablations,
        )
        manifest_path = handle.artifacts.store_output(
            manifest_filename(workflow_run_id),
            json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
        )

        current = handle.objects.get(Assessment, handle.assessment_id)
        updated = Assessment.model_validate(
            {
                **current.model_dump(),
                "final_report_path": relative,
                "updated_at": now(),
            }
        )
        with handle.objects.transaction():
            handle.objects.save(updated)

        execution.produced(updated.id)
        execution.metadata["report_path"] = relative
        execution.metadata["report_hash"] = report_hash
        execution.metadata["unsupported_claim_count"] = sections_outcome.unsupported_statement_count

    return PublishedReport(
        report=report,
        report_path=report_path,
        manifest=manifest,
        manifest_path=manifest_path,
        assessment=updated,
        sections_outcome=sections_outcome,
        rendered_outcome=rendered_outcome,
    )
