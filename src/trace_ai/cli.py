"""The command line: the interface, not a development affordance.

DEC-032 settles what this is. Through M4 the command line is how a reviewer uses Trace, including
both human checkpoints, and a read-only local view may follow in Stage 5 for the demonstration.
`argparse` from the standard library, no dependency — the entry states the trigger for revisiting
that, which is command count or help quality rather than preference.

**Every command calls a service.** This module parses arguments, formats output, and sets an exit
code. It contains no ingestion, no indexing, and no analysis: `current-architecture.md` section 5.2
puts that in the application service, and a CLI that grew logic would become a second place where
the pipeline lives.

**Source-derived text is printed only where it was asked for.** `evidence show` prints a quotation
because that is the command's entire purpose. Nothing else prints document content, and no command
prints an absolute path from the artifact store — a path is not useful to a reviewer and is the one
piece of output that describes the machine rather than the assessment.

**The context group is the checkpoint's interface.** `roadmap.md` Stage 2 permits the first review
experience to be command line based or to use structured files, and it is both: `context review`
takes flags for a decision or two and exports an editable file for a real review. Both write the
same `ReviewerDecision` rows, because both call the same functions.

**Exit codes are answers.** A refused approval exits non-zero and names what is outstanding, so an
evaluation script can act on it without parsing prose. `context show` exits non-zero when the
context is not approvable, for the same reason.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

from trace_ai.config import MissingSettingError
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.enums import ReviewDisposition, Severity, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import RunStatus, WorkflowRun
from trace_ai.domain.finding import Finding
from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.domain.source_document import SourceDocument, TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore, StoreError
from trace_ai.infrastructure.filesystem.artifact_store import DEFAULT_ROOT, ArtifactStoreError
from trace_ai.infrastructure.model.factory import UnknownProviderError, build_model
from trace_ai.infrastructure.model.fake import ResponsesExhaustedError
from trace_ai.infrastructure.model.profiles import UnknownModelProfileError, resolve_profile
from trace_ai.infrastructure.model.recorded import load_recorded_responses
from trace_ai.services.assessment import AssessmentService, AssessmentServiceError
from trace_ai.services.context.pipeline import context_objects, run_context_slice
from trace_ai.services.context.review_file import (
    ReviewFileError,
    apply_review_file,
    read_review_file,
    write_review_file,
)
from trace_ai.services.driver import resume_assessment, run_assessment
from trace_ai.services.evidence.index import EvidenceIndex, EvidenceNotFoundError
from trace_ai.services.evidence.indexing import IndexingError, index_document
from trace_ai.services.findings.review_package import (
    build_finding_review_package,
    render_markdown,
)
from trace_ai.services.ingestion.loader import DocumentLoader, DocumentLoadError
from trace_ai.services.verification import verify_assessment
from trace_ai.workflow.checkpoint import load_state
from trace_ai.workflow.context_review import (
    ApprovalRefusedError,
    ReviewerActionError,
    answer_question,
    approve_context,
    build_context_review_package,
    confirm_assumption,
    current_system_context,
    decide_object,
    request_re_extraction,
)
from trace_ai.workflow.context_validation import validate_context
from trace_ai.workflow.errors import WorkflowError
from trace_ai.workflow.finding_review import (
    approve_finding,
    change_severity,
    conclude_finding_review,
    edit_finding,
    reject_finding,
)
from trace_ai.workflow.limits import LimitExceededError
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.workflow.context_review import ContextReviewPackage
    from trace_ai.workflow.state import PendingHumanReview

__all__ = ["build_parser", "main", "run"]

# The default threat methodology and model profile a created assessment carries. Both are
# `AssessmentConfiguration` fields with no default (section 6 marks them required), so the CLI
# states them rather than leaving a reviewer to supply strings they have no basis to choose.
DEFAULT_MODEL_PROFILE = "primary-development"
DEFAULT_THREAT_METHODOLOGY = "stride-scenario-based"

# Errors the services raise by name. These become a message and a non-zero exit code; anything
# else is a bug and keeps its traceback, because hiding an unexpected failure is how a tool starts
# lying about what happened. `MissingSettingError` and `ResponsesExhaustedError` are the two an
# operator causes from the command line — an unset provider key, and fewer `--response` files than
# the run makes model calls — so both are answered in a sentence rather than a traceback.
EXPECTED_ERRORS = (
    AssessmentServiceError,
    DocumentLoadError,
    IndexingError,
    EvidenceNotFoundError,
    ArtifactStoreError,
    StoreError,
    ReviewFileError,
    ReviewerActionError,
    UnknownModelProfileError,
    UnknownProviderError,
    WorkflowError,
    LimitExceededError,
    MissingSettingError,
    ResponsesExhaustedError,
    FileNotFoundError,
    ValueError,
)


# Who a decision is attributed to when nobody says. DEC-023: a configured local string defaulting
# to the operating-system username, recorded so evaluation can attribute decisions when more than
# one person reviews the same benchmark. It is not authentication and must not be read as one.
def _default_reviewer() -> str:
    import getpass

    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def build_parser() -> argparse.ArgumentParser:
    """The command surface DEC-032 confirms.

    `context extract` and `context show` are absent rather than stubbed: `--help` is a promise.
    """
    parser = argparse.ArgumentParser(
        prog="trace",
        description="Context-aware security architecture analysis.",
    )
    parser.add_argument(
        "--data-root",
        type=_path,
        default=DEFAULT_ROOT,
        help="where assessments are stored (default: the repository's data directory)",
    )
    commands = parser.add_subparsers(dest="group")

    assessment = commands.add_parser("assessment", help="create and inspect assessments")
    assessment_commands = assessment.add_subparsers(dest="command")

    created = assessment_commands.add_parser("create", help="create an assessment")
    created.add_argument("--name", required=True)
    created.add_argument("--description")
    created.add_argument("--tag", action="append", dest="tags", default=[])

    assessment_commands.add_parser("list", help="list assessments")

    status = assessment_commands.add_parser("status", help="report an assessment's state")
    status.add_argument("assessment_id")

    archive = assessment_commands.add_parser("archive", help="retire an assessment")
    archive.add_argument("assessment_id")

    source = commands.add_parser("source", help="register and inspect source documents")
    source_commands = source.add_subparsers(dest="command")

    added = source_commands.add_parser("add", help="register a file or a directory")
    added.add_argument("assessment_id")
    added.add_argument("path", type=_path)
    added.add_argument(
        "--no-index",
        action="store_true",
        help="register without normalizing and indexing",
    )

    listed = source_commands.add_parser("list", help="list registered documents")
    listed.add_argument("assessment_id")

    evidence = commands.add_parser("evidence", help="inspect evidence references")
    evidence_commands = evidence.add_subparsers(dest="command")

    evidence_list = evidence_commands.add_parser("list", help="list evidence references")
    evidence_list.add_argument("assessment_id")
    evidence_list.add_argument("--source", dest="source_document_id")

    evidence_show = evidence_commands.add_parser("show", help="print one evidence reference")
    evidence_show.add_argument("evidence_id")
    evidence_show.add_argument("--assessment", dest="assessment_id", required=True)

    verify = evidence_commands.add_parser("verify", help="re-check evidence against its source")
    verify.add_argument("assessment_id")

    context = commands.add_parser("context", help="extract, review, and approve the context")
    context_commands = context.add_subparsers(dest="command")

    extract = context_commands.add_parser(
        "extract", help="extract and validate a context, then stop at the review checkpoint"
    )
    extract.add_argument("assessment_id")
    extract.add_argument(
        "--model-profile",
        default=DEFAULT_MODEL_PROFILE,
        help="the provider, model, and settings bundle to run with",
    )
    extract.add_argument(
        "--response",
        type=_path,
        help="a recorded extraction response to replay, for a run that reaches no provider",
    )
    extract.add_argument(
        "--max-model-calls",
        type=int,
        help="stop the run before exceeding this many model calls",
    )
    extract.add_argument("--max-cost", help="stop the run before exceeding this estimated cost")

    show = context_commands.add_parser(
        "show", help="print the review package for the pending checkpoint"
    )
    show.add_argument("assessment_id")
    show.add_argument(
        "--evidence",
        action="store_true",
        help="print the source excerpt behind each claim",
    )

    review = context_commands.add_parser("review", help="record reviewer decisions")
    review.add_argument("assessment_id")
    review.add_argument(
        "--reviewer",
        help="who the decisions are attributed to (default: the operating-system username)",
    )
    review.add_argument("--export", type=_path, help="write an editable review file to this path")
    review.add_argument("--apply", type=_path, help="apply an edited review file")
    review.add_argument("--approve", action="append", dest="approved", default=[], metavar="ID")
    review.add_argument("--reject", action="append", dest="rejected", default=[], metavar="ID")
    review.add_argument(
        "--confirm",
        action="append",
        dest="confirmed",
        default=[],
        metavar="ID",
        help="record a claim as user_confirmed",
    )
    review.add_argument(
        "--answer",
        action="append",
        dest="answers",
        default=[],
        metavar="ID=TEXT",
        help="answer an open question",
    )
    review.add_argument(
        "--request-re-extraction",
        dest="re_extraction",
        metavar="REASON",
        help="reject the extracted context and say what was wrong",
    )

    approve = context_commands.add_parser("approve", help="approve the context baseline")
    approve.add_argument("assessment_id")
    approve.add_argument(
        "--reviewer",
        help="who the approval is attributed to (default: the operating-system username)",
    )
    approve.add_argument("--note", help="why the baseline was approved")

    running = commands.add_parser(
        "run",
        help="run the pipeline until it pauses at a checkpoint or completes",
        description=(
            "Runs every phase the transition table names, in order, and stops where the table "
            "stops: at a checkpoint (exit 0, the run is paused and waiting for a person), at "
            "completion (exit 0), or at a classified error (exit 1). Pausing is stopping: the "
            "process exits and `trace resume` continues in a new one."
        ),
    )
    running.add_argument("assessment_id")
    _model_flags(running)

    resuming = commands.add_parser(
        "resume",
        help="resume a paused run in a new process",
        description=(
            "Loads the paused state, re-runs the checkpoint, and continues when every subject "
            "has a decision. With subjects still undecided the run pauses again, which is "
            "partial progress rather than an error."
        ),
    )
    resuming.add_argument("assessment_id")
    resuming.add_argument("--run", dest="workflow_run_id", help="a specific paused run")
    _model_flags(resuming)

    findings = commands.add_parser("findings", help="review and approve candidate findings")
    findings_commands = findings.add_subparsers(dest="command")

    findings_show = findings_commands.add_parser(
        "show", help="print the review package for the finding checkpoint"
    )
    findings_show.add_argument("assessment_id")

    findings_review = findings_commands.add_parser("review", help="record reviewer decisions")
    findings_review.add_argument("assessment_id")
    findings_review.add_argument(
        "--reviewer",
        help="who the decisions are attributed to (default: the operating-system username)",
    )
    findings_review.add_argument(
        "--severity",
        action="append",
        dest="severities",
        default=[],
        metavar="ID=LEVEL",
        help="assign a severity; the reviewer's to give and recorded as an edit (DEC-030)",
    )
    findings_review.add_argument(
        "--edit",
        action="append",
        nargs=2,
        dest="edits",
        default=[],
        metavar=("ID", "FIELD=VALUE"),
        help="change one field; validated in full and recorded with the delta (DEC-023)",
    )
    findings_review.add_argument(
        "--approve", action="append", dest="approved", default=[], metavar="ID"
    )
    findings_review.add_argument(
        "--reject", action="append", dest="rejected", default=[], metavar="ID"
    )
    findings_review.add_argument("--note", help="a rationale recorded with each decision")
    findings_review.add_argument(
        "--override-rationale",
        dest="override_rationale",
        help="approve past the deterministic gate, with the override recorded (DEC-055)",
    )

    findings_approve = findings_commands.add_parser(
        "approve", help="conclude the finding review once every finding is decided"
    )
    findings_approve.add_argument("assessment_id")

    evaluate = commands.add_parser(
        "evaluate",
        help="replay a registered benchmark scenario through the harness",
        description=(
            "Runs a scenario from benchmarks/scenarios.yaml through the ordinary pipeline, "
            "offline, from its committed recording (DEC-073). Metrics persist with the replayed "
            "assessment; a derived feed lands under benchmarks/results/, keyed by scenario, "
            "condition, and label. A scenario without a recording is refused by name."
        ),
    )
    evaluate.add_argument("scenario", nargs="?", help="a registered scenario slug")
    evaluate.add_argument(
        "--all",
        action="store_true",
        dest="all_scenarios",
        help="run every registered scenario that has a recording, naming the ones skipped",
    )
    evaluate.add_argument(
        "--condition",
        default="clean",
        help="the condition axis for the results feed (default: clean)",
    )
    evaluate.add_argument(
        "--baseline",
        choices=["generic", "structured"],
        help=(
            "score a single-pass baseline instead of the pipeline (DEC-074): one model call over "
            "the same documents, replayed from the scenario's recorded baseline response"
        ),
    )
    evaluate.add_argument(
        "--ablation-set",
        action="store_true",
        dest="ablation_set",
        help=(
            "run the authoritative pipeline and each section-14 ablation for one scenario, and "
            "report what each removed component changed (DEC-012)"
        ),
    )
    evaluate.add_argument(
        "--stability",
        type=int,
        metavar="N",
        help=(
            "run one scenario N times live and report per-metric variance and per-item agreement "
            "(DEC-077); refuses the offline profile, which would measure nothing"
        ),
    )
    evaluate.add_argument(
        "--model-profile",
        default="offline-fake",
        help="the model profile for a stability run (default: offline-fake, which it refuses)",
    )
    evaluate.add_argument(
        "--ablate",
        action="append",
        dest="ablations",
        default=[],
        metavar="NAME",
        help="apply an ablation (repeatable); the run is marked non-authoritative (DEC-012)",
    )
    evaluate.add_argument(
        "--label",
        default="local",
        help="the run's name in the results tree (default: local)",
    )
    evaluate.add_argument(
        "--work-root",
        type=_path,
        help="where the replayed assessment is written (default: a temporary directory)",
    )
    evaluate.add_argument(
        "--diff-against",
        dest="diff_against",
        metavar="LABEL",
        help="classify each expected item against a prior feed with this label (DEC-073)",
    )
    evaluate.add_argument(
        "--results-root",
        dest="results_root",
        type=_path,
        help="where the feed is written (default: benchmarks/results/)",
    )

    verify = commands.add_parser(
        "verify",
        help="re-hash stored documents and evidence, and check the report manifest",
        description=(
            "Walks the evidence chain: every stored document against its recorded hash, every "
            "evidence reference against its source, and the report manifest against the store. "
            "Exit 0 when everything verifies; exit 1 with each drift named — identifier, "
            "expected hash, found hash — and never the content that changed."
        ),
    )
    verify.add_argument("assessment_id")

    report = commands.add_parser("report", help="inspect the rendered report")
    report_commands = report.add_subparsers(dest="command")

    report_show = report_commands.add_parser("show", help="print the rendered report")
    report_show.add_argument("assessment_id")
    report_show.add_argument(
        "--manifest",
        action="store_true",
        help="print the report's manifest instead of the report",
    )

    return parser


def _model_flags(parser: argparse.ArgumentParser) -> None:
    """The flags every model-reaching run command shares."""
    parser.add_argument(
        "--model-profile",
        default=DEFAULT_MODEL_PROFILE,
        help="the provider, model, and settings bundle to run with",
    )
    parser.add_argument(
        "--response",
        action="append",
        dest="responses",
        default=[],
        type=_path,
        metavar="PATH",
        help=(
            "a recorded model response to replay, repeatable; files are consumed in the order "
            "given, one per model call the run makes"
        ),
    )
    parser.add_argument(
        "--max-model-calls",
        type=int,
        help="stop the run before exceeding this many model calls",
    )
    parser.add_argument("--max-cost", help="stop the run before exceeding this estimated cost")


def _path(value: str) -> Path:
    from pathlib import Path

    return Path(value).expanduser()


def run(argv: Sequence[str] | None = None) -> int:
    """Parse and dispatch. Returns the exit code rather than calling `sys.exit`, so tests can
    drive it directly."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        ("assessment", "create"): _assessment_create,
        ("assessment", "list"): _assessment_list,
        ("assessment", "status"): _assessment_status,
        ("assessment", "archive"): _assessment_archive,
        ("source", "add"): _source_add,
        ("source", "list"): _source_list,
        ("evidence", "list"): _evidence_list,
        ("evidence", "show"): _evidence_show,
        ("evidence", "verify"): _evidence_verify,
        ("context", "extract"): _context_extract,
        ("context", "show"): _context_show,
        ("context", "review"): _context_review,
        ("context", "approve"): _context_approve,
        ("run", None): _run,
        ("resume", None): _resume,
        ("verify", None): _verify,
        ("evaluate", None): _evaluate,
        ("findings", "show"): _findings_show,
        ("findings", "review"): _findings_review,
        ("findings", "approve"): _findings_approve,
        ("report", "show"): _report_show,
    }

    if args.group is None:
        return _banner()
    command = getattr(args, "command", None)
    if command is None and (args.group, None) not in handlers:
        parser.parse_args([args.group, "--help"])
        return 2
    handler = handlers[(args.group, command)]

    try:
        with AssessmentStore.at_root(args.data_root) as store:
            return handler(args, AssessmentService(store, artifact_root=args.data_root))
    except EXPECTED_ERRORS as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _banner() -> int:
    """The no-argument behaviour, unchanged: environment, log level, configured credentials.

    Credentials are reported as names only. `Settings` holds them as `SecretStr`, and printing one
    would defeat that at the last step.
    """
    from trace_ai import bootstrap

    settings = bootstrap()
    configured = [
        name.removesuffix("_api_key")
        for name in ("anthropic_api_key", "openai_api_key", "langsmith_api_key")
        if getattr(settings, name) is not None
    ]
    print("trace: context-aware security architecture analysis")
    print(f"env: {settings.app_env}  log level: {settings.log_level}")
    print(f"credentials configured: {', '.join(configured) if configured else 'none'}")
    return 0


