"""The report-generation prompt as an artifact (issue #105).

`prompts/reporting/generate-report-sections-v1.md` is the sixth and last agent prompt held to
`agent-design.md` section 24's thirteen sections by a test written from the document. The
sentences worth pinning are section 19's: the agent writes four passages inside a document it
does not own, a zero-finding assessment is a result and never an assurance, and structure
belongs to the renderer.
"""

from __future__ import annotations

import json
import re

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.proposals.report_sections import ReportSections
from trace_ai.services.prompts import PromptRegistry, UnresolvedMarkerError

AGENT_DESIGN = PROJECT_ROOT / "docs" / "architecture" / "agent-design.md"
PROMPT = PROJECT_ROOT / "prompts" / "reporting" / "generate-report-sections-v1.md"
SHARED = PROJECT_ROOT / "prompts" / "shared"

SCHEMA_MARKER = "schema.report_sections"


def documented_sections() -> list[str]:
    body = AGENT_DESIGN.read_text(encoding="utf-8").split("# 24. Prompt Structure", 1)[1]
    body = body.split("# 25.", 1)[0]
    stop = "The authoritative instructions must clearly separate"
    return [
        line.strip()
        for line in body.split(stop, 1)[0].splitlines()
        if line.strip() and not line.strip().startswith(("#", "Each agent prompt"))
    ]


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def prompt_headings() -> list[str]:
    return re.findall(r"^## (.+)$", PROMPT.read_text(encoding="utf-8"), flags=re.MULTILINE)


def composed() -> str:
    return (
        PromptRegistry()
        .compose(
            "generate-report-sections",
            "v1",
            {
                SCHEMA_MARKER: json.dumps(ReportSections.model_json_schema(), indent=2),
                "input.report": "<the assembled approved input>",
            },
        )
        .text
    )


def test_the_prompt_exists_where_section_34_names_it() -> None:
    assert PROMPT.is_file()


def test_the_prompt_carries_all_thirteen_sections_in_order() -> None:
    headings = prompt_headings()
    for documented in documented_sections():
        assert documented in headings, f"the prompt has no {documented!r} section"

    positions = [headings.index(section) for section in documented_sections()]
    assert positions == sorted(positions)


def test_the_input_data_section_is_last() -> None:
    assert prompt_headings()[-1] == "Input data"


@pytest.mark.parametrize("heading", ["## Evidence policy", "## Handling uncertainty"])
def test_each_shared_block_is_composed_in_exactly_once(heading: str) -> None:
    assert composed().count(heading) == 1


def test_the_source_content_boundary_is_composed_in_exactly_once() -> None:
    policy = (SHARED / "source-content-boundary-v1.md").read_text(encoding="utf-8")
    heading = next(line for line in policy.splitlines() if line.startswith("## "))
    assert composed().count(heading) == 1


def test_the_schema_marker_is_substituted_from_the_application_model() -> None:
    text = composed()
    assert SCHEMA_MARKER not in text
    assert "executive_summary" in text
    assert "limitation_id" in text


def test_an_unsubstituted_marker_is_refused() -> None:
    with pytest.raises(UnresolvedMarkerError):
        PromptRegistry().compose("generate-report-sections", "v1", {})


def test_the_prompt_says_the_agent_does_not_own_the_document() -> None:
    body = flat(PROMPT.read_text(encoding="utf-8"))
    assert "four passages inside a document you do not own" in body
    assert "You are not writing the report" in body


def test_the_prompt_states_the_zero_finding_meaning() -> None:
    """A report with no findings is a successful report, and never an assurance."""
    body = flat(PROMPT.read_text(encoding="utf-8"))
    assert "is a result, not an omission" in body
    assert "never as an assurance that the system is secure" in body


def test_the_prompt_forbids_document_structure_and_uncarried_identifiers() -> None:
    body = flat(PROMPT.read_text(encoding="utf-8"))
    assert "Markdown headings, tables, links, anchors" in body
    assert "identifier the input did not carry" in body


def test_the_prompt_separates_the_gap_from_the_finding() -> None:
    """The DEC-009 distinction, stated where the prose writer will read it."""
    body = flat(PROMPT.read_text(encoding="utf-8"))
    assert "different conclusions" in body
