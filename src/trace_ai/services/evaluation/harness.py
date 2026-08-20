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
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.actor import Actor
from trace_ai.domain.assessment import Assessment, default_configuration
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.enums import ObjectStatus, ReviewDisposition, SourceOrigin
from trace_ai.domain.evaluation_result import EvaluationResult
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import ExecutionRecord, RunStatus, WorkflowRun
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import Question, QuestionStatus
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.factory import build_model
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.recorded import load_recorded_responses
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.context.pipeline import context_objects
from trace_ai.services.context.review_file import (
    ReviewFileError,
    apply_review_file,
    read_review_file,
)
from trace_ai.services.driver import resume_assessment, run_assessment
from trace_ai.services.evaluation.matching import (
    FindingMatchOutcome,
    context_decision_fingerprints,
    live_context_fingerprint,
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
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["RESULTS_ROOT", "HarnessOutcome", "diff_feeds", "run_scenario"]

RESULTS_ROOT = PROJECT_ROOT / "benchmarks" / "results"
FEED_VERSION = "1"
HARNESS_REVIEWER = "recorded-reviewer"

# The one deterministic stamp every renderer shares (`stamps.py`), so the harness renders the same
# ForgeFlow report deterministically; the offline replay's own pin is `report-hash-offline.txt`
# (#505), distinct from the script's capture-conditions `report-hash.txt` -- the two replay
# paths stamp different model profiles into the report, so one pin cannot serve both.
GENERATED_AT = DETERMINISTIC_STAMP

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

    report_hash_verified: bool | None = None
    """`True`/`False` against the scenario's pinned `recorded/report-hash-offline.txt` (#505); `None`
    when the scenario pins no hash or the run did not render a report. `False` is drift — the
    replay stopped reproducing the recording's report — and the CLI answers it as exit 3, the
    same answer `trace verify` gives a drifted report (DEC-088)."""

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
    profile = resolve_profile(profile_name)
    live = profile.provider != "fake"
    if live:
        # A live run replays nothing: the provider answers, and the checkpoints are decided by
        # DEC-077's named default policy (with recorded question answers matched by text). This
        # path is manual and priced by the operator; CI never takes it.
        model = build_model(profile)
    else:
        if not entry.has_recording_for(condition):
            raise HarnessError(
                f"scenario {slug!r} has no recording for condition {condition!r}; the harness "
                f"replays recordings (DEC-073) and cannot run a variant that has none"
            )
        recordings = _recordings_for(entry, ablations, condition=condition)
        model = build_model(profile, responses=load_recorded_responses(recordings))
        # DEC-136: a replayed row is attributed to the model that produced its recording, read
        # from the envelopes' recorded usage. An authored recording carries no usage and yields
        # no attribution — absent, never invented.
        models = _recorded_models(recordings)

    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        created = service.create(
            entry.name,
            default_configuration(profile_name, "stride-scenario-based"),
            requirements_catalog_version=entry.catalog_version,
            # A replay pins the registry's workflow version so the recording is consumed under
            # the call shape that produced it (DEC-134) — the condition's own pin where its
            # recording carries one, because a promoted clean capture must not re-shape the
            # replay of a condition recording it did not touch. A live run pins nothing: it
            # measures the current pipeline, and what it records carries the current version.
            workflow_version=None if live else entry.workflow_version_for(condition),
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
        defaulted_decisions = 0
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
                if live:
                    defaulted_decisions += _apply_context_decisions_live(
                        entry, service, assessment_id, condition=condition
                    )
                else:
                    _apply_context_decisions(entry, service, assessment_id, condition=condition)
            elif paused_at is Phase.HUMAN_FINDING_REVIEW:
                if live:
                    defaulted_decisions += _apply_finding_decisions_live(service, assessment_id)
                else:
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
        if live:
            # DEC-136: a live row is attributed from the execution ledger — the model that
            # actually answered each call, which an overlaid profile may make more than one.
            models = _live_models(handle, run.id)
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
            defaulted_decisions=defaulted_decisions,
            stopped_because=outcome.stopped_because,
            results_root=results_root if results_root is not None else RESULTS_ROOT,
            models=models,
        )
        report_hash_verified = _verify_report_hash(handle, entry, condition=condition)

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
        report_hash_verified=report_hash_verified,
    )


