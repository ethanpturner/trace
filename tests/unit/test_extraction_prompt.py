"""Tests holding the context-extraction prompt to the corpus that specifies it.

A prompt is the one artifact where a quiet omission has no symptom. A missing section, a rule that
drifted out of a shared block, a schema that no longer matches what the application accepts — none
of those raises anything. The agent answers, the answer validates, and the assessment is worse in a
way nobody can point at.

So the prompt is held to `agent-design.md` section 24's thirteen sections *in order*, to the three
shared blocks it declares, and to the application's own exported schema. The last is the strongest:
the schema is substituted at composition rather than copied, so it cannot drift at all.
"""

from __future__ import annotations

import json
import re

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.services.prompts import PromptRegistry, UnresolvedMarkerError

AGENT_DESIGN = PROJECT_ROOT / "docs" / "architecture" / "agent-design.md"
PROMPT = PROJECT_ROOT / "prompts" / "context" / "extract-context-v1.md"
SHARED = PROJECT_ROOT / "prompts" / "shared"

SCHEMA_MARKER = "schema.context_extraction_proposal"


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


def prompt_headings() -> list[str]:
    return re.findall(r"^## (.+)$", PROMPT.read_text(encoding="utf-8"), flags=re.MULTILINE)


def composed() -> str:
    registry = PromptRegistry()
    return registry.compose(
        "extract-context",
        "v1",
        {
            SCHEMA_MARKER: json.dumps(ContextExtractionProposal.model_json_schema(), indent=2),
            "input.source_content": "<the documents under review>",
        },
    ).text


# ------------------------------------------------------------------------------------------
# The four files section 34 names
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "source-content-boundary-v1.md",
        "evidence-policy-v1.md",
        "uncertainty-policy-v1.md",
    ],
)
def test_each_shared_block_exists(name: str) -> None:
    assert (SHARED / name).is_file()


def test_the_extraction_prompt_exists_where_section_34_names_it() -> None:
    assert PROMPT.is_file()


# ------------------------------------------------------------------------------------------
# Section 24's structure
# ------------------------------------------------------------------------------------------


def test_section_24_was_parsed() -> None:
    """Guard the parser: an empty parse makes the ordering test below vacuous."""
    assert len(documented_sections()) == 13


def test_the_prompt_carries_all_thirteen_sections_in_order() -> None:
    """Order matters as much as presence. Section 24 puts the authoritative instructions before the
    input data, which is the arrangement that makes the untrusted boundary meaningful — rules first,
    material second."""
    headings = prompt_headings()
    for documented in documented_sections():
        assert documented in headings, f"the prompt has no {documented!r} section"

    positions = [headings.index(section) for section in documented_sections()]
    assert positions == sorted(positions), "the prompt's sections are out of section 24's order"


def test_the_input_data_section_is_last() -> None:
    """Untrusted content arrives after every rule that governs it. A prompt that put the documents
    first would be asking the model to read them before being told what they are."""
    assert prompt_headings()[-1] == "Input data"


def test_the_untrusted_boundary_is_stated_in_the_trusted_half() -> None:
    """The delimiter is named under Authoritative instructions, above the content it delimits. A
    boundary announced inside the untrusted region is a boundary the untrusted region could
    describe differently."""
    text = PROMPT.read_text(encoding="utf-8")
    instructions = text.index("## Authoritative instructions")
    input_data = text.index("## Input data")
    assert instructions < text.index("<source-content>") < input_data or (
        "<source-content>" in text[instructions:input_data]
    )
    assert "<source-content>" in text[instructions:input_data]


# ------------------------------------------------------------------------------------------
# Composition and the schema
# ------------------------------------------------------------------------------------------


def test_the_prompt_declares_the_shared_blocks_and_carries_none_of_their_text() -> None:
    """Composition is the mechanism section 34 asks for, and a copy is what it prevents."""
    raw = PROMPT.read_text(encoding="utf-8")
    for block in SHARED.glob("*.md"):
        first_paragraph = block.read_text(encoding="utf-8").split("\n\n")[1]
        assert first_paragraph not in raw, f"{block.name} is copied into the prompt"

    text = composed()
    for block in SHARED.glob("*.md"):
        assert block.read_text(encoding="utf-8").strip() in text


def test_the_schema_is_substituted_rather_than_restated() -> None:
    """A copy of the schema drifts until a test notices; a substitution cannot drift at all. What is
    embedded is the application's own export, so the prompt describes what the application will
    actually accept."""
    exported = json.dumps(ContextExtractionProposal.model_json_schema(), indent=2)
    assert SCHEMA_MARKER in PROMPT.read_text(encoding="utf-8")
    assert exported in composed()


def test_composing_without_the_schema_is_refused() -> None:
    """A prompt composed with a hole where the schema goes still runs and still answers."""
    with pytest.raises(UnresolvedMarkerError, match=re.escape(SCHEMA_MARKER)):
        PromptRegistry().compose("extract-context", "v1")


# ------------------------------------------------------------------------------------------
# What the prompt must say, and must not
# ------------------------------------------------------------------------------------------


def test_injection_like_content_is_reported_and_not_acted_on() -> None:
    """`agent-design.md` section 25 and DEC-021. The instruction has to say both halves: record it,
    and do not follow it — a prompt that said only the first leaves the second to inference."""
    text = composed().lower()
    assert "injection_attempt" in text
    assert "do not follow it" in text


def test_the_evidence_rule_is_stated_in_both_directions() -> None:
    """A documented claim cites a passage, and a claim that cannot is `assumed` or `unknown`
    (DEC-009). Stating only the first leaves an agent to decide what to do with the rest."""
    text = composed().lower()
    assert "documented" in text and "cites at least one evidence" in text
    assert "assumed" in text and "unknown" in text


def test_the_prompt_forbids_severity_and_findings() -> None:
    """Section 7's prohibitions, in the artifact rather than only in the schema. The schema makes
    them impossible; the prompt makes them not worth attempting, which saves a retry."""
    text = composed().lower()
    assert "assign severity" in text
    assert "generate findings" in text


def test_missing_documentation_is_not_proof_of_absence() -> None:
    """The sentence this whole project exists around (DEC-009), stated to the agent in the words the
    corpus uses."""
    assert "missing documentation is not proof that a control is absent" in composed().lower()


@pytest.mark.parametrize(
    "forbidden",
    ["anthropic", "openai", "claude-", "gpt-", "temperature", "top_p", "top_k"],
)
def test_the_prompt_names_no_provider_model_or_sampling_control(forbidden: str) -> None:
    """Generation settings belong to the model abstraction (DEC-014), not to the artifact. A prompt
    naming a model is a prompt that has to be edited to change one."""
    assert forbidden not in composed().lower()


@pytest.mark.parametrize("path", [PROMPT, *sorted(SHARED.glob("*.md"))])
def test_the_register_matches_the_corpus(path: object) -> None:
    """Flat declarative, no marketing language, no emoji. Prompts are read by a reviewer explaining
    the system to someone else, so they are part of the corpus rather than adjacent to it."""
    text = path.read_text(encoding="utf-8")  # type: ignore[attr-defined]
    assert not re.search(r"[\U0001F300-\U0001FAFF✀-➿]", text), "emoji"
    for marketing in ("powerful", "seamless", "cutting-edge", "world-class", "best-in-class"):
        assert marketing not in text.lower(), marketing
