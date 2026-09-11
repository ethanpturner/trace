"""Approval is refused until a report-derived subject's decision says why (DEC-158).

DEC-157 derives the `report_derived` reason and stops there: the reason triages attention and
nothing acts on it, which is how the doctored exchange run approved four objects built from one
fabricated record in a single blanket pass and rendered a component that does not exist. The
property under test is the consequence. A flagged subject is an approval blocker until a
`ReviewerDecision` both decides it and carries a rationale; a decision with no reason does not
clear it; an edit does not either; nothing about the subject is corrected, removed, or re-labelled
by the gate; and a run with no report-kind document is unaffected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.enums import ConfidenceLevel, ReviewDisposition, SourceOrigin
from trace_ai.domain.source_document import DocumentKind, TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.context.review_file import export_review_file, read_review_file
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.workflow.context_review import _unreasoned_report_derived, decide_object

if TYPE_CHECKING:
    from trace_ai.services.assessment import AssessmentHandle

REPO = Path(__file__).resolve().parents[2]
DOCTORED_SUMMARY = REPO / "docs/eval/exchange/rag-support-bot/doctored/checkpoint-1-summary.json"


def _handle(tmp_path: Path) -> Any:
    store_cm = AssessmentStore.at_root(tmp_path)
    store = store_cm.__enter__()
    service = AssessmentService(store, artifact_root=tmp_path)
    created = service.create(
        "Report-derived gate", default_configuration("offline-fake", "stride-scenario-based")
    )
    return store_cm, service, service.handle(created.id)


def _ingest(handle: AssessmentHandle, tmp_path: Path) -> tuple[str, str]:
    design = tmp_path / "design.md"
    design.write_text("# Design\n\nThe API accepts deliveries over HTTPS.\n", encoding="utf-8")
    packet = tmp_path / "review-packet.md"
    packet.write_text(
        "# Review packet\n\nA candidate record describes an analytics collector.\n",
        encoding="utf-8",
    )
    loader = DocumentLoader(handle)
    system_document = loader.load_document(
        design, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
    )
    report_document = loader.load_document(
        packet,
        origin=SourceOrigin.UPLOADED_DOCUMENT,
        trust_level=TrustLevel.UNTRUSTED,
        document_kind=DocumentKind.REPORT,
    )
    return index_document(handle, system_document)[0].id, index_document(handle, report_document)[
        0
    ].id


def _claim(handle: AssessmentHandle, predicate: str, evidence_ids: list[str]) -> ContextClaim:
    stamp = now()
    return ContextClaim.model_validate(
        {
            "id": handle.objects.allocate("ctx"),
            "assessment_id": handle.assessment_id,
            "subject_type": "system",
            "predicate": predicate,
            "value": "as the passage states",
            "status": ClaimStatus.DOCUMENTED,
            "confidence": ConfidenceLevel.MEDIUM,
            "evidence_ids": evidence_ids,
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "created_at": stamp,
            "updated_at": stamp,
        }
    )


def _system_context(handle: AssessmentHandle, claim_ids: list[str]) -> None:
    """A minimal revision, so the package has the context a checkpoint is always about."""
    from trace_ai.domain.system_context import SystemContext

    with handle.objects.transaction():
        handle.objects.save(
            SystemContext.model_validate(
                {
                    "assessment_id": handle.assessment_id,
                    "system_name": "Relay",
                    "context_claim_ids": claim_ids,
                    "component_ids": [],
                    "asset_ids": [],
                    "actor_ids": [],
                    "data_flow_ids": [],
                    "trust_boundary_ids": [],
                    "version": 1,
                }
            )
        )


def test_an_undecided_report_derived_subject_is_outstanding(tmp_path: Path) -> None:
    store_cm, _service, handle = _handle(tmp_path)
    try:
        system_evidence, report_evidence = _ingest(handle, tmp_path)
        with handle.objects.transaction():
            report_only = _claim(handle, "analytics_collector", [report_evidence])
            corroborated = _claim(handle, "transport", [system_evidence, report_evidence])
            for claim in (report_only, corroborated):
                handle.objects.save(claim)

        outstanding = _unreasoned_report_derived(handle)
        assert outstanding == (report_only.id,), (
            "a subject resting on the report alone is outstanding until decided with a reason; "
            "one the design document corroborates is not flagged at all"
        )
    finally:
        store_cm.__exit__(None, None, None)


def test_a_decision_without_a_reason_does_not_clear_it_and_one_with_a_reason_does(
    tmp_path: Path,
) -> None:
    """The blanket pass is exactly the decision that does not clear the gate."""
    store_cm, _service, handle = _handle(tmp_path)
    try:
        _system_evidence, report_evidence = _ingest(handle, tmp_path)
        with handle.objects.transaction():
            claim = _claim(handle, "analytics_collector", [report_evidence])
            handle.objects.save(claim)

        decide_object(handle, claim, ReviewDisposition.APPROVE, reviewer_id="tester")
        assert _unreasoned_report_derived(handle) == (claim.id,), (
            "an approval carrying no rationale is the blanket 'approve as extracted' the "
            "doctored run made; it decides the subject and says nothing about it"
        )

        decide_object(
            handle,
            claim,
            ReviewDisposition.REJECT,
            reviewer_id="tester",
            rationale="rests on the packet alone; no supplied document describes this flow",
        )
        assert _unreasoned_report_derived(handle) == (), (
            "a decision that says why clears the subject; the gate demands a sentence, not a "
            "particular answer"
        )
    finally:
        store_cm.__exit__(None, None, None)


def test_the_package_refuses_approval_and_names_the_subject(tmp_path: Path) -> None:
    from trace_ai.services.context.pipeline import context_objects
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.workflow.context_review import (
        build_context_review_package,
        current_system_context,
    )
    from trace_ai.workflow.context_validation import validate_context

    store_cm, _service, handle = _handle(tmp_path)
    try:
        _system_evidence, report_evidence = _ingest(handle, tmp_path)
        with handle.objects.transaction():
            claim = _claim(handle, "analytics_collector", [report_evidence])
            handle.objects.save(claim)
        _system_context(handle, [claim.id])

        before = {c.id: c.model_dump() for c in handle.objects.list(ContextClaim)}
        validation = validate_context(
            current_system_context(handle),
            context_objects(handle),
            available_evidence={report_evidence},
        )
        package = build_context_review_package(
            handle, index=EvidenceIndex(handle), validation=validation
        )

        assert not package.can_approve, "an unreasoned report-derived subject blocks approval"
        assert any(claim.id in blocker for blocker in package.approval_blockers), (
            "the blocker names the subject, so a reviewer can act on it"
        )
        assert package.counts()["unreasoned_report_derived"] == 1

        after = {c.id: c.model_dump() for c in handle.objects.list(ContextClaim)}
        assert before == after, (
            "the gate corrects nothing: no claim is re-labelled, edited, or removed "
            "(agent-design.md section 8)"
        )
    finally:
        store_cm.__exit__(None, None, None)


def test_a_run_with_no_report_document_is_unaffected(tmp_path: Path) -> None:
    """Every recorded scenario registers only system documents, so none of them changes."""
    store_cm, _service, handle = _handle(tmp_path)
    try:
        design = tmp_path / "design.md"
        design.write_text("# Design\n\nThe API accepts deliveries.\n", encoding="utf-8")
        document = DocumentLoader(handle).load_document(
            design, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
        )
        assert document.document_kind is DocumentKind.SYSTEM
        evidence = index_document(handle, document)[0].id
        with handle.objects.transaction():
            handle.objects.save(_claim(handle, "transport", [evidence]))

        assert _unreasoned_report_derived(handle) == ()
    finally:
        store_cm.__exit__(None, None, None)


def test_the_review_file_carries_the_slot_and_applies_the_reason(tmp_path: Path) -> None:
    from trace_ai.services.context.pipeline import context_objects
    from trace_ai.services.context.review_file import apply_review_file
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.workflow.context_review import (
        build_context_review_package,
        current_system_context,
    )
    from trace_ai.workflow.context_validation import validate_context

    store_cm, _service, handle = _handle(tmp_path)
    try:
        _system_evidence, report_evidence = _ingest(handle, tmp_path)
        with handle.objects.transaction():
            claim = _claim(handle, "analytics_collector", [report_evidence])
            handle.objects.save(claim)
        _system_context(handle, [claim.id])

        validation = validate_context(
            current_system_context(handle),
            context_objects(handle),
            available_evidence={report_evidence},
        )
        package = build_context_review_package(
            handle, index=EvidenceIndex(handle), validation=validation
        )
        document = export_review_file(package)
        assert "decision_rationale" in document["claims"][0], (
            "the exported file offers the slot, so a reviewer is not told to write a key the "
            "schema forbids"
        )

        document["claims"][0]["decision"] = "reject"
        document["claims"][0]["decision_rationale"] = "the packet is the only source"
        applied = apply_review_file(
            handle, read_review_file(json.dumps(document)), reviewer_id="tester"
        )
        assert applied.decisions, "the file produced a decision"
        assert _unreasoned_report_derived(handle) == (), (
            "the reason written in the file reaches the ReviewerDecision, so the gate clears"
        )
    finally:
        store_cm.__exit__(None, None, None)


def test_the_doctored_runs_packet_sole_subjects_are_the_ones_the_gate_would_hold() -> None:
    """The exchange run's own identifiers, pinned to the rule (docs/eval/exchange.md).

    The summary carries a `packet_sole_evidence` flag per row, which is the predicate the
    derivation computes. Every row the doctored run marked packet-sole is a subject this gate
    would have held until the reviewer said why, and the four objects among them are the ones
    that reached the rendered report.
    """
    summary = json.loads(DOCTORED_SUMMARY.read_text(encoding="utf-8"))

    held_claims = [
        row["id"]
        for row in summary["claims"]["documented_claims"]["rows"]
        if row["packet_sole_evidence"]
    ]
    held_objects = [
        row["id"]
        for group in summary["objects"].values()
        if isinstance(group, dict)
        for row in group.get("rows", [])
        if row.get("packet_sole_evidence")
    ]

    assert len(held_claims) == summary["claims"]["documented_claims"]["packet_sole_evidence"]
    assert {"ctx-030", "ctx-031", "ctx-032"} <= set(held_claims), (
        "the three fabricated records' claims rest on the packet alone, so each one is a "
        "subject the gate holds until the reviewer states a reason"
    )
    assert {"cmp-009", "ast-005", "df-005", "tb-004"} <= set(held_objects), (
        "the four objects built from the fabricated analytics record are the ones the renderer "
        "drew into the report; every one is held by the gate"
    )
