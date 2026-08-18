"""Capture a registered scenario's recording from a live model run (#482, DEC-091).

The three stages mirror `scripts/replay_forgeflow.py` exactly — the same service calls, the same
decision writers, the same pinned report timestamp — because the point of a capture is that the
replayer can consume it without changing. What differs is the model: every call goes to the live
provider through the seam, and a wrapper records each response the run consumed, in consumption
order, shaped exactly as `load_recorded_responses` reads them back.

Everything lands in a staging directory (`<scenario>/capture/`) rather than in `recorded/`, so a
partial capture cannot half-replace the committed recording. Promotion into `recorded/` is a
deliberate copy after the replay round-trip is verified.

Checkpoint decisions are authored per capture, in the staging directory, from the files each
stage exports. A scenario's committed `recorded/decisions-*.yaml` answer the *replay* of the
recording they were authored against; a fresh live run allocates identifiers against its own
objects, so applying a previous capture's decisions blind would decide objects nobody reviewed.
The committed files are a starting point for authoring, never an input to a live run (DEC-091).

The capture spends real money and each stage refuses to run twice: re-running a stage would
re-spend it. The refusal is an answer, not a fault — the CLI renders it as exit code 3 (DEC-088).

A rehearsal (#534) is the same three stages with the money removed: the caller supplies a
deterministic model serving authored responses, staging goes to `capture-rehearsal/` beside the
real staging directory, and every envelope written carries a `rehearsal` marker that
`load_recorded_responses` refuses everywhere except inside a rehearsal's own resume. DEC-091
traded away offline rehearsal to keep a zero-usage capture out of staging; the marker keeps that
guarantee — a rehearsal artifact cannot be promoted, because every reader of a promoted
recording refuses it — while giving a new scenario's capture flow a free dry run before the
first dollar.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import Assessment, default_configuration
from trace_ai.domain.enums import Severity, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import WorkflowRun
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import Question
from trace_ai.domain.source_document import TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.recorded import load_recorded_responses
from trace_ai.infrastructure.model.seam import (
    GenerationSettings,
    ModelCapability,
    ModelOutcome,
    ModelSuccess,
    ModelUsage,
    StructuredModel,
)
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.context.pipeline import context_objects
from trace_ai.services.context.review_file import (
    apply_review_file,
    read_review_file,
    write_review_file,
)
from trace_ai.services.driver import resume_assessment, run_assessment
from trace_ai.services.evaluation.stamps import DETERMINISTIC_STAMP
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.workflow.context_review import (
    approve_context,
    build_context_review_package,
    current_system_context,
    previous_approved_context,
)
from trace_ai.workflow.context_validation import validate_context
from trace_ai.workflow.finding_review import (
    approve_finding,
    change_severity,
    conclude_finding_review,
    reject_finding,
)
from trace_ai.workflow.limits import Budget

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel

    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.infrastructure.model.recorded import RecordedResponse
    from trace_ai.services.evaluation.registry import Scenario

__all__ = [
    "REHEARSAL_MARKER",
    "CaptureError",
    "CaptureRefusedError",
    "RecordingModel",
    "capture_data_root",
    "capture_dir",
    "stage_baseline",
    "stage_extract",
    "stage_reason",
    "stage_report",
]

REVIEWER = "recorded-reviewer"

# The capture's generation timestamp, pinned so the replay is byte-identical. The replayer must
# carry the same value when a capture is promoted.
GENERATED_AT = DETERMINISTIC_STAMP

# A hard stop well above the ~28-call, single-digit-dollar shape of a scenario run: a runaway
# costs one order of magnitude, never an open-ended bill.
BUDGET_CALLS = 60
BUDGET_COST = Decimal("30")
"""The cost ceiling is checked against a projection of max_output_tokens per call, and the
64,000-token ceiling makes that projection ~4x any plausible actual spend -- so the guard sits
well above the estimate to stop a runaway without stopping the run it is guarding."""

_SLUGS = {
    "ContextExtractionProposal": "context-extraction",
    "ThreatAnalysisProposal": "threat-analysis",
    "MappingProposal": "mapping",
    "EvidenceValidationProposal": "evidence-validation",
    "CriticalReviewProposal": "critical-review",
    "ReportSections": "report-sections",
}


class CaptureError(ValueError):
    """A capture input the operator can fix: a missing decisions file, a run that stopped where a
    pause was expected. Rendered by the CLI as a one-line exit-1 error (DEC-088)."""


class CaptureRefusedError(ValueError):
    """A stage that already ran and would re-spend if run again. The refusal is an answer — the
    stage's output exists — so the CLI renders it as exit code 3, not a fault (DEC-088)."""


