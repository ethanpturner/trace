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

**Two commands are absent rather than stubbed.** `trace context extract` and `trace context show`
need an agent that does not exist, and `--help` is a promise. Issue #58.
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


def test_archive_is_the_only_transition_offered(
    data_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DEC-031: every other transition is written by a workflow node.

    A user-settable `approved` would be a checkpoint bypass with extra steps, so the surface does
    not offer one.
    """
    identifier = created(data_root, capsys)
    assert invoke(data_root, "assessment", "archive", identifier) == 0
    assert "archived" in capsys.readouterr().out

    offered = _subcommands("assessment")
    assert offered == {"create", "list", "status", "archive"}
    assert "approve" not in offered


# ------------------------------------------------------------------------------------------
# Sources and evidence
# ------------------------------------------------------------------------------------------


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

    assert "Hello from trace!" in output
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


def test_context_commands_are_absent_rather_than_stubbed() -> None:
    """They need the Context Extraction agent, which does not exist, and `--help` is a promise."""
    parser = build_parser()
    groups = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    assert "context" not in groups.choices


def test_the_command_surface_is_the_one_dec_032_confirms() -> None:
    parser = build_parser()
    groups = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    assert set(groups.choices) == {"assessment", "source", "evidence"}
    assert _subcommands("source") == {"add", "list"}
    assert _subcommands("evidence") == {"list", "show", "verify"}


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
    assert "splitlines" not in called, "the CLI is segmenting something"


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
