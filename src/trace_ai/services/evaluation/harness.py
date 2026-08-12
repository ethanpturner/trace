"""The evaluation harness: a caller of the ordinary pipeline, and nothing more (DEC-073).

A harness run reads a scenario from the registry, replays its committed recording through
`services/driver.py` — the same nodes, the same transition table, the same stores an interactive
assessment uses — and answers both checkpoints from the scenario's recorded reviewer decisions
through the same writers an interactive session calls. Replay is not an ablation: the checkpoint
nodes execute, their gates hold, and `ReviewerDecision` rows are written (DEC-012, DEC-017).

**Ablations are run construction.** The driver substitutes named stand-ins for the removed nodes
and the `WorkflowRun` is marked non-authoritative from birth (`WorkflowRun.ablations`); the
harness only chooses which recordings still apply — a recording addressed to an ablated agent is
never queued, because the call it answers will not be made.

**Results have one authoritative home and one derived feed.** `EvaluationResult` rows persist
with the assessment through the ordinary stores. The feed under `benchmarks/results/` — keyed by
scenario, condition, and a caller-supplied label — is metrics plus the per-item match sets,
derived and regenerable, never authoritative. It is gitignored rather than committed: DEC-073
left the tree's location open, and a derived artifact that regenerates from the stores by one
command earns no place in history. The scorecard (DEC-076) and CI read the feed; anything that
doubts it re-runs the harness.

**The run diff is per item** (DEC-073). Each expected finding is classified against a named
prior feed as `matched`, `changed` (matched in both runs by a different DEC-066 identity),
`missed`, `regressed` (matched before, missed now), or `recovered`; spurious findings are listed
with the new ones named. Two runs can hold the same F1 while disagreeing on half their items,
and the diff is what makes a regression a list rather than a delta.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import Assessment, default_configuration
from trace_ai.domain.enums import ObjectStatus, ReviewDisposition, SourceOrigin
from trace_ai.domain.evaluation_result import EvaluationResult
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import RunStatus, WorkflowRun
from trace_ai.domain.finding import Finding
from trace_ai.domain.source_document import TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.factory import build_model
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.recorded import load_recorded_responses
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.context.pipeline import context_objects
from trace_ai.services.context.review_file import apply_review_file, read_review_file
from trace_ai.services.driver import resume_assessment, run_assessment
from trace_ai.services.evaluation.matching import (
    FindingMatchOutcome,
    match_findings,
    match_gaps,
    normalized_name,
)
from trace_ai.services.evaluation.metrics import (
    compute_benchmark_metrics,
    compute_metrics,
    persist_metrics,
)
from trace_ai.services.evaluation.registry import Scenario
from trace_ai.services.evaluation.registry import scenario as load_scenario
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.workflow.context_review import (
    approve_context,
    build_context_review_package,
    current_system_context,
)
from trace_ai.workflow.context_validation import validate_context
from trace_ai.workflow.finding_review import (
    approve_finding,
    change_severity,
    conclude_finding_review,
)
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["RESULTS_ROOT", "HarnessOutcome", "diff_feeds", "run_scenario"]

RESULTS_ROOT = PROJECT_ROOT / "benchmarks" / "results"
FEED_VERSION = "1"
HARNESS_REVIEWER = "recorded-reviewer"

# The recording's generation timestamp, pinned so replayed reports are byte-stable.
GENERATED_AT = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)

# Which recording filenames an ablation makes unconsumable: the file answers a call the ablated
# agent will not make. Filenames carry their agent's name by convention (see
# demo/forgeflow/recorded/provenance.md).
_ABLATED_RECORDING_MARKERS = {
    "no-evidence-validation": ("evidence-validation",),
    "no-critical-review": ("critical-review",),
}


class HarnessError(RuntimeError):
    """A scenario the harness cannot run, with the reason stated."""


@dataclass(slots=True)
class HarnessOutcome:
    """What one harness run produced, and where its feed landed."""

    scenario: str
    condition: str
    label: str
    assessment_id: str
    workflow_run_id: str
    run_status: str
    stopped_because: str
    ablations: list[str] = field(default_factory=list)
    metrics: list[EvaluationResult] = field(default_factory=list)
    feed_path: Path | None = None

    @property
    def completed(self) -> bool:
        return self.run_status == RunStatus.COMPLETED.value


def run_scenario(
    slug: str,
    *,
    data_root: Path,
    label: str,
    condition: str = "clean",
    ablations: Sequence[str] = (),
    profile_name: str = "offline-fake",
    registry_path: Path | None = None,
    results_root: Path | None = None,
    stop_after_findings: bool = False,
) -> HarnessOutcome:
    """Replay one registered scenario through the ordinary pipeline and export its feed.

    `label` names the run in the results tree — a commit hash, a date, or `local`. The caller
    supplies it because the harness computes nothing about its environment; a feed's identity is
    stated, never inferred.

    `stop_after_findings` ends the run at the finding checkpoint rather than resuming into the
    report, and the finding-quality metrics are computed there. The ablation set (DEC-012) uses
    it: an ablation that changes the finding set is measured on the findings, and the report's
    recorded sections — authored for the authoritative findings — would not fit the ablated ones.
    The report is not what the decision gate asks about.
    """
    entry = load_scenario(slug, registry_path=registry_path)
    if not entry.has_recording_for(condition):
        raise HarnessError(
            f"scenario {slug!r} has no recording for condition {condition!r}; the harness "
            f"replays recordings (DEC-073) and cannot run a variant that has none"
        )

    recordings = _recordings_for(entry, ablations, condition=condition)
    profile = resolve_profile(profile_name)
    model = build_model(profile, responses=load_recorded_responses(recordings))

    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        created = service.create(
            entry.name, default_configuration(profile_name, "stride-scenario-based")
        )
        assessment_id = created.id
        handle = service.handle(assessment_id)
        loader = DocumentLoader(handle)
        for path in entry.input_documents(condition):
            loader.load_document(
                path, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
            )

        stop_before = Phase.REPORT_GENERATION if stop_after_findings else None
        outcome = run_assessment(
            service,
            assessment_id,
            model=model,
            profile=profile,
            generated_at=GENERATED_AT,
            ablations=ablations,
            stop_before=stop_before,
        )

        previously_paused_at: Phase | None = None
        while outcome.paused:
            paused_at = outcome.state.current_phase
            if paused_at is previously_paused_at:
                pending = outcome.state.pending_human_review
                waiting = pending.object_ids if pending is not None else []
                raise HarnessError(
                    f"the recorded decisions leave {paused_at.value} incomplete; "
                    f"still awaiting: {', '.join(waiting)}"
                )
            previously_paused_at = paused_at
            if paused_at is Phase.HUMAN_CONTEXT_REVIEW:
                _apply_context_decisions(entry, service, assessment_id, condition=condition)
            elif paused_at is Phase.HUMAN_FINDING_REVIEW:
                _apply_finding_decisions(entry, service, assessment_id, condition=condition)
            outcome = resume_assessment(
                service,
                assessment_id,
                model=model,
                profile=profile,
                generated_at=GENERATED_AT,
                stop_before=stop_before,
            )

        run = handle.objects.get(WorkflowRun, outcome.state.workflow_run_id)
        metrics = _metrics_for(handle, run, entry, condition=condition)
        items = _items_for(handle, entry, condition=condition)
        adversarial = _adversarial_for(handle, entry, condition)
        feed_path = _export_feed(
            entry,
            handle,
            run,
            metrics=metrics,
            items=items,
            adversarial=adversarial,
            condition=condition,
            label=label,
            stopped_because=outcome.stopped_because,
            results_root=results_root if results_root is not None else RESULTS_ROOT,
        )

    return HarnessOutcome(
        scenario=entry.slug,
        condition=condition,
        label=label,
        assessment_id=assessment_id,
        workflow_run_id=run.id,
        run_status=run.status.value,
        stopped_because=outcome.stopped_because,
        ablations=list(run.ablations),
        metrics=metrics,
        feed_path=feed_path,
    )


def _recordings_for(
    entry: Scenario, ablations: Sequence[str], *, condition: str = "clean"
) -> list[Path]:
    """The scenario's response recordings, in consumption order, minus the ablated agents'."""
    skipped_markers = [
        marker for ablation in ablations for marker in _ABLATED_RECORDING_MARKERS.get(ablation, ())
    ]
    return [
        path
        for path in sorted(entry.recorded_dir_for(condition).glob("*.json"))
        if not any(marker in path.name for marker in skipped_markers)
    ]


def _apply_context_decisions(
    entry: Scenario, service: AssessmentService, assessment_id: str, *, condition: str = "clean"
) -> None:
    handle = service.handle(assessment_id)
    decisions_path = entry.recorded_dir_for(condition) / "decisions-context.yaml"
    document = read_review_file(decisions_path.read_text(encoding="utf-8"))
    # The recorded file carries the authoring-time assessment id; rebind it to this run's.
    # A replay assigns a fresh identifier (asm-002 when a prior scenario took asm-001 in a shared
    # store), and the review-file guard exists to stop one assessment's decisions reaching
    # another's — which is not what a rebind to the current run is.
    document["assessment_id"] = assessment_id
    apply_review_file(handle, document, reviewer_id=HARNESS_REVIEWER)
    validation = validate_context(
        current_system_context(handle),
        context_objects(handle),
        available_evidence={ref.id for ref in handle.objects.list(EvidenceReference)},
    )
    package = build_context_review_package(
        handle, index=EvidenceIndex(handle), validation=validation
    )
    approve_context(handle, package, reviewer_id=HARNESS_REVIEWER)


def _apply_finding_decisions(
    entry: Scenario, service: AssessmentService, assessment_id: str, *, condition: str = "clean"
) -> None:
    from trace_ai.domain.enums import Severity

    handle = service.handle(assessment_id)
    recorded = yaml.safe_load(
        (entry.recorded_dir_for(condition) / "decisions-findings.yaml").read_text(encoding="utf-8")
    )
    # Findings are matched by the recording's order rather than by identifier: a shared store
    # gives this run's findings different identifiers than the recording captured, and the
    # decisions apply to the candidate set positionally.
    candidates = sorted(
        (finding for finding in handle.objects.list(Finding) if finding.duplicate_of_id is None),
        key=lambda finding: finding.id,
    )
    recorded_findings = recorded.get("findings", [])
    for decided, candidate in zip(recorded_findings, candidates, strict=False):
        finding = candidate
        _ = decided.get("id")  # recorded for provenance; matching is positional
        if "severity" in decided:
            finding, _ = change_severity(
                handle, finding, Severity(decided["severity"]), reviewer_id=HARNESS_REVIEWER
            )
        if decided.get("decision") == ReviewDisposition.APPROVE.value:
            approve_finding(
                handle, finding, reviewer_id=HARNESS_REVIEWER, rationale=decided.get("rationale")
            )
    conclude_finding_review(service, assessment_id)


def _has_outcome_truth(entry: Scenario, condition: str) -> bool:
    expected = entry.expected_dir_for(condition)
    return (expected / "expected-findings.yaml").is_file() and (
        expected / "expected-documentation-gaps.yaml"
    ).is_file()


def _metrics_for(
    handle: AssessmentHandle, run: WorkflowRun, entry: Scenario, *, condition: str = "clean"
) -> list[EvaluationResult]:
    """This run's full metric set, topping up rather than duplicating the pipeline's rows.

    A completed run already carries the run-derived metrics its evaluation node persisted; the
    harness adds the benchmark metrics the node could not compute (nothing under `expected/`
    reaches a run, DEC-027). A run that stopped before its evaluation node has no rows, and the
    harness computes everything it can.
    """
    expected_dir = entry.expected_dir_for(condition)
    has_truth = _has_outcome_truth(entry, condition)
    existing = [
        result
        for result in handle.objects.list(EvaluationResult)
        if result.workflow_run_id == run.id
    ]
    if not existing:
        computed = compute_metrics(handle, run, expected_dir=expected_dir if has_truth else None)
        persist_metrics(handle, run, computed)
        return computed
    if not has_truth:
        return existing
    benchmark = compute_benchmark_metrics(handle, run, expected_dir=expected_dir)
    with handle.objects.transaction():
        for result in benchmark:
            handle.objects.save(result)
    return [*existing, *benchmark]


def _items_for(
    handle: AssessmentHandle, entry: Scenario, *, condition: str = "clean"
) -> dict[str, Any] | None:
    """The per-item match sets behind the rates, for the feed and the diff (DEC-073)."""
    if not _has_outcome_truth(entry, condition):
        return None
    from trace_ai.domain.component import Component as ComponentModel
    from trace_ai.domain.control_mapping import ControlMapping
    from trace_ai.domain.documentation_gap import DocumentationGap
    from trace_ai.services.findings.approved import approved_findings

    expected_dir = entry.expected_dir_for(condition)
    component_names = {
        component.id: normalized_name(component.name)
        for component in handle.objects.list(ComponentModel)
    }
    expected_findings = yaml.safe_load(
        (expected_dir / "expected-findings.yaml").read_text(encoding="utf-8")
    )["findings"]
    finding_matches: FindingMatchOutcome = match_findings(
        approved_findings(handle), expected_findings, component_names=component_names
    )

    expected_gaps = yaml.safe_load(
        (expected_dir / "expected-documentation-gaps.yaml").read_text(encoding="utf-8")
    )["documentation_gaps"]
    requirement_by_mapping = {
        mapping.id: mapping.requirement_id for mapping in handle.objects.list(ControlMapping)
    }
    gap_matches = match_gaps(
        [
            gap
            for gap in handle.objects.list(DocumentationGap)
            if gap.status is not ObjectStatus.SUPERSEDED
        ],
        {str(entry_["requirement_id"]) for entry_ in expected_gaps},
        requirement_by_mapping=requirement_by_mapping,
    )
    return {
        "findings": {
            "matched": finding_matches.matched,
            "missed": finding_matches.missed,
            "spurious": finding_matches.spurious,
            "fingerprints": finding_matches.fingerprints,
        },
        "documentation_gaps": {
            "matching": gap_matches.matching,
            "non_matching": gap_matches.non_matching,
        },
    }


def _adversarial_for(
    handle: AssessmentHandle, entry: Scenario, condition: str
) -> dict[str, Any] | None:
    """The two-axis adversarial result for a condition carrying a payload manifest (DEC-075).

    Axis one lives in the finding metrics already recorded, read as deltas against clean. Axis two
    is the injected-instruction compliance rate scored here against `expected-adversarial.yaml`.
    """
    manifest = entry.expected_dir_for(condition) / "expected-adversarial.yaml"
    if not manifest.is_file():
        return None
    from trace_ai.domain.component import Component as ComponentModel
    from trace_ai.domain.source_observation import ObservationKind, SourceObservation
    from trace_ai.services.evaluation.adversarial import score_compliance
    from trace_ai.services.findings.approved import approved_findings

    expected_findings = yaml.safe_load(
        (entry.expected_dir_for(condition) / "expected-findings.yaml").read_text(encoding="utf-8")
    )["findings"]
    component_names = {
        component.id: normalized_name(component.name)
        for component in handle.objects.list(ComponentModel)
    }
    attack_detected = any(
        observation.kind is ObservationKind.INJECTION_ATTEMPT
        for observation in handle.objects.list(SourceObservation)
    )
    score = score_compliance(
        manifest,
        approved_findings=approved_findings(handle),
        expected_findings=expected_findings,
        component_names=component_names,
        attack_detected=attack_detected,
    )
    return {
        "attack_detected": score.attack_detected,
        "injected_instruction_compliance_rate": score.compliance_rate,
        "compliance_by_class": score.compliance_by_class(),
        "payloads": [
            {"key": p.key, "payload_class": p.payload_class, "complied": p.complied}
            for p in score.payloads
        ],
    }


def _export_feed(
    entry: Scenario,
    handle: AssessmentHandle,
    run: WorkflowRun,
    *,
    metrics: list[EvaluationResult],
    items: dict[str, Any] | None,
    adversarial: dict[str, Any] | None = None,
    condition: str,
    label: str,
    stopped_because: str,
    results_root: Path,
) -> Path:
    assessment = handle.objects.get(Assessment, handle.assessment_id)
    feed: dict[str, Any] = {
        "feed_version": FEED_VERSION,
        "scenario": entry.slug,
        "condition": condition,
        "label": label,
        "assessment_id": assessment.id,
        "workflow_run_id": run.id,
        "run_status": run.status.value,
        "stopped_because": stopped_because,
        "ablations": list(run.ablations),
        "authoritative": run.is_authoritative,
        "metrics": {
            result.metric_name: {
                "value": result.metric_value,
                "unit": result.unit,
                "evaluator_type": result.evaluator_type.value,
                "sample_size": result.sample_size,
            }
            for result in metrics
        },
        "items": items,
    }
    if adversarial is not None:
        feed["adversarial"] = adversarial
        feed["metrics"]["injected_instruction_compliance_rate"] = {
            "value": adversarial["injected_instruction_compliance_rate"]
        }
    target = results_root / entry.slug / condition / f"{label}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(feed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


# -- the per-item run diff ---------------------------------------------------------------------


@dataclass(slots=True)
class RunDiff:
    """Each expected item classified against a named prior run (DEC-073)."""

    scenario: str
    condition: str
    current_label: str
    prior_label: str
    matched: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    regressed: list[str] = field(default_factory=list)
    recovered: list[str] = field(default_factory=list)
    spurious: list[str] = field(default_factory=list)
    new_spurious: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.changed or self.missed or self.regressed or self.new_spurious)


def diff_feeds(current_path: Path, prior_path: Path) -> RunDiff:
    """Classify every expected item in the current feed against the prior one.

    `changed` means both runs matched the expectation but by findings with different DEC-066
    identities — the same score concealing a different conclusion, which is exactly what an
    aggregate delta cannot show.
    """
    current = json.loads(current_path.read_text(encoding="utf-8"))
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    if current.get("scenario") != prior.get("scenario"):
        raise ValueError(
            f"feeds describe different scenarios: {current.get('scenario')!r} versus "
            f"{prior.get('scenario')!r}; a diff across scenarios classifies nothing"
        )

    diff = RunDiff(
        scenario=str(current["scenario"]),
        condition=str(current["condition"]),
        current_label=str(current["label"]),
        prior_label=str(prior["label"]),
    )
    current_items = current.get("items") or {}
    prior_items = prior.get("items") or {}
    current_findings = current_items.get("findings") or {}
    prior_findings = prior_items.get("findings") or {}

    current_matched: dict[str, list[str]] = current_findings.get("matched") or {}
    prior_matched: dict[str, list[str]] = prior_findings.get("matched") or {}
    current_prints: dict[str, list[str]] = current_findings.get("fingerprints") or {}
    prior_prints: dict[str, list[str]] = prior_findings.get("fingerprints") or {}
    current_missed = set(current_findings.get("missed") or [])
    prior_missed = set(prior_findings.get("missed") or [])

    for key in sorted({*current_matched, *current_missed}):
        if key in current_matched:
            if key in prior_missed:
                diff.recovered.append(key)
            elif sorted(current_prints.get(key, [])) == sorted(prior_prints.get(key, [])):
                diff.matched.append(key)
            else:
                diff.changed.append(key)
        else:
            diff.missed.append(key)
            if key in prior_matched:
                diff.regressed.append(key)

    diff.spurious = sorted(current_findings.get("spurious") or [])
    prior_spurious = set(prior_findings.get("spurious") or [])
    diff.new_spurious = sorted(set(diff.spurious) - prior_spurious)
    return diff
