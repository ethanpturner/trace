"""The HTML report's lineage appendix: the nine-hop walk, portable (#600).

Three properties carry the file. Every approved finding in the replayed corpus report resolves
all nine hops — the conformance the issue names. Hostile text in any hop renders as text, never
markup — the DEC-108 escaping discipline extended to the appendix. And the render stays
byte-deterministic, appendix included, because the walk is state, not time.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    ReviewDisposition,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.finding import Finding
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.domain.source_document import (
    IngestionStatus,
    MediaType,
    SourceDocument,
    TrustLevel,
)
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.evidence.index import VerificationOutcome, VerificationResult
from trace_ai.services.findings.lineage import finding_lineage
from trace_ai.services.report.html import render_report_html
from trace_ai.services.report.lineage_html import (
    UNTRUSTED_LABEL,
    finding_walk_html,
    lineage_appendix,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

HOP_LABELS = [
    "Source documents",
    "Evidence, quoted and checked",
    "Context claims",
    "Threats",
    "Requirements and their mappings",
    "Controls",
    "Evidence assessments",
    "Critiques",
    "Reviewer decisions",
    "Finding",
]

HOSTILE = '<script>alert("owned")</script>'


def _replay(data_root: Path) -> None:
    path = PROJECT_ROOT / "scripts" / "replay_forgeflow.py"
    spec = importlib.util.spec_from_file_location("replay_forgeflow_lineage_html", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["replay_forgeflow_lineage_html"] = module
    spec.loader.exec_module(module)
    module.replay(data_root)


@pytest.fixture(scope="module")
def replayed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    root = tmp_path_factory.mktemp("lineage-html")
    _replay(root)
    yield root


def test_every_approved_finding_in_the_replayed_corpus_resolves_all_nine_hops(
    replayed: Path,
) -> None:
    with AssessmentStore.at_root(replayed) as store:
        service = AssessmentService(store, artifact_root=replayed)
        handle = service.handle("asm-001")
        from trace_ai.services.findings.approved import approved_findings

        findings = approved_findings(handle)
        assert findings, "the replayed corpus report carries approved findings"

        first = lineage_appendix(handle)
        second = lineage_appendix(handle)
        assert first == second, "the walk is state, not time"

        assert first.count("<details") == len(findings)
        for finding in findings:
            assert finding.id in first
        for label in HOP_LABELS:
            assert first.count(f"<h4>{label}</h4>") == len(findings), label
        assert "verifies" in first, "the evidence leaf shows the verification verdict"
        assert UNTRUSTED_LABEL in first

        page = render_report_html("# Report", title="T", appendix=first)
        assert "lineage-appendix" in page
        assert page.index("lineage-appendix") > page.index("Report")


def test_the_appendix_parameter_defaults_to_the_unchanged_page() -> None:
    bare = render_report_html("# Report", title="T")
    empty = render_report_html("# Report", title="T", appendix="")
    assert bare == empty
    assert "lineage-appendix" not in bare


def test_hostile_content_in_any_hop_renders_as_text_never_markup() -> None:
    stamped = now()
    document = SourceDocument.model_validate(
        {
            "id": "src-001",
            "assessment_id": "asm-001",
            "filename": "notes.md",
            "media_type": MediaType.MARKDOWN,
            "origin": SourceOrigin.UPLOADED_DOCUMENT,
            "content_hash": content_hash(HOSTILE.encode()),
            "created_at": stamped,
            "ingestion_status": IngestionStatus.REGISTERED,
            "trust_level": TrustLevel.UNTRUSTED,
        }
    )
    reference = EvidenceReference.model_validate(
        {
            "id": "evd-001",
            "assessment_id": "asm-001",
            "source_document_id": "src-001",
            "start_line": 1,
            "end_line": 1,
            "quoted_text": HOSTILE,
            "content_hash": content_hash(HOSTILE.encode()),
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "created_at": stamped,
        }
    )
    claim = ContextClaim.model_validate(
        {
            "id": "ctx-001",
            "assessment_id": "asm-001",
            "subject_type": "component",
            "subject_id": "cmp-001",
            "predicate": "purpose",
            "value": HOSTILE,
            "status": ClaimStatus.DOCUMENTED,
            "confidence": ConfidenceLevel.HIGH,
            "evidence_ids": ["evd-001"],
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "generated_by": "context-extraction-v1",
            "created_at": stamped,
            "updated_at": stamped,
        }
    )
    threat = Threat.model_validate(
        {
            "id": "thr-001",
            "assessment_id": "asm-001",
            "title": HOSTILE,
            "description": "d",
            "methodology": "stride-scenario-based",
            "affected_component_ids": ["cmp-001"],
            "affected_asset_ids": ["ast-001"],
            "impact": "i",
            "confidence": ConfidenceLevel.MEDIUM,
            "evidence_ids": ["evd-001"],
            "assumption_ids": ["ctx-001"],
            "status": ObjectStatus.APPROVED,
            "generated_by": "threat-analysis-v1",
            "created_at": stamped,
        }
    )
    mapping = ControlMapping.model_validate(
        {
            "id": "map-001",
            "assessment_id": "asm-001",
            "threat_id": "thr-001",
            "requirement_id": "req-WEBHOOK-001",
            "applicability_status": ApplicabilityStatus.APPLICABLE,
            "applicability_reason": "r",
            "satisfaction_status": SatisfactionStatus.UNMET,
            "evidence_ids": ["evd-001"],
            "confidence": ConfidenceLevel.MEDIUM,
            "generated_by": "mapping-v1",
            "reviewer_status": ObjectStatus.CANDIDATE,
        }
    )
    finding = Finding.model_validate(
        {
            "id": "fnd-001",
            "assessment_id": "asm-001",
            "title": HOSTILE,
            "summary": "s",
            "description": "d",
            "threat_ids": ["thr-001"],
            "requirement_ids": ["req-WEBHOOK-001"],
            "control_mapping_ids": ["map-001"],
            "affected_component_ids": ["cmp-001"],
            "affected_asset_ids": ["ast-001"],
            "evidence_ids": ["evd-001"],
            "validation_status": ValidationStatus.SUPPORTED,
            "severity": Severity.MEDIUM,
            "impact": "i",
            "recommendation": "r",
            "confidence": ConfidenceLevel.MEDIUM,
            "status": ObjectStatus.APPROVED,
            "generated_by": "finding-consolidation-v1",
            "created_at": stamped,
            "updated_at": stamped,
        }
    )
    decision = ReviewerDecision.model_validate(
        {
            "id": "dec-001",
            "assessment_id": "asm-001",
            "subject_type": "finding",
            "subject_id": "fnd-001",
            "disposition": ReviewDisposition.APPROVE,
            "rationale": HOSTILE,
            "created_at": stamped,
        }
    )
    lineage = finding_lineage(
        finding,
        threats=[threat],
        control_mappings=[mapping],
        context_claims=[claim],
        evidence_references=[reference],
        source_documents=[document],
    )

    def verify(evidence_id: str) -> VerificationResult:
        return VerificationResult(evidence_id, VerificationOutcome.MATCHES)

    walk = finding_walk_html(
        finding, lineage, controls_by_id={}, decisions=[decision], verify=verify
    )
    assert HOSTILE not in walk, "raw hostile markup must never survive"
    assert walk.count("&lt;script&gt;") >= 4, "title, claim, quote, and rationale all escape"
    assert "verifies" in walk


def test_the_untrusted_label_matches_the_live_view() -> None:
    from trace_ai.interface import render as live_view

    assert live_view.UNTRUSTED_LABEL == UNTRUSTED_LABEL


def _drifted(evidence_id: str) -> VerificationResult:
    return VerificationResult(evidence_id, VerificationOutcome.CONTENT_CHANGED)


def test_a_drifted_excerpt_says_so_at_the_leaf() -> None:
    stamped = now()
    passage = "The receiver accepts any well-formed delivery."
    document = SourceDocument.model_validate(
        {
            "id": "src-001",
            "assessment_id": "asm-001",
            "filename": "overview.md",
            "media_type": MediaType.MARKDOWN,
            "origin": SourceOrigin.UPLOADED_DOCUMENT,
            "content_hash": content_hash(passage.encode()),
            "created_at": stamped,
            "ingestion_status": IngestionStatus.REGISTERED,
            "trust_level": TrustLevel.UNTRUSTED,
        }
    )
    reference = EvidenceReference.model_validate(
        {
            "id": "evd-001",
            "assessment_id": "asm-001",
            "source_document_id": "src-001",
            "start_line": 1,
            "end_line": 1,
            "quoted_text": passage,
            "content_hash": content_hash(passage.encode()),
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "created_at": stamped,
        }
    )
    threat = Threat.model_validate(
        {
            "id": "thr-001",
            "assessment_id": "asm-001",
            "title": "t",
            "description": "d",
            "methodology": "stride-scenario-based",
            "affected_component_ids": ["cmp-001"],
            "affected_asset_ids": ["ast-001"],
            "impact": "i",
            "confidence": ConfidenceLevel.MEDIUM,
            "evidence_ids": ["evd-001"],
            "assumption_ids": [],
            "status": ObjectStatus.APPROVED,
            "generated_by": "threat-analysis-v1",
            "created_at": stamped,
        }
    )
    mapping = ControlMapping.model_validate(
        {
            "id": "map-001",
            "assessment_id": "asm-001",
            "threat_id": "thr-001",
            "requirement_id": "req-WEBHOOK-001",
            "applicability_status": ApplicabilityStatus.APPLICABLE,
            "applicability_reason": "r",
            "satisfaction_status": SatisfactionStatus.UNMET,
            "evidence_ids": ["evd-001"],
            "confidence": ConfidenceLevel.MEDIUM,
            "generated_by": "mapping-v1",
            "reviewer_status": ObjectStatus.CANDIDATE,
        }
    )
    finding = Finding.model_validate(
        {
            "id": "fnd-001",
            "assessment_id": "asm-001",
            "title": "t",
            "summary": "s",
            "description": "d",
            "threat_ids": ["thr-001"],
            "requirement_ids": ["req-WEBHOOK-001"],
            "control_mapping_ids": ["map-001"],
            "affected_component_ids": ["cmp-001"],
            "affected_asset_ids": ["ast-001"],
            "evidence_ids": ["evd-001"],
            "validation_status": ValidationStatus.SUPPORTED,
            "severity": Severity.MEDIUM,
            "impact": "i",
            "recommendation": "r",
            "confidence": ConfidenceLevel.MEDIUM,
            "status": ObjectStatus.APPROVED,
            "generated_by": "finding-consolidation-v1",
            "created_at": stamped,
            "updated_at": stamped,
        }
    )
    lineage = finding_lineage(
        finding,
        threats=[threat],
        control_mappings=[mapping],
        evidence_references=[reference],
        source_documents=[document],
    )
    walk = finding_walk_html(finding, lineage, controls_by_id={}, decisions=[], verify=_drifted)
    assert "content_changed" in walk
    assert "verifies</strong>" not in walk
