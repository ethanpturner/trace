"""The pipeline driver: all fourteen phases, two pauses, one process exit per pause (#260).

The end-to-end test here is the acceptance criterion made executable: a full assessment runs
offline from creation to a rendered report, pausing at both checkpoints, with every stage between
pauses opened against a fresh store the way a new process would open it (DEC-017: resuming is a
read). Every model response is queued on the deterministic fake, so the test spends nothing and
proves the recorded-response path the CLI exposes.
"""

from __future__ import annotations

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
from trace_ai.domain.evidence_assessment import Recommendation, SubjectType
from trace_ai.domain.execution import ExecutionType, RunStatus, WorkflowRun
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
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.driver import build_nodes, resume_assessment, run_assessment
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.report.input_assembly import assemble_report_input
from trace_ai.workflow.context_review import (
    approve_context,
    build_context_review_package,
    decide_object,
)
from trace_ai.workflow.finding_review import (
    approve_finding,
    change_severity,
    conclude_finding_review,
)
from trace_ai.workflow.limits import Budget, LimitKind
from trace_ai.workflow.orchestrator import PhaseProgress
from trace_ai.workflow.phases import NODES_BY_PHASE, Phase

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from types import TracebackType

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

# The batched evidence shape (DEC-134) assesses every supplied subject, so the fixture covers
# the claim and the threat beside the mapping — three subjects, one batch, full coverage.
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


