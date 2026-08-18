"""Assessment diffing (#488, DEC-097): conservative matching, honest classification.

The load-bearing properties: identical approved models diff as unchanged; identity is the
DEC-093 fingerprint, not the per-assessment identifier; a renamed object is removed-and-added,
never force-paired; a content change names its fields; ambiguity falls to added/removed; and an
unapproved side is refused like every export.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus
from trace_ai.domain.system_context import SystemContext
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.diff import diff_assessments
from trace_ai.services.export import ExportError
from trace_ai.workflow.finding_review import approve_finding

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

REVIEWER = "diff-test-reviewer"
FINGERPRINT = "sha256:" + "a" * 64


def _save(handle: AssessmentHandle, obj: Any) -> Any:
    with handle.objects.transaction():
        handle.objects.save(obj)
    return obj


def _build(
    service: AssessmentService,
    *,
    components: Sequence[tuple[str, str, str | None]],
    question: str | None = "Is webhook authenticity verified?",
    finding_fingerprint: str | None = FINGERPRINT,
    approve_context: bool = True,
) -> AssessmentHandle:
    created = service.create(
        "ForgeFlow", default_configuration("offline-fake", "stride-scenario-based")
    )
    handle = service.handle(created.id)
    stamped = now()
    for cid, name, description in components:
        _save(
            handle,
            Component.model_validate(
                {
                    "id": cid,
                    "assessment_id": handle.assessment_id,
                    "name": name,
                    "component_type": "service",
                    "description": description,
                    "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                    "status": ObjectStatus.APPROVED,
                }
            ),
        )
    if question is not None:
        _save(
            handle,
            Question.model_validate(
                {
                    "id": "qst-001",
                    "assessment_id": handle.assessment_id,
                    "question": question,
                    "rationale": "The endpoint accepts external events.",
                    "priority": QuestionPriority.HIGH,
                    "blocking": False,
                    "status": QuestionStatus.OPEN,
                    "generated_by": "context-extraction-v1",
                }
            ),
        )
    _save(
        handle,
        SystemContext.model_validate(
            {
                "assessment_id": handle.assessment_id,
                "system_name": "ForgeFlow",
                "system_purpose": "AI-assisted pull request review platform",
                "context_claim_ids": [],
                "component_ids": [cid for cid, _, _ in components],
                "asset_ids": [],
                "actor_ids": [],
                "data_flow_ids": [],
                "trust_boundary_ids": [],
                "approved_at": stamped if approve_context else None,
                "approved_by": REVIEWER if approve_context else None,
                "version": 1,
            }
        ),
    )
    if finding_fingerprint is not None:
        finding = Finding.model_validate(
            {
                "id": "fnd-001",
                "assessment_id": handle.assessment_id,
                "title": "Webhook requests may be processed without verified authenticity",
                "summary": "The receiver may accept events without verifying their origin.",
                "description": "Validation is structural, not cryptographic.",
                "threat_ids": ["thr-001"],
                "requirement_ids": ["req-WEBHOOK-001"],
                "control_mapping_ids": [],
                "affected_component_ids": [components[0][0]],
                "affected_asset_ids": [],
                "evidence_ids": ["evd-001"],
                "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
                "severity": Severity.HIGH,
                "impact": "Unauthorized job execution.",
                "recommendation": "Verify signatures.",
                "confidence": ConfidenceLevel.MEDIUM,
                "status": ObjectStatus.CANDIDATE,
                "generated_by": "finding-consolidation-v1",
                "content_fingerprint": finding_fingerprint,
                "created_at": stamped,
                "updated_at": stamped,
            }
        )
        _save(handle, finding)
        approve_finding(handle, finding, reviewer_id=REVIEWER)
    return handle


BASE = [
    ("cmp-001", "Webhook Receiver", "Accepts external events."),
    ("cmp-002", "Analysis Worker", "Runs the analysis jobs."),
]


def test_identical_approved_models_diff_as_unchanged(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        after = _build(service, components=BASE)

        diff = diff_assessments(before, after)

    assert diff.moved is False
    assert diff.families["components"].unchanged == 2
    assert diff.families["findings"].unchanged == 1
    assert diff.families["open_questions"].unchanged == 1


def test_identity_is_the_fingerprint_never_the_identifier(tmp_path: Path) -> None:
    """The same component under different allocated identifiers is the same component."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        renumbered = [("cmp-777", *BASE[0][1:]), ("cmp-888", *BASE[1][1:])]
        after = _build(service, components=renumbered)

        diff = diff_assessments(before, after)

    assert diff.families["components"].unchanged == 2
    assert not diff.families["components"].moved