def _assessment_create(args: argparse.Namespace, service: AssessmentService) -> int:
    assessment = service.create(
        args.name,
        default_configuration(DEFAULT_MODEL_PROFILE, DEFAULT_THREAT_METHODOLOGY),
        description=args.description,
        tags=list(args.tags),
    )
    print(assessment.id)
    return 0


def _assessment_list(args: argparse.Namespace, service: AssessmentService) -> int:
    assessments = service.list()
    if not assessments:
        print("no assessments")
        return 0
    for assessment in assessments:
        print(f"{assessment.id}  {assessment.status:<15} {assessment.name}")
    return 0


def _assessment_status(args: argparse.Namespace, service: AssessmentService) -> int:
    """The deliverable's lifecycle, the run's position, and what the run is waiting for.

    Three different things, printed as three (DEC-031). `Assessment.status` is the deliverable's
    lifecycle and never the pipeline's position; `WorkflowRun.status` is the pipeline's; and
    `pending_human_review` is what a paused run is waiting for. Collapsing any two of them is the
    mistake DEC-031 was written to undo.
    """
    reported = service.status(args.assessment_id)
    handle = service.handle(args.assessment_id)
    run = _latest_run(handle)

    # `Assessment.active_workflow_run_id` is not written by `start_run`, so the latest run stands
    # in for it. Reporting "none" next to "run status: paused" would be the two lines contradicting
    # each other, and the run is the thing a reviewer needs the identifier of.
    active = reported.active_workflow_run_id or (run.id if run is not None else None)

    print(f"assessment:       {reported.assessment_id}")
    print(f"status:           {reported.status}")
    print(f"workflow run:     {active or 'none'}")
    print(f"source documents: {reported.source_documents}")
    print(f"evidence:         {reported.evidence_references}")

    if run is None:
        print("phase:            no workflow run has started")
        return 0

    print(f"run status:       {run.status}")
    print(f"phase:            {run.current_node or '-'}")
    print(f"model calls:      {run.total_model_calls}")
    print(
        f"input tokens:     {run.total_input_tokens if run.total_input_tokens is not None else '-'}"
    )
    print(
        f"output tokens:    {run.total_output_tokens if run.total_output_tokens is not None else '-'}"
    )
    print(f"estimated cost:   {run.estimated_cost if run.estimated_cost is not None else '-'}")

    pending = _pending_review(handle, run.id)
    if pending is None:
        print("checkpoint:       none pending")
        return 0
    print(f"checkpoint:       {pending.checkpoint_type.value}")
    print(f"awaiting:         {len(pending.object_ids)} object(s)")
    return 0