def _recorded_models(recordings: Sequence[Path]) -> list[str]:
    """The distinct models the recordings say produced them (DEC-136).

    Captured envelopes carry the provider's reported model in their recorded usage; authored
    envelopes carry no usage block at all, so an authored recording attributes to nothing and
    the scorecard renders the absence as a dash rather than inventing a model no call reached.
    """
    models: set[str] = set()
    for path in recordings:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        usage = envelope.get("usage") if isinstance(envelope, dict) else None
        model = usage.get("model") if isinstance(usage, dict) else None
        if isinstance(model, str) and model:
            models.add(model)
    return sorted(models)


def _live_models(handle: AssessmentHandle, run_id: str) -> list[str]:
    """The distinct models the execution ledger attributes this run's calls to (DEC-136)."""
    return sorted(
        {
            record.model_name
            for record in handle.objects.list(ExecutionRecord)
            if record.workflow_run_id == run_id and record.model_name
        }
    )


def _verify_report_hash(
    handle: AssessmentHandle, entry: Scenario, *, condition: str
) -> bool | None:
    """The replayed report's hash against the scenario's pin, where one exists (#505).

    Generalizes what `scripts/replay_forgeflow.py` pinned for one scenario: any scenario may
    commit `recorded/report-hash-offline.txt`, and its replay then verifies the rendered bytes. `None`
    when no pin exists or the run rendered no report — absence of a pin is not a pass.
    """
    pin_path = entry.recorded_dir_for(condition) / "report-hash-offline.txt"
    if not pin_path.is_file():
        return None
    assessment = handle.objects.get(Assessment, handle.assessment_id)
    if assessment.final_report_path is None:
        return None
    filename = assessment.final_report_path.rpartition("/")[2]
    return (
        handle.artifacts.hash_of("outputs", filename)
        == pin_path.read_text(encoding="utf-8").strip()
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
        # rglob, sorted by relative path: the flagship recording is organized by segment
        # (extraction/, reasoning/, report/), whose alphabetical order is the consumption
        # order; a flat benchmark directory sorts identically to before.
        for path in sorted(entry.recorded_dir_for(condition).rglob("[0-9]*.json"))
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
    reviewed = current_system_context(handle)
    validation = validate_context(
        reviewed,
        context_objects(handle),
        available_evidence={ref.id for ref in handle.objects.list(EvidenceReference)},
        previous=previous_approved_context(handle, reviewed),
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
    candidates = sorted(
        (finding for finding in handle.objects.list(Finding) if finding.duplicate_of_id is None),
        key=lambda finding: finding.id,
    )
    recorded_findings = recorded.get("findings", [])
    # A count mismatch means the truth set no longer describes the run -- a pipeline change produced
    # a different finding set than the decisions were authored against. Silently zipping the shorter
    # of the two (the old `strict=False`) scored a different assessment than the truth set and said
    # nothing; a loud failure is the only honest answer.
    if len(recorded_findings) != len(candidates):
        raise HarnessError(
            f"{entry.slug}/{condition}: the recording holds {len(recorded_findings)} finding "
            f"decision(s) but the run produced {len(candidates)}. The truth set no longer matches "
            f"the run; re-capture the decisions or investigate the pipeline change."
        )
    # Match on the recorded identifier when every one resolves to a produced finding -- the
    # single-scenario case, where a fresh store re-mints the same identifiers, so a reordering of the
    # finding set cannot land a decision on the wrong finding. A shared store (the `--all` sweep)
    # mints different identifiers, so there the documented positional fallback stands: both the
    # candidates and the recording are in allocation order.
    by_id = {finding.id: finding for finding in candidates}
    recorded_ids = [str(decided.get("id")) for decided in recorded_findings]
    if len(set(recorded_ids)) == len(recorded_ids) and all(rid in by_id for rid in recorded_ids):
        pairs = [(decided, by_id[str(decided["id"])]) for decided in recorded_findings]
    else:
        pairs = list(zip(recorded_findings, candidates, strict=True))
    for decided, candidate in pairs:
        finding = candidate
        if "severity" in decided:
            finding, _ = change_severity(
                handle, finding, Severity(decided["severity"]), reviewer_id=HARNESS_REVIEWER
            )
        if decided.get("decision") == ReviewDisposition.APPROVE.value:
            approve_finding(
                handle, finding, reviewer_id=HARNESS_REVIEWER, rationale=decided.get("rationale")
            )
        elif decided.get("decision") == ReviewDisposition.REJECT.value:
            reject_finding(
                handle, finding, reviewer_id=HARNESS_REVIEWER, rationale=decided.get("rationale")
            )
    conclude_finding_review(service, assessment_id)


STABILITY_REVIEWER = "stability-default-v1"
"""DEC-077's named default policy, as the reviewer identity every defaulted decision carries."""

_DEFAULT_ANSWER = (
    "Stability protocol default (DEC-077): no recorded answer matches this question, and the "
    "measurement holds the reviewer constant, so the run proceeds on the documents alone."
)


def _normalized_question(text: str) -> str:
    return " ".join(text.lower().split())


def _recorded_object_decisions(entry: Scenario, condition: str) -> dict[tuple[str, ...], str]:
    """Fingerprint → disposition from the scenario's recorded run, or nothing when unavailable.

    The recorded review file's decisions were authored against the recorded run's objects
    (DEC-091), so the fingerprints come from the recorded extraction proposal — the objects
    those identifiers were allocated for — and a scenario without a readable recording simply
    contributes no matches, leaving every decision to the default policy, counted.
    """
    from trace_ai.domain.proposals import ContextExtractionProposal
    from trace_ai.infrastructure.model.recorded import parse_recorded_response

    decisions_path = entry.recorded_dir_for(condition) / "decisions-context.yaml"
    if not decisions_path.is_file():
        return {}
    try:
        document = read_review_file(decisions_path.read_text(encoding="utf-8"))
    except ReviewFileError:
        return {}
    for path in sorted(entry.recorded_dir_for(condition).rglob("[0-9]*.json")):
        try:
            recorded = parse_recorded_response(
                path.read_text(encoding="utf-8"), described_as=path.name
            )
        except ValueError:
            continue
        if isinstance(recorded.response, ContextExtractionProposal):
            return context_decision_fingerprints(recorded.response, document)
    return {}


def _apply_context_decisions_live(
    entry: Scenario, service: AssessmentService, assessment_id: str, *, condition: str
) -> int:
    """Checkpoint 1 under DEC-077's named default policy, returning the defaulted count.

    Object decisions replay by content fingerprint (DEC-093): a live object whose fingerprint
    uniquely matches an object the recorded reviewer decided replays that disposition, and only
    an object with no recorded counterpart — a genuinely novel extraction — falls to the default
    approval and counts as defaulted. A blocking question whose text matches a recorded answer
    is answered with it, and one with no match gets the protocol's default answer. The defaulted
    count is every decision that had no recorded counterpart, so the substitution DEC-077 warns
    about is visible in the summary rather than silent — and now measures novelty rather than
    the harness's own leniency.
    """
    from trace_ai.workflow.context_review import answer_question, decide_object

    handle = service.handle(assessment_id)
    defaulted = 0
    recorded_decisions = _recorded_object_decisions(entry, condition)
    objects = context_objects(handle)
    names_by_id = {
        obj.id: normalized_name(obj.name)
        for obj in objects
        if isinstance(obj, (Component, Actor, Asset, TrustBoundary))
    }
    fingerprinted = [(live_context_fingerprint(obj, names_by_id), obj) for obj in objects]
    counts = Counter(fp for fp, _ in fingerprinted if fp is not None)
    for fingerprint, obj in fingerprinted:
        replayed: ReviewDisposition | None = None
        if fingerprint is not None and counts[fingerprint] == 1:
            decision = recorded_decisions.get(fingerprint)
            if decision in {ReviewDisposition.APPROVE.value, ReviewDisposition.REJECT.value}:
                replayed = ReviewDisposition(decision)
        decide_object(
            handle, obj, replayed or ReviewDisposition.APPROVE, reviewer_id=STABILITY_REVIEWER
        )
        if replayed is None:
            defaulted += 1

    recorded_answers: dict[str, str] = {}
    decisions_path = entry.recorded_dir_for(condition) / "decisions-context.yaml"
    if decisions_path.is_file():
        document = read_review_file(decisions_path.read_text(encoding="utf-8"))
        for question_entry in document.get("questions") or []:
            answer = (question_entry.get("answer") or "").strip()
            if answer:
                recorded_answers[_normalized_question(str(question_entry.get("question", "")))] = (
                    answer
                )

    for question in handle.objects.list(Question):
        if question.status is QuestionStatus.OPEN and question.blocking:
            matched = recorded_answers.get(_normalized_question(question.question))
            answer_question(
                handle,
                question,
                response=matched or _DEFAULT_ANSWER,
                reviewer_id=STABILITY_REVIEWER,
            )
            if matched is None:
                defaulted += 1

    def _package() -> Any:
        reviewed = current_system_context(handle)
        validation = validate_context(
            reviewed,
            context_objects(handle),
            available_evidence={ref.id for ref in handle.objects.list(EvidenceReference)},
            previous=previous_approved_context(handle, reviewed),
        )
        return build_context_review_package(
            handle, index=EvidenceIndex(handle), validation=validation
        )

    package = _package()
    # The one mechanical remediation the policy performs, because it is the edit any reviewer
    # facing this validation error makes: a false-shaped transport label with nothing behind it
    # becomes `unknown` (data-model.md section 14's own rule), through the same reviewer-edit
    # path a person uses, and counted as a defaulted decision. Three of the first protocol's
    # five runs died on exactly this slip; an analytical error is still the run's to fail on.
    from trace_ai.domain.data_flow import DataFlow
    from trace_ai.domain.vocabulary import UNKNOWN
    from trace_ai.workflow.context_review import apply_edit

    mechanical = [
        error
        for error in package.outstanding_errors
        if error.field in ("authentication", "encryption_in_transit")
        and "Absence of a statement" in error.message
    ]
    if mechanical:
        for error in mechanical:
            flow = handle.objects.find(DataFlow, error.object_id)
            if flow is not None:
                apply_edit(
                    handle,
                    flow,
                    {error.field: UNKNOWN},
                    reviewer_id=STABILITY_REVIEWER,
                    rationale=(
                        "Stability protocol default (DEC-077): the mechanical section-14 "
                        "relabel a reviewer performs — unstated transport security is unknown."
                    ),
                )
                defaulted += 1
        package = _package()
    approve_context(handle, package, reviewer_id=STABILITY_REVIEWER)
    return defaulted


def _apply_finding_decisions_live(service: AssessmentService, assessment_id: str) -> int:
    """Checkpoint 2 under the default policy: approve as generated, protocol severity.

    A finding cannot be approved at `unassigned` (DEC-030), and the documents cannot supply a
    severity, so the policy assigns `medium` uniformly — the flattest choice, held constant
    across runs so severity judgment contributes no variance. Every decision here is defaulted
    by construction; the count keeps that visible.
    """
    from trace_ai.domain.enums import Severity
    from trace_ai.workflow.finding_review import (
        approve_finding,
        change_severity,
        conclude_finding_review,
    )

    handle = service.handle(assessment_id)
    defaulted = 0
    for finding in handle.objects.list(Finding):
        if finding.duplicate_of_id is not None:
            continue
        decided, _ = change_severity(
            handle, finding, Severity.MEDIUM, reviewer_id=STABILITY_REVIEWER
        )
        approve_finding(
            handle,
            decided,
            reviewer_id=STABILITY_REVIEWER,
            rationale="Stability protocol default (DEC-077): approved as generated.",
        )
        defaulted += 1
    conclude_finding_review(service, assessment_id)
    return defaulted


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
    from trace_ai.domain.source_observation import SourceObservation
    from trace_ai.services.evaluation.matching import (
        contradiction_resolved,
        partition_conditional,
    )

    reachable, conditional_unreached = partition_conditional(
        expected_findings,
        resolution_supplied=contradiction_resolved(handle.objects.list(SourceObservation)),
    )
    finding_matches: FindingMatchOutcome = match_findings(
        approved_findings(handle), reachable, component_names=component_names
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
            "conditional_unreached": conditional_unreached,
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
    defaulted_decisions: int = 0,
    models: Sequence[str] = (),
) -> Path:
    assessment = handle.objects.get(Assessment, handle.assessment_id)
    feed: dict[str, Any] = {
        "feed_version": FEED_VERSION,
        "scenario": entry.slug,
        "models": list(models),
        "condition": condition,
        "label": label,
        "assessment_id": assessment.id,
        "workflow_run_id": run.id,
        "run_status": run.status.value,
        "stopped_because": stopped_because,
        "ablations": list(run.ablations),
        "defaulted_decisions": defaulted_decisions,
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
