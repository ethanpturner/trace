"""Tests for the command surface.

DEC-032 makes this the interface rather than a development affordance, so the tests are about what
a reviewer sees. Three groups matter beyond "the command works".

**Output discipline.** No command prints a provider key, and no command prints an absolute path
from the artifact store. Source-derived text appears only from `evidence show`, which exists to
print it — a listing that showed content would put document text on screen as a side effect of
asking what exists.

**Failures are messages, not tracebacks.** The services raise named errors and the CLI turns those
into a line and an exit code. An unexpected exception keeps its traceback on purpose: hiding one is
how a tool starts lying about what happened.

**The context group is the checkpoint's interface.** It was absent through M1 because the Context
Extraction agent did not exist and `--help` is a promise; issue #77 built it once the agent did. A
refused approval exits non-zero and names what is outstanding, so an evaluation script can act on
it without parsing prose.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from trace_ai.cli import build_parser, run
from trace_ai.config import PROJECT_ROOT

FORGEFLOW_INPUT = PROJECT_ROOT / "demo" / "forgeflow" / "input"

FAKE_KEY = "sk-ant-do-not-print-me"


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated store, with a conspicuous provider key configured.

    The key is set for every command so the no-leak assertions are meaningful rather than passing
    because nothing was configured.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    return tmp_path / "data"


def invoke(data_root: Path, *args: str) -> int:
    return run(["--data-root", str(data_root), *args])


def created(data_root: Path, capsys: pytest.CaptureFixture[str], name: str = "ForgeFlow") -> str:
    assert invoke(data_root, "assessment", "create", "--name", name) == 0
    return capsys.readouterr().out.strip()


# ------------------------------------------------------------------------------------------
# Assessments
# ------------------------------------------------------------------------------------------


def test_create_prints_an_identifier_and_persists_it(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys, "ForgeFlow Security Review")
    assert identifier == "asm-001"

    assert invoke(data_root, "assessment", "list") == 0
    listed = capsys.readouterr().out
    assert "asm-001" in listed
    assert "ForgeFlow Security Review" in listed


def test_list_says_so_when_there_is_nothing(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke(data_root, "assessment", "list") == 0
    assert "no assessments" in capsys.readouterr().out


def test_status_reports_the_state_and_the_counts(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    assert invoke(data_root, "assessment", "status", identifier) == 0
    output = capsys.readouterr().out

    assert "draft" in output
    assert "source documents: 8" in output
    assert "evidence:" in output


def test_the_person_performs_archive_and_the_sign_off_and_nothing_else(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DEC-031 as amended by DEC-082: a person archives, and signs off a finished deliverable.

    `approve` is not a status setter: with no rendered report it is refused in one line, so
    offering it on the surface is not the checkpoint bypass DEC-031 rejected — the service
    refuses everything but a completed, authoritative, rendered run.
    """
    identifier = created(data_root, capsys)
    assert invoke(data_root, "assessment", "approve", identifier) == 1
    error = capsys.readouterr().err.strip()
    assert error.startswith("error:")
    assert "no report has been rendered" in error

    assert invoke(data_root, "assessment", "archive", identifier) == 0
    assert "archived" in capsys.readouterr().out

    offered = _subcommands("assessment")
    assert offered == {"create", "list", "status", "candidates", "archive", "approve"}


# ------------------------------------------------------------------------------------------
# Sources and evidence
# ------------------------------------------------------------------------------------------


def test_reset_without_force_lists_and_removes_nothing(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`reset` is the one destructive command, so its default is a preview and a refusal."""
    identifier = created(data_root, capsys)

    assert invoke(data_root, "reset") == 1
    captured = capsys.readouterr()
    assert "would remove" in captured.out
    assert "pass --force" in captured.err

    assert invoke(data_root, "assessment", "status", identifier) == 0


def test_reset_with_force_returns_the_root_to_the_fresh_state(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The rerun problem (#321): a used root mints asm-002 while every documented command names
    asm-001. After a reset, the next create allocates asm-001 again — the property a scripted
    demonstration depends on."""
    identifier = created(data_root, capsys)
    assert invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT)) == 0
    capsys.readouterr()

    assert invoke(data_root, "reset", "--force") == 0
    assert "removed" in capsys.readouterr().out

    assert invoke(data_root, "assessment", "list") == 0
    assert "no assessments" in capsys.readouterr().out
    assert created(data_root, capsys) == "asm-001"