REHEARSAL_MARKER = "REHEARSAL"
"""The marker file a rehearsal staging directory carries, for the operator's eyes; the
load-bearing guard is the `rehearsal` key each staged envelope carries (#534)."""


def capture_dir(scenario: Scenario, *, rehearsal: bool = False) -> Path:
    """The staging directory a capture writes into, beside the scenario's `recorded/`.

    A rehearsal stages into its own directory: its artifacts are mechanics-validation output from
    the deterministic substitute, and a directory shared with a real capture would put a
    no-model-ever-said-this file one copy away from `recorded/` (#534).
    """
    return scenario.path / ("capture-rehearsal" if rehearsal else "capture")


def capture_data_root(scenario: Scenario, *, rehearsal: bool = False) -> Path:
    """The capture's own data root, apart from the operator's assessments."""
    prefix = "capture-rehearsal" if rehearsal else "capture"
    return PROJECT_ROOT / "data" / f"{prefix}-{scenario.slug}"


def _usage_dict(usage: ModelUsage) -> dict[str, object]:
    """A captured `ModelUsage` as the envelope's `usage` mapping (#461). Decimal cost as a string,
    so it round-trips through JSON without a float's rounding."""
    return {
        "model": usage.model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_creation_tokens": usage.cache_creation_tokens,
        "estimated_cost": str(usage.estimated_cost),
        "duration_seconds": usage.duration_seconds,
    }


class RecordingModel:
    """A `StructuredModel` that writes every successful response to the staging directory.

    Every `ModelSuccess` is recorded, including one whose proposal later fails reference
    validation and is retried: the replay then consumes responses in exactly the order the live
    run did, reproducing the retry. Failures record nothing — the replay has no way to serve one
    and does not need to; a live retry that recovered replays as a first-attempt success.
    """

    def __init__(self, inner: StructuredModel, staging: Path, *, rehearsal: bool = False) -> None:
        self._inner = inner
        self._staging = staging
        self._rehearsal = rehearsal

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        return self._inner.capabilities

    def generate[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings | None = None,
        system: str | None = None,
        cache_prefix: str | None = None,
    ) -> ModelOutcome[T]:
        outcome = self._inner.generate(
            prompt=prompt,
            schema=schema,
            settings=settings,
            system=system,
            cache_prefix=cache_prefix,
        )
        if isinstance(outcome, ModelSuccess):
            index = len(list(self._staging.glob("[0-9]*.json"))) + 1
            slug = _SLUGS.get(type(outcome.value).__name__, "response")
            path = self._staging / f"{index:02d}-{slug}.json"
            # The envelope (#461): the named schema, the captured usage the offline ledger replays,
            # and the response. A live capture is the one place real usage exists, so this is where
            # it is written.
            envelope: dict[str, object] = {
                "schema": type(outcome.value).__name__,
                "usage": _usage_dict(outcome.usage),
                "response": outcome.value.model_dump(mode="json"),
            }
            if self._rehearsal:
                # The guard every other reader refuses on (#534): a rehearsal envelope records
                # the deterministic substitute, and must never replay as a recording.
                envelope["rehearsal"] = True
            path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
            cost = outcome.usage.estimated_cost
            print(f"  recorded {path.name}  (${cost:.4f}, {outcome.usage.output_tokens} out)")
        return outcome