def _sections(handle: AssessmentHandle) -> ReportSections:
    assembly = assemble_report_input(
        handle,
        prompt_versions={"generate-report-sections": "generate-report-sections-v1"},
        model=PROFILE.model,
        model_configuration=PROFILE.name,
    )
    return ReportSections.model_validate(
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


def _report_model(handle: AssessmentHandle) -> DeterministicModel:
    return DeterministicModel([_sections(handle)])


class _Stage:
    """One process's view of the assessment: a fresh store, service, and handle."""

    def __init__(self, root: Path, assessment_id: str) -> None:
        self.root = root
        self.assessment_id = assessment_id

    def __enter__(self) -> _Stage:
        self._store = AssessmentStore.at_root(self.root)
        store = self._store.__enter__()
        self.service = AssessmentService(store, artifact_root=self.root)
        self.handle = self.service.handle(self.assessment_id)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._store.__exit__(exc_type, exc_value, traceback)


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    """An assessment with one ForgeFlow document registered and deliberately not yet indexed.

    Not indexed, because the driver's evidence-indexing node owns that step and the test wants to
    see it happen under the orchestrator rather than at registration time.
    """
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        DocumentLoader(handle).load_document(
            FORGEFLOW / "architecture-overview.md",
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )
    yield tmp_path, created.id


def _approve_checkpoint_one(handle: AssessmentHandle) -> None:
    from trace_ai.domain.evidence import EvidenceReference
    from trace_ai.services.context.pipeline import context_objects
    from trace_ai.workflow.context_review import current_system_context
    from trace_ai.workflow.context_validation import validate_context

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


def test_a_full_assessment_runs_offline_pausing_at_both_checkpoints(
    prepared: tuple[Path, str],
) -> None:
    root, assessment_id = prepared

    # Process 1: run until checkpoint 1.
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        outcome = run_assessment(
            stage.service, assessment_id, model=_extraction_model(), profile=PROFILE
        )
        assert outcome.paused
        assert outcome.state.current_phase is Phase.HUMAN_CONTEXT_REVIEW
        run_id = outcome.state.workflow_run_id
        run = handle.objects.get(WorkflowRun, run_id)
        assert run.status is RunStatus.PAUSED
        state_file = handle.artifacts.area("traces") / f"state-{run_id}.json"
        assert state_file.exists(), "DEC-017: a pause without a state file cannot be resumed"

    # Process 2: the reviewer decides, then the run resumes to checkpoint 2.
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        _approve_checkpoint_one(handle)
        outcome = resume_assessment(
            stage.service, assessment_id, model=_reasoning_model(), profile=PROFILE
        )
        assert outcome.paused
        assert outcome.state.current_phase is Phase.HUMAN_FINDING_REVIEW
        assert outcome.state.candidate_finding_ids == ["fnd-001"]
        assert outcome.state.pending_human_review is not None
        assert outcome.state.pending_human_review.object_ids == ["fnd-001"]

    # Process 3: severity assigned, finding approved, run resumes to completion.
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        _approve_checkpoint_two(handle)
        outcome = resume_assessment(
            stage.service, assessment_id, model=_report_model(handle), profile=PROFILE
        )
        assert outcome.completed
        assert outcome.state.current_phase is Phase.ASSESSMENT_COMPLETION
        assert outcome.state.pending_human_review is None

        run = handle.objects.get(WorkflowRun, run_id)
        assert run.status is RunStatus.COMPLETED

        assessment = handle.objects.get(Assessment, assessment_id)
        assert assessment.final_report_path is not None
        report = handle.artifacts.assessment_root / assessment.final_report_path
        assert report.exists()
        manifest = handle.artifacts.area("outputs") / f"report-{run_id}.manifest.json"
        assert manifest.exists()
        metrics = handle.artifacts.area("evaluation") / f"metrics-{run_id}.json"
        assert metrics.exists()

        # The whole chain verifies — and a tampered report is caught by its manifest pin.
        from trace_ai.services.verification import verify_assessment

        verification = verify_assessment(handle)
        assert verification.ok
        assert verification.manifest_checked

        report.write_text(report.read_text(encoding="utf-8") + "\ntampered", encoding="utf-8")
        drifted = verify_assessment(handle)
        assert not drifted.ok
        assert any(d.subject == "report.content_hash" for d in drifted.manifest_drift)


def test_the_assessment_lifecycle_moves_with_the_run(prepared: tuple[Path, str]) -> None:
    """DEC-031: `pending_review` while a person is deciding, `draft` while the run works.

    The move to `pending_review` commits with the pause; resuming returns the assessment to
    `draft` before the run continues, and a re-pause moves it straight back.
    """
    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        run_assessment(stage.service, assessment_id, model=_extraction_model(), profile=PROFILE)
        assessment = stage.handle.objects.get(Assessment, assessment_id)
        assert assessment.status is ObjectStatus.PENDING_REVIEW

    with _Stage(root, assessment_id) as stage:
        _approve_checkpoint_one(stage.handle)
        resume_assessment(stage.service, assessment_id, model=_reasoning_model(), profile=PROFILE)
        assessment = stage.handle.objects.get(Assessment, assessment_id)
        assert assessment.status is ObjectStatus.PENDING_REVIEW, "paused again at checkpoint 2"

    with _Stage(root, assessment_id) as stage:
        _approve_checkpoint_two(stage.handle)
        concluded = conclude_finding_review(stage.service, assessment_id)
        assert concluded.status is ObjectStatus.DRAFT
        outcome = resume_assessment(
            stage.service, assessment_id, model=_report_model(stage.handle), profile=PROFILE
        )
        assert outcome.completed
        assessment = stage.handle.objects.get(Assessment, assessment_id)
        assert assessment.status is ObjectStatus.DRAFT, (
            "approval is a person's verb, not a run's (DEC-082): completion leaves draft, and "
            "the sign-off below is what moves it"
        )
        approved = stage.service.approve(assessment_id)
        assert approved.status is ObjectStatus.APPROVED

    # A revision: re-running an approved assessment returns it to draft (begin_revision) and starts
    # a fresh run that pauses at checkpoint 1, rather than crashing on approved -> pending_review at
    # the pause.
    with _Stage(root, assessment_id) as stage:
        revised = run_assessment(
            stage.service, assessment_id, model=_extraction_model(), profile=PROFILE
        )
        assert revised.paused
        assert (
            stage.handle.objects.get(Assessment, assessment_id).status
            is ObjectStatus.PENDING_REVIEW
        )


def test_re_running_an_abandoned_review_returns_to_draft_and_pauses_again(
    prepared: tuple[Path, str],
) -> None:
    """A run left at checkpoint 1 (a review nobody finished) can be re-run. Before the fix the fresh
    run reached the pause and tried pending_review -> pending_review, which raised deep in the loop
    and left the run row `running`; now `run_assessment` returns the assessment to draft first."""
    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        run_assessment(stage.service, assessment_id, model=_extraction_model(), profile=PROFILE)
        assert (
            stage.handle.objects.get(Assessment, assessment_id).status
            is ObjectStatus.PENDING_REVIEW
        )

    with _Stage(root, assessment_id) as stage:
        outcome = run_assessment(
            stage.service, assessment_id, model=_extraction_model(), profile=PROFILE
        )
        assert outcome.paused
        assert outcome.state.current_phase is Phase.HUMAN_CONTEXT_REVIEW
        assert (
            stage.handle.objects.get(Assessment, assessment_id).status
            is ObjectStatus.PENDING_REVIEW
        )


def test_resuming_a_failed_run_restarts_from_the_failed_phase(prepared: tuple[Path, str]) -> None:
    """A budget of zero model calls fails the run at the first model phase, after the deterministic
    ingestion phases completed. Resuming restarts that run from context extraction -- it does not
    start a new run from initialization and re-mint everything."""
    from trace_ai.domain.evidence import EvidenceReference

    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        outcome = run_assessment(
            stage.service,
            assessment_id,
            model=_extraction_model(),
            profile=PROFILE,
            budget=Budget(maximum_model_calls=0),
        )
        assert outcome.state.status is RunStatus.FAILED
        assert outcome.state.current_phase is Phase.CONTEXT_EXTRACTION
        run_id = outcome.state.workflow_run_id
        run = stage.handle.objects.get(WorkflowRun, run_id)
        assert run.status is RunStatus.FAILED
        # Ingestion happened before the failure and its objects survive the failed run.
        assert stage.handle.objects.list(EvidenceReference)

    with _Stage(root, assessment_id) as stage:
        outcome = resume_assessment(
            stage.service, assessment_id, model=_extraction_model(), profile=PROFILE
        )
        assert outcome.paused
        assert outcome.state.current_phase is Phase.HUMAN_CONTEXT_REVIEW
        assert outcome.state.workflow_run_id == run_id, "a new run was started instead of resuming"
        assert len(stage.handle.objects.list(WorkflowRun)) == 1, "the failed run was not reused"
        run = stage.handle.objects.get(WorkflowRun, run_id)
        assert run.status is RunStatus.PAUSED


def test_stop_before_halts_cleanly_without_the_named_phase(prepared: tuple[Path, str]) -> None:
    """A clean early stop is neither a failure nor a checkpoint pause; the named phase never runs.

    The evaluation harness uses this to measure the finding set without the report. Here it stops
    before context extraction, so the run never calls the model."""
    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        outcome = run_assessment(
            stage.service,
            assessment_id,
            model=DeterministicModel(),
            profile=PROFILE,
            stop_before=Phase.CONTEXT_EXTRACTION,
        )
        assert not outcome.completed
        assert not outcome.paused
        assert outcome.stopped_because == "stopped_before_context_extraction"
        assert outcome.state.status is RunStatus.RUNNING, "a clean stop is not a failure"
        assert outcome.state.current_phase is Phase.DOCUMENT_INGESTION


def test_the_run_records_one_execution_per_node_execution(prepared: tuple[Path, str]) -> None:
    """The agent nodes account for themselves; the orchestrator must not double them.

    `counters()` counts model calls by record, so a wrapper record around a self-recording node
    would report calls that never happened and bill them against the ceiling twice.
    """
    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        outcome = run_assessment(
            stage.service, assessment_id, model=_extraction_model(), profile=PROFILE
        )
        run = handle.objects.get(WorkflowRun, outcome.state.workflow_run_id)
        assert run.total_model_calls == 1

        from trace_ai.domain.execution import ExecutionRecord

        records = [
            record
            for record in handle.objects.list(ExecutionRecord)
            if record.workflow_run_id == run.id
        ]
        extraction_records = [r for r in records if r.node_name == "context-extraction"]
        assert len(extraction_records) == 1
        assert extraction_records[0].execution_type is ExecutionType.MODEL


def test_a_model_call_ceiling_stops_the_run_classified(prepared: tuple[Path, str]) -> None:
    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        outcome = run_assessment(
            stage.service,
            assessment_id,
            model=_extraction_model(),
            profile=PROFILE,
            budget=Budget(maximum_model_calls=0),
        )
        assert outcome.stopped_because == LimitKind.MODEL_CALLS.value
        assert outcome.state.status is RunStatus.FAILED
        run = handle.objects.get(WorkflowRun, outcome.state.workflow_run_id)
        assert run.status is RunStatus.FAILED


def test_a_run_with_no_sources_stops_with_a_classified_error(tmp_path: Path) -> None:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Empty", default_configuration("offline-fake", "stride-scenario-based")
        )
        outcome = run_assessment(service, created.id, model=DeterministicModel(), profile=PROFILE)
        assert outcome.state.status is RunStatus.FAILED
        assert outcome.stopped_because == "missing_required_relationship"
        assert "no source documents" in outcome.state.errors[0]


