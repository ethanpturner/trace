"""The threat prompt as an artifact: structure, composition, and what it must and must not say.

`prompts/threats/generate-scenario-threats-v1.md` is a file, and a file drifts. These tests hold it
to `agent-design.md` section 24's thirteen sections *in order*, to the three shared blocks being
composed rather than copied, and to section 10's prohibitions actually appearing in the text that
reaches the model.

They mirror `tests/unit/test_extraction_prompt.py` deliberately. Two agent prompts held to one
structure by two tests written from one document is the arrangement that keeps the third and fourth
prompts honest when they arrive.

**A prompt test asserts what the prompt says, not what the model does.** Everything here is
advisory by nature -- a sentence in a prompt is a request. The defences that are not advisory are
the schema and the node's validation, and they live in `test_threat_analysis_node.py`.
"""

from __future__ import annotations

import json
import re

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.proposals.threat_analysis import ThreatAnalysisProposal
from trace_ai.services.prompts import PromptRegistry, UnresolvedMarkerError

AGENT_DESIGN = PROJECT_ROOT / "docs" / "architecture" / "agent-design.md"
PROMPT = PROJECT_ROOT / "prompts" / "threats" / "generate-scenario-threats-v1.md"
SHARED = PROJECT_ROOT / "prompts" / "shared"

SCHEMA_MARKER = "schema.threat_analysis_proposal"


def documented_sections() -> list[str]:
    """Section 24's thirteen headings, parsed from the document rather than retyped."""
    body = AGENT_DESIGN.read_text(encoding="utf-8").split("# 24. Prompt Structure", 1)[1]
    body = body.split("# 25.", 1)[0]
    stop = "The authoritative instructions must clearly separate"
    return [
        line.strip()
        for line in body.split(stop, 1)[0].splitlines()
        if line.strip() and not line.strip().startswith(("#", "Each agent prompt"))
    ]


def flat(text: str) -> str:
    """Collapse runs of whitespace, so a phrase assertion survives the prompt being rewrapped.

    Line breaks in a Markdown paragraph are a formatting choice. A test that failed when a
    sentence moved across a line would be testing the wrap, and would be turned off the first
    time somebody reflowed the file.
    """
    return re.sub(r"\s+", " ", text)


def prompt_headings() -> list[str]:
    return re.findall(r"^## (.+)$", PROMPT.read_text(encoding="utf-8"), flags=re.MULTILINE)


def composed() -> str:
    return (
        PromptRegistry()
        .compose(
            "generate-scenario-threats",
            "v1",
            {
                SCHEMA_MARKER: json.dumps(ThreatAnalysisProposal.model_json_schema(), indent=2),
                "input.source_content": "<the documents under review>",
            },
        )
        .text
    )


# ------------------------------------------------------------------------------------------
# The files section 34 names
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["source-content-boundary-v1.md", "evidence-policy-v1.md", "uncertainty-policy-v1.md"],
)
def test_each_shared_block_exists(name: str) -> None:
    assert (SHARED / name).is_file()


def test_the_threat_prompt_exists_where_section_34_names_it() -> None:
    """Hyphenated, under `threats/`. `current-architecture.md` section 10's underscored names were
    corrected to match `agent-design.md` section 34, which is authoritative for agent contracts."""
    assert PROMPT.is_file()


# ------------------------------------------------------------------------------------------
# Section 24's structure
# ------------------------------------------------------------------------------------------


def test_section_24_was_parsed() -> None:
    """Guard the parser: an empty parse makes the ordering test below vacuous."""
    assert len(documented_sections()) == 13


def test_the_prompt_carries_all_thirteen_sections_in_order() -> None:
    headings = prompt_headings()
    for documented in documented_sections():
        assert documented in headings, f"the prompt has no {documented!r} section"

    positions = [headings.index(section) for section in documented_sections()]
    assert positions == sorted(positions), "the prompt's sections are out of section 24's order"


def test_the_input_data_section_is_last() -> None:
    assert prompt_headings()[-1] == "Input data"


def test_the_untrusted_boundary_is_stated_in_the_trusted_half() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    trusted = text[text.index("## Authoritative instructions") : text.index("## Input data")]
    assert "<source-content" in trusted
    assert "</source-content>" in trusted
    assert "neutralised" in trusted


def test_the_prompt_says_the_approved_context_is_not_source_content() -> None:
    """The one place this agent's boundary differs from the extractor's, so it is stated.

    A prompt that fenced everything would tell the model to treat the architecture it is reasoning
    from as untrusted; one that fenced nothing would put quoted source text in the trusted half.
    """
    text = PROMPT.read_text(encoding="utf-8")
    trusted = text[text.index("## Authoritative instructions") : text.index("## Input schema")]
    assert "not fenced" in flat(trusted)
    assert "application data" in flat(trusted)


