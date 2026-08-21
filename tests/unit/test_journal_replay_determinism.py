"""A journaled run replays end-to-end on a fresh root, every entry consumed (DEC-142, #639).

The #332 comparison attempt measured the defect this file pins: a re-drive served its extraction
entry, then missed on `call_sha256` at the first post-checkpoint call, because the threat package
rendered `approved_at` — a wall clock re-minted by every fresh application of the same checkpoint
decisions. DEC-142 removes the field and states the rule: no model-facing package renders a wall
clock. The proof here is the whole promise, not the one field: run A journals a full fourteen-phase
offline assessment; run B rebuilds the same assessment on a fresh root, approves the same
checkpoints at a genuinely different time, and replays run A's journal to completion with the
fallback model empty — so a single diverging byte in any composed request fails the run loudly
(`ResponsesExhaustedError`) instead of silently spending.

The fixtures are `test_driver.py`'s known-good minimal assessment, kept self-contained the way the
unit tree keeps every file.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import Assessment, default_configuration
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    ReviewDisposition,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import Recommendation, SubjectType
from trace_ai.domain.finding import Finding
from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.domain.proposals.critical_review import CriticalReviewProposal
from trace_ai.domain.proposals.evidence_validation import EvidenceValidationProposal
from trace_ai.domain.proposals.mapping import MappingProposal
from trace_ai.domain.proposals.report_sections import LimitationEntry, ReportSections
from trace_ai.domain.proposals.threat_analysis import ThreatAnalysisProposal
from trace_ai.domain.source_document import TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.fake import DeterministicModel
from trace_ai.infrastructure.model.journal import (
    JournalingModel,
    JournalReplayModel,
    read_journal_entry,
    spent_marker,
)
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.driver import resume_assessment, run_assessment
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.report.input_assembly import assemble_report_input
from trace_ai.workflow.context_review import (
    approve_context,
    build_context_review_package,
    current_system_context,
    decide_object,
)
from trace_ai.workflow.context_validation import validate_context
from trace_ai.workflow.finding_review import approve_finding, change_severity
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from trace_ai.infrastructure.model.journal import JournalEntry
    from trace_ai.infrastructure.model.seam import StructuredModel
    from trace_ai.services.assessment import AssessmentHandle

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"
PROFILE = resolve_profile("offline-fake")
REVIEWER = "reviewer"

EXTRACTION: dict[str, Any] = {
    "system": {
        "system_name": "ForgeFlow",
        "system_purpose": "AI-assisted pull-request review",
    },
    "components": [
        {
            "key": "webhook",
            "name": "Webhook Receiver",
            "component_type": "service",
            "internet_accessible": True,
            "evidence_ids": ["evd-001"],
        },
        {
            "key": "worker",
            "name": "Analysis Worker",
            "component_type": "background_worker",
            "evidence_ids": ["evd-002"],
        },
    ],
    "actors": [
        {
            "key": "user",
            "name": "Customer User",
            "actor_type": "end_user",
            "evidence_ids": ["evd-001"],
        }
    ],
    "assets": [
        {
            "key": "source",
            "name": "Customer Source Code",
            "asset_type": "source_code",
            "component_keys": ["worker"],
            "evidence_ids": ["evd-002"],
        }
    ],
    "data_flows": [
        {
            "key": "enqueue",
            "name": "Analysis job enqueue",
            "source_component_key": "webhook",
            "destination_component_key": "worker",
            "direction": "one_way",
            "evidence_ids": ["evd-001"],
        }
    ],
    "trust_boundaries": [
        {
            "key": "public",
            "name": "Public internet boundary",
            "boundary_type": "internet_to_application",
            "inside_component_keys": ["webhook"],
            "evidence_ids": ["evd-001"],
        }
    ],
    "claims": [
        {
            "key": "validation",
            "subject_type": "component",
            "subject_key": "webhook",
            "predicate": "request_validation",
            "value": "documented as validated",
            "status": "documented",
            "confidence": "high",
            "evidence_ids": ["evd-001"],
        }
    ],
}

THREAT: dict[str, Any] = {
    "title": "Forged repository webhooks trigger unauthorized analysis jobs",
    "description": (
        "An attacker who can submit unsigned or incorrectly validated webhook requests may "
        "trigger analysis jobs for repositories they do not control."
    ),
    "methodology": "stride-scenario-based",
    "category": ["spoofing"],
    "affected_component_ids": ["cmp-001"],
    "affected_asset_ids": ["ast-001"],
    "preconditions": ["signature validation is absent or bypassable"],
    "attack_path": ["forge a delivery", "submit it to the receiver"],
    "impact": "Unauthorized jobs and denial of service",
    "confidence": ConfidenceLevel.MEDIUM,
    "evidence_ids": ["evd-001"],
}

MAPPING: dict[str, Any] = {
    "threat_id": "thr-001",
    "requirement_id": "req-WEBHOOK-001",
    "applicability_status": "applicable",
    "applicability_reason": (
        "The system exposes an endpoint accepting events from an external platform, which is "
        "this requirement's first applicable condition, and the threat is about forged events."
    ),
    "satisfaction_status": "unmet",
    "evidence_ids": ["evd-001"],
    "assumptions": [
        "The documentation states requests are validated without naming a mechanism, which is "
        "the requirement's first common false positive; it does not apply here because the "
        "threat concerns signature verification specifically and none is documented."
    ],
    "confidence": ConfidenceLevel.MEDIUM,
}

ASSESSMENT: dict[str, Any] = {
    "subject_type": SubjectType.CONTROL_MAPPING,
    "subject_id": "map-001",
    "evidence_ids": ["evd-001"],
    "evidence_strengths": {"evd-001": EvidenceStrength.DIRECT},
    "validation_status": ValidationStatus.SUPPORTED,
    "rationale": (
        "The documents describe structural validation only, and the cited passage states no "
        "signature verification for incoming deliveries."
    ),
    "confidence": ConfidenceLevel.MEDIUM,
    "recommendation": Recommendation.CONTINUE,
}

CLAIM_ASSESSMENT: dict[str, Any] = {
    "subject_type": SubjectType.CONTEXT_CLAIM,
    "subject_id": "ctx-001",
    "evidence_ids": ["evd-001"],
    "evidence_strengths": {"evd-001": EvidenceStrength.DIRECT},
    "validation_status": ValidationStatus.SUPPORTED,
    "rationale": "The cited passage states the receiver validates request structure.",
    "confidence": ConfidenceLevel.MEDIUM,
    "recommendation": Recommendation.CONTINUE,
}

THREAT_ASSESSMENT: dict[str, Any] = {
    "subject_type": SubjectType.THREAT,
    "subject_id": "thr-001",
    "evidence_ids": ["evd-001"],
    "evidence_strengths": {"evd-001": EvidenceStrength.INDIRECT},
    "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
    "rationale": (
        "The passage establishes the exposed receiver; the forgery precondition rests on the "
        "absence of any documented signature verification."
    ),
    "confidence": ConfidenceLevel.MEDIUM,
    "recommendation": Recommendation.CONTINUE,
}


def _extraction_model() -> DeterministicModel:
    return DeterministicModel([ContextExtractionProposal.model_validate(EXTRACTION)])


def _reasoning_model() -> DeterministicModel:
    return DeterministicModel(
        [
            ThreatAnalysisProposal.model_validate({"threats": [THREAT]}),
            MappingProposal.model_validate({"mappings": [MAPPING]}),
            EvidenceValidationProposal.model_validate(
                {"assessments": [CLAIM_ASSESSMENT, ASSESSMENT, THREAT_ASSESSMENT]}
            ),
            CriticalReviewProposal.model_validate({"critiques": []}),
        ]
    )


def _report_model(handle: AssessmentHandle) -> DeterministicModel:
    assembly = assemble_report_input(
        handle,
        prompt_versions={"generate-report-sections": "generate-report-sections-v1"},
        model=PROFILE.model,
        model_configuration=PROFILE.name,
    )
    sections = ReportSections.model_validate(
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
    return DeterministicModel([sections])


def _prepare(root: Path) -> str:
    """A fresh assessment root with the one ForgeFlow document registered, not yet indexed."""
    with AssessmentStore.at_root(root) as store:
        service = AssessmentService(store, artifact_root=root)
        created = service.create(
            "ForgeFlow", default_configuration("offline-fake", "stride-scenario-based")
        )
        DocumentLoader(service.handle(created.id)).load_document(
            FORGEFLOW / "architecture-overview.md",
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )
    return created.id


def _approve_checkpoint_one(handle: AssessmentHandle) -> None:
    from trace_ai.services.context.pipeline import context_objects

    for obj in context_objects(handle):
        decide_object(handle, obj, ReviewDisposition.APPROVE, reviewer_id=REVIEWER)
    validation = validate_context(
        current_system_context(handle),
        context_objects(handle),
        available_evidence={ref.id for ref in handle.objects.list(EvidenceReference)},
    )
    package = build_context_review_package(
        handle, index=EvidenceIndex(handle), validation=validation
    )
    approve_context(handle, package, reviewer_id=REVIEWER)


def _approve_checkpoint_two(handle: AssessmentHandle) -> None:
    (finding,) = [
        f
        for f in handle.objects.list(Finding)
        if f.duplicate_of_id is None and f.status is ObjectStatus.CANDIDATE
    ]
    finding, _ = change_severity(handle, finding, Severity.MEDIUM, reviewer_id=REVIEWER)
    approve_finding(handle, finding, reviewer_id=REVIEWER)


def _unspent_entries(journal: Path) -> list[JournalEntry]:
    """The CLI's directory rule, locally: unspent numbered entries, in order."""
    return [
        read_journal_entry(candidate)
        for candidate in sorted(journal.glob("[0-9]*.json"))
        if not spent_marker(candidate).exists()
    ]