def _pending_review(handle: AssessmentHandle, workflow_run_id: str) -> PendingHumanReview | None:
    """What the persisted state says the run is waiting for, or nothing if it never paused.

    Read from the state file rather than inferred from the run: DEC-017 makes a paused run a
    complete record on disk, and inferring the answer from `current_node` would be a second place
    the same question is decided.
    """
    try:
        return load_state(handle, workflow_run_id).pending_human_review
    except FileNotFoundError:
        return None


def _assessment_archive(args: argparse.Namespace, service: AssessmentService) -> int:
    """The only status transition a person performs (DEC-031)."""
    archived = service.archive(args.assessment_id)
    print(f"{archived.id} {archived.status}")
    return 0


def _source_add(args: argparse.Namespace, service: AssessmentService) -> int:
    handle = service.handle(args.assessment_id)
    loader = DocumentLoader(handle)

    if args.path.is_dir():
        documents = loader.load_directory(
            args.path, origin=SourceOrigin.UPLOADED_DOCUMENT, trust_level=TrustLevel.UNTRUSTED
        )
    else:
        documents = [
            loader.load_document(
                args.path,
                origin=SourceOrigin.UPLOADED_DOCUMENT,
                trust_level=TrustLevel.UNTRUSTED,
            )
        ]

    references = 0
    if not args.no_index:
        for document in documents:
            references += len(index_document(handle, document))

    print(f"registered {len(documents)} document(s)")
    if not args.no_index:
        print(f"indexed {references} evidence reference(s)")
    return 0