def test_build_nodes_covers_every_declared_node(prepared: tuple[Path, str]) -> None:
    """Every name in `NODES_BY_PHASE`, no extras, no duplicates — the driver is the table's."""
    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        run = start_run(handle, workflow_version="0.1", model_profile=PROFILE.name)
        nodes = build_nodes(handle, ledger=ExecutionLedger(handle, run), profile=PROFILE)
        built = {(node.phase, node.name) for node in nodes}
        declared = {(phase, name) for phase, names in NODES_BY_PHASE.items() for name in names}
        assert built == declared
        assert len(nodes) == len(built)


def test_every_known_ablation_substitutes_at_least_one_node(prepared: tuple[Path, str]) -> None:
    """DEC-090: an ablation whose node names have drifted out of step substitutes nothing and runs
    the full pipeline while marking the run non-authoritative -- a measurement that lies. Building
    with each known ablation must actually replace a node."""
    from trace_ai.services.driver import KNOWN_ABLATIONS
    from trace_ai.workflow.phases import Phase

    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        run = start_run(handle, workflow_version="0.1", model_profile=PROFILE.name)
        for ablation in sorted(KNOWN_ABLATIONS):
            plain = build_nodes(handle, ledger=ExecutionLedger(handle, run), profile=PROFILE)
            ablated = build_nodes(
                handle, ledger=ExecutionLedger(handle, run), profile=PROFILE, ablations=[ablation]
            )
            assert {(n.phase, n.name) for n in ablated} != {
                (n.phase, n.name) for n in plain
            } or any(n.phase is Phase.HUMAN_CONTEXT_REVIEW for n in ablated), (
                f"{ablation} substituted nothing"
            )