# ------------------------------------------------------------------------------------------
# Composition and the schema
# ------------------------------------------------------------------------------------------


def test_the_prompt_declares_the_shared_blocks_and_carries_none_of_their_text() -> None:
    raw = PROMPT.read_text(encoding="utf-8")
    for block in SHARED.glob("*.md"):
        first_paragraph = block.read_text(encoding="utf-8").split("\n\n")[1]
        assert first_paragraph not in raw, f"{block.name} is copied into the prompt"

    text = composed()
    for block in SHARED.glob("*.md"):
        assert block.read_text(encoding="utf-8").strip() in text


def test_each_shared_block_appears_exactly_once_in_the_composed_prompt() -> None:
    """Composed once, not composed and also copied."""
    text = composed()
    for block in SHARED.glob("*.md"):
        body = block.read_text(encoding="utf-8").strip()
        assert text.count(body) == 1, f"{block.name} appears {text.count(body)} times"


def test_the_schema_is_substituted_rather_than_restated() -> None:
    exported = json.dumps(ThreatAnalysisProposal.model_json_schema(), indent=2)
    assert SCHEMA_MARKER in PROMPT.read_text(encoding="utf-8")
    assert exported in composed()


def test_composing_without_the_schema_is_refused() -> None:
    with pytest.raises(UnresolvedMarkerError, match=re.escape(SCHEMA_MARKER)):
        PromptRegistry().compose("generate-scenario-threats", "v1")


# ------------------------------------------------------------------------------------------
# Section 10's contract, in the text that reaches the model
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prohibition",
    [
        "Generate findings",
        "Assert that a control is missing",
        "Assign final severity",
        "Invent components",
        "Treat theoretical possibility as confirmed exposure",
        "Create threats unrelated to the approved context",
        "Recommend controls as a substitute for threat analysis",
    ],
)
def test_every_section_ten_prohibition_is_stated(prohibition: str) -> None:
    text = PROMPT.read_text(encoding="utf-8")
    prohibited = text[text.index("## Prohibited operations") : text.index("## Evidence rules")]
    assert prohibition in flat(prohibited)


@pytest.mark.parametrize(
    "element",
    ["Actor or failure source", "Precondition", "Attack path", "Impact"],
)
def test_the_required_threat_shape_is_defined(element: str) -> None:
    """Section 10's six elements of a scenario. A threat missing one is not yet a scenario."""
    text = PROMPT.read_text(encoding="utf-8")
    definitions = text[text.index("## Definitions") : text.index("## Allowed operations")]
    assert element in flat(definitions)


def test_the_prompt_forbids_one_generic_threat_per_category() -> None:
    """Section 10 states this directly, and it is the failure the node also refuses."""
    text = PROMPT.read_text(encoding="utf-8")
    assert "Do not produce one threat per category" in flat(text)
    assert "not an output quota" in flat(text)


def test_the_prompt_says_evidence_establishes_the_architecture_not_the_exploit() -> None:
    """Section 10: evidence "must establish the architecture conditions that make the threat
    plausible" and need not prove exploitation."""
    text = PROMPT.read_text(encoding="utf-8")
    rules = text[text.index("## Evidence rules") : text.index("## Handling of uncertainty")]
    assert "establishes the architecture, not the exploit" in flat(rules)
    assert "not required to cite a passage proving" in flat(rules)


def test_the_prompt_says_missing_documentation_is_not_absence() -> None:
    """DEC-009, restated where this agent would otherwise get it wrong."""
    text = PROMPT.read_text(encoding="utf-8")
    assert "Missing documentation is not proof that a control is absent" in flat(text)


def test_the_prompt_says_producing_few_threats_is_acceptable() -> None:
    """Section 10 puts quality above volume, and the node never retries for more."""
    text = PROMPT.read_text(encoding="utf-8")
    assert "Producing few threats is an acceptable outcome" in flat(text)


def test_the_prompt_tells_the_agent_not_to_mint_identifiers() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    assert "You do not assign threat identifiers" in flat(text)


@pytest.mark.parametrize(
    "forbidden", ["temperature", "top_p", "top_k", "claude-", "anthropic", "gpt-"]
)
def test_the_prompt_names_no_provider_model_or_sampling_control(forbidden: str) -> None:
    """DEC-014 keeps the provider behind the seam, and section 29's creativity column names no
    knob. A prompt that named one would be a second place a provider decision lived."""
    assert forbidden not in PROMPT.read_text(encoding="utf-8").casefold()
