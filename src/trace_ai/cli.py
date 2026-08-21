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

**Exit codes are answers** (DEC-088). A script can branch on them without parsing prose: 0 is
success; 1 is an error the operator can fix, named in one line; 2 is argparse rejecting the
arguments; and 3 is a stated refusal that is an answer rather than a fault — a context not
approvable, an approval blocked, evidence or a report that drifted, a `reset` dry run. Code 1 and
code 3 are kept distinct precisely so "refused" and "crashed" are not the same signal, which is what
the old single non-zero code made them. `EXPECTED_ERRORS` names the failures rendered as a sentence
under code 1; anything else keeps its traceback, because hiding an unexpected failure is how a tool
starts lying about what happened.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from trace_ai.config import (
    IS_SOURCE_CHECKOUT,
    MissingSettingError,
    Settings,
    SourceCheckoutRequiredError,
)
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.enums import ReviewDisposition, RiskTreatment, Severity, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import RunStatus, WorkflowRun
from trace_ai.domain.finding import Finding
from trace_ai.domain.review_session import ReviewCheckpoint
from trace_ai.domain.source_document import IngestionStatus, SourceDocument, TrustLevel
from trace_ai.infrastructure.database.store import AssessmentStore, StoreError
from trace_ai.infrastructure.filesystem.artifact_store import DEFAULT_ROOT, ArtifactStoreError
from trace_ai.infrastructure.model.factory import UnknownProviderError, build_model
from trace_ai.infrastructure.model.fake import ResponsesExhaustedError
from trace_ai.infrastructure.model.journal import (
    JournalEntry,
    JournalingModel,
    JournalReplayModel,
    SpentJournalEntryError,
    journal_dir,
    read_journal_entry,
    spent_marker,
)
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
from trace_ai.services.evaluation.capture import CaptureRefusedError
from trace_ai.services.evaluation.report_metrics import RUBRIC_CATEGORIES, record_rubric
from trace_ai.services.evidence.index import EvidenceIndex, EvidenceNotFoundError
from trace_ai.services.evidence.indexing import IndexingError, index_document
from trace_ai.services.findings.review_file import (
    FindingReviewFileError,
    apply_finding_review_file,
    read_finding_review_file,
    write_finding_review_file,
)
from trace_ai.services.findings.review_package import (
    build_finding_review_package,
    render_markdown,
)
from trace_ai.services.ingestion.loader import DocumentLoader, DocumentLoadError
from trace_ai.services.requirements.loader import CatalogError
from trace_ai.services.review_timing import record_review_session
from trace_ai.services.verification import Drift, verify_assessment
from trace_ai.workflow.checkpoint import load_state
from trace_ai.workflow.context_review import (
    ApprovalRefusedError,
    ReviewerActionError,
    answer_question,
    approve_context,
    attach_evidence,
    build_context_review_package,
    confirm_assumption,
    current_system_context,
    decide_object,
    previous_approved_context,
    request_re_extraction,
    resolve_contradiction,
)
from trace_ai.workflow.context_validation import validate_context
from trace_ai.workflow.errors import WorkflowError
from trace_ai.workflow.finding_review import (
    approve_finding,
    assign_risk_treatment,
    change_severity,
    conclude_finding_review,
    defer_finding,
    edit_finding,
    reject_finding,
    request_more_analysis,
)
from trace_ai.workflow.limits import LimitExceededError
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from decimal import Decimal
    from pathlib import Path

    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.infrastructure.model.seam import StructuredModel
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.workflow.context_review import ContextReviewPackage
    from trace_ai.workflow.orchestrator import PhaseProgress
    from trace_ai.workflow.state import PendingHumanReview

__all__ = ["build_parser", "main", "run"]

# The default threat methodology and model profile a created assessment carries. Both are
# `AssessmentConfiguration` fields with no default (section 6 marks them required), so the CLI
# states them rather than leaving a reviewer to supply strings they have no basis to choose.
DEFAULT_MODEL_PROFILE = "primary-development"
DEFAULT_THREAT_METHODOLOGY = "stride-scenario-based"

# Exit codes are answers a script can act on without parsing prose (DEC-088):
#   0  the command did what it was asked
#   1  an error the operator can fix, named in one line (an EXPECTED_ERRORS failure)
#   2  argparse rejected the arguments (the standard-library convention)
#   3  a stated, expected refusal: a context not approvable, an approval blocked, evidence or a
#      report that drifted, a `reset` dry run. Not an error -- the answer to a yes/no question.
REFUSED = 3


class CommandInputError(ValueError):
    """An argument the CLI itself rejects: a malformed `ID=VALUE` pair, an unknown identifier, a
    value that is not one of the enum's, a file the operator named that cannot be read.

    A subclass of `ValueError` so the parsing helpers can raise it naturally. It exists to name the
    CLI's own input errors rather than conflate them with a bare `ValueError` from deep code, and to
    let the file-read and enum helpers turn an `OSError` or an enum's `ValueError` into a clean,
    one-line operator message.
    """


# Errors rendered as a message and a non-zero exit code rather than a traceback. `MissingSettingError`
# and `ResponsesExhaustedError` are the two an operator causes from the command line. `ValueError`
# stays because the domain raises it on an operator-supplied identifier (`parse_id`) and a few
# services raise it on operator input; `FileNotFoundError` stays for an operator-named path. What is
# *not* swallowed is a `pydantic.ValidationError` -- also a `ValueError` subclass -- from deep in the
# pipeline: DEC-006 says a domain object never fails validation, so one that does is a bug that keeps
# its traceback. The dispatch re-raises it explicitly, ahead of this tuple.
EXPECTED_ERRORS = (
    AssessmentServiceError,
    CatalogError,
    DocumentLoadError,
    IndexingError,
    EvidenceNotFoundError,
    ArtifactStoreError,
    StoreError,
    FindingReviewFileError,
    ReviewFileError,
    ReviewerActionError,
    UnknownModelProfileError,
    UnknownProviderError,
    WorkflowError,
    LimitExceededError,
    MissingSettingError,
    ResponsesExhaustedError,
    CommandInputError,
    FileNotFoundError,
    ValueError,
    # A write lock held past `busy_timeout` (a second `trace` process, or the view server beside a
    # run) surfaces as sqlite3.OperationalError; answer it as a message, not a traceback.
    sqlite3.Error,
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


def _json_flag(parser: argparse.ArgumentParser) -> None:
    """The DEC-096 flag every read command shares: the same information, machine-shaped."""
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help=(
            "print the same information as one JSON object (DEC-096), data_model_version "
            "stamped; quoted source content appears only where the human view prints it"
        ),
    )