def test_a_stale_ablation_name_raises_rather_than_silently_ablating_nothing() -> None:
    """A known ablation whose removal map no longer matches any node raises, not silently no-ops."""
    from dataclasses import dataclass

    from trace_ai.services.driver import _apply_ablations
    from trace_ai.workflow.phases import Phase

    @dataclass
    class _Stub:
        name: str
        phase: Phase = Phase.THREAT_GENERATION

    # `no-critical-review` removes `critical-review`/`critique-validation`; none is present here.
    with pytest.raises(ValueError, match="substituted no node"):
        _apply_ablations([_Stub("threat-analysis")], ["no-critical-review"])  # type: ignore[list-item]


def test_resuming_with_subjects_still_undecided_pauses_again(
    prepared: tuple[Path, str],
) -> None:
    """DEC-017's partial progress: the checkpoint re-runs, decides nothing, and holds."""
    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        run_assessment(stage.service, assessment_id, model=_extraction_model(), profile=PROFILE)

    with _Stage(root, assessment_id) as stage:
        outcome = resume_assessment(
            stage.service, assessment_id, model=DeterministicModel(), profile=PROFILE
        )
        assert outcome.paused
        assert outcome.state.current_phase is Phase.HUMAN_CONTEXT_REVIEW


def test_a_resumed_run_says_running_on_its_row_while_it_executes(
    prepared: tuple[Path, str],
) -> None:
    """The row a resumed run wears is a running run's, not the pause it resumed from (#641).

    Before DEC-145 the row kept `paused` for the whole resumed run while the state file recorded
    the phases going by, so a process killed anywhere in that stretch left a combination neither
    `trace resume` nor `trace runs repair` would touch. The row is what the run *is*.
    """
    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        run_assessment(stage.service, assessment_id, model=_extraction_model(), profile=PROFILE)

    observed: list[RunStatus] = []
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        _approve_checkpoint_one(handle)
        run_id = handle.objects.list(WorkflowRun)[-1].id

        def observe(_progress: PhaseProgress) -> None:
            observed.append(handle.objects.get(WorkflowRun, run_id).status)

        resume_assessment(
            stage.service,
            assessment_id,
            model=_reasoning_model(),
            profile=PROFILE,
            on_phase=observe,
        )

    assert observed, "the observer saw no phase"
    assert set(observed) == {RunStatus.RUNNING}