def _drive(root: Path, assessment_id: str, models: list[StructuredModel]) -> None:
    """One full assessment: run to checkpoint 1, approve, resume twice, assert completion."""
    extraction, reasoning, report = models
    with AssessmentStore.at_root(root) as store:
        service = AssessmentService(store, artifact_root=root)
        outcome = run_assessment(service, assessment_id, model=extraction, profile=PROFILE)
        assert outcome.paused
        assert outcome.state.current_phase is Phase.HUMAN_CONTEXT_REVIEW

    with AssessmentStore.at_root(root) as store:
        service = AssessmentService(store, artifact_root=root)
        _approve_checkpoint_one(service.handle(assessment_id))
        outcome = resume_assessment(service, assessment_id, model=reasoning, profile=PROFILE)
        assert outcome.paused
        assert outcome.state.current_phase is Phase.HUMAN_FINDING_REVIEW

    with AssessmentStore.at_root(root) as store:
        service = AssessmentService(store, artifact_root=root)
        _approve_checkpoint_two(service.handle(assessment_id))
        outcome = resume_assessment(service, assessment_id, model=report, profile=PROFILE)
        assert outcome.completed


@pytest.fixture
def journaled_run(tmp_path: Path) -> Iterator[Path]:
    """Run A: the full offline assessment, every consumed response journaled."""
    root_a = tmp_path / "run-a"
    root_a.mkdir()
    journal = tmp_path / "journal"
    assessment_id = _prepare(root_a)

    with AssessmentStore.at_root(root_a) as store:
        service = AssessmentService(store, artifact_root=root_a)
        outcome = run_assessment(
            service,
            assessment_id,
            model=JournalingModel(_extraction_model(), journal),
            profile=PROFILE,
        )
        assert outcome.paused
    with AssessmentStore.at_root(root_a) as store:
        service = AssessmentService(store, artifact_root=root_a)
        _approve_checkpoint_one(service.handle(assessment_id))
        outcome = resume_assessment(
            service,
            assessment_id,
            model=JournalingModel(_reasoning_model(), journal),
            profile=PROFILE,
        )
        assert outcome.paused
    with AssessmentStore.at_root(root_a) as store:
        service = AssessmentService(store, artifact_root=root_a)
        handle = service.handle(assessment_id)
        _approve_checkpoint_two(handle)
        outcome = resume_assessment(
            service,
            assessment_id,
            model=JournalingModel(_report_model(handle), journal),
            profile=PROFILE,
        )
        assert outcome.completed

    assert len(list(journal.glob("[0-9]*.json"))) == 6, "one entry per consumed response"
    yield journal