def _print_json(kind: str, payload: Mapping[str, Any]) -> int:
    """One JSON object to stdout: the DEC-096 envelope.

    `kind` names what the object is, `data_model_version` says which schema generation shaped
    it, and the payload carries the same information the human view prints -- no more (a listing
    that dumped fields the human view withholds would put source content and storage paths on
    screen as a side effect of scripting).
    """
    import json

    from trace_ai.domain.assessment import DATA_MODEL_VERSION

    document = {"kind": kind, "data_model_version": DATA_MODEL_VERSION, **payload}
    print(json.dumps(document, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The command surface DEC-032 confirms.

    `--help` is a promise: every command listed here works today, and nothing is stubbed.
    """
    parser = argparse.ArgumentParser(
        prog="trace",
        description="Context-aware security architecture analysis.",
        epilog=(
            "Exit codes (DEC-088): 0 success; 1 an error the operator can fix, named in one line; "
            "2 argparse rejected the arguments; 3 a stated refusal that is an answer, not a fault -- "
            "a context not approvable, an approval blocked, evidence or a report that drifted, or a "
            "`reset` dry run. A script can branch on 3 without parsing prose."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    created.add_argument(
        "--catalog-version",
        dest="catalog_version",
        help=(
            "the requirements catalog version this assessment pins (DEC-010, DEC-098); "
            "default: the loader's current version"
        ),
    )

    assessment_list = assessment_commands.add_parser("list", help="list assessments")
    _json_flag(assessment_list)

    status = assessment_commands.add_parser("status", help="report an assessment's state")
    _json_flag(status)
    status.add_argument("assessment_id")

    candidates = assessment_commands.add_parser(
        "candidates", help="list catalog-gap candidates for the catalog owner"
    )
    candidates.add_argument("assessment_id")
    _json_flag(candidates)

    export = commands.add_parser("export", help="serialize approved objects to interop formats")
    export_commands = export.add_subparsers(dest="command")
    mermaid = export_commands.add_parser(
        "mermaid",
        help="serialize the approved architecture as a Mermaid DFD source",
        description=(
            "DEC-072's third serializer: the approved components, actors, data flows, and trust "
            "boundaries as one deterministic Mermaid flowchart -- never model-drawn, standalone "
            "in the assessment's outputs area, not embedded in the report. Refuses an assessment "
            "with no approved context."
        ),
    )
    mermaid.add_argument("assessment_id")

    sarif = export_commands.add_parser(
        "sarif",
        help="serialize approved findings as a SARIF 2.1.0 log",
        description=(
            "DEC-072's second serializer: approved findings as SARIF results levelled by the "
            'reviewer-assigned severity, documentation gaps as kind "review" at level '
            '"none" -- a gap asserts nothing about the implementation (DEC-009). Refuses an '
            "assessment with no approved context; writes to the assessment's outputs area."
        ),
    )
    sarif.add_argument("assessment_id")

    tm_bom = export_commands.add_parser(
        "tm-bom", help="export the approved model as a TM-BOM document (DEC-072)"
    )
    tm_bom.add_argument("assessment_id")

    archive = assessment_commands.add_parser("archive", help="retire an assessment")
    archive.add_argument("assessment_id")

    purge = assessment_commands.add_parser(
        "purge",
        help="delete one assessment entirely: every row and its whole directory (DEC-089)",
        description=(
            "Removes exactly one assessment -- its stored objects, its identifier counters, and its "
            "artifact directory -- where `reset` removes the whole data root. Destructive: without "
            "--force it prints what would go and removes nothing."
        ),
    )
    purge.add_argument("assessment_id")
    purge.add_argument(
        "--force", action="store_true", help="actually remove; without it, a dry run"
    )

    approve = assessment_commands.add_parser(
        "approve",
        help="sign off the completed deliverable (DEC-082)",
        description=(
            "Moves a completed assessment to approved: the person's statement that they have "
            "read the rendered report and stand behind it. Refused while no report exists, "
            "while the report's run is not completed, or when that run is non-authoritative "
            "(DEC-012) — approval is a sign-off, never a status setter."
        ),
    )
    approve.add_argument("assessment_id")

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

    add_repo = source_commands.add_parser(
        "add-repo",
        help="register a repository's readable files at a pinned commit, read-only (#597)",
    )
    add_repo.add_argument("assessment_id")
    add_repo.add_argument("url", help="https:// repository URL (file:// for local fixtures)")
    add_repo.add_argument(
        "commit", help="full forty-character commit SHA; a branch or tag is refused"
    )
    add_repo.add_argument(
        "--no-index",
        action="store_true",
        help="register without normalizing and indexing",
    )

    listed = source_commands.add_parser("list", help="list registered documents")
    _json_flag(listed)
    listed.add_argument("assessment_id")

    evidence = commands.add_parser("evidence", help="inspect evidence references")
    evidence_commands = evidence.add_subparsers(dest="command")

    evidence_list = evidence_commands.add_parser("list", help="list evidence references")
    _json_flag(evidence_list)
    evidence_list.add_argument("assessment_id")
    evidence_list.add_argument("--source", dest="source_document_id")

    evidence_show = evidence_commands.add_parser("show", help="print one evidence reference")
    _json_flag(evidence_show)
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
    # The same model flags as `run` and `resume`: one definition, so `--response` is repeatable and
    # expands a directory of numbered recordings the same way everywhere. Hand-rolling them here gave
    # `context extract` a singular `--response` that could not take the directory form the demo uses.
    _model_flags(extract)

    show = context_commands.add_parser(
        "show", help="print the review package for the pending checkpoint"
    )
    show.add_argument("assessment_id")
    show.add_argument(
        "--evidence",
        action="store_true",
        help="print the source excerpt behind each claim",
    )
    show.add_argument(
        "--observations",
        action="store_true",
        help=(
            "print only what the extraction observed about the documents themselves: "
            "injection attempts and contradictions awaiting resolution"
        ),
    )
    _json_flag(show)

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
        "--attach",
        action="append",
        dest="attachments",
        default=[],
        metavar="ID=EVD[,EVD...]",
        help="link existing evidence references to an object or claim",
    )
    review.add_argument(
        "--resolve",
        action="append",
        dest="resolutions",
        default=[],
        metavar="ID=VALUE",
        help="settle a contradiction observation with VALUE; requires --rationale",
    )
    review.add_argument(
        "--rationale",
        help="the reasoning recorded with --resolve (and, optionally, with --attach)",
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
    _json_flag(findings_show)

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
        "--treatment",
        action="append",
        dest="treatments",
        default=[],
        metavar="ID=VALUE",
        help=(
            "assign a risk treatment (undecided|mitigate|accept|transfer|avoid); the reviewer's "
            "to give and recorded as an edit (DEC-060)"
        ),
    )
    findings_review.add_argument(
        "--treatment-rationale",
        dest="treatment_rationale",
        help="the residual-risk statement; required to approve a finding treated as 'accept'",
    )
    findings_review.add_argument(
        "--treatment-review-by",
        dest="treatment_review_by",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="an optional date to revisit an accepted risk",
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
    findings_review.add_argument(
        "--defer",
        action="append",
        dest="deferred",
        default=[],
        metavar="ID",
        help="defer the decision; the finding stays a candidate and the deferral is the record",
    )
    findings_review.add_argument(
        "--request-more-analysis",
        action="append",
        dest="more_analysis",
        default=[],
        metavar="ID",
        help="ask for more analysis; requires --note saying what is missing (section 26)",
    )
    findings_review.add_argument(
        "--export", type=_path, help="write an editable review file to this path"
    )
    findings_review.add_argument(
        "--apply",
        type=_path,
        help=(
            "apply an edited review file; the file reaches every reviewer action — "
            "conversions, merges, rationale, and remediation included"
        ),
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
        choices=["generic", "structured", "single-pass"],
        help=(
            "score a prompt baseline instead of the pipeline (DEC-074): one model call over "
            "the same documents, replayed from the scenario's recorded baseline response; "
            "single-pass is the structural baseline — the whole assessment in one call"
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
        help=(
            "the model profile for a live run — one named scenario or --stability; the "
            "offline-fake default replays recordings and spends nothing"
        ),
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
        "--live-workflow-version",
        dest="live_workflow_version",
        metavar="VERSION",
        help=(
            "pin a live run to a named earlier workflow shape (DEC-134's experiment, #331); "
            "refused on a replay, whose version is the recording's fact"
        ),
    )
    evaluate.add_argument(
        "--replay-journal",
        action="append",
        dest="replay_journal",
        default=[],
        type=_path,
        metavar="PATH",
        help=(
            "re-drive an interrupted live harness run from its journal, repeatable; a directory "
            "stands for its unspent numbered entries in order. Live profiles only: a recording "
            "replay serves its own responses and takes no journal (DEC-139)"
        ),
    )
    evaluate.add_argument(
        "--results-root",
        dest="results_root",
        type=_path,
        help="where the feed is written (default: benchmarks/results/)",
    )
    evaluate.add_argument(
        "--report",
        choices=["scorecard", "comparison", "ablation"],
        help=(
            "run the offline sweep and render one evaluation page to stdout or --out (#505); "
            "the committed pages under docs/eval/ stay the build scripts' deliberate step"
        ),
    )
    evaluate.add_argument(
        "--out",
        type=_path,
        help="where --report writes the rendered page (default: stdout)",
    )
    _json_flag(evaluate)

    capture = commands.add_parser(
        "capture",
        help="capture a registered scenario's recording from a live model run",
        description=(
            "Runs one capture stage for a scenario from benchmarks/scenarios.yaml against the "
            "live provider, recording every response the run consumes into the scenario's "
            "capture/ staging directory (DEC-091). Checkpoint decisions are authored per capture, "
            "in the staging directory, from the files each stage exports; promotion into "
            "recorded/ is a deliberate copy after the replay round-trip is verified. Each stage "
            "spends real money and refuses to run twice; the refusal is exit code 3."
        ),
    )
    capture.add_argument("scenario", help="a registered scenario slug")
    capture.add_argument(
        "stage",
        choices=[
            "extract",
            "reason",
            "report",
            "baseline-generic",
            "baseline-structured",
            "baseline-single-pass",
        ],
        help=(
            "extract runs to checkpoint 1 and exports the review file; reason applies the "
            "authored context decisions and runs to checkpoint 2; report applies the authored "
            "finding decisions and runs to completion; baseline-generic and baseline-structured "
            "each make the one DEC-074 baseline call and stage its recording (DEC-100)"
        ),
    )
    capture.add_argument(
        "--from-recorded",
        action="store_true",
        dest="from_recorded",
        help="serve already-staged recordings before going live (resume an interrupted capture)",
    )
    capture.add_argument(
        "--model-profile",
        default=DEFAULT_MODEL_PROFILE,
        help="the provider, model, and settings bundle to capture with (the fake one is refused)",
    )
    capture.add_argument(
        "--rehearse",
        action="store_true",
        help=(
            "run the stage offline against the deterministic substitute serving --response "
            "recordings, staging into capture-rehearsal/ (#534); nothing staged can be promoted"
        ),
    )
    capture.add_argument(
        "--response",
        action="append",
        dest="responses",
        default=[],
        type=_path,
        metavar="PATH",
        help=(
            "a recorded response for --rehearse to serve, in consumption order; a directory "
            "stands for its numbered recordings, as with run --response"
        ),
    )

    verify = commands.add_parser(
        "verify",
        help="re-hash stored documents and evidence, and check the report manifest",
        description=(
            "Walks the evidence chain: every stored document against its recorded hash, every "
            "evidence reference against its source, and the report manifest against the store. "
            "Exit 0 when everything verifies; exit 3 with each drift named — identifier, "
            "expected hash, found hash — and never the content that changed."
        ),
    )
    verify.add_argument("assessment_id")
    _json_flag(verify)

    report = commands.add_parser("report", help="inspect the rendered report")
    report_commands = report.add_subparsers(dest="command")

    report_show = report_commands.add_parser("show", help="print the rendered report")
    report_show.add_argument("assessment_id")
    report_show.add_argument(
        "--manifest",
        action="store_true",
        help="print the report's manifest instead of the report",
    )
    _json_flag(report_show)

    report_render = report_commands.add_parser(
        "render",
        help="write the report in another format, derived from the Markdown deliverable",
        description=(
            "Converts the rendered Markdown report — the deliverable, unchanged (DEC-035) — "
            "into a derived presentation artifact in the assessment's outputs area (DEC-108). "
            "The transform is deterministic and escapes everything except the structure the "
            "renderer itself emits, so source-derived text cannot become markup."
        ),
    )
    report_render.add_argument("assessment_id")
    report_render.add_argument(
        "--format",
        choices=["html"],
        default="html",
        dest="render_format",
        help="the derived format (html is the only one)",
    )

    report_rubric = report_commands.add_parser(
        "rubric",
        help="record the reviewer rubric for the assessment's report",
        description=(
            "Records the evaluation plan's section 9 reviewer rubric: seven categories, each "
            "scored one to five by a person, all in one invocation so a stored rubric is never "
            "partial. Scores persist as evaluation results marked as reviewer judgement; no "
            "rubric value is ever computed (design-principles.md section 15)."
        ),
    )
    report_rubric.add_argument("assessment_id")
    report_rubric.add_argument(
        "--score",
        action="append",
        dest="scores",
        default=[],
        metavar="CATEGORY=N",
        help=(
            "one category scored one to five, repeatable; the seven categories are "
            + ", ".join(RUBRIC_CATEGORIES)
        ),
    )
    report_rubric.add_argument(
        "--comments",
        help="qualitative comments recorded with every rubric row",
    )
    report_rubric.add_argument(
        "--reviewer",
        help="who scored the report (default: the operating-system username, DEC-023)",
    )

    ledger = commands.add_parser(
        "ledger",
        help="print an assessment's per-run, per-node token and cost breakdown",
        description=(
            "Prints what the execution ledger recorded for each workflow run: one line per "
            "model-assisted node with its calls, the DEC-067 token spans kept disjoint (uncached "
            "input, cache reads, cache writes, output), duration, and estimated cost, and a "
            "total line per run. Absent means the provider reported nothing -- an offline replay "
            "of a recording without captured usage prints dashes, never zeros pretending to be "
            "measurements."
        ),
    )
    ledger.add_argument("assessment_id")
    _json_flag(ledger)

    threats = commands.add_parser(
        "threats",
        help="list an assessment's threats",
        description=(
            "Lists the threats the analysis proposed and validation accepted, with their "
            "categories and the components and assets each is grounded in. Threats were "
            "previously visible only through the report or the read-only view (#486)."
        ),
    )
    threats.add_argument("assessment_id")
    _json_flag(threats)

    questions = commands.add_parser(
        "questions",
        help="list an assessment's questions",
        description=(
            "Lists every question the assessment holds -- open and answered, blocking and not -- "
            "with its priority and status (#486)."
        ),
    )
    questions.add_argument("assessment_id")
    _json_flag(questions)

    catalog = commands.add_parser(
        "catalog",
        help="inspect and validate the requirements catalog",
        description=(
            "Reads the version-controlled requirements catalog through the one loader that may "
            "(DEC-010): the manifest and the files checked against each other, every requirement "
            "validated, the content hash recomputed. `show` lists requirements; `validate` loads "
            "and reports, exiting 1 with the loader's reason when the catalog does not verify."
        ),
    )
    catalog_commands = catalog.add_subparsers(dest="command")
    catalog_show = catalog_commands.add_parser("show", help="list a catalog version's requirements")
    catalog_show.add_argument(
        "--catalog-version",
        default="0.1",
        dest="catalog_version",
        help="the catalog version to read (default: 0.1)",
    )
    _json_flag(catalog_show)
    catalog_validate = catalog_commands.add_parser(
        "validate", help="load a catalog version and report what it holds"
    )
    catalog_validate.add_argument(
        "--catalog-version",
        default="0.1",
        dest="catalog_version",
        help="the catalog version to validate (default: 0.1)",
    )

    diff = commands.add_parser(
        "diff",
        help="compare two assessments' approved models",
        description=(
            "Compares two assessments of the same system (DEC-097): what was added, removed, or "
            "changed, per object family, with identity matched by content fingerprint rather "
            "than per-assessment identifiers. Both sides must hold an approved context. Threats "
            "and documentation gaps are compared by ground, never force-paired."
        ),
    )
    diff.add_argument("before", help="the earlier assessment's identifier")
    diff.add_argument("after", help="the later assessment's identifier")
    diff.add_argument(
        "--report",
        action="store_true",
        help=(
            "write the comparison as a Markdown report to the later assessment's outputs area "
            "(DEC-103, future-features 13.3) instead of printing the structural diff"
        ),
    )
    _json_flag(diff)

    runs_commands = commands.add_parser(
        "runs",
        help="workflow-run housekeeping",
    ).add_subparsers(dest="command", required=True)
    run_status = runs_commands.add_parser(
        "status",
        help="where a run is right now: status, phase, model calls, estimated cost (DEC-138)",
        description=(
            "Reports where a workflow run is from what the run already persists: the run row, "
            "the state file under traces/, and the execution records. A derived read for "
            "polling a run from outside the process driving it -- it writes nothing and holds "
            "no state of its own. The phase comes from the state file, which is written on "
            "every transition; a run still in its first phase has not written one yet, and the "
            "command says so rather than guessing."
        ),
    )
    run_status.add_argument("assessment_id", help="the assessment whose run to report")
    run_status.add_argument(
        "--run",
        dest="workflow_run_id",
        default=None,
        metavar="RUN_ID",
        help="a specific run's identifier; omitted, the latest run",
    )
    _json_flag(run_status)
    prune = runs_commands.add_parser(
        "prune",
        help="remove abandoned paused runs: superseded, or paused past a stated age "
        "(DEC-017 amendment)",
        description=(
            "A paused run nobody will resume accumulates forever (DEC-017). A run is abandoned "
            "when it is paused and a later run exists on the same assessment, or -- only when "
            "--older-than is stated -- when it started longer ago than that many days. Pruning "
            "removes the run row, its execution records, and its state file; the assessment, its "
            "objects, and its decisions stay. Completed and failed runs are never pruned. "
            "Destructive: without --force it lists what would go, removes nothing, and exits "
            "non-zero."
        ),
    )
    prune.add_argument(
        "assessment_id",
        nargs="?",
        default=None,
        help="limit to one assessment; omitted, the whole data root is examined",
    )
    prune.add_argument(
        "--older-than",
        type=int,
        default=None,
        metavar="DAYS",
        help="also treat a paused run started at least DAYS days ago as abandoned; "
        "without it, age alone abandons nothing",
    )
    prune.add_argument(
        "--force", action="store_true", help="actually remove; without it, a dry run"
    )
    repair = runs_commands.add_parser(
        "repair",
        help="mark an orphaned running run failed, on the operator's assertion (DEC-137)",
        description=(
            "A killed process leaves its run at `running` with no process behind it; `resume` "
            "refuses -- the run is neither paused nor failed -- and prune covers paused runs "
            "only. Repair marks the run failed with an error summary naming the external kill, "
            "and `trace resume` then restarts the failed phase. The assertion is the operator's: "
            "nothing checks a heartbeat or an age, because a running run that looks stale may be "
            "a slow provider call. Without --force it shows the run and changes nothing."
        ),
    )
    repair.add_argument("assessment_id")
    repair.add_argument("run_id", help="the run to repair; `trace assessment status` lists runs")
    repair.add_argument(
        "--reason",
        default=None,
        metavar="TEXT",
        help="what happened to the process, recorded in the run's error summary; "
        "omitted, the summary states an external kill",
    )
    repair.add_argument(
        "--force", action="store_true", help="actually mark it failed; without it, a dry run"
    )

    reset = commands.add_parser(
        "reset",
        help="return the data root to the fresh-clone state",
        description=(
            "Removes the assessment store and every assessment directory under the data root. "
            "Exists for the rerun problem: a second run against a used root mints asm-002 while "
            "every documented command names asm-001, so a rehearsal that was not wiped diverges "
            "from any script. Without --force it lists what would go and removes nothing, and a "
            "directory that does not look like a trace data root is refused outright."
        ),
    )
    reset.add_argument(
        "--force",
        action="store_true",
        help="actually remove; without it the command lists what would go and exits non-zero",
    )

    view = commands.add_parser(
        "view",
        help="serve a read-only local view of the assessments in the data root",
        description=(
            "Serves a read-only rendering of the persisted assessments on localhost for the "
            "Stage 5 demonstration (DEC-032): the overview, context, workflow, questions, "
            "findings, the finding-lineage walk, and the evaluation scorecard. It drives nothing "
            "-- review stays on the command line -- serves GET only, and binds to 127.0.0.1. "
            "Closing it loses nothing; everything it shows comes from the store."
        ),
    )
    view.add_argument(
        "--port",
        type=int,
        default=8765,
        help="the localhost port to serve on (default: 8765)",
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
            "given, one per model call the run makes. A directory stands for its numbered "
            "recordings in sorted order"
        ),
    )
    parser.add_argument(
        "--replay-journal",
        action="append",
        dest="replay_journal",
        default=[],
        type=_path,
        metavar="PATH",
        help=(
            "replay a live run's journaled response before spending, repeatable; a directory "
            "stands for its unspent numbered entries in order. An entry answers only the call "
            "that recorded it, exactly once — anything it cannot answer runs live (DEC-139)"
        ),
    )
    parser.add_argument(
        "--max-model-calls",
        type=_non_negative_int,
        help="stop the run before exceeding this many model calls",
    )
    parser.add_argument(
        "--max-cost",
        type=_decimal,
        help="stop the run before exceeding this estimated cost",
    )


def _path(value: str) -> Path:
    from pathlib import Path

    return Path(value).expanduser()


def _decimal(value: str) -> Decimal:
    """A non-negative estimated cost, rejected by argparse rather than deep in the run.

    `Decimal("abc")` raises `decimal.InvalidOperation` -- an `ArithmeticError`, not a `ValueError` --
    so an inline construction escaped `EXPECTED_ERRORS` as a traceback. As an argparse `type` it is
    exit 2 with a message, like `--max-model-calls` and `--treatment-review-by`.
    """
    from decimal import Decimal, InvalidOperation

    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"a cost ceiling cannot be negative: {value!r}")
    return parsed


def _non_negative_int(value: str) -> int:
    """A count ceiling: a whole number, not negative. `-1` model calls is not a limit."""
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number") from None
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"a ceiling cannot be negative: {value!r}")
    return parsed


def run(argv: Sequence[str] | None = None) -> int:
    """Parse and dispatch. Returns the exit code rather than calling `sys.exit`, so tests can
    drive it directly."""
    from trace_ai import bootstrap

    parser = build_parser()
    args = parser.parse_args(argv)

    # Once, before any command runs: load `.env` into `os.environ` for the provider SDKs, apply the
    # configured log level, and install the redaction filter. It used to run only for the banner, so
    # every real command -- `run`, `resume`, `evaluate`, the ones that actually process untrusted
    # source documents -- left third-party log output unfiltered and `.env` unloaded. The deferred
    # import mirrors `main`'s: `trace_ai.cli` is imported from within `trace_ai`, so a top-level
    # import here would be circular.
    settings = bootstrap()

    handlers = {
        ("assessment", "create"): _assessment_create,
        ("assessment", "list"): _assessment_list,
        ("assessment", "status"): _assessment_status,
        ("assessment", "candidates"): _assessment_candidates,
        ("assessment", "archive"): _assessment_archive,
        ("assessment", "purge"): _assessment_purge,
        ("assessment", "approve"): _assessment_approve,
        ("export", "tm-bom"): _export_tm_bom,
        ("export", "sarif"): _export_sarif,
        ("export", "mermaid"): _export_mermaid,
        ("source", "add"): _source_add,
        ("source", "add-repo"): _source_add_repo,
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
        ("report", "render"): _report_render,
        ("report", "rubric"): _report_rubric,
        ("ledger", None): _ledger,
        ("threats", None): _threats,
        ("questions", None): _questions,
        ("catalog", "show"): _catalog_show,
        ("catalog", "validate"): _catalog_validate,
        ("diff", None): _diff,
        ("runs", "status"): _runs_status,
        ("runs", "prune"): _runs_prune,
        ("runs", "repair"): _runs_repair,
    }

    if args.group is None:
        return _banner(settings)
    if not IS_SOURCE_CHECKOUT:
        # Every command past the banner reads a repository asset (a prompt, the catalog, the report
        # template) or the data root under the repo. v0.1 is clone-only (DEC-090); say so plainly
        # rather than let a dangling path fail deep in a command. `trace` and `trace --help` still
        # work from a wheel, which is what the packaging smoke test checks.
        print(f"error: {SourceCheckoutRequiredError()}", file=sys.stderr)
        return 1
    if args.group == "reset":
        # Before a store opens: `reset` removes the database, and `AssessmentStore.at_root`
        # would first recreate the thing it is about to delete.
        try:
            return _reset(args)
        except EXPECTED_ERRORS as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    if args.group == "view":
        # The view holds its store open for the server's lifetime; it opens its own rather than
        # borrowing the request-scoped one the dispatch below would close immediately.
        try:
            return _view(args)
        except EXPECTED_ERRORS as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    if args.group == "capture":
        # A capture owns its own data root (data/capture-<slug>), apart from the operator's
        # assessments, so it opens its own store rather than borrowing the request-scoped one.
        try:
            return _capture(args)
        except CaptureRefusedError as refusal:
            print(f"refused: {refusal}", file=sys.stderr)
            return REFUSED
        except EXPECTED_ERRORS as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    command = getattr(args, "command", None)
    if command is None and (args.group, None) not in handlers:
        parser.parse_args([args.group, "--help"])
        return 2
    handler = handlers[(args.group, command)]

    try:
        with AssessmentStore.at_root(args.data_root) as store:
            return handler(args, AssessmentService(store, artifact_root=args.data_root))
    except ValidationError:
        # A schema failure from the pipeline is a bug, not operator input: DEC-006 says a domain
        # object never fails validation, so one that does keeps its traceback rather than being
        # rendered as a one-line operator error. Caught ahead of EXPECTED_ERRORS because
        # ValidationError is a ValueError, which that tuple deliberately still catches.
        raise
    except EXPECTED_ERRORS as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _capture(args: argparse.Namespace) -> int:
    """Run one capture stage against the live provider, staging beside the scenario (#482).

    The whole capture is `services/evaluation/capture.py`'s: this reads flags, resolves the
    scenario through the registry, and dispatches the stage. The staging directory, the spend
    guards, and the decision flow are the service's — a CLI that composed them itself would be a
    second place the capture lives.
    """
    from trace_ai.services.evaluation import capture as capture_service
    from trace_ai.services.evaluation.registry import scenario as registered_scenario

    target = registered_scenario(args.scenario)
    rehearsal_model = None
    if args.rehearse:
        # The rehearsal's whole model: the deterministic substitute serving the supplied
        # recordings (#534). The service refuses a rehearsal with nothing to serve, and
        # rehearsal staging files are readable here because this is the rehearsal reading them.
        if args.stage.startswith("baseline-"):
            raise CommandInputError(
                "--rehearse covers the three pipeline stages; a baseline capture is one call "
                "and has no mechanics to rehearse"
            )
        from trace_ai.infrastructure.model.fake import DeterministicModel

        if not args.responses:
            raise CommandInputError(
                "a rehearsal runs the deterministic substitute; supply --response recordings "
                "for it to serve"
            )
        try:
            responses = load_recorded_responses(
                _response_files(args.responses), allow_rehearsal=True
            )
        except CommandInputError:
            raise
        except (OSError, ValueError) as error:
            raise CommandInputError(f"a recorded response could not be read: {error}") from None
        rehearsal_model = DeterministicModel(list(responses))
    elif args.responses:
        raise CommandInputError("--response is how --rehearse is fed; a live capture records")

    if args.stage == "extract":
        capture_service.stage_extract(
            target,
            profile_name=args.model_profile,
            from_recorded=args.from_recorded,
            live=rehearsal_model,
            rehearsal=args.rehearse,
            on_phase=_print_phase_progress,
        )
    elif args.stage == "reason":
        capture_service.stage_reason(
            target,
            profile_name=args.model_profile,
            from_recorded=args.from_recorded,
            live=rehearsal_model,
            rehearsal=args.rehearse,
            on_phase=_print_phase_progress,
        )
    elif args.stage == "report":
        capture_service.stage_report(
            target,
            profile_name=args.model_profile,
            live=rehearsal_model,
            rehearsal=args.rehearse,
            on_phase=_print_phase_progress,
        )
    else:
        capture_service.stage_baseline(
            target,
            baseline=args.stage.removeprefix("baseline-"),
            profile_name=args.model_profile,
        )
    return 0


def _banner(settings: Settings) -> int:
    """The no-argument behaviour: environment, log level, configured credentials.

    The process is already bootstrapped by `run`, so this receives the settings rather than
    reading them a second time. Credentials are reported as names only. `Settings` holds them as
    `SecretStr`, and printing one would defeat that at the last step.
    """
    configured = [
        name.removesuffix("_api_key")
        for name in ("anthropic_api_key", "openai_api_key")
        if getattr(settings, name) is not None
    ]
    print("trace: context-aware security architecture analysis")
    print(f"env: {settings.app_env}  log level: {settings.log_level}")
    print(f"credentials configured: {', '.join(configured) if configured else 'none'}")
    return 0


def _reset(args: argparse.Namespace) -> int:
    """Return the data root to the fresh-clone state, deliberately.

    Two refusals fail it closed: without `--force` it lists what would go and removes nothing,
    and a directory holding no store database is refused outright — the flag removes data, and
    pointed at the wrong directory it must do nothing at all. Entry names are printed rather
    than paths; `trace.db` and `asm-*` are the assessment's, not the machine's.
    """
    import shutil

    from trace_ai.infrastructure.database.store import DATABASE_FILENAME

    root: Path = args.data_root
    if not root.exists() or not any(root.iterdir()):
        print("nothing to reset: the data root is already fresh")
        return 0
    if not (root / DATABASE_FILENAME).is_file():
        raise CommandInputError(
            f"{root.name!r} holds no {DATABASE_FILENAME}, so it does not look like a trace "
            f"data root; refusing to remove anything"
        )

    entries = sorted(root.iterdir())
    if not args.force:
        print(f"would remove {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}:")
        for child in entries:
            print(f"  {child.name}")
        print("nothing was removed; pass --force to remove them", file=sys.stderr)
        return REFUSED

    for child in entries:
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    print(f"reset: removed {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")
    return 0


def _assessment_create(args: argparse.Namespace, service: AssessmentService) -> int:
    assessment = service.create(
        args.name,
        default_configuration(DEFAULT_MODEL_PROFILE, DEFAULT_THREAT_METHODOLOGY),
        description=args.description,
        tags=list(args.tags),
        requirements_catalog_version=args.catalog_version,
    )
    print(assessment.id)
    return 0


def _assessment_list(args: argparse.Namespace, service: AssessmentService) -> int:
    assessments = service.list()
    if args.as_json:
        return _print_json(
            "assessments",
            {
                "assessments": [
                    {"id": a.id, "status": str(a.status), "name": a.name} for a in assessments
                ]
            },
        )
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

    if args.as_json:
        payload: dict[str, Any] = {
            "assessment": {
                "id": reported.assessment_id,
                "status": str(reported.status),
                "workflow_run_id": active,
                "source_documents": reported.source_documents,
                "evidence_references": reported.evidence_references,
            },
            "run": None,
            "checkpoint": None,
        }
        if run is not None:
            payload["run"] = {
                "id": run.id,
                "status": str(run.status),
                "phase": run.current_node,
                "model_calls": run.total_model_calls,
                "input_tokens": run.total_input_tokens,
                "output_tokens": run.total_output_tokens,
                "estimated_cost": run.estimated_cost,
            }
            pending = _pending_review(handle, run.id)
            if pending is not None:
                payload["checkpoint"] = {
                    "type": pending.checkpoint_type.value,
                    "awaiting_object_ids": list(pending.object_ids),
                }
        return _print_json("assessment-status", payload)

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


def _ledger(args: argparse.Namespace, service: AssessmentService) -> int:
    """Per-run, per-node spend from the execution ledger (#483).

    Prints what the records already carry and computes nothing new: the DEC-067 token spans stay
    disjoint, and a field no record reported prints as a dash. Zero and absent are different
    answers — an offline replay of a recording without captured usage measured nothing, and
    printing 0 would claim it did.
    """
    from trace_ai.domain.execution import ExecutionRecord, ExecutionType

    handle = service.handle(args.assessment_id)
    runs = handle.objects.list(WorkflowRun)
    if not runs:
        print("no workflow run has started")
        return 0

    records_by_run: dict[str, list[ExecutionRecord]] = {}
    for record in handle.objects.list(ExecutionRecord):
        records_by_run.setdefault(record.workflow_run_id, []).append(record)

    if args.as_json:
        from decimal import Decimal

        def _sum(values: list[int | None]) -> int | None:
            reported = [value for value in values if value is not None]
            return sum(reported) if reported else None

        payload_runs = []
        for run in runs:
            model_records = [
                record
                for record in records_by_run.get(run.id, [])
                if record.execution_type is ExecutionType.MODEL
            ]
            grouped: dict[str, list[ExecutionRecord]] = {}
            for record in model_records:
                grouped.setdefault(record.node_name, []).append(record)
            payload_runs.append(
                {
                    "id": run.id,
                    "status": str(run.status),
                    "model_calls": run.total_model_calls,
                    "estimated_cost": run.estimated_cost,
                    "nodes": [
                        {
                            "node": name,
                            "calls": len(rows),
                            "input_tokens": _sum([r.input_tokens for r in rows]),
                            "cache_read_tokens": _sum([r.cache_read_tokens for r in rows]),
                            "cache_creation_tokens": _sum([r.cache_creation_tokens for r in rows]),
                            "output_tokens": _sum([r.output_tokens for r in rows]),
                            "duration_ms": _sum([r.duration_ms for r in rows]),
                            "estimated_cost": (
                                sum(
                                    (
                                        r.estimated_cost
                                        for r in rows
                                        if r.estimated_cost is not None
                                    ),
                                    start=Decimal(0),
                                )
                                if any(r.estimated_cost is not None for r in rows)
                                else None
                            ),
                        }
                        for name, rows in grouped.items()
                    ],
                }
            )
        return _print_json(
            "execution-ledger",
            {"assessment_id": args.assessment_id, "runs": payload_runs},
        )

    for run in runs:
        cost = run.estimated_cost if run.estimated_cost is not None else "-"
        print(f"run {run.id}  status: {run.status}  model calls: {run.total_model_calls}")
        model_records = [
            record
            for record in records_by_run.get(run.id, [])
            if record.execution_type is ExecutionType.MODEL
        ]
        if not model_records:
            print("  no model-assisted executions recorded")
            print()
            continue

        nodes: dict[str, list[ExecutionRecord]] = {}
        for record in model_records:
            nodes.setdefault(record.node_name, []).append(record)

        header = (
            f"  {'node':<28}{'calls':>6}{'input':>10}{'cache-read':>12}"
            f"{'cache-write':>13}{'output':>9}{'seconds':>9}  cost"
        )
        print(header)
        for name, rows in nodes.items():
            print(
                f"  {name:<28}{len(rows):>6}"
                f"{_summed(row.input_tokens for row in rows):>10}"
                f"{_summed(row.cache_read_tokens for row in rows):>12}"
                f"{_summed(row.cache_creation_tokens for row in rows):>13}"
                f"{_summed(row.output_tokens for row in rows):>9}"
                f"{_seconds(rows):>9}"
                f"  {_summed_cost(rows)}"
            )
        print(
            f"  {'total':<28}{len(model_records):>6}"
            f"{_summed(row.input_tokens for row in model_records):>10}"
            f"{_summed(row.cache_read_tokens for row in model_records):>12}"
            f"{_summed(row.cache_creation_tokens for row in model_records):>13}"
            f"{_summed(row.output_tokens for row in model_records):>9}"
            f"{_seconds(model_records):>9}"
            f"  {cost}"
        )
        print()
    return 0


def _summed(values: Iterable[int | None]) -> str:
    """The sum of the reported values, or a dash when nothing was reported.

    A mix sums what was reported: one measured record beside an unmeasured one is a partial
    measurement, which is still a measurement — the per-node lines say which rows carried it.
    """
    reported = [value for value in values if value is not None]
    return str(sum(reported)) if reported else "-"


def _summed_cost(rows: Sequence[Any]) -> str:
    from decimal import Decimal

    reported = [row.estimated_cost for row in rows if row.estimated_cost is not None]
    return str(sum(reported, start=Decimal(0))) if reported else "-"


def _seconds(rows: Sequence[Any]) -> str:
    reported = [row.duration_ms for row in rows if row.duration_ms is not None]
    return f"{sum(reported) / 1000:.1f}" if reported else "-"


def _threats(args: argparse.Namespace, service: AssessmentService) -> int:
    """List the threats the analysis produced, grounded objects named (#486)."""
    from trace_ai.domain.threat import Threat

    threats = service.handle(args.assessment_id).objects.list(Threat)
    if args.as_json:
        return _print_json(
            "threats",
            {
                "assessment_id": args.assessment_id,
                "threats": [threat.model_dump(mode="json") for threat in threats],
            },
        )
    if not threats:
        print("no threats")
        return 0
    for threat in threats:
        categories = ",".join(str(term) for term in threat.category) or "-"
        grounded = ", ".join([*threat.affected_component_ids, *threat.affected_asset_ids])
        print(f"{threat.id}  [{categories}]  {threat.title}  ({grounded})")
    return 0


def _questions(args: argparse.Namespace, service: AssessmentService) -> int:
    """List every question -- open and answered, blocking and not (#486)."""
    from trace_ai.domain.question import Question

    questions = service.handle(args.assessment_id).objects.list(Question)
    if args.as_json:
        return _print_json(
            "questions",
            {
                "assessment_id": args.assessment_id,
                "questions": [question.model_dump(mode="json") for question in questions],
            },
        )
    if not questions:
        print("no questions")
        return 0
    for question in questions:
        marker = "blocking" if question.blocking else str(question.priority)
        print(f"{question.id}  {question.status!s:<9} {marker:<9} {question.question}")
    return 0


def _catalog_show(args: argparse.Namespace, service: AssessmentService) -> int:
    """List a catalog version's requirements through the one loader that may (DEC-010)."""
    from trace_ai.services.requirements.loader import load_catalog

    loaded = load_catalog(args.catalog_version)
    if args.as_json:
        return _print_json(
            "requirements-catalog",
            {
                "catalog": loaded.catalog.model_dump(mode="json"),
                "requirements": [
                    requirement.model_dump(mode="json") for requirement in loaded.requirements
                ],
            },
        )
    print(f"catalog: {loaded.catalog.id} version {loaded.version}, {len(loaded)} requirements")
    for requirement in loaded.requirements:
        print(f"  {requirement.id}  {requirement.title}")
    return 0


def _catalog_validate(args: argparse.Namespace, service: AssessmentService) -> int:
    """Load a catalog version and report what it holds; the loader's refusals are the check."""
    from trace_ai.services.requirements.loader import load_catalog

    loaded = load_catalog(args.catalog_version)
    print(
        f"catalog {loaded.catalog.id} version {loaded.version} verifies: "
        f"{len(loaded)} requirements, content hash {loaded.catalog.content_hash}"
    )
    return 0


def _diff(args: argparse.Namespace, service: AssessmentService) -> int:
    """Compare two assessments' approved models (#488, DEC-097).

    Two scoped reads through two handles -- never a cross-assessment query -- and the
    conservative matching is `services/diff/`'s: this prints what came back.
    """
    from trace_ai.services.diff import diff_assessments, write_comparison_report
    from trace_ai.services.export import ExportError

    if args.report:
        try:
            written = write_comparison_report(
                service.handle(args.before), service.handle(args.after)
            )
        except ExportError as refused:
            print(f"error: {refused}", file=sys.stderr)
            return 1
        print(f"wrote {written.name} to {args.after}'s outputs area")
        return 0

    try:
        outcome = diff_assessments(service.handle(args.before), service.handle(args.after))
    except ExportError as refused:
        print(f"error: {refused}", file=sys.stderr)
        return 1

    if args.as_json:
        from dataclasses import asdict

        def _entries(entries: list[Any]) -> list[dict[str, Any]]:
            return [
                asdict(entry) | {"changed_fields": list(entry.changed_fields)} for entry in entries
            ]

        return _print_json(
            "assessment-diff",
            {
                "before": outcome.before,
                "after": outcome.after,
                "moved": outcome.moved,
                "families": {
                    name: {
                        "unchanged": family.unchanged,
                        "added": _entries(family.added),
                        "removed": _entries(family.removed),
                        "changed": _entries(family.changed),
                        "rename_candidates": [
                            asdict(candidate) for candidate in family.rename_candidates
                        ],
                    }
                    for name, family in outcome.families.items()
                },
                "resolution_shifts": [
                    asdict(shift) | {"requirement_ids": list(shift.requirement_ids)}
                    for shift in outcome.resolution_shifts
                ],
            },
        )

    print(f"diff: {outcome.before} -> {outcome.after}")
    if not outcome.moved:
        print("no differences in the approved models")
        return 0
    for name, family in outcome.families.items():
        if not family.moved:
            continue
        print()
        print(f"{name.replace('_', ' ')}  ({family.unchanged} unchanged)")
        for entry in family.added:
            print(f"  added    {entry.identity}  [{entry.after_id or '-'}]")
        for entry in family.removed:
            print(f"  removed  {entry.identity}  [{entry.before_id or '-'}]")
        for entry in family.changed:
            fields = ", ".join(entry.changed_fields)
            print(
                f"  changed  {entry.identity}  [{entry.before_id or '-'} -> "
                f"{entry.after_id or '-'}]  {fields}"
            )
        for candidate in family.rename_candidates:
            print(
                f"  rename?  {candidate.before_identity} -> {candidate.after_identity}  "
                f"[{candidate.before_id or '-'} -> {candidate.after_id or '-'}]  "
                f"(a candidate: same content, different name; the entries above stand)"
            )
    if outcome.resolution_shifts:
        print()
        print("resolution shifts  (the finding/gap distinction, moved)")
        for shift in outcome.resolution_shifts:
            arrow = "gap -> finding" if shift.direction == "gap_to_finding" else "finding -> gap"
            requirements = ", ".join(shift.requirement_ids)
            print(
                f"  {arrow}  {requirements}  on {shift.ground}  "
                f"[{shift.before_id or '-'} -> {shift.after_id or '-'}]"
            )
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


def _assessment_candidates(args: argparse.Namespace, service: AssessmentService) -> int:
    """The DEC-065 listing surface: catalog-gap candidates, for the catalog owner.

    Answers DEC-065's open question about a listing surface ahead of any aggregation: one
    assessment's candidates, read from the scoped repository. Cross-assessment assembly stays
    manual, which is the recorded tradeoff.
    """
    from trace_ai.domain.catalog_gap_candidate import CatalogGapCandidate

    handle = service.handle(args.assessment_id)
    candidates = handle.objects.list(CatalogGapCandidate)
    if args.as_json:
        return _print_json(
            "catalog-gap-candidates",
            {
                "assessment_id": args.assessment_id,
                "catalog_gap_candidates": [
                    candidate.model_dump(mode="json") for candidate in candidates
                ],
            },
        )
    if not candidates:
        print("no catalog-gap candidates")
        return 0

    print(
        f"{len(candidates)} catalog-gap candidate{'s' if len(candidates) != 1 else ''} "
        f"(DEC-065): concerns no requirement covers, raw material for the next catalog version. "
        f"None is a finding."
    )
    for candidate in candidates:
        print()
        print(f"{candidate.id}  [{candidate.suggested_category}]  {candidate.concern}")
        print(f"  raised by: {candidate.generated_by}")
        print(f"  evidence:  {', '.join(candidate.evidence_ids)}")
        for considered in candidate.nearest_requirements:
            print(f"  nearest:   {considered.requirement_id} — {considered.why_not}")
    return 0


def _export_mermaid(args: argparse.Namespace, service: AssessmentService) -> int:
    """DEC-072's third export: the approved architecture as a Mermaid DFD, to `outputs/`."""
    from trace_ai.services.export import ExportError, write_mermaid

    handle = service.handle(args.assessment_id)
    try:
        written = write_mermaid(handle)
    except ExportError as refused:
        print(f"error: {refused}", file=sys.stderr)
        return 1
    print(f"wrote {written.name} to the assessment's outputs area")
    return 0


def _export_sarif(args: argparse.Namespace, service: AssessmentService) -> int:
    """DEC-072's second export: approved findings as a SARIF log, to `outputs/` (#487)."""
    from trace_ai.services.export import ExportError, write_sarif

    handle = service.handle(args.assessment_id)
    try:
        written = write_sarif(handle)
    except ExportError as refused:
        print(f"error: {refused}", file=sys.stderr)
        return 1
    print(f"wrote {written.name} to the assessment's outputs area")
    return 0


def _export_tm_bom(args: argparse.Namespace, service: AssessmentService) -> int:
    """DEC-072's first export: approved objects as a TM-BOM document, to `outputs/`.

    The path is printed relative to the assessment's own area, per the output discipline: no
    absolute paths on screen.
    """
    from trace_ai.services.export import ExportError, write_tm_bom

    handle = service.handle(args.assessment_id)
    try:
        written = write_tm_bom(handle)
    except ExportError as refused:
        print(f"error: {refused}", file=sys.stderr)
        return 1
    print(f"wrote {written.name} to the assessment's outputs area")
    return 0


def _assessment_approve(args: argparse.Namespace, service: AssessmentService) -> int:
    """Sign off the deliverable. The service owns every refusal (DEC-082)."""
    assessment = service.approve(args.assessment_id)
    print(f"assessment {assessment.id} is {assessment.status.value}")
    return 0


def _assessment_archive(args: argparse.Namespace, service: AssessmentService) -> int:
    """The only status transition a person performs (DEC-031)."""
    archived = service.archive(args.assessment_id)
    print(f"{archived.id} {archived.status}")
    return 0


def _runs_status(args: argparse.Namespace, service: AssessmentService) -> int:
    """Report where a run is, from what the run already persists (DEC-138).

    Three sources, every one written by the run itself: the run row (status, timestamps, error
    summary), the state file under `traces/` (the phase, rewritten on every transition), and the
    execution records (model calls and estimated cost, computed exactly as the ledger computes
    them). The command stores nothing, so polling it cannot disagree with the run.
    """
    from trace_ai.services.execution_ledger import ExecutionLedger

    handle = service.handle(args.assessment_id)
    runs = handle.objects.list(WorkflowRun)
    if not runs:
        print(f"{args.assessment_id} has no workflow runs", file=sys.stderr)
        return 1
    if args.workflow_run_id is None:
        run = runs[-1]
    else:
        matches = [candidate for candidate in runs if candidate.id == args.workflow_run_id]
        if not matches:
            print(f"{args.assessment_id} has no run {args.workflow_run_id}", file=sys.stderr)
            return 1
        run = matches[0]

    counters = ExecutionLedger(handle, run).counters()
    order = list(Phase)
    phase = None
    awaiting = 0
    try:
        state = load_state(handle, run.id)
    except FileNotFoundError:
        # The state file is written on the first transition; a run still in its first phase has
        # not written one, and saying so beats inventing a phase the run never recorded.
        state = None
    if state is not None:
        phase = state.current_phase
        if state.pending_human_review is not None:
            awaiting = len(state.pending_human_review.object_ids)

    if args.as_json:
        return _print_json(
            "run-status",
            {
                "assessment_id": args.assessment_id,
                "workflow_run_id": run.id,
                "run_status": run.status.value,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "phase": phase.value if phase is not None else None,
                "phase_number": order.index(phase) + 1 if phase is not None else None,
                "phase_total": len(order),
                "model_calls": counters["total_model_calls"],
                "estimated_cost": counters["estimated_cost"],
                "awaiting_review": awaiting,
                "error_summary": run.error_summary,
            },
        )

    print(f"workflow run:   {run.id} (of {len(runs)} on {args.assessment_id})")
    print(f"status:         {run.status.value}")
    if run.started_at is not None:
        print(f"started:        {run.started_at.isoformat()}")
    if run.completed_at is not None:
        print(f"ended:          {run.completed_at.isoformat()}")
    if phase is not None:
        print(f"phase:          {phase.value} ({order.index(phase) + 1}/{len(order)})")
    else:
        print("phase:          not yet recorded (the run has not completed its first phase)")
    print(f"model calls:    {counters['total_model_calls']}")
    cost = counters["estimated_cost"]
    if cost is not None:
        print(f"estimated cost: ${cost}")
    else:
        print("estimated cost: none recorded")
    if awaiting:
        print(f"awaiting:       {awaiting} subject(s)")
    if run.error_summary:
        print(f"error:          {run.error_summary}")
    return 0


def _runs_prune(args: argparse.Namespace, service: AssessmentService) -> int:
    """Remove abandoned paused runs (DEC-017 amendment). A dry run without --force refuses."""
    from trace_ai.services.run_pruning import abandoned_runs, prune_runs

    targets = abandoned_runs(
        service, assessment_id=args.assessment_id, older_than_days=args.older_than
    )
    if not targets:
        print("no abandoned runs")
        return 0
    for target in targets:
        cost = "-" if target.estimated_cost is None else f"${target.estimated_cost}"
        state = "state file" if target.has_state_file else "no state file"
        print(
            f"{target.assessment_id}  {target.run_id}  {target.reason:<10}  "
            f"started {target.started_at_display}  "
            f"{target.execution_record_count} execution record(s)  {cost}  {state}"
        )
    if not args.force:
        print(
            f"nothing was removed; pass --force to remove {len(targets)} run(s)",
            file=sys.stderr,
        )
        return REFUSED
    result = prune_runs(service, targets)
    print(
        f"pruned {result.runs_removed} run(s): {result.execution_records_removed} execution "
        f"record(s), {result.state_files_removed} state file(s), recorded spend "
        f"${result.estimated_cost_removed} removed with them"
    )
    return 0


def _runs_repair(args: argparse.Namespace, service: AssessmentService) -> int:
    """Mark an orphaned running run failed (DEC-137). A dry run without --force refuses."""
    from trace_ai.services.run_repair import RunRepairError, describe_run, repair_run

    handle = service.handle(args.assessment_id)
    candidate = describe_run(handle, args.run_id)
    cost = "-" if candidate.estimated_cost is None else f"${candidate.estimated_cost}"
    print(
        f"{args.assessment_id}  {candidate.run_id}  {candidate.status:<10}  "
        f"started {candidate.started_at_display}  "
        f"{candidate.execution_record_count} execution record(s)  {cost}"
    )
    if not args.force:
        print(
            "nothing was changed; pass --force to mark it failed, asserting its process is gone",
            file=sys.stderr,
        )
        return REFUSED
    try:
        updated = repair_run(handle, args.run_id, reason=args.reason)
    except RunRepairError as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return REFUSED
    print(f"marked {updated.id} failed: {updated.error_summary}")
    print(f"Restart the failed phase with `trace resume {args.assessment_id}`.")
    return 0


def _assessment_purge(args: argparse.Namespace, service: AssessmentService) -> int:
    """Delete one assessment entirely (DEC-089). A dry run without --force is a stated refusal."""
    assessment = service.get(args.assessment_id)  # a message, not a traceback, if it is unknown
    counts = service.handle(args.assessment_id).objects.counts_by_type()
    total = sum(counts.values())
    if not args.force:
        print(
            f"would purge {assessment.id} ({assessment.status}): {total} object(s) and its directory"
        )
        for object_type, count in sorted(counts.items()):
            print(f"  {object_type:<28} {count}")
        print("nothing was removed; pass --force to remove it", file=sys.stderr)
        return REFUSED
    removed = service.purge(args.assessment_id)
    print(f"purged {args.assessment_id}: removed {removed} object(s) and its directory")
    return 0


def _source_add(args: argparse.Namespace, service: AssessmentService) -> int:
    """Register documents, reporting what was new and what was already there.

    Registration is idempotent in the loader (#320), so a repeated `source add` returns the
    existing documents; this handler tells the difference by identifier and does not count a
    skipped document as registered — the numbers a reviewer quotes must not move on a rerun.
    """
    handle = service.handle(args.assessment_id)
    loader = DocumentLoader(handle)
    before = {document.id for document in handle.objects.list(SourceDocument)}

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
    skipped = [document for document in documents if document.id in before]

    # Index whatever is still unindexed, which is every new document and any earlier
    # `--no-index` registration this command is now completing.
    references = 0
    if not args.no_index:
        for document in documents:
            if document.ingestion_status is IngestionStatus.REGISTERED:
                references += len(index_document(handle, document))

    print(f"registered {len(documents) - len(skipped)} document(s)")
    for document in skipped:
        print(f"already registered: {document.id}  {document.filename}")
    if not args.no_index:
        print(f"indexed {references} evidence reference(s)")
    return 0


def _source_add_repo(args: argparse.Namespace, service: AssessmentService) -> int:
    """Register a repository's selected files at a pinned commit (#597).

    Same reporting contract as `source add`: idempotent registration, counts that do not move
    on a rerun, and indexing for whatever is still unindexed.
    """
    from trace_ai.config import get_settings
    from trace_ai.services.ingestion.repository import (
        RepositoryIngestionError,
        ingest_repository,
    )

    handle = service.handle(args.assessment_id)
    before = {document.id for document in handle.objects.list(SourceDocument)}
    try:
        documents = ingest_repository(
            handle, args.url, args.commit, github_token=get_settings().github_token
        )
    except RepositoryIngestionError as refused:
        print(f"error: {refused}", file=sys.stderr)
        return 1
    skipped = [document for document in documents if document.id in before]

    references = 0
    if not args.no_index:
        for document in documents:
            if document.ingestion_status is IngestionStatus.REGISTERED:
                references += len(index_document(handle, document))

    print(
        f"registered {len(documents) - len(skipped)} document(s) from {args.url} @ {args.commit[:12]}"
    )
    for document in skipped:
        print(f"already registered: {document.id}  {document.filename}")
    if not args.no_index:
        print(f"indexed {references} evidence reference(s)")
    return 0


def _source_list(args: argparse.Namespace, service: AssessmentService) -> int:
    handle = service.handle(args.assessment_id)
    documents = handle.objects.list(SourceDocument)
    if args.as_json:
        return _print_json(
            "source-documents",
            {
                "assessment_id": args.assessment_id,
                "source_documents": [
                    {
                        "id": d.id,
                        "ingestion_status": str(d.ingestion_status),
                        "media_type": d.media_type,
                        "filename": d.filename,
                    }
                    for d in documents
                ],
            },
        )
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
    if args.as_json:
        return _print_json(
            "evidence-references",
            {
                "assessment_id": args.assessment_id,
                "evidence_references": [
                    {
                        "id": r.id,
                        "source_document_id": r.source_document_id,
                        "start_line": r.start_line,
                        "end_line": r.end_line,
                        "location": r.section_title or r.json_pointer,
                    }
                    for r in references
                ],
            },
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

    if args.as_json:
        # The quotation is this command's entire purpose, so the JSON view carries it too --
        # the one listing where source content appears (DEC-096).
        return _print_json("evidence", {"evidence": rendered})

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
    return REFUSED


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
        previous=previous_approved_context(handle, context),
    )
    return build_context_review_package(handle, index=EvidenceIndex(handle), validation=validation)


def _context_extract(args: argparse.Namespace, service: AssessmentService) -> int:
    """Run the extraction and validation nodes, and stop at the checkpoint.

    The whole run is `services/context/pipeline.py`'s: this reads flags, builds the model the
    profile names, and prints what came back. A CLI that composed the nodes itself would be a
    second place the pipeline lives.
    """
    handle = service.handle(args.assessment_id)
    assessment = service.get(args.assessment_id)
    profile, model = _run_model(args, service)

    outcome = run_context_slice(
        handle,
        model=model,
        profile=profile,
        assessment_name=assessment.name,
        budget=_budget_from(args),
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

    if args.as_json:
        _print_json(
            "context-review-package",
            {
                "assessment_id": args.assessment_id,
                "system_context": {
                    "system_name": context.system_name,
                    "version": context.version,
                    "approved": context.is_approved,
                    "purpose": context.system_purpose,
                },
                "objects": {
                    group: [obj.model_dump(mode="json") for obj in objects]
                    for group, objects in package.objects_by_type.items()
                },
                "documented_claims": [
                    item.claim.model_dump(mode="json") for item in package.documented_claims
                ],
                "interpreted_claims": [
                    item.claim.model_dump(mode="json") for item in package.interpreted_claims
                ],
                "questions": [q.model_dump(mode="json") for q in package.questions],
                "triggers": [
                    {"name": t.name, "detail": t.detail, "object_ids": list(t.object_ids)}
                    for t in package.triggers
                ],
                "outstanding_errors": [
                    {"object_id": e.object_id, "field": e.field, "message": e.message}
                    for e in package.outstanding_errors
                ],
                "consistency_observations": [
                    {
                        "kind": "zone_mismatch",
                        "object_ids": [mismatch.flow_id],
                        "detail": mismatch.detail,
                    }
                    for mismatch in package.zone_mismatches
                ]
                + [
                    {
                        "kind": observation.kind,
                        "object_ids": list(observation.object_ids),
                        "detail": observation.detail,
                    }
                    for observation in package.cross_claim_observations
                ],
                "can_approve": package.can_approve,
            },
        )
        # The same answer the human view gives (DEC-088): a context that cannot be approved is
        # a stated refusal, exit 3, JSON or not.
        return 0 if package.can_approve else REFUSED

    print(f"system:   {context.system_name}")
    print(f"revision: version {context.version}, {'approved' if context.is_approved else 'draft'}")
    print(f"purpose:  {context.system_purpose or '-'}")

    if args.observations:
        # The observation view (#429): what the extraction noticed about the documents
        # themselves, short enough for a demonstration beat and never clipped by a pager.
        _print_observations(package, empty_note=True)
        return 0

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

    _print_observations(package)

    print()
    print(f"human-review triggers ({len(package.triggers)})")
    for trigger in package.triggers:
        caused = ", ".join(trigger.object_ids) if trigger.object_ids else "-"
        print(f"  {trigger.name}: {trigger.detail} [{caused}]")

    consistency = len(package.zone_mismatches) + len(package.cross_claim_observations)
    if consistency:
        # Warn-only consistency observations (DEC-068's zone check, DEC-070's cross-claim
        # checks, #526): stated disagreements shown for the reviewer, blocking nothing.
        print()
        print(f"consistency observations ({consistency}, warn-only)")
        for mismatch in package.zone_mismatches:
            print(f"  zone_mismatch: {mismatch.detail}")
        for observation in package.cross_claim_observations:
            print(f"  {observation.kind}: {observation.detail}")

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
    return REFUSED


def _print_observations(package: ContextReviewPackage, *, empty_note: bool = False) -> None:
    """The extraction's observations about the documents themselves (#429).

    Injection attempts and contradictions are both `SourceObservation`s, and both exist to be
    read by the reviewer: an attempt triages attention toward its flagged subjects, and a
    contradiction names the identifier a `--resolve` call needs — an action that
    was unreachable while nothing printed the observation it acts on.
    """
    if package.injection_attempts:
        print()
        print(f"injection attempts detected ({len(package.injection_attempts)})")
        for observation in package.injection_attempts:
            cited = ", ".join(observation.evidence_ids)
            print(f"  {observation.id}  {observation.summary} [{cited}]")

    if package.contradictions:
        print()
        print(f"contradictions awaiting resolution ({len(package.contradictions)})")
        for observation in package.contradictions:
            cited = ", ".join(observation.evidence_ids)
            print(f"  {observation.id}  {observation.summary} [{cited}]")
        print("  settle one with `trace context review --resolve ID=VALUE --rationale ...`")

    if empty_note and not package.injection_attempts and not package.contradictions:
        print()
        print("no injection attempts or contradictions were observed in the supplied documents")


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
    record_review_session(
        handle, ReviewCheckpoint.CONTEXT_APPROVAL, reviewer_id=reviewer, workflow_run_id=run_id
    )

    if args.export is not None:
        _write_named_file(args.export, write_review_file(_package_for(handle)))
        print(f"wrote a review file for {handle.assessment_id}")
        print("Edit it, then apply it with `trace context review --apply`.")
        return 0

    written = []

    if args.apply is not None:
        document = read_review_file(_read_named_file(args.apply))
        reviewer = args.reviewer or document.get("reviewer") or _default_reviewer()
        applied = apply_review_file(handle, document, reviewer_id=reviewer, workflow_run_id=run_id)
        written.extend(applied.decisions)
        for name in applied.skipped_additions:
            print(f"skipped addition {name!r}: an object with that name already exists")

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
            raise CommandInputError(f"{identifier} is not a claim, so there is nothing to confirm")
        _, decision = confirm_assumption(
            handle, claim, reviewer_id=reviewer, workflow_run_id=run_id
        )
        written.append(decision)

    for pair in args.answers:
        identifier, separator, response = pair.partition("=")
        if not separator:
            raise CommandInputError(f"--answer takes ID=TEXT; {pair!r} has no '='")
        _, decision = answer_question(
            handle,
            _require(questions, identifier.strip(), "an open question"),
            response=response.strip(),
            reviewer_id=reviewer,
            workflow_run_id=run_id,
        )
        written.append(decision)

    for pair in args.attachments:
        identifier, separator, listed = pair.partition("=")
        evidence_ids = [item.strip() for item in listed.split(",") if item.strip()]
        if not separator or not evidence_ids:
            raise CommandInputError(f"--attach takes ID=EVD[,EVD...]; {pair!r} names no evidence")
        _, decision = attach_evidence(
            handle,
            _require(lookup, identifier.strip(), "an object in this assessment"),
            evidence_ids,
            index=EvidenceIndex(handle),
            reviewer_id=reviewer,
            rationale=args.rationale,
            workflow_run_id=run_id,
        )
        written.append(decision)

    if args.resolutions:
        from trace_ai.domain.source_observation import SourceObservation

        if not (args.rationale or "").strip():
            raise CommandInputError(
                "--resolve requires --rationale: a resolution with no reasoning is "
                "indistinguishable from quietly choosing the safer statement"
            )
        observations: dict[str, Any] = {
            observation.id: observation for observation in handle.objects.list(SourceObservation)
        }
        for pair in args.resolutions:
            identifier, separator, value = pair.partition("=")
            if not separator:
                raise CommandInputError(f"--resolve takes ID=VALUE; {pair!r} has no '='")
            resolved = resolve_contradiction(
                handle,
                _require(observations, identifier.strip(), "an observation in this assessment"),
                resolution=value.strip(),
                rationale=args.rationale,
                reviewer_id=reviewer,
                workflow_run_id=run_id,
            )
            written.extend(resolved.decisions)

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
        raise CommandInputError(f"{identifier} is not {described_as}")
    return found


def _severity(level: str) -> Severity:
    """A reviewer's severity string as the enum, or a named refusal listing the choices.

    `Severity(level)` raises a bare `ValueError` on an unknown value; wrapping it in
    `CommandInputError` keeps that value error out of the pipeline's and names the valid levels."""
    try:
        return Severity(level)
    except ValueError:
        choices = ", ".join(member.value for member in Severity)
        raise CommandInputError(f"{level!r} is not a severity; choose one of: {choices}") from None


def _risk_treatment(value: str) -> RiskTreatment:
    """A reviewer's treatment string as the enum, or a named refusal listing the choices."""
    try:
        return RiskTreatment(value)
    except ValueError:
        choices = ", ".join(member.value for member in RiskTreatment)
        raise CommandInputError(
            f"{value!r} is not a risk treatment; choose one of: {choices}"
        ) from None


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
        return REFUSED

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
    from trace_ai.workflow.limits import Budget

    # `--max-cost` and `--max-model-calls` are already parsed and validated by their argparse
    # converters (`_decimal`, `_non_negative_int`), so they arrive as a Decimal/int or None.
    if args.max_model_calls is None and args.max_cost is None:
        return None
    return Budget(
        maximum_model_calls=args.max_model_calls,
        maximum_cost=args.max_cost,
    )


def _print_phase_progress(progress: PhaseProgress) -> None:
    """One stderr line as the run enters each phase (DEC-138).

    Stderr, not stdout: the run's documented output contract stays what `_print_run_outcome`
    prints, and a script capturing stdout sees nothing new. Everything on the line is an
    identifier, a phase name, or a counter — never source-derived content.
    """
    cost = (
        f", estimated cost ${progress.estimated_cost}"
        if progress.estimated_cost is not None
        else ""
    )
    print(
        f"{progress.workflow_run_id}: {progress.phase.value} "
        f"({progress.phase_number}/{progress.phase_total}), "
        f"{progress.model_calls} model call(s) so far{cost}",
        file=sys.stderr,
    )


def _run(args: argparse.Namespace, service: AssessmentService) -> int:
    """Run the pipeline from initialization until it pauses, completes, or stops.

    The run is `services/driver.py`'s; this reads flags, builds the model, and prints where the
    run got to. Exit codes are the documented ones: 0 for a pause or a completion (the table
    stopped the run where it says to stop), 1 for a failed run.
    """
    profile, model = _run_model(args, service)
    outcome = run_assessment(
        service,
        args.assessment_id,
        model=model,
        profile=profile,
        budget=_budget_from(args),
        on_phase=_print_phase_progress,
    )
    return _print_run_outcome(outcome)


def _response_files(supplied: list[Path]) -> list[Path]:
    """Each `--response` as the files it names, a directory standing for its numbered recordings.

    A recording is dozens of files consumed in order — the live capture's runs retry, and a
    retried call consumes an extra response — so a command line naming each file is unwritable
    by hand. A directory expands to its `NN-*.json` files sorted, which is the consumption
    order the capture wrote them in.
    """
    files: list[Path] = []
    for path in supplied:
        if path.is_dir():
            numbered = sorted(path.glob("[0-9]*.json"))
            if not numbered:
                raise CommandInputError(f"{path} contains no numbered recordings (NN-*.json)")
            files.extend(numbered)
        else:
            files.append(path)
    return files


def _recorded_responses(args: argparse.Namespace) -> list[Any]:
    """The `--response` recordings, with a missing or malformed file named rather than tracebacked.

    Reading and parsing an operator-supplied recording can raise `OSError` (the file is absent) or
    `ValueError` (the JSON fits no proposal schema); both are the operator's mistake to fix, so they
    become a `CommandInputError` rather than a stack trace."""
    try:
        return load_recorded_responses(_response_files(args.responses))
    except CommandInputError:
        raise
    except (OSError, ValueError) as error:
        raise CommandInputError(f"a recorded response could not be read: {error}") from None


def _run_model(
    args: argparse.Namespace, service: AssessmentService
) -> tuple[ModelProfile, StructuredModel]:
    """The model a run command drives: journaled when live, replaying what the operator names.

    A live profile's model is wrapped so every response the run consumes lands in the
    assessment's own `traces/journal/` area (DEC-139). The fake provider journals nothing:
    a journal of the deterministic substitute would hold responses no model gave, which is
    the exact artifact the rehearsal marker exists to refuse.
    """
    profile = resolve_profile(args.model_profile)
    model: StructuredModel = build_model(profile, responses=_recorded_responses(args))
    if profile.provider == "fake":
        if args.replay_journal:
            raise CommandInputError(
                f"--replay-journal replays a live run's journal, and profile {profile.name!r} "
                f"reaches no provider; replay a recording with --response instead"
            )
        return profile, model
    artifacts = service.handle(args.assessment_id).artifacts
    model = JournalingModel(model, journal_dir(artifacts))
    entries = _journal_entries(args.replay_journal)
    if entries:
        model = JournalReplayModel(entries, model)
    return profile, model


def _journal_entries(supplied: list[Path]) -> list[JournalEntry]:
    """The named journal entries, spent ones refused or skipped by how they were named.

    A directory stands for its unspent numbered entries in order — a resume after a second
    interruption should not have to name files an earlier resume already consumed — and each
    skip says so. A file named explicitly and already spent is refused: the operator asserted
    that exact entry, and silently serving nothing would look like serving it.
    """
    entries: list[JournalEntry] = []
    try:
        for path in supplied:
            if path.is_dir():
                for candidate in sorted(path.glob("[0-9]*.json")):
                    if spent_marker(candidate).exists():
                        print(f"skipping {candidate.name} (spent)", file=sys.stderr)
                        continue
                    entries.append(read_journal_entry(candidate))
                continue
            entries.append(read_journal_entry(path))
    except SpentJournalEntryError as error:
        raise CommandInputError(str(error)) from None
    except (OSError, ValueError) as error:
        raise CommandInputError(f"a journal entry could not be read: {error}") from None
    if supplied and not entries:
        raise CommandInputError(
            "--replay-journal names no unspent entries; omit it to run the calls live"
        )
    return entries


def _read_named_file(path: Path) -> str:
    """Read a file the operator named on the command line, naming an I/O failure rather than
    tracebacking. A missing `--apply` file is an operator slip, not a bug in the pipeline."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise CommandInputError(f"cannot read {path}: {error}") from None


def _write_named_file(path: Path, text: str) -> None:
    """Write to a path the operator named (`--export`), naming an I/O failure rather than
    tracebacking. A directory or an unwritable location is an operator slip, not a bug."""
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        raise CommandInputError(f"cannot write {path}: {error}") from None


def _resume(args: argparse.Namespace, service: AssessmentService) -> int:
    """Resume a paused run: the checkpoint re-runs, and decided subjects let it advance."""
    profile, model = _run_model(args, service)
    outcome = resume_assessment(
        service,
        args.assessment_id,
        model=model,
        profile=profile,
        workflow_run_id=args.workflow_run_id,
        budget=_budget_from(args),
        on_phase=_print_phase_progress,
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
    """Print the checkpoint-2 review package, findings first, evidence excerpts labelled.

    The JSON view carries identifiers where the human view prints quotations (DEC-096): the
    excerpts stay reachable through `evidence show`, which is the command whose purpose they
    are, and a scripted consumer holding evidence identifiers loses nothing.
    """
    handle = service.handle(args.assessment_id)
    package = build_finding_review_package(handle, index=EvidenceIndex(handle))
    if args.as_json:
        return _print_json(
            "finding-review-package",
            {
                "assessment_id": package.assessment_id,
                "summary": {
                    "finding_count": package.summary.finding_count,
                    "documentation_gap_count": package.summary.documentation_gap_count,
                    "open_question_count": package.summary.open_question_count,
                    "awaiting_severity_count": package.summary.awaiting_severity_count,
                    "statement": package.summary.statement,
                },
                "findings": [
                    {
                        "finding": item.finding.model_dump(mode="json"),
                        "supporting_evidence_ids": [x.evidence_id for x in item.supporting],
                        "contradictory_evidence_ids": [x.evidence_id for x in item.contradictory],
                        "threat_ids": [t.id for t in item.threats],
                        "mapping_ids": [m.id for m in item.mappings],
                        "critiques": [
                            {
                                "critique": c.critique.model_dump(mode="json"),
                                "outcome": c.outcome,
                            }
                            for c in item.critiques
                        ],
                        "reasons": list(package.reasons_for(item.finding.id)),
                    }
                    for item in package.findings
                ],
                "documentation_gaps": [
                    {
                        "gap": item.gap.model_dump(mode="json"),
                        "evidence_ids": [x.evidence_id for x in item.excerpts],
                    }
                    for item in package.documentation_gaps
                ],
                "questions": [q.model_dump(mode="json") for q in package.questions],
            },
        )
    print(render_markdown(package))
    return 0


def _findings_review(args: argparse.Namespace, service: AssessmentService) -> int:
    """Record finding decisions: severity, treatment, and edits first, then rejections, approvals.

    The order inside one invocation is fixed so `--severity fnd-001=medium --approve fnd-001`
    means what it reads as: the severity and the treatment land before the approval gate checks
    them, so `--treatment fnd-001=accept --treatment-rationale "..." --approve fnd-001` passes.
    """
    handle = service.handle(args.assessment_id)
    reviewer = args.reviewer or _default_reviewer()
    run = _latest_run(handle)
    run_id = run.id if run is not None else None
    record_review_session(
        handle, ReviewCheckpoint.FINDING_APPROVAL, reviewer_id=reviewer, workflow_run_id=run_id
    )

    if args.export:
        package = build_finding_review_package(handle, index=EvidenceIndex(handle))
        _write_named_file(args.export, write_finding_review_file(package))
        print(f"wrote {args.export}")
        print("Edit it, then apply it with `trace findings review --apply`.")
        return 0
    if args.apply:
        document = read_finding_review_file(_read_named_file(args.apply))
        if document.get("reviewer"):
            reviewer = str(document["reviewer"])
        applied = apply_finding_review_file(
            handle, document, reviewer_id=reviewer, workflow_run_id=run_id
        )
        if not applied:
            print("no decisions recorded; the file matches what was exported")
            return 0
        for decision in applied:
            print(f"{decision.id}  {decision.disposition:<22} {decision.subject_id}")
        print(f"{len(applied)} decision(s) recorded as {reviewer}")
        return 0

    findings = {finding.id: finding for finding in handle.objects.list(Finding)}
    decisions = []

    for entry in args.severities:
        identifier, separator, level = entry.partition("=")
        if not separator:
            raise CommandInputError(f"--severity takes ID=LEVEL, not {entry!r}")
        finding = _require(findings, identifier, "a finding in this assessment")
        updated, decision = change_severity(
            handle,
            finding,
            _severity(level),
            reviewer_id=reviewer,
            rationale=args.note,
            workflow_run_id=run_id,
        )
        findings[identifier] = updated
        decisions.append(decision)

    for entry in args.treatments:
        identifier, separator, value = entry.partition("=")
        if not separator:
            raise CommandInputError(f"--treatment takes ID=VALUE, not {entry!r}")
        finding = _require(findings, identifier, "a finding in this assessment")
        updated, decision = assign_risk_treatment(
            handle,
            finding,
            _risk_treatment(value),
            rationale=args.treatment_rationale,
            review_by=args.treatment_review_by,
            reviewer_id=reviewer,
            workflow_run_id=run_id,
        )
        findings[identifier] = updated
        decisions.append(decision)

    for identifier, assignment in args.edits:
        field, separator, value = assignment.partition("=")
        if not separator or not field:
            raise CommandInputError(f"--edit takes ID FIELD=VALUE, not {assignment!r}")
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

    for identifier in args.deferred:
        finding = _require(findings, identifier, "a finding in this assessment")
        updated, decision = defer_finding(
            handle, finding, reviewer_id=reviewer, rationale=args.note, workflow_run_id=run_id
        )
        findings[identifier] = updated
        decisions.append(decision)

    for identifier in args.more_analysis:
        finding = _require(findings, identifier, "a finding in this assessment")
        updated, decision = request_more_analysis(
            handle,
            finding,
            reviewer_id=reviewer,
            rationale=args.note or "",
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

    if args.as_json:
        _print_json(
            "verification",
            {
                "assessment_id": args.assessment_id,
                "ok": outcome.ok,
                "document_count": outcome.document_count,
                "evidence_count": outcome.evidence_count,
                "manifest_checked": outcome.manifest_checked,
                "document_drift": [_drift_entry(drift) for drift in outcome.document_drift],
                "evidence_failures": [
                    {
                        "evidence_id": failure.evidence_id,
                        "outcome": failure.outcome.value,
                        "detail": failure.detail,
                    }
                    for failure in outcome.evidence_failures
                ],
                "manifest_drift": [_drift_entry(drift) for drift in outcome.manifest_drift],
            },
        )
        return 0 if outcome.ok else REFUSED

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
    return REFUSED


def _drift_entry(drift: Drift) -> dict[str, str]:
    """One drift as the fields the human line prints: identifiers and hashes, never content."""
    return {"subject": drift.subject, "expected": drift.expected, "found": drift.found}


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
    text = handle.artifacts.read("outputs", filename).decode("utf-8")
    if args.as_json:
        import json

        if args.manifest:
            return _print_json(
                "report-manifest",
                {
                    "assessment_id": args.assessment_id,
                    "filename": filename,
                    "manifest": json.loads(text),
                },
            )
        return _print_json(
            "report",
            {"assessment_id": args.assessment_id, "filename": filename, "report": text},
        )
    print(text)
    return 0


def _report_render(args: argparse.Namespace, service: AssessmentService) -> int:
    """Write the derived HTML view of the rendered report (#527, DEC-108).

    The Markdown deliverable is read back and transformed; nothing re-renders from objects, so
    the two cannot disagree. Refused while no report exists, like `report show`.
    """
    from trace_ai.services.report.html import render_report_html
    from trace_ai.services.report.lineage_html import lineage_appendix

    assessment = service.get(args.assessment_id)
    if assessment.final_report_path is None:
        print(
            "error: no report has been rendered for this assessment; run the pipeline to "
            "completion first",
            file=sys.stderr,
        )
        return 1
    filename = assessment.final_report_path.rpartition("/")[2]
    handle = service.handle(args.assessment_id)
    markdown = handle.artifacts.read("outputs", filename).decode("utf-8")
    derived = filename.removesuffix(".md") + ".html"
    page = render_report_html(
        markdown,
        title=f"Security Architecture Assessment: {assessment.name}",
        appendix=lineage_appendix(handle),
    )
    handle.artifacts.store_output(derived, page.encode("utf-8"))
    print(f"wrote {derived} to {args.assessment_id}'s outputs area")
    return 0


def _report_rubric(args: argparse.Namespace, service: AssessmentService) -> int:
    """Record the section 9 reviewer rubric against the assessment's latest run.

    Parsing stops at `CATEGORY=N`. Which categories exist, that all seven are present, and that
    every value is one to five are `record_rubric`'s refusals — they surface here as one-line
    errors rather than being duplicated.
    """
    handle = service.handle(args.assessment_id)
    run = _latest_run(handle)
    if run is None:
        print(
            "error: no workflow run exists to attach the rubric to; run the pipeline first",
            file=sys.stderr,
        )
        return 1

    scores: dict[str, int] = {}
    for entry in args.scores:
        category, separator, value = entry.partition("=")
        if not separator or not category or not value:
            raise CommandInputError(f"a score is written CATEGORY=N: {entry!r}")
        if category in scores:
            raise CommandInputError(f"category {category!r} is scored twice")
        try:
            scores[category] = int(value)
        except ValueError:
            raise CommandInputError(
                f"a rubric score is a whole number one to five: {entry!r}"
            ) from None

    # `record_rubric` validates the operator's scores (all seven categories, each one to five) and
    # raises a bare ValueError; wrap it as a command-input error so it stays a one-line refusal
    # rather than a traceback now that bare ValueError is no longer swallowed wholesale.
    try:
        results = record_rubric(
            handle,
            run,
            scores,
            reviewer_id=args.reviewer or _default_reviewer(),
            comments=args.comments,
        )
    except ValueError as error:
        raise CommandInputError(str(error)) from None
    print(f"recorded {len(results)} rubric score(s) for run {run.id}")
    for result in results:
        print(f"  {result.metric_name:<28} {result.metric_value:.0f}")
    return 0


def _evaluate(args: argparse.Namespace, service: AssessmentService) -> int:
    """Replay one scenario, or every recorded one, through the evaluation harness.

    The harness opens its own store at the work root — a replayed assessment is a measurement,
    not part of the user's assessment data — and everything printed is metrics, identifiers, and
    repo-relative feed paths. Exit 0 when every attempted run completed; 1 when any did not.
    """
    import contextlib
    import tempfile

    from trace_ai.config import PROJECT_ROOT
    from trace_ai.services.evaluation.harness import HarnessError, diff_feeds, run_scenario
    from trace_ai.services.evaluation.registry import CLEAN_CONDITION, load_registry

    if args.report is None and args.all_scenarios == bool(args.scenario):
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

    if args.report is not None:
        return _evaluate_report(args)

    registry = load_registry()

    # A live profile prices every scenario it touches; `--all` under one would bill the whole
    # corpus on a single flag. Live harness runs are singly named (the DEC-077 posture: manual,
    # priced by the operator), and the offline default keeps a bare sweep free.
    live_profile = args.model_profile != "offline-fake"
    if live_profile and args.all_scenarios:
        print(
            "error: a live --model-profile prices each scenario; name one scenario, not --all",
            file=sys.stderr,
        )
        return 1

    # A journal re-drives one interrupted live run (DEC-139); offline replays serve their own
    # recorded responses, so offering them a journal is refused the way `_run_model` refuses it.
    if args.replay_journal and not live_profile:
        print(
            "error: --replay-journal re-drives a live harness run; a recording replay serves "
            "its own responses. Name a live --model-profile, or omit the flag",
            file=sys.stderr,
        )
        return 1
    journal_entries = _journal_entries(args.replay_journal)

    # Validate the condition once, not once per scenario: an unknown `--condition` used to produce
    # twelve identical HarnessErrors on `--all`. `clean` is always valid; any other must be declared
    # by some scenario.
    if args.condition != CLEAN_CONDITION:
        declared = {condition for entry in registry for condition in entry.conditions}
        if args.condition not in declared:
            print(
                f"error: no scenario declares condition {args.condition!r}; "
                f"known conditions: {', '.join(sorted(declared)) or 'none'}",
                file=sys.stderr,
            )
            return 1

    if args.all_scenarios:
        slugs = []
        for entry in registry:
            if entry.has_recording:
                slugs.append(entry.slug)
            else:
                print(f"skipped {entry.slug}: no recording")
    else:
        slugs = [args.scenario]

    failures = 0
    drifted = 0
    runs_payload: list[dict[str, Any]] = []
    for slug in slugs:
        with contextlib.ExitStack() as stack:
            # A named `--work-root` is the operator's to keep and inspect; an unnamed one is a
            # throwaway store and artifact tree, cleaned up when the scenario finishes rather than
            # left behind (one per scenario on `--all`, six full sweeps on the CI scorecard job).
            # On `--all` each scenario gets its own subdirectory (#505): a shared store would
            # mint asm-002 onward for later scenarios, and the replayed report's own bytes --
            # which the offline pin verifies -- carry the assessment identifier.
            if args.work_root is not None:
                work_root = args.work_root / slug if args.all_scenarios else args.work_root
            else:
                work_root = _path(
                    stack.enter_context(tempfile.TemporaryDirectory(prefix=f"trace-eval-{slug}-"))
                )
            try:
                outcome = run_scenario(
                    slug,
                    data_root=work_root,
                    label=args.label,
                    condition=args.condition,
                    ablations=args.ablations,
                    profile_name=args.model_profile,
                    results_root=args.results_root,
                    live_workflow_version=args.live_workflow_version,
                    replay_journal=journal_entries,
                )
            except HarnessError as refused:
                print(f"error: {refused}", file=sys.stderr)
                failures += 1
                continue

            if outcome.report_hash_verified is False:
                drifted += 1
            if args.as_json:
                import json

                feed_relative = None
                adversarial = None
                if outcome.feed_path is not None:
                    adversarial = json.loads(outcome.feed_path.read_text(encoding="utf-8")).get(
                        "adversarial"
                    )
                    feed_relative = (
                        str(outcome.feed_path.relative_to(PROJECT_ROOT))
                        if outcome.feed_path.is_relative_to(PROJECT_ROOT)
                        else str(outcome.feed_path)
                    )
                runs_payload.append(
                    {
                        "scenario": outcome.scenario,
                        "condition": outcome.condition,
                        "label": outcome.label,
                        "workflow_run_id": outcome.workflow_run_id,
                        "run_status": outcome.run_status,
                        "stopped_because": outcome.stopped_because,
                        "ablations": outcome.ablations,
                        "metrics": {
                            result.metric_name: result.metric_value for result in outcome.metrics
                        },
                        "report_hash_verified": outcome.report_hash_verified,
                        "adversarial": adversarial,
                        "feed": feed_relative,
                    }
                )
                if not outcome.completed:
                    failures += 1
                continue

            print(f"scenario:     {outcome.scenario} ({outcome.condition}, label {outcome.label})")
            print(f"workflow run: {outcome.workflow_run_id}  {outcome.run_status}")
            if outcome.ablations:
                print(f"ablations:    {', '.join(outcome.ablations)} (non-authoritative, DEC-012)")
            if outcome.report_hash_verified is True:
                print("report hash:  verified against the scenario's recorded pin")
            elif outcome.report_hash_verified is False:
                print("report hash:  DRIFTED from the scenario's recorded pin", file=sys.stderr)
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
                # A missing prior feed is this scenario's failure, not the whole sweep's: catch it in
                # the loop and continue, the same as a HarnessError, rather than aborting `--all`
                # and discarding the scenarios already printed.
                try:
                    diff = diff_feeds(outcome.feed_path, prior)
                except OSError as missing:
                    print(f"diff against {args.diff_against}: skipped ({missing})", file=sys.stderr)
                    failures += 1
                    print()
                    continue
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

    if args.as_json:
        _print_json("evaluation-runs", {"runs": runs_payload})
    if failures:
        return 1
    # A drifted report hash is the DEC-088 refusal `trace verify` gives the same fact: the
    # replay stopped reproducing the recording's report. An answer, not a fault.
    return REFUSED if drifted else 0


def _evaluate_report(args: argparse.Namespace) -> int:
    """Run the offline sweep and render one evaluation page (#505).

    The committed pages under docs/eval/ remain the build scripts' deliberate step -- they carry
    the DEC-081 history snapshotting and the CI currency check. This renders the same pages from
    the same sweep for a person or a pipe, to stdout or --out, and stamps nothing into history.
    """
    import tempfile

    from trace_ai.config import PROJECT_ROOT
    from trace_ai.services.evaluation.registry import catalog_version_summary, load_registry
    from trace_ai.services.evaluation.stamps import DETERMINISTIC_STAMP

    pins = {
        "registry": "1.0",
        "catalog": catalog_version_summary(),
    }
    with tempfile.TemporaryDirectory(prefix="trace-eval-report-") as tmp:
        root = _path(tmp)
        if args.report == "ablation":
            from trace_ai.services.evaluation.ablation import render_ablation
            from trace_ai.services.evaluation.stability import run_ablation_set

            comparisons = [
                run_ablation_set(
                    entry.slug,
                    data_root=root / "work" / entry.slug,
                    label="ablation",
                    results_root=root / "feeds",
                )
                for entry in load_registry()
                if entry.has_recording_for("clean")
            ]
            page = render_ablation(comparisons, generated_at=DETERMINISTIC_STAMP, pins=pins)
        else:
            from trace_ai.services.evaluation.sweep import collect_feeds

            feeds = collect_feeds(root)
            if args.report == "comparison":
                import json as json_module

                from trace_ai.services.evaluation.comparison import render_comparison

                live_path = PROJECT_ROOT / "docs" / "eval" / "live-stability.json"
                live = (
                    json_module.loads(live_path.read_text(encoding="utf-8"))
                    if live_path.is_file()
                    else None
                )
                page = render_comparison(
                    feeds, generated_at=DETERMINISTIC_STAMP, pins=pins, live_stability=live
                )
            else:
                import json as json_module

                from trace_ai.services.evaluation.history import load_history
                from trace_ai.services.evaluation.scorecard import render_scorecard

                history_path = PROJECT_ROOT / "docs" / "eval" / "history.jsonl"
                live_path = PROJECT_ROOT / "docs" / "eval" / "live-stability.json"
                live = (
                    json_module.loads(live_path.read_text(encoding="utf-8"))
                    if live_path.is_file()
                    else None
                )
                page = render_scorecard(
                    feeds,
                    generated_at=DETERMINISTIC_STAMP,
                    history=load_history(history_path),
                    live_stability=live,
                )
    if args.out is not None:
        args.out.write_text(page, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(page)
    return 0


def _evaluate_baseline(args: argparse.Namespace) -> int:
    """Score a single-pass baseline over one scenario, replayed from its recorded response.

    The baseline is a measurement, not an assessment: it opens no store, prints metrics and the
    feed path only, and its feed is marked non-authoritative. Exit 1 when the scored scenario has
    no baseline recording or no truth set, so a comparison cannot silently score nothing.
    """
    from trace_ai.config import PROJECT_ROOT
    from trace_ai.services.evaluation.baselines import (
        BASELINE_SCHEMAS,
        BaselineError,
        run_baseline,
    )
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
    response = BASELINE_SCHEMAS[condition].model_validate_json(
        recording.read_text(encoding="utf-8")
    )

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
    import contextlib
    import tempfile

    from trace_ai.services.evaluation.harness import HarnessError
    from trace_ai.services.evaluation.stability import ABLATION_SET, run_ablation_set

    with contextlib.ExitStack() as stack:
        work_root = args.work_root or _path(
            stack.enter_context(
                tempfile.TemporaryDirectory(prefix=f"trace-ablate-{args.scenario}-")
            )
        )
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
    import contextlib
    import tempfile
    from pathlib import Path

    from trace_ai.services.evaluation.stability import StabilityError, run_stability

    with contextlib.ExitStack() as stack:
        work_root = args.work_root or _path(
            stack.enter_context(
                tempfile.TemporaryDirectory(prefix=f"trace-stability-{args.scenario}-")
            )
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
        if summary.failed_runs:
            print(f"failed runs: {summary.failed_runs} of {summary.failed_runs + summary.n}")

        import json as _json

        # The summary is a deliverable, so it goes to a persistent location -- the named
        # `--results-root`, or the current directory -- never the throwaway store, which is cleaned
        # up when this returns. Writing it into `work_root` would delete the file whose path was
        # just printed.
        summary_root = args.results_root if args.results_root is not None else Path.cwd()
        summary_path = summary_root / f"stability-{summary.scenario}-{args.label}.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            _json.dumps(summary.to_payload(), indent=2) + "\n", encoding="utf-8"
        )
        print(f"summary:      {summary_path}")
        print(
            "Commit it as docs/eval/live-stability.json to put the measurement on the scorecard "
            "(DEC-077 reports it; nothing gates on it)."
        )
        return 0


def _view(args: argparse.Namespace) -> int:
    """Serve the read-only interface over the data root until interrupted (DEC-032).

    The server is `trace_ai.interface`'s; this reads the flags and hands off. It opens its own
    store for the server's lifetime, which is why it is dispatched before the request-scoped store.
    """
    import errno

    from trace_ai.interface.server import serve

    try:
        serve(args.data_root, port=args.port)
    except OSError as error:
        # Running the view twice is the likeliest slip for a demonstration command; the port is
        # taken, which is EADDRINUSE, and a stack trace is the wrong answer to it.
        if error.errno == errno.EADDRINUSE:
            print(
                f"error: port {args.port} is already in use; pass --port to choose another",
                file=sys.stderr,
            )
        else:
            print(f"error: could not serve on port {args.port}: {error}", file=sys.stderr)
        return 1
    return 0
