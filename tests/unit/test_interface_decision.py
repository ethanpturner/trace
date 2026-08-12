"""Tests keeping the corpus saying one thing about the interface, and the dependency list short.

DEC-032 settles a contradiction that survived because nobody had to read both halves at once:
`current-architecture.md` section 5.1 preferred a local web application, and the roadmap said the
opposite in four places. Neither document was wrong on its own.

These tests check documents and configuration rather than behaviour. The read-only view now exists
(#276, DEC-078); its rendering and read-only discipline are tested in `test_interface.py`, and what
remains here guards the corpus agreeing with itself and no CLI or web framework arriving by import.
Issue #35.
"""

from __future__ import annotations

import re
import tomllib

from trace_ai.config import PROJECT_ROOT

ARCHITECTURE = PROJECT_ROOT / "docs" / "architecture" / "current-architecture.md"
ROADMAP = PROJECT_ROOT / "docs" / "product" / "roadmap.md"
DECISION_LOG = PROJECT_ROOT / "docs" / "architecture" / "decision-log.md"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"

# Packages that would mean a CLI framework had been adopted. `argparse` is in the standard library
# and needs no entry, which is the point.
CLI_FRAMEWORKS = ("typer", "click", "fire", "docopt", "cleo", "rich-click")


def declared_dependencies() -> set[str]:
    """Runtime dependency names, without version specifiers or extras."""
    parsed = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    declared = parsed["project"]["dependencies"]
    return {re.split(r"[<>=!\[ ]", entry, maxsplit=1)[0].strip().lower() for entry in declared}


def test_no_cli_framework_is_declared() -> None:
    """DEC-032 chose `argparse`, and the reasoning was partly about the dependency list itself.

    Every declared dependency is a supply-chain surface on a project whose subject is architectural
    risk. Adopting a framework is a decision with a stated trigger -- command count or help quality
    -- not something that arrives with a convenient import.
    """
    adopted = declared_dependencies() & set(CLI_FRAMEWORKS)
    assert not adopted, (
        f"{sorted(adopted)} is declared. DEC-032 chose argparse; adopting a framework needs an "
        f"entry saying the trigger was reached."
    )


def test_the_issue_s_claim_about_typer_was_already_stale() -> None:
    """Recorded because the issue asserted it and it was false by the time it was read.

    `m0-dx-17` said `typer` was "present only transitively through another package", which was true
    when the backlog was seeded and stopped being true when DEC-016 removed the orchestration
    packages that carried it. Adopting it would have been adding a dependency, not using one.
    """
    import importlib.util

    assert importlib.util.find_spec("typer") is None


def test_section_five_one_no_longer_prefers_a_web_application() -> None:
    """The sentence that made the corpus contradict itself."""
    text = ARCHITECTURE.read_text(encoding="utf-8")
    assert "preferred MVP interface is a small local web application" not in text
    assert "DEC-032" in text, "section 5.1 should cite the decision that corrected it"


def test_the_roadmap_and_the_architecture_agree() -> None:
    """The contradiction was lopsided: one sentence against four.

    Both documents now say the same thing, so a reader reaching either first is not misled.
    """
    assert "do not begin with the web interface" in ROADMAP.read_text(encoding="utf-8").casefold()
    assert "command-line interface" in ARCHITECTURE.read_text(encoding="utf-8")


def test_the_resolved_open_questions_are_struck() -> None:
    """DEC-004 and `project-scope.md` both carried the question; leaving either open re-opens it."""
    log = DECISION_LOG.read_text(encoding="utf-8")
    assert "~~Should the MVP lead with a local web interface or command-line interface?~~" in log

    scope = (PROJECT_ROOT / "docs" / "architecture" / "project-scope.md").read_text(
        encoding="utf-8"
    )
    assert "~~Should the first interface be a CLI, local web application, or both?~~" in scope


def test_the_planned_command_surface_is_stated_the_same_way_twice() -> None:
    """`README.md` and the roadmap both list it, so they are the pair that can drift."""
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")

    for command in (
        "trace assessment create",
        "trace assessment list",
        "trace assessment status",
        "trace assessment archive",
        "trace source add",
        "trace context extract",
        "trace context show",
    ):
        assert command in roadmap, f"the roadmap does not list {command!r}"
        assert command in readme, f"README.md does not list {command!r}"


def test_the_threat_model_records_the_read_only_view_boundary() -> None:
    """The Stage 5 read-only view (DEC-078) re-introduced the browser-to-application boundary.

    Through M8 the threat model recorded the boundary as absent, and this test was its trip-wire:
    if a view shipped, the assertion failed and the threat model had to be revisited. It has been,
    so the test now pins the boundary's presence — the review trigger fired and section 5 was
    rewritten with the view's mitigations rather than dropped.
    """
    threat_model = (PROJECT_ROOT / "docs" / "architecture" / "threat-model.md").read_text(
        encoding="utf-8"
    )
    assert "This boundary exists as of the Stage 5 read-only view" in threat_model
    assert "DEC-078" in threat_model
    # The read-only discipline is the request-forgery mitigation, not a token on a mutable surface.
    assert "nothing to forge" in threat_model


def test_no_web_framework_is_declared_either() -> None:
    """Stage 5's read-only view uses stdlib `http.server` (DEC-078); no web framework is declared."""
    web = {"fastapi", "flask", "django", "starlette", "uvicorn"}
    assert not (declared_dependencies() & web)
