"""Walking the evidence chain on demand: stored bytes, recorded hashes, and the manifest.

Every `SourceDocument` carries the hash of its stored bytes, every `EvidenceReference` carries the
hash of the passage it quotes, and the report's manifest (#108) pins the rendered document and the
versions that produced it. Each hash was written once and verified never — this module is the walk,
and `trace verify` is its command.

A drift is reported with the identifier, the expected hash, and the found hash, and nothing else:
hashes are safe output, document content is not, and a verification report that quoted the changed
passage would be printing exactly the untrusted content whose change it is reporting.

What manifest verification checks is agreement with the store *now*: the report bytes still hash to
the manifest's pin, and the approved-object counts still match the objects the assessment holds. A
mismatch does not say which side moved — that is what makes it worth stopping for.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from trace_ai.domain.assessment import Assessment
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import WorkflowRun
from trace_ai.domain.source_document import SourceDocument
from trace_ai.infrastructure.filesystem.artifact_store import ArtifactStoreError
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.findings.approved import approved_findings

if TYPE_CHECKING:
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.evidence.index import VerificationResult

__all__ = ["AssessmentVerification", "Drift", "verify_assessment"]


@dataclass(frozen=True, slots=True)
class Drift:
    """One thing that no longer agrees with its recorded value."""

    subject: str
    """The identifier or manifest field, never content."""

    expected: str
    found: str

    def line(self) -> str:
        return f"{self.subject}  expected {self.expected}  found {self.found}"


@dataclass(slots=True)
class AssessmentVerification:
    """What one verification pass covered, and everything that drifted."""

    document_count: int = 0
    evidence_count: int = 0
    manifest_checked: bool = False
    document_drift: list[Drift] = field(default_factory=list)
    evidence_failures: list[VerificationResult] = field(default_factory=list)
    manifest_drift: list[Drift] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.document_drift or self.evidence_failures or self.manifest_drift)


def verify_assessment(handle: AssessmentHandle) -> AssessmentVerification:
    """Re-hash every stored document, re-check every evidence reference, verify the manifest."""
    report = AssessmentVerification()

    documents = handle.objects.list(SourceDocument)
    report.document_count = len(documents)
    for document in sorted(documents, key=lambda item: item.id):
        try:
            found = handle.artifacts.hash_of("sources", document.filename)
        except ArtifactStoreError:
            found = "artifact_missing"
        if found != document.content_hash:
            report.document_drift.append(
                Drift(subject=document.id, expected=document.content_hash, found=found)
            )

    report.evidence_count = len(handle.objects.list(EvidenceReference))
    report.evidence_failures = EvidenceIndex(handle).verify_all()

    assessment = handle.objects.get(Assessment, handle.assessment_id)
    if assessment.final_report_path is not None:
        report.manifest_checked = True
        report.manifest_drift = _verify_manifest(handle, assessment)

    return report


def _verify_manifest(handle: AssessmentHandle, assessment: Assessment) -> list[Drift]:
    """The manifest against the store: the report's bytes, the run, and the approved counts."""
    drift: list[Drift] = []
    report_filename = (assessment.final_report_path or "").rpartition("/")[2]
    manifest_filename = report_filename.removesuffix(".md") + ".manifest.json"

    try:
        manifest = json.loads(handle.artifacts.read("outputs", manifest_filename))
    except ArtifactStoreError:
        return [Drift(subject="manifest", expected=manifest_filename, found="artifact_missing")]

    try:
        found_hash = handle.artifacts.hash_of("outputs", report_filename)
    except ArtifactStoreError:
        found_hash = "artifact_missing"
    pinned = manifest.get("report", {}).get("content_hash", "unrecorded")
    if found_hash != pinned:
        drift.append(Drift(subject="report.content_hash", expected=pinned, found=found_hash))

    if manifest.get("assessment_id") != assessment.id:
        drift.append(
            Drift(
                subject="assessment_id",
                expected=str(manifest.get("assessment_id")),
                found=assessment.id,
            )
        )

    run_id = str(manifest.get("workflow_run_id"))
    if handle.objects.find(WorkflowRun, run_id) is None:
        drift.append(Drift(subject="workflow_run_id", expected=run_id, found="no such run"))

    counts = manifest.get("counts", {})
    approved_now = len(approved_findings(handle))
    if counts.get("approved_findings") != approved_now:
        drift.append(
            Drift(
                subject="counts.approved_findings",
                expected=str(counts.get("approved_findings")),
                found=str(approved_now),
            )
        )
    gaps_now = len(
        [
            gap
            for gap in handle.objects.list(DocumentationGap)
            if gap.status is ObjectStatus.APPROVED
        ]
    )
    if counts.get("documentation_gaps") != gaps_now:
        drift.append(
            Drift(
                subject="counts.documentation_gaps",
                expected=str(counts.get("documentation_gaps")),
                found=str(gaps_now),
            )
        )

    return drift