def test_a_repaired_strand_resumes_and_finishes_the_run(prepared: tuple[Path, str]) -> None:
    """The whole recovery, end to end: strand, repair, resume (DEC-145, #641).

    The strand is built the way a kill builds one — the row paused, the state file still recording
    the phase the process was running, because a pause commits the row before it writes the file.
    Repair is what makes the run reachable again; the work already persisted is not re-run.
    """
    from trace_ai.services.run_repair import repair_run
    from trace_ai.workflow.checkpoint import load_state, save_state

    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        run_assessment(stage.service, assessment_id, model=_extraction_model(), profile=PROFILE)
        run_id = stage.handle.objects.list(WorkflowRun)[-1].id

    # The kill: the state file never got the pause the row already committed.
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        save_state(handle, load_state(handle, run_id).restarted())
        assert handle.objects.get(WorkflowRun, run_id).status is RunStatus.PAUSED
        with pytest.raises(ValueError, match="not paused; there is nothing to resume"):
            resume_assessment(
                stage.service, assessment_id, model=DeterministicModel(), profile=PROFILE
            )

    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        _approve_checkpoint_one(handle)
        repaired = repair_run(handle, run_id, reason="killed mid-resume")
        assert repaired.status is RunStatus.FAILED

        outcome = resume_assessment(
            stage.service, assessment_id, model=_reasoning_model(), profile=PROFILE
        )
        assert outcome.paused, "the repaired run resumed and reached the next checkpoint"
        assert outcome.state.current_phase is Phase.HUMAN_FINDING_REVIEW
        assert outcome.state.workflow_run_id == run_id


def test_resuming_without_a_paused_run_is_refused(prepared: tuple[Path, str]) -> None:
    root, assessment_id = prepared
    with (
        _Stage(root, assessment_id) as stage,
        pytest.raises(ValueError, match="no paused or failed workflow run"),
    ):
        resume_assessment(stage.service, assessment_id, model=DeterministicModel(), profile=PROFILE)


def test_the_resumed_state_is_running_and_carries_no_stale_pause(
    prepared: tuple[Path, str],
) -> None:
    """`paused_for` is cleared the moment the checkpoint completes, not at the next pause."""
    root, assessment_id = prepared
    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        run_assessment(stage.service, assessment_id, model=_extraction_model(), profile=PROFILE)

    with _Stage(root, assessment_id) as stage:
        handle = stage.handle
        _approve_checkpoint_one(handle)
        outcome = resume_assessment(
            stage.service, assessment_id, model=_reasoning_model(), profile=PROFILE
        )
        # Paused again at checkpoint 2 — but for checkpoint 2's subjects, not checkpoint 1's.
        assert outcome.state.pending_human_review is not None
        assert outcome.state.pending_human_review.checkpoint_type is Phase.HUMAN_FINDING_REVIEW