class _FallbackModel:
    """Serves the already-recorded responses in order, then delegates to the live model.

    This is how an interrupted capture resumes without re-spending: a fresh data root replays the
    recorded prefix — same responses, same conversions, same allocated identifiers — and the first
    unanswered call goes live. Only the live inner is a `RecordingModel`, so a replayed response
    is never re-recorded.
    """

    def __init__(self, recorded: list[RecordedResponse], live: StructuredModel) -> None:
        self._recorded = list(recorded)
        self._live = live

    @property
    def name(self) -> str:
        return self._live.name

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        return self._live.capabilities

    def generate[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings | None = None,
        system: str | None = None,
        cache_prefix: str | None = None,
    ) -> ModelOutcome[T]:
        if self._recorded:
            queued = self._recorded.pop(0)
            value = queued.response
            if not isinstance(value, schema):
                raise CaptureError(
                    f"the next recorded response is a {type(value).__name__}, not the "
                    f"{schema.__name__} this call asks for; the capture and the recording have "
                    f"diverged and continuing live would corrupt the sequence"
                )
            print(f"  replayed a recorded {type(value).__name__} (no spend)")
            usage = queued.usage if queued.usage is not None else ModelUsage(model=self._live.name)
            return ModelSuccess(value=value, usage=usage)
        return self._live.generate(
            prompt=prompt,
            schema=schema,
            settings=settings,
            system=system,
            cache_prefix=cache_prefix,
        )


def _budget() -> Budget:
    # Four retries rather than the default two: a live 100KB proposal is regenerated whole on
    # each attempt, so a handful of misfilled fields can take an extra round to converge even
    # with the field-location feedback, and a fifth attempt is cheaper than a re-run.
    # Four hours of segment time rather than one: fifteen threats means fifteen mapping calls
    # and fifteen critique calls in one reasoning segment, each minutes long at live speed.
    return Budget(
        maximum_model_calls=BUDGET_CALLS,
        maximum_cost=BUDGET_COST,
        maximum_retries_per_node=4,
        maximum_duration_seconds=4 * 3600.0,
    )


def _refuse_fake(profile: ModelProfile, live: StructuredModel | None) -> None:
    """Refuse the fake provider before a stage takes its first side effect.

    The check runs at stage entry, not at model construction: by construction time the staging
    directory, the capture data root, and the loaded documents already exist, and a refusal that
    late leaves half a capture on disk. An injected `live` model (a test's deterministic stand-in)
    is exempt — the profile then only prices the run.
    """
    if live is None and profile.provider == "fake":
        raise CaptureError(
            f"a capture spends live provider calls; profile {profile.name!r} names the fake "
            f"provider, which would record the deterministic substitute replay already has"
        )


def _live_model(profile: ModelProfile) -> StructuredModel:
    # Deferred so importing this module — and every offline test of it — needs no provider SDK
    # client construction. The adapter itself defers the API key to the first call.
    from trace_ai.infrastructure.model.factory import build_model

    return build_model(profile)


def _model(
    scenario: Scenario,
    *,
    profile: ModelProfile,
    from_recorded: bool,
    skip: int = 0,
    live: StructuredModel | None = None,
    rehearsal: bool = False,
) -> StructuredModel:
    staging = capture_dir(scenario, rehearsal=rehearsal)
    recording = RecordingModel(
        live if live is not None else _live_model(profile), staging, rehearsal=rehearsal
    )
    if not from_recorded:
        return recording
    paths = sorted(staging.glob("[0-9]*.json"))[skip:]
    return _FallbackModel(
        list(load_recorded_responses(paths, allow_rehearsal=rehearsal)), recording
    )


def _assessment_id(scenario: Scenario, *, rehearsal: bool = False) -> str:
    staging = capture_dir(scenario, rehearsal=rehearsal)
    return (staging / "assessment-id.txt").read_text(encoding="utf-8").strip()


def _require_rehearsal_model(rehearsal: bool, live: StructuredModel | None) -> None:
    """A rehearsal never constructs a provider: the caller supplies the substitute it runs.

    The CLI builds a `DeterministicModel` from `--response` recordings; a rehearsal reaching this
    guard with nothing to serve is an operator slip, named before any side effect (#534).
    """
    if rehearsal and live is None:
        raise CaptureError(
            "a rehearsal runs the deterministic substitute; supply --response recordings for it "
            "to serve"
        )


