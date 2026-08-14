"""Capture the ForgeFlow recording from a live model run (#324).

    uv run python scripts/capture_forgeflow.py extract
    # author capture/decisions-context.yaml from the exported review file, then
    uv run python scripts/capture_forgeflow.py reason
    # author capture/decisions-findings.yaml from the exported findings summary, then
    uv run python scripts/capture_forgeflow.py report

The three stages mirror `scripts/replay_forgeflow.py` exactly — the same service calls, the same
decision writers, the same pinned report timestamp — because the point of a capture is that the
replayer can consume it without changing. What differs is the model: every call goes to the live
provider through the seam, and a wrapper records each response the run consumed, in consumption
order, shaped exactly as `load_recorded_responses` reads them back.

Everything lands in a staging directory (`demo/forgeflow/capture/`) rather than in `recorded/`,
so a partial capture cannot half-replace the committed recording. Promotion into `recorded/` is a
deliberate copy after the replay round-trip is verified.

The capture spends real money — about 28 calls on `claude-opus-5`, $2.25-$5.97 by the 2026-08-09
estimate — and each stage refuses to run twice: re-running a stage would re-spend it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import Assessment, default_configuration
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import Question
from trace_ai.domain.source_document import TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.anthropic_adapter import AnthropicModel
from trace_ai.infrastructure.model.profiles import resolve_profile
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
    from pydantic import BaseModel

INPUT = PROJECT_ROOT / "demo" / "forgeflow" / "input"
CAPTURE = PROJECT_ROOT / "demo" / "forgeflow" / "capture"
DATA_ROOT = PROJECT_ROOT / "data" / "capture-forgeflow"
PROFILE_NAME = "primary-development"
REVIEWER = "recorded-reviewer"

# The capture's generation timestamp, pinned so the replay is byte-identical. The replayer must
# carry the same value when this capture is promoted.
GENERATED_AT = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)

# A hard stop well above the ~28-call, ~$5 estimate: a runaway costs one order of magnitude,
# never an open-ended bill.
BUDGET_CALLS = 60
BUDGET_COST = Decimal("30")
"""The cost ceiling is checked against a projection of max_output_tokens per call, and the
64,000-token ceiling makes that projection ~4x any plausible actual spend -- so the guard sits
well above the ~$5 estimate to stop a runaway without stopping the run it is guarding."""

_SLUGS = {
    "ContextExtractionProposal": "context-extraction",
    "ThreatAnalysisProposal": "threat-analysis",
    "MappingProposal": "mapping",
    "EvidenceValidationProposal": "evidence-validation",
    "CriticalReviewProposal": "critical-review",
    "ReportSections": "report-sections",
}


class RecordingModel:
    """A `StructuredModel` that writes every successful response to the staging directory.

    Every `ModelSuccess` is recorded, including one whose proposal later fails reference
    validation and is retried: the replay then consumes responses in exactly the order the live
    run did, reproducing the retry. Failures record nothing — the replay has no way to serve one
    and does not need to; a live retry that recovered replays as a first-attempt success.
    """

    def __init__(self, inner: StructuredModel) -> None:
        self._inner = inner

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
        settings: GenerationSettings,
        system: str | None = None,
    ) -> ModelOutcome[T]:
        outcome = self._inner.generate(
            prompt=prompt, schema=schema, settings=settings, system=system
        )
        if isinstance(outcome, ModelSuccess):
            index = len(list(CAPTURE.glob("[0-9]*.json"))) + 1
            slug = _SLUGS.get(type(outcome.value).__name__, "response")
            path = CAPTURE / f"{index:02d}-{slug}.json"
            path.write_text(outcome.value.model_dump_json(indent=2) + "\n", encoding="utf-8")
            cost = outcome.usage.estimated_cost
            print(f"  recorded {path.name}  (${cost:.4f}, {outcome.usage.output_tokens} out)")
        return outcome


class FallbackModel:
    """Serves the already-recorded responses in order, then delegates to the live model.

    This is how an interrupted capture resumes without re-spending (#324): a fresh data root
    replays the recorded prefix — same responses, same conversions, same allocated identifiers —
    and the first unanswered call goes live. Only the live inner is a `RecordingModel`, so a
    replayed response is never re-recorded.
    """

    def __init__(self, recorded: list[BaseModel], live: StructuredModel) -> None:
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
        settings: GenerationSettings,
        system: str | None = None,
    ) -> ModelOutcome[T]:
        if self._recorded:
            queued = self._recorded.pop(0)
            if not isinstance(queued, schema):
                raise SystemExit(
                    f"the next recorded response is a {type(queued).__name__}, not the "
                    f"{schema.__name__} this call asks for; the capture and the recording have "
                    f"diverged and continuing live would corrupt the sequence"
                )
            print(f"  replayed a recorded {type(queued).__name__} (no spend)")
            return ModelSuccess(value=queued, usage=ModelUsage(model=self._live.name))
        return self._live.generate(prompt=prompt, schema=schema, settings=settings, system=system)


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


def _model(*, from_recorded: bool, skip: int = 0) -> StructuredModel:
    live = RecordingModel(AnthropicModel(PROFILE_NAME))
    if not from_recorded:
        return live
    from trace_ai.infrastructure.model.recorded import load_recorded_responses

    paths = sorted(CAPTURE.glob("[0-9]*.json"))[skip:]
    return FallbackModel(list(load_recorded_responses(paths)), live)


def _assessment_id() -> str:
    return (CAPTURE / "assessment-id.txt").read_text(encoding="utf-8").strip()


def _spent(service: AssessmentService, assessment_id: str) -> str:
    from trace_ai.domain.execution import WorkflowRun

    handle = service.handle(assessment_id)
    runs = handle.objects.list(WorkflowRun)
    cost = sum((run.estimated_cost or Decimal(0) for run in runs), Decimal(0))
    calls = sum(run.total_model_calls for run in runs)
    return f"{calls} calls, ${cost:.2f} per the run rows so far"


def stage_extract(*, from_recorded: bool = False) -> None:
    """Create the assessment, load the inputs, and run to checkpoint 1.

    With `--from-recorded`, existing recordings answer the calls they cover (an interrupted
    capture resumed on a fresh data root) and only unanswered calls go live.
    """
    if CAPTURE.exists() and any(CAPTURE.glob("[0-9]*.json")) and not from_recorded:
        raise SystemExit(
            f"{CAPTURE} holds recordings; a re-run would re-spend them. Resume with "
            f"--from-recorded, or remove the directory to start over."
        )
    CAPTURE.mkdir(parents=True, exist_ok=True)
    if DATA_ROOT.exists():
        raise SystemExit(f"{DATA_ROOT} exists; remove it to start a fresh capture")

    profile = resolve_profile(PROFILE_NAME)
    with AssessmentStore.at_root(DATA_ROOT) as store:
        service = AssessmentService(store, artifact_root=DATA_ROOT)
        created = service.create(
            "ForgeFlow", default_configuration(PROFILE_NAME, "stride-scenario-based")
        )
        (CAPTURE / "assessment-id.txt").write_text(created.id + "\n", encoding="utf-8")
        loader = DocumentLoader(service.handle(created.id))
        for path in sorted(INPUT.iterdir()):
            if path.is_file():
                loader.load_document(
                    path, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
                )
        outcome = run_assessment(
            service,
            created.id,
            model=_model(from_recorded=from_recorded),
            profile=profile,
            budget=_budget(),
        )
        if not outcome.paused:
            raise SystemExit(f"expected a pause at checkpoint 1, got {outcome.stopped_because}")

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
        (CAPTURE / "review-export.yaml").write_text(write_review_file(package), encoding="utf-8")
        print(f"paused at checkpoint 1; {_spent(service, created.id)}")
        print(f"author {CAPTURE / 'decisions-context.yaml'} from review-export.yaml, then: reason")


def stage_reason(*, from_recorded: bool = False) -> None:
    """Apply the authored context decisions, approve, and run live to checkpoint 2."""
    decisions = CAPTURE / "decisions-context.yaml"
    if not decisions.is_file():
        raise SystemExit(f"{decisions} does not exist; author it from review-export.yaml first")
    if (CAPTURE / "findings-export.yaml").exists():
        raise SystemExit("the reasoning stage already ran; a re-run would re-spend its calls")

    profile = resolve_profile(PROFILE_NAME)
    assessment_id = _assessment_id()
    with AssessmentStore.at_root(DATA_ROOT) as store:
        service = AssessmentService(store, artifact_root=DATA_ROOT)
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
            model=_model(from_recorded=from_recorded, skip=1),
            profile=profile,
            budget=_budget(),
        )
        if not outcome.paused:
            raise SystemExit(f"expected a pause at checkpoint 2, got {outcome.stopped_because}")

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
        (CAPTURE / "findings-export.yaml").write_text(
            yaml.safe_dump(
                {"assessment_id": assessment_id, "findings": findings, "questions": questions},
                sort_keys=False,
                allow_unicode=True,
                width=100,
            ),
            encoding="utf-8",
        )
        print(f"paused at checkpoint 2; {_spent(service, assessment_id)}")
        print(f"author {CAPTURE / 'decisions-findings.yaml'}, then: report")


def stage_report() -> None:
    """Apply the authored finding decisions and run live to completion."""
    decisions = CAPTURE / "decisions-findings.yaml"
    if not decisions.is_file():
        raise SystemExit(f"{decisions} does not exist; author it from findings-export.yaml first")
    if (CAPTURE / "report-hash.txt").exists():
        raise SystemExit("the report stage already ran; a re-run would re-spend its call")

    profile = resolve_profile(PROFILE_NAME)
    assessment_id = _assessment_id()
    with AssessmentStore.at_root(DATA_ROOT) as store:
        service = AssessmentService(store, artifact_root=DATA_ROOT)
        handle = service.handle(assessment_id)
        recorded = yaml.safe_load(decisions.read_text(encoding="utf-8"))
        if recorded.get("assessment_id") != assessment_id:
            raise SystemExit(
                f"the finding decisions are for {recorded.get('assessment_id')}, "
                f"not {assessment_id}"
            )
        findings = {finding.id: finding for finding in handle.objects.list(Finding)}
        for entry in recorded.get("findings", []):
            finding = findings[entry["id"]]
            if "severity" in entry:
                from trace_ai.domain.enums import Severity

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
            model=_model(from_recorded=False),
            profile=profile,
            budget=_budget(),
            generated_at=GENERATED_AT,
        )
        if not outcome.completed:
            raise SystemExit(f"expected completion, got {outcome.stopped_because}")

        handle = service.handle(assessment_id)
        assessment = handle.objects.get(Assessment, assessment_id)
        if assessment.final_report_path is None:
            raise SystemExit("the run completed and no report path was recorded")
        filename = assessment.final_report_path.rpartition("/")[2]
        report_hash = handle.artifacts.hash_of("outputs", filename)
        (CAPTURE / "report-hash.txt").write_text(report_hash + "\n", encoding="utf-8")
        usage: dict[str, object] = {
            "report_hash": report_hash,
            "spent": _spent(service, assessment_id),
        }
        print(json.dumps(usage, indent=2))
        print("verify the round trip, then promote capture/ into recorded/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stage", choices=["extract", "reason", "report"])
    parser.add_argument(
        "--from-recorded",
        action="store_true",
        help="serve existing recordings before going live (resume an interrupted capture)",
    )
    args = parser.parse_args(argv)
    if args.stage == "extract":
        stage_extract(from_recorded=args.from_recorded)
    elif args.stage == "reason":
        stage_reason(from_recorded=args.from_recorded)
    else:
        stage_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