def _source_list(args: argparse.Namespace, service: AssessmentService) -> int:
    handle = service.handle(args.assessment_id)
    documents = handle.objects.list(SourceDocument)
    if not documents:
        print("no source documents")
        return 0
    for document in documents:
        print(
            f"{document.id}  {document.ingestion_status:<11} "
            f"{document.media_type:<18} {document.filename}"
        )
    return 0


def _evidence_list(args: argparse.Namespace, service: AssessmentService) -> int:
    """Locations and titles, never quotations.

    A listing that printed source text would put document content on screen as a side effect of
    asking what exists, which is the distinction `evidence show` is for.
    """
    index = EvidenceIndex(service.handle(args.assessment_id))
    references = (
        index.for_document(args.source_document_id)
        if args.source_document_id
        else index.handle.objects.list(EvidenceReference)
    )
    if not references:
        print("no evidence references")
        return 0
    for reference in references:
        location = reference.section_title or reference.json_pointer or "-"
        print(
            f"{reference.id}  {reference.source_document_id}  "
            f"lines {reference.start_line}-{reference.end_line}  {location}"
        )
    return 0


def _evidence_show(args: argparse.Namespace, service: AssessmentService) -> int:
    index = EvidenceIndex(service.handle(args.assessment_id))
    (rendered,) = index.render_for_prompt([args.evidence_id])

    print(f"evidence:  {rendered['evidence_id']}")
    print(f"source:    {rendered['source_filename']}")
    location = rendered["location"]
    print(f"section:   {location['section_title'] or location.get('json_pointer') or '-'}")
    print(f"lines:     {location['start_line']}-{location['end_line']}")
    print(f"hash:      {rendered['content_hash']}")
    print()
    print(rendered["quoted_text"])
    return 0


def _evidence_verify(args: argparse.Namespace, service: AssessmentService) -> int:
    """Re-read every artifact and report what no longer matches."""
    failures = EvidenceIndex(service.handle(args.assessment_id)).verify_all()
    if not failures:
        print("all evidence verifies")
        return 0
    for failure in failures:
        print(f"{failure.evidence_id}  {failure.outcome}  {failure.detail or ''}".rstrip())
    print(f"{len(failures)} reference(s) no longer match", file=sys.stderr)
    return 1


def _evidence_type() -> type:
    from trace_ai.domain.evidence import EvidenceReference

    return EvidenceReference


def main() -> int:
    """The `trace` console entry point."""
    return run()


# ------------------------------------------------------------------------------------------
# The context slice
# ------------------------------------------------------------------------------------------


def _package_for(handle: AssessmentHandle) -> ContextReviewPackage:
    """The review package as it stands now, derived rather than read from anywhere (section 31)."""
    context = current_system_context(handle)
    validation = validate_context(
        context,
        context_objects(handle),
        available_evidence={reference.id for reference in handle.objects.list(EvidenceReference)},
    )
    return build_context_review_package(handle, index=EvidenceIndex(handle), validation=validation)