def _spent(service: AssessmentService, assessment_id: str) -> str:
    handle = service.handle(assessment_id)
    runs = handle.objects.list(WorkflowRun)
    cost = sum((run.estimated_cost or Decimal(0) for run in runs), Decimal(0))
    calls = sum(run.total_model_calls for run in runs)
    return f"{calls} calls, ${cost:.2f} per the run rows so far"


def stage_extract(
    scenario: Scenario,
    *,
    profile_name: str,
    from_recorded: bool = False,
    live: StructuredModel | None = None,
    data_root: Path | None = None,
    rehearsal: bool = False,
) -> None:
    """Create the assessment, load the scenario's inputs, and run to checkpoint 1.

    With `from_recorded`, existing staged recordings answer the calls they cover (an interrupted
    capture resumed on a fresh data root) and only unanswered calls go live. `data_root` exists
    for tests, which must not write under the repository's `data/`. With `rehearsal`, the whole
    stage runs against a supplied deterministic model into the rehearsal staging directory,
    spending nothing (#534) — the mechanics-validation pass DEC-091 traded away.
    """
    staging = capture_dir(scenario, rehearsal=rehearsal)
    if data_root is None:
        data_root = capture_data_root(scenario, rehearsal=rehearsal)
    if staging.exists() and any(staging.glob("[0-9]*.json")) and not from_recorded:
        raise CaptureRefusedError(
            f"{staging} holds recordings; a re-run would re-spend them. Resume with "
            f"--from-recorded, or remove the directory to start over."
        )
    if data_root.exists():
        raise CaptureError(f"{data_root} exists; remove it to start a fresh capture")

    from trace_ai.infrastructure.model.profiles import resolve_profile

    profile = resolve_profile(profile_name)
    _require_rehearsal_model(rehearsal, live)
    _refuse_fake(profile, live)
    staging.mkdir(parents=True, exist_ok=True)
    if rehearsal:
        (staging / REHEARSAL_MARKER).write_text(
            "This directory was staged by `trace capture --rehearse` from the deterministic\n"
            "substitute. Nothing in it records a model response; nothing in it may be promoted\n"
            "into recorded/.\n",
            encoding="utf-8",
        )
    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        created = service.create(
            scenario.name,
            default_configuration(profile_name, "stride-scenario-based"),
            requirements_catalog_version=scenario.catalog_version,
        )
        (staging / "assessment-id.txt").write_text(created.id + "\n", encoding="utf-8")
        loader = DocumentLoader(service.handle(created.id))
        for path in scenario.input_documents():
            loader.load_document(
                path, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
            )
        outcome = run_assessment(
            service,
            created.id,
            model=_model(
                scenario,
                profile=profile,
                from_recorded=from_recorded,
                live=live,
                rehearsal=rehearsal,
            ),
            profile=profile,
            budget=_budget(),
        )
        if not outcome.paused:
            raise CaptureError(f"expected a pause at checkpoint 1, got {outcome.stopped_because}")

        handle = service.handle(created.id)
        context = current_system_context(handle)
        validation = validate_context(
            context,
            context_objects(handle),
            available_evidence={ref.id for ref in handle.objects.list(EvidenceReference)},
            previous=previous_approved_context(handle, context),
        )
        package = build_context_review_package(
            handle, index=EvidenceIndex(handle), validation=validation
        )
        (staging / "review-export.yaml").write_text(write_review_file(package), encoding="utf-8")
        print(f"paused at checkpoint 1; {_spent(service, created.id)}")
        print(f"author {staging / 'decisions-context.yaml'} from review-export.yaml, then: reason")