def test_reset_refuses_a_directory_that_is_not_a_data_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A flag that removes data, pointed at the wrong directory, must do nothing at all."""
    other = tmp_path / "not-a-data-root"
    other.mkdir()
    (other / "keep.txt").write_text("not trace's", encoding="utf-8")

    assert invoke(other, "reset", "--force") == 1
    assert "does not look like a trace data root" in capsys.readouterr().err
    assert (other / "keep.txt").exists()


def test_reset_on_a_fresh_root_is_a_no_op(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke(data_root, "reset", "--force") == 0
    assert "already fresh" in capsys.readouterr().out


def test_adding_a_directory_registers_and_indexes_the_corpus(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)

    assert invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT)) == 0
    output = capsys.readouterr().out

    assert "registered 8 document(s)" in output
    assert "evidence reference(s)" in output


def test_adding_one_file_registers_one_document(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    path = FORGEFLOW_INPUT / "product-overview.md"

    assert invoke(data_root, "source", "add", identifier, str(path)) == 0
    assert "registered 1 document(s)" in capsys.readouterr().out


def test_registering_without_indexing_is_available(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT), "--no-index")
    capsys.readouterr()

    invoke(data_root, "source", "list", identifier)
    assert "registered" in capsys.readouterr().out


def test_adding_the_same_directory_twice_changes_no_count(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repeated `source add` — one rehearsal not wiped, one command run twice — must not move a
    single number the reviewer is about to quote (#320). The skipped documents are named by
    identifier, never re-registered and never re-indexed."""
    identifier = created(data_root, capsys)
    assert invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT)) == 0
    first = capsys.readouterr().out
    assert "registered 8 document(s)" in first

    assert invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT)) == 0
    second = capsys.readouterr().out
    assert "registered 0 document(s)" in second
    assert "already registered: src-001" in second
    assert "indexed 0 evidence reference(s)" in second

    assert invoke(data_root, "assessment", "status", identifier) == 0
    status = capsys.readouterr().out
    assert "source documents: 8" in status