def test_a_rename_is_removed_and_added_never_force_paired(tmp_path: Path) -> None:
    """The entries stand — and beside them, the rename candidate is declared (#529): one
    removed and one added object agreeing on every content field but the name."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        renamed = [BASE[0], ("cmp-002", "Analysis Engine", "Runs the analysis jobs.")]
        after = _build(service, components=renamed)

        diff = diff_assessments(before, after)

    components = diff.families["components"]
    assert [entry.identity for entry in components.removed] == ["analysis worker"]
    assert [entry.identity for entry in components.added] == ["analysis engine"]
    assert components.unchanged == 1
    (candidate,) = components.rename_candidates
    assert candidate.before_identity == "Analysis Worker"
    assert candidate.after_identity == "Analysis Engine"


def test_a_rename_with_a_content_edit_declares_no_candidate(tmp_path: Path) -> None:
    """Name and description both moved: any pairing would be a guess, so nothing is claimed."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        rewritten = [BASE[0], ("cmp-002", "Analysis Engine", "Renders reports too.")]
        after = _build(service, components=rewritten)

        diff = diff_assessments(before, after)

    assert diff.families["components"].rename_candidates == []


def test_two_plausible_rename_partners_declare_nothing(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        twins = [
            *BASE,
            ("cmp-003", "Queue A", "A queue."),
            ("cmp-004", "Queue B", "A queue."),
        ]
        before = _build(service, components=twins)
        merged = [*BASE, ("cmp-003", "Queue C", "A queue.")]
        after = _build(service, components=merged)

        diff = diff_assessments(before, after)

    assert diff.families["components"].rename_candidates == []


def test_a_content_change_names_its_fields(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        edited = [BASE[0], ("cmp-002", "Analysis Worker", "Now also renders reports.")]
        after = _build(service, components=edited)

        diff = diff_assessments(before, after)

    (changed,) = diff.families["components"].changed
    assert changed.identity == "analysis worker"
    assert changed.changed_fields == ("description",)
    assert changed.before_id == "cmp-002"
    assert changed.after_id == "cmp-002"


def test_ambiguous_fingerprints_fall_to_added_and_removed(tmp_path: Path) -> None:
    """Two objects sharing a fingerprint make every pairing a guess, and a diff must not guess."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        duplicated = [
            ("cmp-001", "Worker", "One."),
            ("cmp-002", "Worker", "Two."),
        ]
        before = _build(service, components=duplicated)
        after = _build(service, components=duplicated)

        diff = diff_assessments(before, after)

    components = diff.families["components"]
    assert components.unchanged == 0
    assert len(components.removed) == 2
    assert len(components.added) == 2


def test_an_unapproved_side_is_refused(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        after = _build(service, components=BASE, approve_context=False, finding_fingerprint=None)

        with pytest.raises(ExportError, match="approved"):
            diff_assessments(before, after)


def test_a_new_question_and_a_changed_finding_classify(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        after = _build(
            service,
            components=BASE,
            question="What enforces bucket authorization?",
            finding_fingerprint="sha256:" + "b" * 64,
        )

        diff = diff_assessments(before, after)

    questions = diff.families["open_questions"]
    assert [entry.identity for entry in questions.added] == ["what enforces bucket authorization?"]
    assert [entry.identity for entry in questions.removed] == ["is webhook authenticity verified?"]
    findings = diff.families["findings"]
    assert len(findings.removed) == 1 and len(findings.added) == 1


# ------------------------------------------------------------------------------------------
# Resolution shifts (#529): the finding/gap distinction, diffed
# ------------------------------------------------------------------------------------------


def _add_gap(handle: AssessmentHandle) -> None:
    """A gap over req-WEBHOOK-001 on the Webhook Receiver, resolved through its mapping."""
    from trace_ai.domain.control_mapping import (
        ApplicabilityStatus,
        ControlMapping,
        SatisfactionStatus,
    )
    from trace_ai.domain.documentation_gap import DocumentationGap
    from trace_ai.domain.threat import Threat

    stamped = now()
    _save(
        handle,
        Threat.model_validate(
            {
                "id": "thr-001",
                "assessment_id": handle.assessment_id,
                "title": "Forged webhooks trigger unauthorized analysis jobs",
                "description": "An attacker submits unsigned webhook requests.",
                "methodology": "stride-scenario-based",
                "category": ["spoofing"],
                "affected_component_ids": ["cmp-001"],
                "affected_asset_ids": ["ast-001"],
                "impact": "Unauthorized job execution.",
                "confidence": ConfidenceLevel.MEDIUM,
                "evidence_ids": ["evd-001"],
                "status": ObjectStatus.APPROVED,
                "generated_by": "threat-analysis-v1",
                "created_at": stamped,
            }
        ),
    )
    _save(
        handle,
        ControlMapping.model_validate(
            {
                "id": "map-001",
                "assessment_id": handle.assessment_id,
                "threat_id": "thr-001",
                "requirement_id": "req-WEBHOOK-001",
                "applicability_status": ApplicabilityStatus.APPLICABLE,
                "applicability_reason": "The receiver accepts external events.",
                "satisfaction_status": SatisfactionStatus.UNVERIFIED,
                "confidence": ConfidenceLevel.MEDIUM,
                "generated_by": "requirement-control-mapping-v1",
                "reviewer_status": ObjectStatus.APPROVED,
            }
        ),
    )
    _save(
        handle,
        DocumentationGap.model_validate(
            {
                "id": "gap-001",
                "assessment_id": handle.assessment_id,
                "title": "Webhook authenticity verification is undocumented",
                "description": "No document states whether signatures are verified.",
                "importance": "The receiver is internet-accessible.",
                "related_object_ids": ["map-001"],
                "severity": Severity.MEDIUM,
                "status": ObjectStatus.APPROVED,
                "generated_by": "requirement-control-mapping-v1",
            }
        ),
    )


def test_a_gap_resolving_into_a_finding_reports_the_shift(tmp_path: Path) -> None:
    """The signature distinction, diffed: before could not determine the control; after supports
    a weakness over the same requirement and ground. Reported with its direction."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE, finding_fingerprint=None)
        _add_gap(before)
        after = _build(service, components=BASE)

        diff = diff_assessments(before, after)

    (shift,) = diff.resolution_shifts
    assert shift.direction == "gap_to_finding"
    assert shift.requirement_ids == ("req-WEBHOOK-001",)
    assert shift.ground == "webhook receiver"
    assert shift.before_id == "gap-001"
    assert shift.after_id == "fnd-001"


def test_a_gap_persisting_beside_a_finding_is_not_a_shift(tmp_path: Path) -> None:
    """Two statements coexisting on the after side is not one resolving into the other."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE, finding_fingerprint=None)
        _add_gap(before)
        after = _build(service, components=BASE)
        _add_gap(after)

        diff = diff_assessments(before, after)

    assert diff.resolution_shifts == []


# ------------------------------------------------------------------------------------------
# The comparison report (#509, DEC-103)
# ------------------------------------------------------------------------------------------


def test_the_comparison_report_narrates_the_diff_findings_first(tmp_path: Path) -> None:
    from trace_ai.services.diff import render_comparison_report

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        renamed = [BASE[0], ("cmp-002", "Analysis Engine", "Runs the analysis jobs.")]
        after = _build(service, components=renamed)
        diff = diff_assessments(before, after)

    report = render_comparison_report(diff, before_name="Before", after_name="After")
    assert report.startswith("# Assessment comparison")
    # Findings lead the detail: the section order puts them ahead of Components.
    assert report.index("### Components") > 0
    assert "analysis engine" in report and "analysis worker" in report
    assert "## Unchanged" in report


def test_an_identical_pair_reports_no_difference(tmp_path: Path) -> None:
    from trace_ai.services.diff import render_comparison_report

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        after = _build(service, components=BASE)
        diff = diff_assessments(before, after)

    report = render_comparison_report(diff, before_name="A", after_name="B")
    assert "do not differ" in report


def test_the_report_writes_to_the_later_assessments_outputs(tmp_path: Path) -> None:
    from trace_ai.services.diff import write_comparison_report

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        before = _build(service, components=BASE)
        after = _build(service, components=BASE)
        written = write_comparison_report(before, after)

    assert written.name.startswith("comparison-")
    assert written.name.endswith(".md")
    assert written.is_file()
    assert after.assessment_id in str(written)