def _context_extract(args: argparse.Namespace, service: AssessmentService) -> int:
    """Run the extraction and validation nodes, and stop at the checkpoint.

    The whole run is `services/context/pipeline.py`'s: this reads flags, builds the model the
    profile names, and prints what came back. A CLI that composed the nodes itself would be a
    second place the pipeline lives.
    """
    from decimal import Decimal

    from trace_ai.workflow.limits import Budget

    handle = service.handle(args.assessment_id)
    assessment = service.get(args.assessment_id)
    profile = resolve_profile(args.model_profile)

    responses = []
    if args.response is not None:
        responses = [ContextExtractionProposal.model_validate_json(args.response.read_text())]

    budget = None
    if args.max_model_calls is not None or args.max_cost is not None:
        budget = Budget(
            maximum_model_calls=args.max_model_calls,
            maximum_cost=Decimal(args.max_cost) if args.max_cost else None,
        )

    outcome = run_context_slice(
        handle,
        model=build_model(profile, responses=responses),
        profile=profile,
        assessment_name=assessment.name,
        budget=budget,
    )

    counts = outcome.package.counts()
    print(f"workflow run:   {outcome.run.id}")
    print(f"paused at:      {outcome.paused_at.value}")
    print(f"context:        version {outcome.package.system_context.version}, unapproved")
    print(f"objects:        {len(outcome.produced_object_ids)} produced")
    print(
        f"claims:         {counts['documented_claims']} documented, "
        f"{counts['interpreted_claims']} inferred, assumed, unknown, or contradicted"
    )
    print(f"open questions: {counts['open_questions']} ({counts['blocking_questions']} blocking)")
    print(f"triggers:       {counts['triggers']}")
    print(f"model calls:    {outcome.run.total_model_calls}")
    if outcome.run.estimated_cost is not None:
        print(f"estimated cost: {outcome.run.estimated_cost}")
    print()
    print("Review it with `trace context show` and approve it with `trace context approve`.")
    return 0


def _context_show(args: argparse.Namespace, service: AssessmentService) -> int:
    """Print the review package, keeping documented facts apart from everything else.

    Excerpts are labelled `quoted untrusted source content` (`UNTRUSTED_LABEL`), so a reviewer
    meeting the ForgeFlow injection fixture meets it framed as data rather than as guidance. The
    text itself is verbatim: a reviewer judging whether a document instructs its reader has to see
    the instruction.
    """
    package = _package_for(service.handle(args.assessment_id))
    context = package.system_context

    print(f"system:   {context.system_name}")
    print(f"revision: version {context.version}, {'approved' if context.is_approved else 'draft'}")
    print(f"purpose:  {context.system_purpose or '-'}")

    for group, objects in package.objects_by_type.items():
        print()
        print(f"{group.replace('_', ' ')} ({len(objects)})")
        for obj in objects:
            object_id = getattr(obj, "id", "-")
            print(f"  {object_id}  {_object_line(obj)}{_reasons(package, object_id)}")

    for heading, presented in (
        ("documented claims", package.documented_claims),
        ("inferred, assumed, unknown, and contradicted claims", package.interpreted_claims),
    ):
        print()
        print(f"{heading} ({len(presented)})")
        for item in presented:
            claim = item.claim
            print(
                f"  {claim.id}  {claim.status:<15} {claim.confidence:<7} "
                f"{claim.predicate} = {claim.value!r}{_reasons(package, claim.id)}"
            )
            if claim.rationale:
                print(f"      rationale: {claim.rationale}")
            if args.evidence:
                for excerpt in item.excerpts:
                    print(_indent(excerpt.rendered(), "      "))

    print()
    print(f"open questions ({len(package.questions)})")
    for question in package.questions:
        marker = "blocking" if question.blocking else question.priority.value
        print(f"  {question.id}  {marker:<9} {question.question}")

    if package.injection_attempts:
        print()
        print(f"injection attempts detected ({len(package.injection_attempts)})")
        for observation in package.injection_attempts:
            cited = ", ".join(observation.evidence_ids)
            print(f"  {observation.id}  {observation.summary} [{cited}]")

    print()
    print(f"human-review triggers ({len(package.triggers)})")
    for trigger in package.triggers:
        caused = ", ".join(trigger.object_ids) if trigger.object_ids else "-"
        print(f"  {trigger.name}: {trigger.detail} [{caused}]")

    if package.outstanding_errors:
        print()
        print(f"outstanding validation errors ({len(package.outstanding_errors)})")
        for error in package.outstanding_errors:
            print(f"  {error.object_id}.{error.field}: {error.message}")

    print()
    if package.can_approve:
        print("The context is ready to approve.")
        return 0
    print("The context cannot be approved yet:", file=sys.stderr)
    for blocker in package.approval_blockers:
        print(f"  {blocker}", file=sys.stderr)
    return 1


def _reasons(package: ContextReviewPackage, object_id: str) -> str:
    """The routing reasons for one subject, appended to its line (DEC-062).

    A subject with an `injection_flag` came from a document that tried to inject; the reviewer
    sees the reason and looks closer. Reasons triage attention and never filter — every subject
    still needs a decision — so this only annotates, never hides.
    """
    codes = package.reasons_for(object_id)
    return f"  [{', '.join(codes)}]" if codes else ""


def _object_line(obj: object) -> str:
    """One object as a line: its name, its type term, and how it was sourced."""
    kind = next(
        (
            str(getattr(obj, field))
            for field in (
                "component_type",
                "actor_type",
                "asset_type",
                "boundary_type",
                "direction",
            )
            if hasattr(obj, field)
        ),
        "-",
    )
    origin = getattr(obj, "source_origin", None)
    suffix = "  (added by the reviewer)" if origin is not None and origin == "reviewer_edit" else ""
    return f"{kind:<26} {getattr(obj, 'name', '')}{suffix}"


