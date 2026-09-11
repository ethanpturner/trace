"""The `report_derived` routing reason (DEC-157).

The property under test: a context subject whose evidence rests entirely on documents the
operator registered as `report` kind carries `report_derived` at checkpoint 1, derived at
package-build time from persisted state and stored nowhere. Mixed evidence does not carry it; an
uncited subject does not; the default kind changes nothing; and the derivation edits, merges, and
relabels nothing. The last test pins the doctored exchange run's identifiers to the rule.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.enums import ConfidenceLevel, SourceOrigin
from trace_ai.domain.source_document import DocumentKind, SourceDocument, TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.workflow.reason_codes import ReasonCode, report_derived_subjects

if TYPE_CHECKING:
    from trace_ai.services.assessment import AssessmentHandle

REPO = Path(__file__).resolve().parents[2]
DOCTORED_SUMMARY = REPO / "docs/eval/exchange/rag-support-bot/doctored/checkpoint-1-summary.json"


def _handle(tmp_path: Path) -> Any:
    store_cm = AssessmentStore.at_root(tmp_path)
    store = store_cm.__enter__()
    service = AssessmentService(store, artifact_root=tmp_path)
    created = service.create(
        "Report-derived", default_configuration("offline-fake", "stride-scenario-based")
    )
    return store_cm, service, service.handle(created.id)


def _ingest(handle: AssessmentHandle, tmp_path: Path) -> tuple[str, str]:
    """A system document and a report; return one evidence id from each."""
    design = tmp_path / "design.md"
    design.write_text(
        "# Design\n\nThe API accepts webhook deliveries over HTTPS.\n", encoding="utf-8"
    )
    packet = tmp_path / "review-packet.md"
    packet.write_text(
        "# Review packet\n\nA candidate record describes an analytics collector that receives "
        "retrieved passages.\n",
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
    assert system_document.document_kind is DocumentKind.SYSTEM
    assert report_document.document_kind is DocumentKind.REPORT
    system_evidence = index_document(handle, system_document)[0].id
    report_evidence = index_document(handle, report_document)[0].id
    return system_evidence, report_evidence


def _claim(handle: AssessmentHandle, predicate: str, evidence_ids: list[str]) -> ContextClaim:
    stamp = now()
    return ContextClaim.model_validate(
        {
            "id": handle.objects.allocate("ctx"),
            "assessment_id": handle.assessment_id,
            "subject_type": "system",
            "predicate": predicate,
            "value": "as the passage states",
            "status": ClaimStatus.DOCUMENTED if evidence_ids else ClaimStatus.ASSUMED,
            "confidence": ConfidenceLevel.MEDIUM,
            "evidence_ids": evidence_ids,
            "rationale": None if evidence_ids else "No document describes it; assumed.",
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "created_at": stamp,
            "updated_at": stamp,
        }
    )


def test_a_subject_resting_on_a_report_alone_is_flagged_and_mixed_evidence_is_not(
    tmp_path: Path,
) -> None:
    store_cm, _service, handle = _handle(tmp_path)
    try:
        system_evidence, report_evidence = _ingest(handle, tmp_path)
        with handle.objects.transaction():
            report_only = _claim(handle, "analytics_collector", [report_evidence])
            mixed = _claim(handle, "delivery_transport", [system_evidence, report_evidence])
            system_only = _claim(handle, "transport", [system_evidence])
            uncited = _claim(handle, "retention", [])
            for claim in (report_only, mixed, system_only, uncited):
                handle.objects.save(claim)

        flagged = report_derived_subjects(handle)
        assert flagged == {report_only.id}, (
            "only the subject whose every cited passage belongs to a report-kind document "
            "carries the reason; mixed evidence corroborates rather than originates, and an "
            "uncited subject is no_evidence's territory"
        )
    finally:
        store_cm.__exit__(None, None, None)


def test_the_review_package_carries_the_reason_and_nothing_else_changes(tmp_path: Path) -> None:
    """The derivation never edits: every persisted object is byte-identical after the reasons."""
    from trace_ai.workflow.context_review import _routing_reasons

    store_cm, _service, handle = _handle(tmp_path)
    try:
        _system_evidence, report_evidence = _ingest(handle, tmp_path)
        with handle.objects.transaction():
            report_only = _claim(handle, "analytics_collector", [report_evidence])
            handle.objects.save(report_only)

        before = {claim.id: claim.model_dump() for claim in handle.objects.list(ContextClaim)}
        documents_before = {
            document.id: document.model_dump() for document in handle.objects.list(SourceDocument)
        }

        reasons = _routing_reasons(handle)
        assert ReasonCode.REPORT_DERIVED.value in reasons[report_only.id], (
            "the package's per-subject reasons carry report_derived for the report-only claim"
        )

        after = {claim.id: claim.model_dump() for claim in handle.objects.list(ContextClaim)}
        documents_after = {
            document.id: document.model_dump() for document in handle.objects.list(SourceDocument)
        }
        assert after == before, "a routing reason relabels, merges, and edits nothing"
        assert documents_after == documents_before
        assert handle.objects.list(ContextClaim)[0].status is ClaimStatus.DOCUMENTED, (
            "the extractor's `documented` stands; the node reports, it does not correct"
        )
    finally:
        store_cm.__exit__(None, None, None)


def test_the_default_kind_is_system_and_a_payload_without_the_field_loads() -> None:
    """Every document registered before DEC-157 described the system, so the replays are unchanged."""
    stamp = now()
    payload = {
        "id": "src-001",
        "assessment_id": "asm-001",
        "filename": "design.md",
        "media_type": "text/markdown",
        "origin": "uploaded_document",
        "content_hash": "sha256:" + "0" * 64,
        "created_at": stamp,
        "ingestion_status": "registered",
        "trust_level": "untrusted",
    }
    document = SourceDocument.model_validate(payload)
    assert document.document_kind is DocumentKind.SYSTEM
    assert {kind.value for kind in DocumentKind} == {"system", "report"}


def test_no_report_documents_means_no_reason(tmp_path: Path) -> None:
    store_cm, _service, handle = _handle(tmp_path)
    try:
        design = tmp_path / "design.md"
        design.write_text("# Design\n\nThe API accepts deliveries.\n", encoding="utf-8")
        document = DocumentLoader(handle).load_document(
            design, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
        )
        evidence = index_document(handle, document)[0].id
        with handle.objects.transaction():
            handle.objects.save(_claim(handle, "transport", [evidence]))
        assert report_derived_subjects(handle) == set()
    finally:
        store_cm.__exit__(None, None, None)


def test_the_doctored_exchange_run_would_have_carried_the_reason_on_eleven_subjects() -> None:
    """The committed summary's `packet_sole_evidence` flag is the derivation's predicate.

    The summary carries object and claim identifiers with a per-row flag stating whether every
    cited passage belonged to the packet (`src-002`). That flag is exactly what
    `report_derived_subjects` computes when the packet is registered as `report` kind, so the
    set it marks is the set the reason would have marked. The summary does not carry evidence
    identifiers per subject, so the derivation itself cannot be re-run against it; this pins its
    output, and the tests above pin the function on a rebuilt input.
    """
    summary = json.loads(DOCTORED_SUMMARY.read_text(encoding="utf-8"))
    assert summary["label"] == "doctored"
    assert summary["packet_source_id"] == "src-002"

    packet_sole_objects = {
        row["id"]
        for group in summary["objects"].values()
        for row in group["rows"]
        if row["packet_sole_evidence"]
    }
    packet_sole_claims = {
        row["id"]
        for group in summary["claims"].values()
        for row in group["rows"]
        if row["packet_sole_evidence"]
    }
    assert packet_sole_objects == {"cmp-009", "ast-005", "df-005", "tb-004"}, (
        "the component, asset, data flow, and trust boundary built from fabricated record B.7"
    )
    assert len(packet_sole_claims) == 7
    assert {"ctx-030", "ctx-031", "ctx-032"} <= packet_sole_claims, (
        "the three fabrications' claims are among the packet-sole documented claims"
    )
    # Every packet-sole subject is a subject the reason would mark; no subject citing a design
    # document beside the packet is.
    mixed = {
        row["id"]
        for group in list(summary["objects"].values()) + list(summary["claims"].values())
        for row in group["rows"]
        if row["cites_packet"] and not row["packet_sole_evidence"]
    }
    assert mixed.isdisjoint(packet_sole_objects | packet_sole_claims)
    assert mixed, "the summary also records subjects the packet corroborated, which stay unflagged"
