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

Two commands the roadmap names are deliberately absent. `trace context extract` and `trace context
show` need the Context Extraction agent, which does not exist; a stub that prints "not implemented"
is worse than a command that is not there, because `--help` would advertise it.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.source_document import SourceDocument, TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore, StoreError
from trace_ai.infrastructure.filesystem.artifact_store import DEFAULT_ROOT, ArtifactStoreError
from trace_ai.services.assessment import AssessmentService, AssessmentServiceError
from trace_ai.services.evidence.index import EvidenceIndex, EvidenceNotFoundError
from trace_ai.services.evidence.indexing import IndexingError, index_document
from trace_ai.services.ingestion.loader import DocumentLoader, DocumentLoadError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

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
    ValueError,
)


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
    reported = service.status(args.assessment_id)
    print(f"assessment:       {reported.assessment_id}")
    print(f"status:           {reported.status}")
    print(f"workflow run:     {reported.active_workflow_run_id or 'none'}")
    print(f"source documents: {reported.source_documents}")
    print(f"evidence:         {reported.evidence_references}")
    return 0


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