def _indent(text: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def _context_review(args: argparse.Namespace, service: AssessmentService) -> int:
    """Record reviewer decisions, from flags or from an edited file.

    Both paths call the same functions in `workflow/context_review.py`, so a file and the
    equivalent flags write identical `ReviewerDecision` rows. The file exists because a reviewer
    with forty claims is not going to pass forty flags.
    """
    handle = service.handle(args.assessment_id)
    reviewer = args.reviewer or _default_reviewer()
    run = _latest_run(handle)
    run_id = run.id if run is not None else None

    if args.export is not None:
        args.export.write_text(write_review_file(_package_for(handle)), encoding="utf-8")
        print(f"wrote a review file for {handle.assessment_id}")
        print("Edit it, then apply it with `trace context review --apply`.")
        return 0

    written = []

    if args.apply is not None:
        document = read_review_file(args.apply.read_text(encoding="utf-8"))
        reviewer = args.reviewer or document.get("reviewer") or _default_reviewer()
        written.extend(
            apply_review_file(handle, document, reviewer_id=reviewer, workflow_run_id=run_id)
        )

    lookup: dict[str, Any] = {obj.id: obj for obj in context_objects(handle)}  # type: ignore[attr-defined]
    from trace_ai.domain.question import Question

    questions: dict[str, Any] = {
        question.id: question for question in handle.objects.list(Question)
    }

    for identifier, disposition in (
        *[(item, ReviewDisposition.APPROVE) for item in args.approved],
        *[(item, ReviewDisposition.REJECT) for item in args.rejected],
    ):
        _, decision = decide_object(
            handle,
            _require(lookup, identifier, "an object in this assessment"),
            disposition,
            reviewer_id=reviewer,
            workflow_run_id=run_id,
        )
        written.append(decision)

    for identifier in args.confirmed:
        from trace_ai.domain.context_claim import ContextClaim

        claim = _require(lookup, identifier, "a claim in this assessment")
        if not isinstance(claim, ContextClaim):
            raise ValueError(f"{identifier} is not a claim, so there is nothing to confirm")
        _, decision = confirm_assumption(
            handle, claim, reviewer_id=reviewer, workflow_run_id=run_id
        )
        written.append(decision)

    for pair in args.answers:
        identifier, separator, response = pair.partition("=")
        if not separator:
            raise ValueError(f"--answer takes ID=TEXT; {pair!r} has no '='")
        _, decision = answer_question(
            handle,
            _require(questions, identifier.strip(), "an open question"),
            response=response.strip(),
            reviewer_id=reviewer,
            workflow_run_id=run_id,
        )
        written.append(decision)

    if args.re_extraction:
        written.append(
            request_re_extraction(
                handle,
                _package_for(handle),
                reviewer_id=reviewer,
                rationale=args.re_extraction,
                workflow_run_id=run_id,
            )
        )

    if not written:
        print("no decisions recorded")
        return 0

    for decision in written:
        print(f"{decision.id}  {decision.disposition:<22} {decision.subject_id}")
    print(f"{len(written)} decision(s) recorded as {reviewer}")

    if args.re_extraction:
        print()
        print(
            "Re-extraction is the assessment's next workflow run, not a resumed one (DEC-038). "
            "Start it with `trace context extract`; the reason above is carried into it."
        )
    return 0


def _require(lookup: Mapping[str, Any], identifier: str, described_as: str) -> Any:
    found = lookup.get(identifier)
    if found is None:
        raise ValueError(f"{identifier} is not {described_as}")
    return found


def _context_approve(args: argparse.Namespace, service: AssessmentService) -> int:
    """Approve the baseline, or exit non-zero naming what is outstanding.

    The non-zero exit is what makes this usable from an evaluation script without parsing prose,
    and the refusal names every blocker rather than the first: a reviewer fixing a context wants
    the whole list.
    """
    handle = service.handle(args.assessment_id)
    run = _latest_run(handle)
    reviewer = args.reviewer or _default_reviewer()

    try:
        approved, decision = approve_context(
            handle,
            _package_for(handle),
            reviewer_id=reviewer,
            rationale=args.note,
            workflow_run_id=run.id if run is not None else None,
        )
    except ApprovalRefusedError as refused:
        print("the context was not approved:", file=sys.stderr)
        for blocker in refused.blockers:
            print(f"  {blocker}", file=sys.stderr)
        return 1

    print(f"approved version {approved.version} as {approved.approved_by}")
    print(f"decision:  {decision.id}")
    print(
        f"components {len(approved.component_ids)}  actors {len(approved.actor_ids)}  "
        f"assets {len(approved.asset_ids)}  flows {len(approved.data_flow_ids)}  "
        f"boundaries {len(approved.trust_boundary_ids)}  claims {len(approved.context_claim_ids)}"
    )
    return 0


def _latest_run(handle: AssessmentHandle) -> WorkflowRun | None:
    runs = handle.objects.list(WorkflowRun)
    return runs[-1] if runs else None


# ------------------------------------------------------------------------------------------
# The pipeline: run, resume, the finding checkpoint, and the report
# ------------------------------------------------------------------------------------------


def _budget_from(args: argparse.Namespace) -> Any:
    from decimal import Decimal

    from trace_ai.workflow.limits import Budget

    if args.max_model_calls is None and args.max_cost is None:
        return None
    return Budget(
        maximum_model_calls=args.max_model_calls,
        maximum_cost=Decimal(args.max_cost) if args.max_cost else None,
    )


def _run(args: argparse.Namespace, service: AssessmentService) -> int:
    """Run the pipeline from initialization until it pauses, completes, or stops.

    The run is `services/driver.py`'s; this reads flags, builds the model, and prints where the
    run got to. Exit codes are the documented ones: 0 for a pause or a completion (the table
    stopped the run where it says to stop), 1 for a failed run.
    """
    profile = resolve_profile(args.model_profile)
    outcome = run_assessment(
        service,
        args.assessment_id,
        model=build_model(profile, responses=load_recorded_responses(args.responses)),
        profile=profile,
        budget=_budget_from(args),
    )
    return _print_run_outcome(outcome)


def _resume(args: argparse.Namespace, service: AssessmentService) -> int:
    """Resume a paused run: the checkpoint re-runs, and decided subjects let it advance."""
    profile = resolve_profile(args.model_profile)
    outcome = resume_assessment(
        service,
        args.assessment_id,
        model=build_model(profile, responses=load_recorded_responses(args.responses)),
        profile=profile,
        workflow_run_id=args.workflow_run_id,
        budget=_budget_from(args),
    )
    return _print_run_outcome(outcome)


def _print_run_outcome(outcome: Any) -> int:
    state = outcome.state

    if state.status is RunStatus.FAILED:
        for recorded in state.errors:
            print(f"error: {recorded}", file=sys.stderr)
        print(
            f"run {state.workflow_run_id} failed at {state.current_phase.value} "
            f"({outcome.stopped_because})",
            file=sys.stderr,
        )
        return 1

    print(f"workflow run: {state.workflow_run_id}")
    if outcome.paused:
        pending = state.pending_human_review
        waiting = len(pending.object_ids) if pending is not None else 0
        print(f"paused at:    {state.current_phase.value}")
        print(f"awaiting:     {waiting} subject(s)")
        if state.current_phase is Phase.HUMAN_FINDING_REVIEW:
            print()
            print(
                "Review with `trace findings show` and `trace findings review`, conclude with "
                "`trace findings approve`, then continue with `trace resume`."
            )
        else:
            print()
            print(
                "Review with `trace context show` and `trace context review`, approve with "
                "`trace context approve`, then continue with `trace resume`."
            )
        return 0

    print("completed; the report and its manifest are in the assessment's outputs")
    print("Print the report with `trace report show`.")
    return 0


def _findings_show(args: argparse.Namespace, service: AssessmentService) -> int:
    """Print the checkpoint-2 review package, findings first, evidence excerpts labelled."""
    handle = service.handle(args.assessment_id)
    package = build_finding_review_package(handle, index=EvidenceIndex(handle))
    print(render_markdown(package))
    return 0


def _findings_review(args: argparse.Namespace, service: AssessmentService) -> int:
    """Record finding decisions: severity and edits first, then rejections, then approvals.

    The order inside one invocation is fixed so `--severity fnd-001=medium --approve fnd-001`
    means what it reads as: the severity lands before the approval gate checks it.
    """
    handle = service.handle(args.assessment_id)
    reviewer = args.reviewer or _default_reviewer()
    run = _latest_run(handle)
    run_id = run.id if run is not None else None
    findings = {finding.id: finding for finding in handle.objects.list(Finding)}
    decisions = []

    for entry in args.severities:
        identifier, separator, level = entry.partition("=")
        if not separator:
            raise ValueError(f"--severity takes ID=LEVEL, not {entry!r}")
        finding = _require(findings, identifier, "a finding in this assessment")
        updated, decision = change_severity(
            handle,
            finding,
            Severity(level),
            reviewer_id=reviewer,
            rationale=args.note,
            workflow_run_id=run_id,
        )
        findings[identifier] = updated
        decisions.append(decision)

    for identifier, assignment in args.edits:
        field, separator, value = assignment.partition("=")
        if not separator or not field:
            raise ValueError(f"--edit takes ID FIELD=VALUE, not {assignment!r}")
        finding = _require(findings, identifier, "a finding in this assessment")
        updated, decision = edit_finding(
            handle,
            finding,
            {field: value},
            reviewer_id=reviewer,
            rationale=args.note,
            workflow_run_id=run_id,
        )
        findings[identifier] = updated
        decisions.append(decision)

    for identifier in args.rejected:
        finding = _require(findings, identifier, "a finding in this assessment")
        updated, decision = reject_finding(
            handle, finding, reviewer_id=reviewer, rationale=args.note, workflow_run_id=run_id
        )
        findings[identifier] = updated
        decisions.append(decision)

    for identifier in args.approved:
        finding = _require(findings, identifier, "a finding in this assessment")
        updated, decision = approve_finding(
            handle,
            finding,
            reviewer_id=reviewer,
            rationale=args.note,
            override_rationale=args.override_rationale,
            workflow_run_id=run_id,
        )
        findings[identifier] = updated
        decisions.append(decision)

    if not decisions:
        print("no decisions recorded")
        return 0
    for decision in decisions:
        print(f"{decision.id}  {decision.disposition:<22} {decision.subject_id}")
    print(f"{len(decisions)} decision(s) recorded as {reviewer}")
    return 0


def _findings_approve(args: argparse.Namespace, service: AssessmentService) -> int:
    """Conclude the finding review, or exit non-zero naming the findings still undecided."""
    assessment = conclude_finding_review(service, args.assessment_id)
    print(f"finding review concluded; assessment {assessment.id} is {assessment.status.value}")
    print("Continue the run with `trace resume`.")
    return 0


def _verify(args: argparse.Namespace, service: AssessmentService) -> int:
    """Walk the evidence chain and exit non-zero on any drift, each one named.

    The walk is `services/verification.py`'s; nothing here reads a file or computes a hash. A
    drift line carries identifiers and hashes only — the changed content is exactly what must not
    be printed.
    """
    outcome = verify_assessment(service.handle(args.assessment_id))

    if outcome.ok:
        manifest = "1 manifest" if outcome.manifest_checked else "no manifest yet"
        print(
            f"verified: {outcome.document_count} document(s), "
            f"{outcome.evidence_count} evidence reference(s), {manifest}"
        )
        return 0

    for drift in outcome.document_drift:
        print(f"  {drift.line()}", file=sys.stderr)
    for failure in outcome.evidence_failures:
        print(
            f"  {failure.evidence_id}  {failure.outcome}  {failure.detail or ''}", file=sys.stderr
        )
    for drift in outcome.manifest_drift:
        print(f"  {drift.line()}", file=sys.stderr)
    total = (
        len(outcome.document_drift) + len(outcome.evidence_failures) + len(outcome.manifest_drift)
    )
    print(f"{total} item(s) no longer verify", file=sys.stderr)
    return 1


def _report_show(args: argparse.Namespace, service: AssessmentService) -> int:
    """Print the rendered report, or its manifest. Non-zero while no report exists."""
    assessment = service.get(args.assessment_id)
    if assessment.final_report_path is None:
        print(
            "error: no report has been rendered for this assessment; run the pipeline to "
            "completion first",
            file=sys.stderr,
        )
        return 1
    filename = assessment.final_report_path.rpartition("/")[2]
    if args.manifest:
        filename = filename.removesuffix(".md") + ".manifest.json"
    handle = service.handle(args.assessment_id)
    print(handle.artifacts.read("outputs", filename).decode("utf-8"))
    return 0


def _evaluate(args: argparse.Namespace, service: AssessmentService) -> int:
    """Replay one scenario, or every recorded one, through the evaluation harness.

    The harness opens its own store at the work root — a replayed assessment is a measurement,
    not part of the user's assessment data — and everything printed is metrics, identifiers, and
    repo-relative feed paths. Exit 0 when every attempted run completed; 1 when any did not.
    """
    import tempfile

    from trace_ai.config import PROJECT_ROOT
    from trace_ai.services.evaluation.harness import HarnessError, diff_feeds, run_scenario
    from trace_ai.services.evaluation.registry import load_registry

    if args.all_scenarios == bool(args.scenario):
        print("error: name one scenario or pass --all", file=sys.stderr)
        return 1

    if args.baseline is not None:
        if not args.scenario:
            print("error: --baseline scores one named scenario, not --all", file=sys.stderr)
            return 1
        return _evaluate_baseline(args)

    if args.ablation_set:
        if not args.scenario:
            print("error: --ablation-set runs one named scenario, not --all", file=sys.stderr)
            return 1
        return _evaluate_ablation_set(args)

    if args.stability is not None:
        if not args.scenario:
            print("error: --stability runs one named scenario, not --all", file=sys.stderr)
            return 1
        return _evaluate_stability(args)

    if args.all_scenarios:
        slugs = []
        for entry in load_registry():
            if entry.has_recording:
                slugs.append(entry.slug)
            else:
                print(f"skipped {entry.slug}: no recording")
    else:
        slugs = [args.scenario]

    failures = 0
    for slug in slugs:
        work_root = args.work_root or _path(tempfile.mkdtemp(prefix=f"trace-eval-{slug}-"))
        try:
            outcome = run_scenario(
                slug,
                data_root=work_root,
                label=args.label,
                condition=args.condition,
                ablations=args.ablations,
                results_root=args.results_root,
            )
        except HarnessError as refused:
            print(f"error: {refused}", file=sys.stderr)
            failures += 1
            continue

        print(f"scenario:     {outcome.scenario} ({outcome.condition}, label {outcome.label})")
        print(f"workflow run: {outcome.workflow_run_id}  {outcome.run_status}")
        if outcome.ablations:
            print(f"ablations:    {', '.join(outcome.ablations)} (non-authoritative, DEC-012)")
        for result in outcome.metrics:
            value = f"{result.metric_value:.4g}"
            print(f"  {result.metric_name:<32} {value}")
        if outcome.feed_path is not None:
            import json

            adversarial = json.loads(outcome.feed_path.read_text(encoding="utf-8")).get(
                "adversarial"
            )
            if adversarial is not None:
                rate = adversarial["injected_instruction_compliance_rate"]
                detected = "yes" if adversarial["attack_detected"] else "no"
                print(f"attack detected: {detected} (DEC-075)")
                print(f"  injected_instruction_compliance_rate  {rate:.4g} (target 0)")
                for payload in adversarial["payloads"]:
                    mark = "complied" if payload["complied"] else "resisted"
                    print(f"  {payload['payload_class']:<32} {mark}")
            feed = outcome.feed_path
            if feed.is_relative_to(PROJECT_ROOT):
                feed = feed.relative_to(PROJECT_ROOT)
            print(f"feed:         {feed}")
        if not outcome.completed:
            print(f"run stopped: {outcome.stopped_because}", file=sys.stderr)
            failures += 1

        if args.diff_against and outcome.feed_path is not None:
            prior = outcome.feed_path.with_name(f"{args.diff_against}.json")
            diff = diff_feeds(outcome.feed_path, prior)
            print(f"diff against {args.diff_against}:")
            for label, keys in (
                ("matched", diff.matched),
                ("changed", diff.changed),
                ("missed", diff.missed),
                ("regressed", diff.regressed),
                ("recovered", diff.recovered),
                ("spurious", diff.spurious),
                ("new spurious", diff.new_spurious),
            ):
                print(f"  {label:<13} {', '.join(keys) if keys else '-'}")
        print()

    return 1 if failures else 0


def _evaluate_baseline(args: argparse.Namespace) -> int:
    """Score a single-pass baseline over one scenario, replayed from its recorded response.

    The baseline is a measurement, not an assessment: it opens no store, prints metrics and the
    feed path only, and its feed is marked non-authoritative. Exit 1 when the scored scenario has
    no baseline recording or no truth set, so a comparison cannot silently score nothing.
    """
    from trace_ai.config import PROJECT_ROOT
    from trace_ai.domain.proposals.baseline import BaselineFindings
    from trace_ai.services.evaluation.baselines import BaselineError, run_baseline
    from trace_ai.services.evaluation.registry import scenario as load_scenario

    condition = f"baseline-{args.baseline}"
    entry = load_scenario(args.scenario)
    recording = entry.recorded_dir / "baselines" / f"{condition}.json"
    if not recording.is_file():
        print(
            f"error: scenario {args.scenario!r} has no recorded {condition} response at "
            f"{recording.relative_to(PROJECT_ROOT)}",
            file=sys.stderr,
        )
        return 1
    response = BaselineFindings.model_validate_json(recording.read_text(encoding="utf-8"))

    try:
        outcome = run_baseline(
            args.scenario,
            condition,
            label=args.label,
            response=response,
            results_root=args.results_root,
        )
    except BaselineError as refused:
        print(f"error: {refused}", file=sys.stderr)
        return 1

    print(f"scenario:     {outcome.scenario} ({outcome.baseline}, label {outcome.label})")
    print(f"schema valid: {outcome.schema_valid}")
    print(f"  false_negative_rate              {outcome.metrics['false_negative_rate']:.4g}")
    print(f"  spurious_finding_count           {int(outcome.metrics['spurious_finding_count'])}")
    if outcome.spurious:
        print("spurious (findings the truth set does not expect):")
        for spurious in outcome.spurious:
            print(
                f"  {spurious['requirement_id']}  {spurious['affected_component']}: {spurious['title']}"
            )
    if outcome.feed_path is not None:
        feed = outcome.feed_path
        if feed.is_relative_to(PROJECT_ROOT):
            feed = feed.relative_to(PROJECT_ROOT)
        print(f"feed:         {feed}")
    return 0


def _evaluate_ablation_set(args: argparse.Namespace) -> int:
    """Run the ablation set for one scenario and report what each removal changed."""
    import tempfile

    from trace_ai.services.evaluation.harness import HarnessError
    from trace_ai.services.evaluation.stability import ABLATION_SET, run_ablation_set

    work_root = args.work_root or _path(tempfile.mkdtemp(prefix=f"trace-ablate-{args.scenario}-"))
    try:
        comparison = run_ablation_set(
            args.scenario,
            data_root=work_root,
            label=args.label,
            results_root=args.results_root,
        )
    except HarnessError as refused:
        print(f"error: {refused}", file=sys.stderr)
        return 1

    metrics = sorted(comparison.authoritative)
    print(f"scenario:     {comparison.scenario} (ablation set, label {comparison.label})")
    print("authoritative (DEC-012 baseline):")
    for metric in metrics:
        print(f"  {metric:<32} {comparison.authoritative[metric]:.4g}")
    for ablation in ABLATION_SET:
        print(f"{ablation} (non-authoritative):")
        for metric in metrics:
            delta = comparison.delta(ablation, metric)
            shown = "-" if delta is None else f"{delta:+.4g}"
            value = comparison.ablations.get(ablation, {}).get(metric)
            value_shown = "-" if value is None else f"{value:.4g}"
            print(f"  {metric:<32} {value_shown:>8}  (delta {shown})")
    return 0


def _evaluate_stability(args: argparse.Namespace) -> int:
    """Run one scenario N times live and report variance; refuse the offline profile (DEC-077)."""
    import tempfile

    from trace_ai.services.evaluation.stability import StabilityError, run_stability

    work_root = args.work_root or _path(
        tempfile.mkdtemp(prefix=f"trace-stability-{args.scenario}-")
    )
    try:
        summary = run_stability(
            args.scenario,
            n=args.stability,
            data_root=work_root,
            label=args.label,
            profile_name=args.model_profile,
            results_root=args.results_root,
        )
    except StabilityError as refused:
        print(f"error: {refused}", file=sys.stderr)
        return 1

    print(f"scenario:     {summary.scenario} (stability, n={summary.n})")
    for metric in sorted(summary.metric_mean):
        print(
            f"  {metric:<32} mean {summary.metric_mean[metric]:.4g}  "
            f"stdev {summary.metric_stdev[metric]:.4g}"
        )
    print(f"unanimous items:  {', '.join(summary.unanimous) or '-'}")
    print(f"flickering items: {', '.join(summary.flickering) or '-'}")
    print(f"defaulted decisions: {summary.defaulted_decisions}")
    return 0