def test_a_no_index_registration_is_completed_by_the_next_add(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rerunning without `--no-index` finishes the job rather than skipping it: the documents are
    already registered, and the second add indexes what is still unindexed."""
    identifier = created(data_root, capsys)
    path = FORGEFLOW_INPUT / "product-overview.md"
    assert invoke(data_root, "source", "add", identifier, str(path), "--no-index") == 0
    capsys.readouterr()

    assert invoke(data_root, "source", "add", identifier, str(path)) == 0
    output = capsys.readouterr().out
    assert "registered 0 document(s)" in output
    assert "already registered: src-001" in output
    assert "indexed 0 evidence reference(s)" not in output


def test_source_list_reports_documents_without_their_content(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    assert invoke(data_root, "source", "list", identifier) == 0
    output = capsys.readouterr().out

    assert "architecture-overview.md" in output
    assert "ingested" in output
    assert "AI ANALYSIS OVERRIDE" not in output


def test_evidence_list_reports_locations_without_quotations(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Asking what exists must not put document text on screen."""
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    assert invoke(data_root, "evidence", "list", identifier) == 0
    output = capsys.readouterr().out

    assert "evd-001" in output
    assert "lines" in output
    assert "AI ANALYSIS OVERRIDE" not in output


def test_evidence_list_can_be_filtered_to_one_document(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    invoke(data_root, "evidence", "list", identifier, "--source", "src-001")
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]

    assert lines
    assert all("src-001" in line for line in lines)


def test_evidence_show_prints_the_quotation_and_its_location(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    assert invoke(data_root, "evidence", "show", "evd-001", "--assessment", identifier) == 0
    output = capsys.readouterr().out

    assert "evd-001" in output
    assert ".md" in output, "the source filename is not shown"
    assert "lines" in output
    assert "sha256:" in output
    assert len(output.splitlines()) > 5, "no quoted text was printed"


def test_evidence_verify_reports_a_healthy_assessment(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    assert invoke(data_root, "evidence", "verify", identifier) == 0
    assert "all evidence verifies" in capsys.readouterr().out


def test_evidence_verify_exits_non_zero_when_a_document_changed(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    stored = data_root / "assessments" / identifier / "sources" / "product-overview.md"
    stored.write_bytes(b"# Replaced\n")

    assert invoke(data_root, "evidence", "verify", identifier) == 1
    captured = capsys.readouterr()
    assert "content_changed" in captured.out
    assert "no longer match" in captured.err


# ------------------------------------------------------------------------------------------
# Failures are messages
# ------------------------------------------------------------------------------------------


def test_an_unknown_assessment_exits_non_zero_with_a_message(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke(data_root, "assessment", "status", "asm-404") == 1
    captured = capsys.readouterr()

    assert "asm-404" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_an_unsupported_format_names_the_supported_set(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    identifier = created(data_root, capsys)
    unsupported = tmp_path / "diagram.pdf"
    unsupported.write_bytes(b"%PDF-1.4\n")

    assert invoke(data_root, "source", "add", identifier, str(unsupported)) == 1
    message = capsys.readouterr().err

    for media_type in ("text/markdown", "text/plain", "application/json", "application/yaml"):
        assert media_type in message
    assert "Traceback" not in message


def test_an_unknown_evidence_identifier_exits_non_zero(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    assert invoke(data_root, "evidence", "show", "evd-999", "--assessment", identifier) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_a_malformed_identifier_is_a_message_not_a_traceback(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke(data_root, "assessment", "status", "not-an-identifier") == 1
    assert "Traceback" not in capsys.readouterr().err


# ------------------------------------------------------------------------------------------
# Output discipline
# ------------------------------------------------------------------------------------------


def test_no_command_prints_a_provider_key(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The key is configured for every command in this file, so this is a real check."""
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    invoke(data_root, "assessment", "status", identifier)
    invoke(data_root, "source", "list", identifier)
    invoke(data_root, "evidence", "list", identifier)
    invoke(data_root, "evidence", "show", "evd-001", "--assessment", identifier)
    invoke(data_root, "assessment", "list")

    captured = capsys.readouterr()
    assert FAKE_KEY not in captured.out
    assert FAKE_KEY not in captured.err


def test_no_command_prints_an_artifact_path(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A path describes the machine rather than the assessment, and a model has no filesystem."""
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    invoke(data_root, "source", "list", identifier)
    invoke(data_root, "evidence", "show", "evd-001", "--assessment", identifier)

    captured = capsys.readouterr()
    for stream in (captured.out, captured.err):
        assert str(data_root) not in stream
        assert "/assessments/" not in stream
        assert "normalized/" not in stream


def test_the_banner_still_reports_credentials_as_names_only(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The no-argument behaviour, unchanged."""
    monkeypatch.setattr("trace_ai.config.ENV_FILE", tmp_path / "absent.env")
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)

    assert run([]) == 0
    output = capsys.readouterr().out

    assert "context-aware security architecture analysis" in output
    assert "anthropic" in output
    assert FAKE_KEY not in output


# ------------------------------------------------------------------------------------------
# The surface itself
# ------------------------------------------------------------------------------------------


def _subcommands(group: str) -> set[str]:
    parser = build_parser()
    groups = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    nested = next(
        action
        for action in groups.choices[group]._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return set(nested.choices)


def test_the_context_group_exists_now_that_the_agent_does() -> None:
    """It was absent through M1 rather than stubbed, because `--help` is a promise and the Context
    Extraction agent did not exist. It does now (#73), so the commands do."""
    assert _subcommands("context") == {"extract", "show", "review", "approve"}


def test_the_command_surface_is_the_one_dec_032_confirms() -> None:
    parser = build_parser()
    groups = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    assert set(groups.choices) == {
        "assessment",
        "source",
        "evidence",
        "context",
        "run",
        "resume",
        "findings",
        "report",
        "verify",
        "evaluate",
        "export",
        "reset",
        "view",
    }
    assert _subcommands("source") == {"add", "list"}
    assert _subcommands("evidence") == {"list", "show", "verify"}
    assert _subcommands("assessment") == {
        "create",
        "list",
        "status",
        "candidates",
        "archive",
        "approve",
    }
    assert _subcommands("findings") == {"show", "review", "approve"}
    assert _subcommands("report") == {"show", "rubric"}


def test_a_group_with_no_subcommand_prints_help() -> None:
    with pytest.raises(SystemExit):
        run(["assessment"])


def test_no_command_needs_an_api_key(
    data_root: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    identifier = created(data_root, capsys)
    assert invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT)) == 0
    assert invoke(data_root, "evidence", "verify", identifier) == 0


def test_the_cli_contains_no_pipeline_logic() -> None:
    """Section 5.2 puts ingestion and analysis in the application service.

    A CLI that grew logic would become a second place the pipeline lives, and the two would drift.
    """
    import ast

    source = PROJECT_ROOT / "src" / "trace_ai" / "cli.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "read_bytes" not in called, "the CLI reads a file itself"
    assert "write_bytes" not in called

    # `splitlines` is allowed in exactly one place: the helper that indents a block for display.
    # Anywhere else it would mean the CLI was segmenting a document, which is the indexer's work.
    segmenting = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "splitlines"
        and node.name != "_indent"
    ]
    assert not segmenting, (
        f"{[node.name for node in segmenting]} split text into lines; the CLI is segmenting "
        f"something and the indexer is where that belongs"
    )


def test_rendered_evidence_reaches_the_terminal_unaltered(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The injection fixture prints as it is stored.

    Altering it here would hide it from the reviewer, who is the one person positioned to notice.
    """
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    invoke(data_root, "evidence", "list", identifier)
    listing = capsys.readouterr().out

    notes = [line.split()[0] for line in listing.splitlines() if line.strip()]
    for evidence_id in notes:
        invoke(data_root, "evidence", "show", evidence_id, "--assessment", identifier)
        if "AI ANALYSIS OVERRIDE" in capsys.readouterr().out:
            return
    pytest.fail("no evidence reference printed the injection block")


def test_serialized_output_is_plain_text(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing here emits JSON yet; asserted so a later change is a decision rather than a drift."""
    created(data_root, capsys)
    invoke(data_root, "assessment", "list")
    output = capsys.readouterr().out.strip()

    with pytest.raises(json.JSONDecodeError):
        json.loads(output)


# ------------------------------------------------------------------------------------------
# The context slice
# ------------------------------------------------------------------------------------------

RECORDED = {
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
        },
        {
            "key": "region",
            "subject_type": "system",
            "predicate": "processing_region",
            "value": "us-east-1",
            "status": "assumed",
            "confidence": "low",
            "rationale": "Taken from the structured input and not confirmed in prose.",
        },
    ],
    "questions": [
        {
            "key": "hmac",
            "question": "Does webhook validation include HMAC signature verification?",
            "rationale": "Without it the receiver accepts forged deliveries.",
            "priority": "high",
            "blocking": True,
        }
    ],
}


def recorded_response(path: Path, **changes: object) -> Path:
    """A recorded extraction response, written where `--response` can replay it."""
    from trace_ai.domain.proposals import ContextExtractionProposal

    payload = {**RECORDED, **changes}
    path.write_text(
        ContextExtractionProposal.model_validate(payload).model_dump_json(indent=2),
        encoding="utf-8",
    )
    return path


def extracted(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path, **changes: object
) -> str:
    """An assessment with the ForgeFlow corpus ingested and a context extracted offline."""
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    response = recorded_response(tmp_path / "response.json", **changes)
    assert (
        invoke(
            data_root,
            "context",
            "extract",
            identifier,
            "--model-profile",
            "offline-fake",
            "--response",
            str(response),
        )
        == 0
    )
    capsys.readouterr()
    return identifier


def test_extract_runs_the_slice_and_stops_at_the_checkpoint(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The run pauses because the checkpoint is a phase, not because the command chose to."""
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    assert (
        invoke(
            data_root,
            "context",
            "extract",
            identifier,
            "--model-profile",
            "offline-fake",
            "--response",
            str(recorded_response(tmp_path / "response.json")),
        )
        == 0
    )
    output = capsys.readouterr().out

    assert "paused at:      human_context_review" in output
    assert "version 1, unapproved" in output
    assert "model calls:    1" in output


def test_extract_reaches_no_provider_under_the_offline_profile(
    data_root: Path,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`current-architecture.md` section 5.1 wants the command line usable for repeatable
    evaluation and for demo recovery. Both need a run that reaches no provider, so replaying a
    recorded response is a supported way to run the pipeline rather than a test-only hook."""
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    assert extracted(data_root, capsys, tmp_path)


def test_extract_refuses_an_unknown_profile(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    assert invoke(data_root, "context", "extract", identifier, "--model-profile", "gpt") == 1
    assert "gpt" in capsys.readouterr().err


def test_extract_says_so_when_there_is_nothing_indexed(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    assert (
        invoke(data_root, "context", "extract", identifier, "--model-profile", "offline-fake") == 1
    )
    assert "no indexed evidence" in capsys.readouterr().err


def test_show_renders_every_context_object_type(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    identifier = extracted(data_root, capsys, tmp_path)

    invoke(data_root, "context", "show", identifier)
    output = capsys.readouterr().out

    for heading in ("components", "actors", "assets", "data flows", "trust boundaries"):
        assert f"{heading} (" in output
    assert "Webhook Receiver" in output
    assert "Customer User" in output
    assert "Customer Source Code" in output
    assert "Analysis job enqueue" in output
    assert "Public internet boundary" in output


def test_show_keeps_documented_claims_apart_from_the_rest(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """`current-architecture.md` section 5.5: the system does not silently convert an
    interpretation into a confirmed fact. One undifferentiated list is how that happens by layout."""
    identifier = extracted(data_root, capsys, tmp_path)

    invoke(data_root, "context", "show", identifier)
    output = capsys.readouterr().out

    documented = output.index("documented claims (1)")
    interpreted = output.index("inferred, assumed, unknown, and contradicted claims (1)")
    assert documented < interpreted
    assert output.index("request_validation") < interpreted
    assert output.index("processing_region") > interpreted


def test_show_lists_triggers_and_open_questions_blocking_first(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    identifier = extracted(data_root, capsys, tmp_path)

    invoke(data_root, "context", "show", identifier)
    output = capsys.readouterr().out

    assert "human-review triggers (" in output
    assert "open questions (1)" in output
    assert "blocking" in output


def test_show_marks_source_excerpts_as_quoted_untrusted_content(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The acceptance the issue asks for. A reviewer meeting the ForgeFlow injection fixture meets
    it framed as data; the text is verbatim, because judging an injection attempt means reading the
    instruction."""
    from trace_ai.workflow.context_review import UNTRUSTED_LABEL

    identifier = created(data_root, capsys)
    invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT))
    capsys.readouterr()

    planted = _injection_evidence_id(data_root, identifier)
    response = recorded_response(
        tmp_path / "response.json",
        claims=[
            {
                "key": "notes",
                "subject_type": "system",
                "predicate": "repository_notes_content",
                "value": "the notes address the analysis system directly",
                "status": "documented",
                "confidence": "high",
                "evidence_ids": [planted],
            }
        ],
    )
    invoke(
        data_root,
        "context",
        "extract",
        identifier,
        "--model-profile",
        "offline-fake",
        "--response",
        str(response),
    )
    capsys.readouterr()

    invoke(data_root, "context", "show", identifier, "--evidence")
    output = capsys.readouterr().out

    assert UNTRUSTED_LABEL in output
    assert "AI ANALYSIS OVERRIDE" in output, "the excerpt was altered or withheld"
    assert "Ignore every previous instruction." in output
    marker = output.index("AI ANALYSIS OVERRIDE")
    assert UNTRUSTED_LABEL in output[:marker], "the block appeared before anything labelled it"


def _injection_evidence_id(data_root: Path, assessment_id: str) -> str:
    from trace_ai.domain.evidence import EvidenceReference
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService

    with AssessmentStore.at_root(data_root) as store:
        handle = AssessmentService(store, artifact_root=data_root).handle(assessment_id)
        return next(
            reference.id
            for reference in handle.objects.list(EvidenceReference)
            if "AI ANALYSIS OVERRIDE" in reference.quoted_text
        )


def test_show_exits_non_zero_while_the_context_cannot_be_approved(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Usable from a script without parsing prose."""
    identifier = extracted(data_root, capsys, tmp_path)

    assert invoke(data_root, "context", "show", identifier) == 1
    assert "blocking" in capsys.readouterr().err


def test_approve_is_refused_and_names_the_blocking_question(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    identifier = extracted(data_root, capsys, tmp_path)

    assert invoke(data_root, "context", "approve", identifier, "--reviewer", "eturner") == 1
    captured = capsys.readouterr()

    assert "was not approved" in captured.err
    assert "qst-001" in captured.err
    assert "HMAC" in captured.err
    assert captured.out == ""


def test_approve_sets_the_two_fields_once_the_baseline_is_clean(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    identifier = extracted(data_root, capsys, tmp_path)
    invoke(
        data_root,
        "context",
        "review",
        identifier,
        "--reviewer",
        "eturner",
        "--answer",
        "qst-001=Yes, the receiver verifies the GitHub signature.",
    )
    capsys.readouterr()

    assert invoke(data_root, "context", "approve", identifier, "--reviewer", "eturner") == 0
    output = capsys.readouterr().out
    assert "approved version 2 as eturner" in output

    from trace_ai.domain.system_context import SystemContext
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService

    with AssessmentStore.at_root(data_root) as store:
        handle = AssessmentService(store, artifact_root=data_root).handle(identifier)
        revisions = {item.version: item for item in handle.objects.list(SystemContext)}

    assert set(revisions) == {1, 2}
    assert revisions[2].approved_by == "eturner"
    assert revisions[2].approved_at is not None
    assert not revisions[1].is_approved


def test_review_records_the_decisions_the_flags_name(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    identifier = extracted(data_root, capsys, tmp_path)

    assert (
        invoke(
            data_root,
            "context",
            "review",
            identifier,
            "--reviewer",
            "eturner",
            "--approve",
            "cmp-001",
            "--reject",
            "cmp-002",
            "--confirm",
            "ctx-002",
            "--answer",
            "qst-001=Yes, HMAC is verified.",
        )
        == 0
    )
    output = capsys.readouterr().out

    assert "4 decision(s) recorded as eturner" in output
    assert "approve" in output
    assert "reject" in output


def test_a_review_file_round_trips_to_the_same_decisions_as_the_flags(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The property worth having: the file is a way of *saying* what to do, not a second
    implementation of doing it. Both paths call the same functions in `workflow/context_review.py`,
    and this asserts the rows come out identical.
    """
    import yaml

    by_flags = extracted(data_root, capsys, tmp_path)
    invoke(
        data_root,
        "context",
        "review",
        by_flags,
        "--reviewer",
        "eturner",
        "--approve",
        "cmp-001",
        "--reject",
        "cmp-002",
        "--confirm",
        "ctx-002",
        "--answer",
        "qst-001=Yes, HMAC is verified.",
    )
    capsys.readouterr()

    by_file = extracted(data_root, capsys, tmp_path)
    exported = tmp_path / "review.yaml"
    assert invoke(data_root, "context", "review", by_file, "--export", str(exported)) == 0
    capsys.readouterr()

    document = yaml.safe_load(exported.read_text())
    for entry in document["components"]:
        entry["decision"] = "approve" if entry["id"] == "cmp-001" else "reject"
    for entry in document["claims"]:
        entry["confirm"] = entry["id"] == "ctx-002"
    for entry in document["questions"]:
        entry["answer"] = "Yes, HMAC is verified."
    exported.write_text(yaml.safe_dump(document, sort_keys=False))

    assert (
        invoke(
            data_root,
            "context",
            "review",
            by_file,
            "--reviewer",
            "eturner",
            "--apply",
            str(exported),
        )
        == 0
    )
    capsys.readouterr()

    assert _decision_shapes(data_root, by_flags) == _decision_shapes(data_root, by_file)


def _decision_shapes(data_root: Path, assessment_id: str) -> list[tuple[object, ...]]:
    """Every decision, reduced to what it says rather than when it was made."""
    from trace_ai.domain.reviewer_decision import ReviewerDecision
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService

    with AssessmentStore.at_root(data_root) as store:
        handle = AssessmentService(store, artifact_root=data_root).handle(assessment_id)
        decisions = handle.objects.list(ReviewerDecision)

    return sorted(
        (
            decision.subject_type,
            decision.subject_id,
            decision.disposition,
            decision.reviewer_id,
            tuple(sorted((decision.prior_value or {}).keys() - {"updated_at"})),
        )
        for decision in decisions
    )


def test_an_unedited_review_file_applies_nothing(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A format where the exported state was itself an instruction would record a decision for
    every object each time somebody looked."""
    identifier = extracted(data_root, capsys, tmp_path)
    exported = tmp_path / "review.yaml"
    invoke(data_root, "context", "review", identifier, "--export", str(exported))
    capsys.readouterr()

    assert invoke(data_root, "context", "review", identifier, "--apply", str(exported)) == 0
    assert "no decisions recorded" in capsys.readouterr().out


def test_a_review_file_for_another_assessment_is_refused(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Applying it would record one reviewer's decisions against another assessment."""
    first = extracted(data_root, capsys, tmp_path)
    second = extracted(data_root, capsys, tmp_path)
    exported = tmp_path / "review.yaml"
    invoke(data_root, "context", "review", first, "--export", str(exported))
    capsys.readouterr()

    assert invoke(data_root, "context", "review", second, "--apply", str(exported)) == 1
    assert first in capsys.readouterr().err


def test_requesting_re_extraction_records_it_and_says_what_happens_next(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """DEC-038: re-extraction is the assessment's next workflow run, not a resumed one. The command
    has to say so, or the rejection reads as having done nothing."""
    identifier = extracted(data_root, capsys, tmp_path)

    assert (
        invoke(
            data_root,
            "context",
            "review",
            identifier,
            "--reviewer",
            "eturner",
            "--request-re-extraction",
            "The comment service and the webhook receiver were merged into one component.",
        )
        == 0
    )
    output = capsys.readouterr().out

    assert "request_more_analysis" in output
    assert "next workflow run" in output


def test_status_reports_the_phase_and_the_pending_checkpoint(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Three different things printed as three (DEC-031): the deliverable's lifecycle, the run's
    position, and what the run is waiting for."""
    identifier = extracted(data_root, capsys, tmp_path)

    assert invoke(data_root, "assessment", "status", identifier) == 0
    output = capsys.readouterr().out

    assert "status:           draft" in output
    assert "run status:       paused" in output
    assert "phase:            human_context_review" in output
    assert "checkpoint:       human_context_review" in output
    assert "awaiting:" in output
    assert "model calls:      1" in output


def test_status_says_so_before_any_run_has_started(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)

    assert invoke(data_root, "assessment", "status", identifier) == 0
    assert "no workflow run has started" in capsys.readouterr().out


def test_no_context_command_prints_a_provider_key(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The key is configured for every command in this file, so this is a real check."""
    identifier = extracted(data_root, capsys, tmp_path)
    exported = tmp_path / "review.yaml"

    invoke(data_root, "context", "show", identifier, "--evidence")
    invoke(data_root, "context", "review", identifier, "--export", str(exported))
    invoke(data_root, "context", "review", identifier, "--approve", "cmp-001")
    invoke(data_root, "context", "approve", identifier)
    invoke(data_root, "assessment", "status", identifier)

    captured = capsys.readouterr()
    assert FAKE_KEY not in captured.out
    assert FAKE_KEY not in captured.err
    assert FAKE_KEY not in exported.read_text()


def test_context_help_follows_the_corpus_prose_register() -> None:
    """Flat declarative, no marketing language, no emoji — `CLAUDE.md`'s working norm, applied to
    the one surface a reviewer reads before anything else."""
    import io
    from contextlib import redirect_stdout

    parser = build_parser()
    groups = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    context = groups.choices["context"]
    nested = next(
        action for action in context._actions if isinstance(action, argparse._SubParsersAction)
    )

    texts = [context.format_help()]
    for command in nested.choices.values():
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            command.print_help()
        texts.append(buffer.getvalue())

    banned = ("powerful", "simply", "easily", "seamless", "just ", "!", "🚀", "✨", "✅")
    for text in texts:
        lowered = text.lower()
        for word in banned:
            assert word not in lowered, f"{word!r} appears in help output"
        assert text == text.replace("  \n", "\n")


# ------------------------------------------------------------------------------------------
# The pipeline: run, resume, the finding checkpoint, and the report (#261)
# ------------------------------------------------------------------------------------------


def _recorded_file(path: Path, payload: object) -> str:
    from pydantic import BaseModel

    assert isinstance(payload, BaseModel)
    path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    return str(path)


def _pipeline_recordings(tmp_path: Path) -> dict[str, str]:
    """The five agents' recorded responses, borrowed from the driver's end-to-end test."""
    from test_driver import ASSESSMENT, EXTRACTION, MAPPING, THREAT

    from trace_ai.domain.proposals import ContextExtractionProposal
    from trace_ai.domain.proposals.critical_review import CriticalReviewProposal
    from trace_ai.domain.proposals.evidence_validation import EvidenceValidationProposal
    from trace_ai.domain.proposals.mapping import MappingProposal
    from trace_ai.domain.proposals.threat_analysis import ThreatAnalysisProposal

    return {
        "extraction": _recorded_file(
            tmp_path / "extraction.json", ContextExtractionProposal.model_validate(EXTRACTION)
        ),
        "threats": _recorded_file(
            tmp_path / "threats.json", ThreatAnalysisProposal.model_validate({"threats": [THREAT]})
        ),
        "mapping": _recorded_file(
            tmp_path / "mapping.json", MappingProposal.model_validate({"mappings": [MAPPING]})
        ),
        "evidence": _recorded_file(
            tmp_path / "evidence.json",
            EvidenceValidationProposal.model_validate({"assessments": [ASSESSMENT]}),
        ),
        "critique": _recorded_file(
            tmp_path / "critique.json", CriticalReviewProposal.model_validate({"critiques": []})
        ),
    }


def _approve_everything_in(review_file: Path) -> None:
    import yaml

    document = yaml.safe_load(review_file.read_text(encoding="utf-8"))
    for group in ("components", "actors", "assets", "data_flows", "trust_boundaries", "claims"):
        for entry in document.get(group) or []:
            entry["decision"] = "approve"
    review_file.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def _sections_file(data_root: Path, identifier: str, path: Path) -> str:
    from trace_ai.domain.proposals.report_sections import LimitationEntry, ReportSections
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.report.input_assembly import assemble_report_input

    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        assembly = assemble_report_input(
            service.handle(identifier),
            prompt_versions={"generate-report-sections": "generate-report-sections-v1"},
            model="deterministic-fake",
            model_configuration="offline-fake",
        )
        sections = ReportSections.model_validate(
            {
                "executive_summary": "The assessment reviewed the webhook processing path.",
                "system_overview": "The system accepts repository events and queues jobs.",
                "risk_summary": "The approved findings concern unverified event ingestion.",
                "limitations": [
                    LimitationEntry.model_validate(
                        {"limitation_id": limitation.limitation_id, "text": limitation.facts}
                    )
                    for limitation in assembly.required_limitations
                ],
            }
        )
    return _recorded_file(path, sections)


def test_the_pipeline_runs_end_to_end_from_the_command_line(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """#261's acceptance criterion: create, run, review both checkpoints, and render the report
    using only documented commands and recorded responses. No provider key exists in this test."""
    identifier = created(data_root, capsys)
    assert (
        invoke(
            data_root,
            "source",
            "add",
            identifier,
            str(FORGEFLOW_INPUT / "architecture-overview.md"),
        )
        == 0
    )
    recordings = _pipeline_recordings(tmp_path)
    capsys.readouterr()

    # Run to checkpoint 1.
    assert (
        invoke(
            data_root,
            "run",
            identifier,
            "--model-profile",
            "offline-fake",
            "--response",
            recordings["extraction"],
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "paused at:    human_context_review" in output

    # Resuming with nothing decided pauses again — partial progress, not an error.
    assert invoke(data_root, "resume", identifier, "--model-profile", "offline-fake") == 0
    assert "paused at:    human_context_review" in capsys.readouterr().out

    # Checkpoint 1: export, approve everything, apply, approve the baseline.
    review_file = tmp_path / "context-review.yaml"
    assert invoke(data_root, "context", "review", identifier, "--export", str(review_file)) == 0
    _approve_everything_in(review_file)
    assert (
        invoke(
            data_root,
            "context",
            "review",
            identifier,
            "--reviewer",
            "reviewer",
            "--apply",
            str(review_file),
        )
        == 0
    )
    assert invoke(data_root, "context", "approve", identifier, "--reviewer", "reviewer") == 0
    capsys.readouterr()

    # Resume to checkpoint 2.
    assert (
        invoke(
            data_root,
            "resume",
            identifier,
            "--model-profile",
            "offline-fake",
            "--response",
            recordings["threats"],
            "--response",
            recordings["mapping"],
            "--response",
            recordings["evidence"],
            "--response",
            recordings["critique"],
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "paused at:    human_finding_review" in output

    # Concluding with an undecided finding is refused, with the finding named.
    assert invoke(data_root, "findings", "approve", identifier) == 1
    assert "fnd-001" in capsys.readouterr().err

    # The package prints; severity is assigned; the finding is approved; the review concludes.
    assert invoke(data_root, "findings", "show", identifier) == 0
    assert "fnd-001" in capsys.readouterr().out
    assert (
        invoke(
            data_root,
            "findings",
            "review",
            identifier,
            "--reviewer",
            "reviewer",
            "--severity",
            "fnd-001=medium",
            "--approve",
            "fnd-001",
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "2 decision(s) recorded as reviewer" in output
    assert invoke(data_root, "findings", "approve", identifier) == 0
    capsys.readouterr()

    # Resume to completion, then print the report and its manifest.
    sections = _sections_file(data_root, identifier, tmp_path / "sections.json")
    assert (
        invoke(
            data_root,
            "resume",
            identifier,
            "--model-profile",
            "offline-fake",
            "--response",
            sections,
        )
        == 0
    )
    assert "completed" in capsys.readouterr().out

    assert invoke(data_root, "report", "show", identifier) == 0
    report = capsys.readouterr().out
    assert "fnd-001" in report

    assert invoke(data_root, "report", "show", identifier, "--manifest") == 0
    manifest = capsys.readouterr().out
    assert '"manifest_version"' in manifest

    # The whole chain verifies from the command line, in one line of output.
    assert invoke(data_root, "verify", identifier) == 0
    verified = capsys.readouterr().out
    assert "1 manifest" in verified


def test_report_show_is_refused_while_no_report_exists(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    assert invoke(data_root, "report", "show", identifier) == 1
    assert "no report has been rendered" in capsys.readouterr().err


def test_a_failed_run_exits_one_and_names_the_error(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The documented exit codes: 0 for a pause or completion, 1 for a failed run."""
    identifier = created(data_root, capsys)
    assert invoke(data_root, "run", identifier, "--model-profile", "offline-fake") == 1
    assert "no source documents" in capsys.readouterr().err


def test_an_unreadable_recording_is_refused_by_name(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    identifier = created(data_root, capsys)
    bad = tmp_path / "empty.json"
    bad.write_text("{}", encoding="utf-8")
    assert (
        invoke(
            data_root,
            "run",
            identifier,
            "--model-profile",
            "offline-fake",
            "--response",
            str(bad),
        )
        == 1
    )
    assert "empty.json" in capsys.readouterr().err


def test_run_without_a_key_is_a_sentence_not_a_traceback(
    data_root: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The most likely operator slip: forgetting `--model-profile offline-fake`, so the default
    profile builds the real adapter with no key configured. `MissingSettingError` is in
    `EXPECTED_ERRORS`, so the answer is the fix in one line rather than a stack trace (#319)."""
    from trace_ai.config import Settings

    identifier = created(data_root, capsys)
    assert invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT)) == 0
    capsys.readouterr()

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "trace_ai.infrastructure.model.anthropic_adapter.get_settings",
        lambda: Settings(_env_file=None),
    )
    assert invoke(data_root, "run", identifier) == 1
    captured = capsys.readouterr()
    assert "error: ANTHROPIC_API_KEY is not set" in captured.err
    assert "Traceback" not in captured.err


def test_an_offline_run_with_missing_responses_is_a_sentence_not_a_traceback(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The second slip: `offline-fake` with no `--response`. The fake's exhaustion is typed and in
    `EXPECTED_ERRORS`, and the message speaks to an operator — no test vocabulary (#319)."""
    identifier = created(data_root, capsys)
    assert invoke(data_root, "source", "add", identifier, str(FORGEFLOW_INPUT)) == 0
    capsys.readouterr()

    assert invoke(data_root, "run", identifier, "--model-profile", "offline-fake") == 1
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "no response left to serve" in captured.err
    assert "Traceback" not in captured.err
    assert "test" not in captured.err.split("error:")[1].lower()


def test_evaluate_replays_a_scenario_and_prints_its_metrics(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """`trace evaluate` is the harness's surface (#266): offline, metrics printed, feed named."""
    assert (
        invoke(
            data_root,
            "evaluate",
            "forgeflow",
            "--label",
            "cli-test",
            "--work-root",
            str(tmp_path / "work"),
            "--results-root",
            str(tmp_path / "results"),
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "scenario:     forgeflow (clean, label cli-test)" in output
    assert "false_negative_rate" in output
    assert "feed:" in output


def test_evaluate_requires_a_scenario_or_all(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke(data_root, "evaluate") == 1
    assert "name one scenario or pass --all" in capsys.readouterr().err


def test_evaluate_all_names_the_scenarios_it_skips(
    data_root: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """No silent caps: a scenario without a recording is reported, never quietly dropped."""
    assert (
        invoke(
            data_root,
            "evaluate",
            "--all",
            "--label",
            "cli-all",
            "--work-root",
            str(tmp_path / "work"),
            "--results-root",
            str(tmp_path / "results"),
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "skipped" not in output
    assert "scenario:     forgeflow" in output
    assert "scenario:     husky-ai" in output
    assert "scenario:     crypto-wallet" in output
    assert "scenario:     missing-docs" in output
    assert "scenario:     order-notifier" in output
    assert "scenario:     translation-gateway" in output
    assert "scenario:     parcel-platform" in output
    assert "scenario:     unsigned-webhooks" in output
    assert "scenario:     contradictory-docs" in output
    assert "scenario:     invoice-agent" in output
    assert "scenario:     oidc-portal" in output
    assert "scenario:     managed-db-service" in output


# ------------------------------------------------------------------------------------------
# The reviewer rubric (issue #334)
# ------------------------------------------------------------------------------------------


def _seed_run(data_root: Path) -> str:
    """An assessment with a started run, seeded directly: the rubric attaches to a run."""
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.execution_ledger import start_run

    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        created = service.create(
            "Rubric", default_configuration("primary-development", "stride-scenario-based")
        )
        start_run(
            service.handle(created.id),
            workflow_version="0.1",
            model_profile="primary-development",
        )
        return created.id


def _full_scores(**changes: str) -> list[str]:
    from trace_ai.services.evaluation.report_metrics import RUBRIC_CATEGORIES

    scores = dict.fromkeys(RUBRIC_CATEGORIES, "4") | changes
    arguments: list[str] = []
    for category, value in scores.items():
        arguments += ["--score", f"{category}={value}"]
    return arguments


def test_rubric_records_all_seven_scores_as_reviewer_judgement(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from trace_ai.domain.evaluation_result import EvaluationResult, EvaluatorType
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.evaluation.report_metrics import RUBRIC_CATEGORIES

    identifier = _seed_run(data_root)
    assert (
        invoke(
            data_root,
            "report",
            "rubric",
            identifier,
            "--reviewer",
            "reviewer-local",
            "--comments",
            "readable throughout",
            *_full_scores(),
        )
        == 0
    )
    assert "recorded 7 rubric score(s)" in capsys.readouterr().out

    with AssessmentStore.at_root(data_root) as store:
        service = AssessmentService(store, artifact_root=data_root)
        rows = service.handle(identifier).objects.list(EvaluationResult)
    assert {row.metric_name for row in rows} == {
        f"rubric_{category}" for category in RUBRIC_CATEGORIES
    }
    assert all(row.evaluator_type is EvaluatorType.REVIEWER for row in rows)
    assert all("reviewer-local" in (row.notes or "") for row in rows)


def test_rubric_refuses_an_unknown_dimension_in_one_line(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = _seed_run(data_root)
    arguments = [*_full_scores()[:-2], "--score", "vibes=3"]
    assert invoke(data_root, "report", "rubric", identifier, *arguments) == 1
    error = capsys.readouterr().err.strip()
    assert error.startswith("error:")
    assert "vibes" in error
    assert "\n" not in error


def test_rubric_refuses_an_out_of_range_score_in_one_line(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = _seed_run(data_root)
    assert invoke(data_root, "report", "rubric", identifier, *_full_scores(report_quality="6")) == 1
    error = capsys.readouterr().err.strip()
    assert error.startswith("error:")
    assert "one to five" in error
    assert "\n" not in error


def test_rubric_refuses_a_malformed_or_duplicated_score(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = _seed_run(data_root)
    assert invoke(data_root, "report", "rubric", identifier, "--score", "report_quality") == 1
    assert "CATEGORY=N" in capsys.readouterr().err

    arguments = [*_full_scores(), "--score", "report_quality=2"]
    assert invoke(data_root, "report", "rubric", identifier, *arguments) == 1
    assert "scored twice" in capsys.readouterr().err


def test_rubric_without_a_run_exits_non_zero(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    identifier = created(data_root, capsys)
    assert invoke(data_root, "report", "rubric", identifier, *_full_scores()) == 1
    assert "no workflow run" in capsys.readouterr().err
