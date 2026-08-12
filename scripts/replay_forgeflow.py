"""Replay the recorded ForgeFlow run end to end, offline, and check the report hash.

    uv run python scripts/replay_forgeflow.py

This is the repository's fastest verifiable claim: the whole pipeline — six agents, two human
checkpoints, deterministic rendering — re-runs from the committed recordings in
`demo/forgeflow/recorded/` with no provider, no key, and no network, and produces a report whose
content hash matches the one pinned in `report-hash.txt`. A reviewer who trusts nothing else can
trust this in about a minute.

The recorded reviewer decisions reach the workflow through the same writers an interactive
session uses (DEC-017): the context decisions are an exported review file applied verbatim, and
the finding decisions call the same severity and approval functions the CLI calls. Replay is not
an ablation — both checkpoints execute, their gates hold, and `ReviewerDecision` rows are
written (DEC-012).

Exit codes: 0 when the run completes and the hash matches; 1 when either is not true.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import Assessment, default_configuration
from trace_ai.domain.enums import ReviewDisposition, Severity, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
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

RECORDED = PROJECT_ROOT / "demo" / "forgeflow" / "recorded"
INPUT = PROJECT_ROOT / "demo" / "forgeflow" / "input"
REVIEWER = "recorded-reviewer"

# The recording's generation timestamp. Pinning it is what makes two replays byte-identical:
# the rendered report carries exactly one timestamp, and this is it.
GENERATED_AT = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


def _extraction_stage(service: AssessmentService, assessment_id: str, profile_name: str) -> None:
    profile = resolve_profile(profile_name)
    responses = load_recorded_responses([RECORDED / "01-context-extraction.json"])
    outcome = run_assessment(
        service,
        assessment_id,
        model=build_model(profile, responses=responses),
        profile=profile,
    )
    if not outcome.paused:
        raise SystemExit(f"expected a pause at checkpoint 1, got {outcome.stopped_because}")


def _context_decisions(service: AssessmentService, assessment_id: str) -> None:
    handle = service.handle(assessment_id)
    document = read_review_file((RECORDED / "decisions-context.yaml").read_text(encoding="utf-8"))
    apply_review_file(handle, document, reviewer_id=REVIEWER)
    validation = validate_context(
        current_system_context(handle),
        context_objects(handle),
        available_evidence={ref.id for ref in handle.objects.list(EvidenceReference)},
    )
    package = build_context_review_package(
        handle, index=EvidenceIndex(handle), validation=validation
    )
    approve_context(handle, package, reviewer_id=REVIEWER)


def _reasoning_stage(service: AssessmentService, assessment_id: str, profile_name: str) -> None:
    profile = resolve_profile(profile_name)
    responses = load_recorded_responses(
        [
            RECORDED / "02-threat-analysis.json",
            RECORDED / "03-mapping-thr-001.json",
            RECORDED / "04-mapping-thr-002.json",
            RECORDED / "05-evidence-validation.json",
            RECORDED / "06-critical-review-thr-001.json",
            RECORDED / "07-critical-review-thr-002.json",
        ]
    )
    outcome = resume_assessment(
        service,
        assessment_id,
        model=build_model(profile, responses=responses),
        profile=profile,
    )
    if not outcome.paused:
        raise SystemExit(f"expected a pause at checkpoint 2, got {outcome.stopped_because}")


def _finding_decisions(service: AssessmentService, assessment_id: str) -> None:
    handle = service.handle(assessment_id)
    recorded = yaml.safe_load((RECORDED / "decisions-findings.yaml").read_text(encoding="utf-8"))
    if recorded.get("assessment_id") != assessment_id:
        raise SystemExit(
            f"the recorded finding decisions are for {recorded.get('assessment_id')}, "
            f"not {assessment_id}"
        )
    findings = {finding.id: finding for finding in handle.objects.list(Finding)}
    for entry in recorded.get("findings", []):
        finding = findings[entry["id"]]
        if "severity" in entry:
            finding, _ = change_severity(
                handle, finding, Severity(entry["severity"]), reviewer_id=REVIEWER
            )
        if entry.get("decision") == ReviewDisposition.APPROVE.value:
            finding, _ = approve_finding(
                handle, finding, reviewer_id=REVIEWER, rationale=entry.get("rationale")
            )
        findings[finding.id] = finding
    conclude_finding_review(service, assessment_id)


def _report_stage(service: AssessmentService, assessment_id: str, profile_name: str) -> str:
    profile = resolve_profile(profile_name)
    responses = load_recorded_responses([RECORDED / "08-report-sections.json"])
    outcome = resume_assessment(
        service,
        assessment_id,
        model=build_model(profile, responses=responses),
        profile=profile,
        generated_at=GENERATED_AT,
    )
    if not outcome.completed:
        raise SystemExit(f"expected completion, got {outcome.stopped_because}")
    handle = service.handle(assessment_id)
    assessment = handle.objects.get(Assessment, assessment_id)
    if assessment.final_report_path is None:
        raise SystemExit("the run completed and no report path was recorded")
    filename = assessment.final_report_path.rpartition("/")[2]
    return handle.artifacts.hash_of("outputs", filename)


def replay(data_root: Path, *, profile_name: str = "offline-fake") -> str:
    """Run the whole recording against a fresh data root and return the report's content hash.

    Each stage opens its own store, the way a fresh process would (DEC-017: resuming is a read).
    """
    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        created = service.create(
            "ForgeFlow", default_configuration(profile_name, "stride-scenario-based")
        )
        assessment_id = created.id
        loader = DocumentLoader(service.handle(assessment_id))
        for path in sorted(INPUT.iterdir()):
            if path.is_file():
                loader.load_document(
                    path, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
                )
        _extraction_stage(service, assessment_id, profile_name)

    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        _context_decisions(service, assessment_id)
        _reasoning_stage(service, assessment_id, profile_name)

    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        _finding_decisions(service, assessment_id)
        return _report_stage(service, assessment_id, profile_name)


def pinned_hash() -> str:
    return (RECORDED / "report-hash.txt").read_text(encoding="utf-8").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="where the replayed assessment is written (default: a temporary directory)",
    )
    args = parser.parse_args(argv)

    data_root = args.data_root or Path(tempfile.mkdtemp(prefix="trace-replay-"))
    produced = replay(data_root)
    expected = pinned_hash()

    print(f"report hash: {produced}")
    if produced != expected:
        print(f"expected:    {expected}", file=sys.stderr)
        print("the replay no longer reproduces the recorded report", file=sys.stderr)
        return 1
    print("matches the pinned hash; the recorded run reproduces byte-for-byte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