def test_a_journaled_run_replays_end_to_end_on_a_fresh_root(
    journaled_run: Path, tmp_path: Path
) -> None:
    """Run B: same document, same decisions, a later wall clock — every entry serves.

    The fallback model is empty, so a single diverging byte in any composed request fails the
    run with `ResponsesExhaustedError` instead of quietly going live. Before DEC-142 removed
    `approved_at` from the threat package this failed at the first post-checkpoint call —
    the #639 signature, reproduced offline.
    """
    journal = journaled_run
    root_b = tmp_path / "run-b"
    root_b.mkdir()
    assessment_id = _prepare(root_b)

    _drive(
        root_b,
        assessment_id,
        models=[
            JournalReplayModel(_unspent_entries(journal), DeterministicModel([])),
            JournalReplayModel(_unspent_entries(journal), DeterministicModel([])),
            JournalReplayModel(_unspent_entries(journal), DeterministicModel([])),
        ],
    )

    remaining = _unspent_entries(journal)
    assert remaining == [], (
        "every journal entry must be consumed; an unspent entry means a composed request "
        f"diverged and the replay fell through: {[e.path.name for e in remaining]}"
    )

    with AssessmentStore.at_root(root_b) as store:
        service = AssessmentService(store, artifact_root=root_b)
        handle = service.handle(assessment_id)
        assessment = handle.objects.get(Assessment, assessment_id)
        assert assessment.final_report_path is not None