def stage_reason(
    scenario: Scenario,
    *,
    profile_name: str,
    from_recorded: bool = False,
    live: StructuredModel | None = None,
    data_root: Path | None = None,
    rehearsal: bool = False,
) -> None:
    """Apply the authored context decisions, approve, and run live to checkpoint 2."""
    staging = capture_dir(scenario, rehearsal=rehearsal)
    if data_root is None:
        data_root = capture_data_root(scenario, rehearsal=rehearsal)
    decisions = staging / "decisions-context.yaml"
    if not decisions.is_file():
        raise CaptureError(f"{decisions} does not exist; author it from review-export.yaml first")
    if (staging / "findings-export.yaml").exists():
        raise CaptureRefusedError(
            "the reasoning stage already ran; a re-run would re-spend its calls"
        )

    from trace_ai.infrastructure.model.profiles import resolve_profile

    profile = resolve_profile(profile_name)
    _require_rehearsal_model(rehearsal, live)
    _refuse_fake(profile, live)
    assessment_id = _assessment_id(scenario, rehearsal=rehearsal)
    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        handle = service.handle(assessment_id)
        document = read_review_file(decisions.read_text(encoding="utf-8"))
        apply_review_file(handle, document, reviewer_id=REVIEWER)
        context = current_system_context(handle)
        validation = validate_context(
            context,
            context_objects(handle),
            available_evidence={ref.id for ref in handle.objects.list(EvidenceReference)},
            previous=previous_approved_context(handle, context),
        )
        package = build_context_review_package(
            handle, index=EvidenceIndex(handle), validation=validation
        )
        approve_context(handle, package, reviewer_id=REVIEWER)

        outcome = resume_assessment(
            service,
            assessment_id,
            model=_model(
                scenario,
                profile=profile,
                from_recorded=from_recorded,
                skip=1,
                live=live,
                rehearsal=rehearsal,
            ),
            profile=profile,
            budget=_budget(),
        )
        if not outcome.paused:
            raise CaptureError(f"expected a pause at checkpoint 2, got {outcome.stopped_because}")

        handle = service.handle(assessment_id)
        findings = [
            {
                "id": finding.id,
                "title": finding.title,
                "description": finding.description,
                "requirement_ids": list(finding.requirement_ids),
                "affected_component_ids": list(finding.affected_component_ids),
                "confidence": finding.confidence.value,
                "evidence_ids": list(finding.evidence_ids),
            }
            for finding in handle.objects.list(Finding)
        ]
        questions = [
            {"id": question.id, "question": question.question, "status": question.status.value}
            for question in handle.objects.list(Question)
        ]
        (staging / "findings-export.yaml").write_text(
            yaml.safe_dump(
                {"assessment_id": assessment_id, "findings": findings, "questions": questions},
                sort_keys=False,
                allow_unicode=True,
                width=100,
            ),
            encoding="utf-8",
        )
        print(f"paused at checkpoint 2; {_spent(service, assessment_id)}")
        print(f"author {staging / 'decisions-findings.yaml'}, then: report")


def stage_report(
    scenario: Scenario,
    *,
    profile_name: str,
    live: StructuredModel | None = None,
    data_root: Path | None = None,
    rehearsal: bool = False,
) -> None:
    """Apply the authored finding decisions and run live to completion."""
    staging = capture_dir(scenario, rehearsal=rehearsal)
    if data_root is None:
        data_root = capture_data_root(scenario, rehearsal=rehearsal)
    decisions = staging / "decisions-findings.yaml"
    if not decisions.is_file():
        raise CaptureError(f"{decisions} does not exist; author it from findings-export.yaml first")
    if (staging / "report-hash.txt").exists():
        raise CaptureRefusedError("the report stage already ran; a re-run would re-spend its call")

    from trace_ai.infrastructure.model.profiles import resolve_profile

    profile = resolve_profile(profile_name)
    _require_rehearsal_model(rehearsal, live)
    _refuse_fake(profile, live)
    assessment_id = _assessment_id(scenario, rehearsal=rehearsal)
    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        handle = service.handle(assessment_id)
        recorded = yaml.safe_load(decisions.read_text(encoding="utf-8"))
        if recorded.get("assessment_id") != assessment_id:
            raise CaptureError(
                f"the finding decisions are for {recorded.get('assessment_id')}, "
                f"not {assessment_id}"
            )
        findings = {finding.id: finding for finding in handle.objects.list(Finding)}
        for entry in recorded.get("findings", []):
            finding = findings[entry["id"]]
            if "severity" in entry:
                finding, _ = change_severity(
                    handle, finding, Severity(entry["severity"]), reviewer_id=REVIEWER
                )
            if entry.get("decision") == "approve":
                finding, _ = approve_finding(
                    handle, finding, reviewer_id=REVIEWER, rationale=entry.get("rationale")
                )
            elif entry.get("decision") == "reject":
                finding, _ = reject_finding(
                    handle, finding, reviewer_id=REVIEWER, rationale=entry["rationale"]
                )
            findings[finding.id] = finding
        conclude_finding_review(service, assessment_id)

        outcome = resume_assessment(
            service,
            assessment_id,
            model=_model(
                scenario, profile=profile, from_recorded=False, live=live, rehearsal=rehearsal
            ),
            profile=profile,
            budget=_budget(),
            generated_at=GENERATED_AT,
        )
        if not outcome.completed:
            raise CaptureError(f"expected completion, got {outcome.stopped_because}")

        handle = service.handle(assessment_id)
        assessment = handle.objects.get(Assessment, assessment_id)
        if assessment.final_report_path is None:
            raise CaptureError("the run completed and no report path was recorded")
        filename = assessment.final_report_path.rpartition("/")[2]
        report_hash = handle.artifacts.hash_of("outputs", filename)
        (staging / "report-hash.txt").write_text(report_hash + "\n", encoding="utf-8")
        summary: dict[str, object] = {
            "report_hash": report_hash,
            "spent": _spent(service, assessment_id),
        }
        print(json.dumps(summary, indent=2))
        if rehearsal:
            print("rehearsal complete; nothing staged here may be promoted into recorded/")
        else:
            print(f"verify the round trip, then promote {staging.name}/ into recorded/")


