"""Stale-evidence detection (#571, DEC-118): capture age, per-assessment threshold, flags only.

The properties that carry the file: the age anchor is the citation's capture time measured
against a caller-supplied stamp, never a wall clock read inside the computation; no configured
threshold means no flags anywhere, because absence of a policy is not a policy; and a flag
changes nothing — the finding renders with every field it had, plus one line.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.domain.assessment import AssessmentConfiguration, default_configuration
from trace_ai.domain.base import now
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
from trace_ai.services.evidence.staleness import stale_evidence_ids

PASSAGE = "The receiver accepts and processes any well-formed delivery."
STAMP = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)


def a_reference(evidence_id: str, created_at: datetime) -> EvidenceReference:
    return EvidenceReference.model_validate(
        {
            "id": evidence_id,
            "assessment_id": "asm-001",
            "source_document_id": "src-001",
            "start_line": 1,
            "end_line": 2,
            "quoted_text": PASSAGE,
            "content_hash": content_hash(PASSAGE.encode()),
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "created_at": created_at,
        }
    )


def a_finding(*evidence_ids: str) -> Finding:
    stamped = now()
    return Finding.model_validate(
        {
            "id": "fnd-001",
            "assessment_id": "asm-001",
            "title": "Webhook requests may be processed without verified authenticity",
            "summary": "The receiver may accept events without verifying their origin.",
            "description": "The documents describe validation as structural.",
            "threat_ids": ["thr-001"],
            "requirement_ids": ["req-WEBHOOK-001"],
            "control_mapping_ids": ["map-001"],
            "affected_component_ids": ["cmp-001"],
            "affected_asset_ids": ["ast-001"],
            "evidence_ids": list(evidence_ids),
            "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
            "severity": Severity.HIGH,
            "impact": "Unauthorized job execution.",
            "recommendation": "Verify each event with the platform's signature mechanism.",
            "confidence": ConfidenceLevel.MEDIUM,
            "status": ObjectStatus.APPROVED,
            "generated_by": "finding-consolidation-v1",
            "created_at": stamped,
            "updated_at": stamped,
        }
    )


# ------------------------------------------------------------------------------------------
# The computation
# ------------------------------------------------------------------------------------------


def test_a_citation_older_than_the_threshold_is_named() -> None:
    references = {"evd-001": a_reference("evd-001", STAMP - timedelta(days=91))}
    stale = stale_evidence_ids(a_finding("evd-001"), references, threshold_days=90, as_of=STAMP)
    assert stale == ("evd-001",)


def test_a_citation_at_or_inside_the_threshold_is_not_stale() -> None:
    references = {
        "evd-001": a_reference("evd-001", STAMP - timedelta(days=90)),
        "evd-002": a_reference("evd-002", STAMP - timedelta(days=1)),
    }
    stale = stale_evidence_ids(
        a_finding("evd-001", "evd-002"), references, threshold_days=90, as_of=STAMP
    )
    assert stale == ()


def test_stale_ids_keep_the_findings_citation_order() -> None:
    references = {
        "evd-002": a_reference("evd-002", STAMP - timedelta(days=400)),
        "evd-001": a_reference("evd-001", STAMP - timedelta(days=200)),
    }
    stale = stale_evidence_ids(
        a_finding("evd-002", "evd-001"), references, threshold_days=90, as_of=STAMP
    )
    assert stale == ("evd-002", "evd-001")


def test_an_unresolvable_citation_is_not_called_stale() -> None:
    """A missing passage is its own, louder problem; calling it old would dress it up."""
    stale = stale_evidence_ids(a_finding("evd-404"), {}, threshold_days=1, as_of=STAMP)
    assert stale == ()


# ------------------------------------------------------------------------------------------
# The configuration field
# ------------------------------------------------------------------------------------------


def test_the_threshold_is_unset_by_default() -> None:
    configuration = default_configuration("primary-development", "stride-scenario-based")
    assert configuration.evidence_age_threshold_days is None


@pytest.mark.parametrize("days", [0, -30])
def test_a_non_positive_threshold_is_refused(days: int) -> None:
    with pytest.raises(ValidationError):
        default_configuration(
            "primary-development",
            "stride-scenario-based",
            evidence_age_threshold_days=days,
        )


def test_the_threshold_is_carried_when_set() -> None:
    configuration = default_configuration(
        "primary-development", "stride-scenario-based", evidence_age_threshold_days=90
    )
    assert isinstance(configuration, AssessmentConfiguration)
    assert configuration.evidence_age_threshold_days == 90


# ------------------------------------------------------------------------------------------
# The report line and the view column
# ------------------------------------------------------------------------------------------


def _seed(handle: Any) -> None:
    from trace_ai.domain.source_document import (
        IngestionStatus,
        MediaType,
        SourceDocument,
        TrustLevel,
    )
    from trace_ai.workflow.finding_review import approve_finding

    stamped = now()
    with handle.objects.transaction():
        handle.objects.save(
            SourceDocument.model_validate(
                {
                    "id": "src-001",
                    "assessment_id": handle.assessment_id,
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
        reference = a_reference("evd-001", stamped)
        handle.objects.save(
            type(reference).model_validate(
                {**reference.model_dump(), "assessment_id": handle.assessment_id}
            )
        )
    finding = a_finding("evd-001")
    finding = type(finding).model_validate(
        {
            **finding.model_dump(),
            "assessment_id": handle.assessment_id,
            "status": ObjectStatus.CANDIDATE,
        }
    )
    with handle.objects.transaction():
        handle.objects.save(finding)
    approve_finding(handle, finding, reviewer_id="reviewer-local")


def _sections(assembly: Any) -> Any:
    from trace_ai.domain.proposals.report_sections import LimitationEntry, ReportSections

    return ReportSections.model_validate(
        {
            "executive_summary": "One approved finding.",
            "system_overview": "A webhook receiver and a worker.",
            "risk_summary": "Origin verification is the open risk.",
            "limitations": [
                LimitationEntry.model_validate(
                    {"limitation_id": limitation.limitation_id, "text": limitation.facts}
                )
                for limitation in assembly.required_limitations
            ],
        }
    )


def _rendered_with(tmp_path: Any, *, threshold: int | None, age_days: int) -> str:
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.report.input_assembly import assemble_report_input
    from trace_ai.workflow.report_rendering import render_report

    overrides: dict[str, object] = (
        {} if threshold is None else {"evidence_age_threshold_days": threshold}
    )
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Staleness",
            default_configuration("primary-development", "stride-scenario-based", **overrides),
        )
        handle = service.handle(created.id)
        _seed(handle)
        assembly = assemble_report_input(
            handle,
            prompt_versions={"generate-report-sections": "generate-report-sections-v1"},
            model="claude-opus-5",
            model_configuration="primary-development",
        )
        return render_report(
            assembly, _sections(assembly), generated_at=now() + timedelta(days=age_days)
        )


def test_the_report_flags_a_stale_citation_when_the_threshold_is_set(tmp_path: Any) -> None:
    report = _rendered_with(tmp_path, threshold=30, age_days=90)
    assert "Stale evidence: evd-001" in report
    assert "30 days" in report


def test_the_report_carries_no_flag_without_a_threshold(tmp_path: Any) -> None:
    report = _rendered_with(tmp_path, threshold=None, age_days=90)
    assert "Stale evidence" not in report


def test_the_flag_removes_nothing_from_the_finding(tmp_path: Any) -> None:
    flagged = _rendered_with(tmp_path, threshold=30, age_days=90)
    plain = _rendered_with(tmp_path.joinpath("plain"), threshold=None, age_days=90)
    for line in ("Severity: high", "Unauthorized job execution.", "evd-001"):
        assert line in flagged
        assert line in plain


def test_the_view_adds_a_stale_column_only_when_the_threshold_is_set(tmp_path: Any) -> None:
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.interface.render import render_findings
    from trace_ai.services.assessment import AssessmentService

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Staleness view",
            default_configuration(
                "primary-development",
                "stride-scenario-based",
                evidence_age_threshold_days=30,
            ),
        )
        handle = service.handle(created.id)
        _seed(handle)
        page = render_findings(handle, created)
        assert "Stale evidence (&gt;30d)" in page

        plain = service.create(
            "No threshold",
            default_configuration("primary-development", "stride-scenario-based"),
        )
        plain_handle = service.handle(plain.id)
        _seed(plain_handle)
        assert "Stale evidence" not in render_findings(plain_handle, plain)