def test_a_carried_journal_replays_a_third_generation_end_to_end(
    journaled_run: Path, tmp_path: Path
) -> None:
    """Run B carries what it replays; run C replays run B's journal (DEC-144, #645).

    The #332 attempt could not do this: run B spent run A's entries and recorded nothing of
    its own, so run C found the prefix spent, the remainder positioned against a consumption
    order that no longer existed, and bought the whole assessment again. Run C's fallback is
    empty here, so every one of its fourteen phases must be answered by what run B carried.
    """
    generation_one = journaled_run
    generation_two = tmp_path / "journal-b"

    root_b = tmp_path / "run-b"
    root_b.mkdir()
    assessment_b = _prepare(root_b)
    _drive(
        root_b,
        assessment_b,
        models=[
            JournalReplayModel(
                _unspent_entries(generation_one),
                DeterministicModel([]),
                carry_forward=generation_two,
            )
            for _ in range(3)
        ],
    )
    assert _unspent_entries(generation_one) == [], "run B replayed run A's journal entire"
    carried = _unspent_entries(generation_two)
    assert len(carried) == 6, "run B's own journal holds every call it consumed"
    assert all(
        json.loads(entry.path.read_text(encoding="utf-8"))["replayed_from"] for entry in carried
    ), "each carried entry names the entry it came from"

    root_c = tmp_path / "run-c"
    root_c.mkdir()
    assessment_c = _prepare(root_c)
    _drive(
        root_c,
        assessment_c,
        models=[
            JournalReplayModel(_unspent_entries(generation_two), DeterministicModel([]))
            for _ in range(3)
        ],
    )

    assert _unspent_entries(generation_two) == [], (
        "run C must consume run B's journal entire; anything left unspent means the carried "
        "copy did not answer the call it recorded"
    )