def stage_baseline(
    scenario: Scenario,
    *,
    baseline: str,
    profile_name: str,
    response: object | None = None,
) -> None:
    """Capture one baseline recording from a live call, staged beside the pipeline stages.

    The DEC-074 baseline is one model call, so the stage is one file:
    `capture/baselines/baseline-<name>.json`, shaped exactly as `recorded/baselines/` holds it
    and the replay reads it. The call runs through `run_baseline`, so the capture is also scored
    against the truth set immediately — a captured baseline whose quality is unknown would be a
    recording nobody can judge. The same guards as the pipeline stages: an existing staged file
    refuses the re-spend (exit 3), and the fake provider is refused before the call.

    `response` is the test seam, mirroring the pipeline stages' `live`: a supplied
    `BaselineFindings` replays instead of spending, and the fake-provider refusal is waived.
    """
    from trace_ai.domain.proposals.baseline import BaselineFindings
    from trace_ai.infrastructure.model.profiles import resolve_profile
    from trace_ai.services.evaluation.baselines import run_baseline

    name = baseline if baseline.startswith("baseline-") else f"baseline-{baseline}"
    staging = capture_dir(scenario) / "baselines" / f"{name}.json"
    if staging.exists():
        raise CaptureRefusedError(
            f"{staging} exists; a re-run would re-spend the call. Remove it to re-capture."
        )
    profile = resolve_profile(profile_name)
    if response is None and profile.provider == "fake":
        raise CaptureError(
            f"a capture spends live provider calls; profile {profile.name!r} names the fake "
            f"provider, which would record the deterministic substitute replay already has"
        )
    if response is not None and not isinstance(response, BaselineFindings):
        raise CaptureError("response must be a BaselineFindings when supplied")

    # A supplied response replays through the fake provider -- build_model feeds queued
    # responses only to the deterministic substitute, and a real adapter ignores them (its
    # docstring says why: a caller that could feed a live provider could silently stop calling
    # it). The profile prices the live path only.
    outcome = run_baseline(
        scenario.slug,
        name,
        label="capture",
        profile_name="offline-fake" if response is not None else profile_name,
        response=response if isinstance(response, BaselineFindings) else None,
        record_to=staging,
    )
    if not outcome.schema_valid:
        raise CaptureError(
            f"the {baseline} baseline call did not produce a schema-valid response; nothing was "
            f"recorded, and the schema failure is the scored result in {outcome.feed_path}"
        )
    print(
        f"  recorded {staging.name}  (matched {len(outcome.matched)}, "
        f"missed {len(outcome.missed)}, spurious {len(outcome.spurious)})"
    )
    print(f"verify the scoring, then promote {staging.parent.name}/ into recorded/baselines/")
