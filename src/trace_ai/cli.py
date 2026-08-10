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

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.enums import ReviewDisposition, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import WorkflowRun
from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.domain.source_document import SourceDocument, TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore, StoreError
from trace_ai.infrastructure.filesystem.artifact_store import DEFAULT_ROOT, ArtifactStoreError
from trace_ai.infrastructure.model.factory import UnknownProviderError, build_model
from trace_ai.infrastructure.model.profiles import UnknownModelProfileError, resolve_profile
from trace_ai.services.assessment import AssessmentService, AssessmentServiceError
from trace_ai.services.context.pipeline import context_objects, run_context_slice
from trace_ai.services.context.review_file import (
    ReviewFileError,
    apply_review_file,
    read_review_file,
    write_review_file,
)
from trace_ai.services.evidence.index import EvidenceIndex, EvidenceNotFoundError
from trace_ai.services.evidence.indexing import IndexingError, index_document
from trace_ai.services.ingestion.loader import DocumentLoader, DocumentLoadError
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
from trace_ai.workflow.limits import LimitExceededError

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
# lying about what happened.
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
    review.add_argument("--reviewer", help="who the decisions are attributed to")
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
    approve.add_argument("--reviewer", help="who the approval is attributed to")
    approve.add_argument("--note", help="why the baseline was approved")

    return parser


def _path(value: str) -> Path:
    from pathlib import Path

    return Path(value).expanduser()


def run(argv: Sequence[str] | None = None) -> int:
    """Parse and dispatch. Returns the exit code rather than calling `sys.exit`, so tests can
    drive it directly."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.group is None:
        return _banner()
    if getattr(args, "command", None) is None:
        parser.parse_args([args.group, "--help"])
        return 2

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
    }
    handler = handlers[(args.group, args.command)]

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
    print("Hello from trace!")
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
            print(f"  {getattr(obj, 'id', '-')}  {_object_line(obj)}")

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
                f"{claim.predicate} = {claim.value!r}"
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
