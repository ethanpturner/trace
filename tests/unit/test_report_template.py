"""Tests for the report template and the section-ownership split DEC-035 fixes.

The report is described in three places — the decision entry's section table, the template artifact
the renderer follows, and `current-architecture.md` section 5.13 — and the whole point of the
decision is that they agree. Two documents disagreeing about how many sections the report has is
what produced the issue in the first place, so the agreement is asserted rather than maintained by
hand.

The property that matters most is **exactly one owner per section**. A section that is half
model-written prose and half rendered table is one a reviewer cannot check: they would have to read
every sentence against every object to know which parts a model wrote. That invariant is checked
from both directions here — the table assigns one owner, and the template's markers agree with it.

Nothing renders anything yet. These tests hold the specification together until the renderer exists
(#106), which is when the template stops being the only description of the report.
"""

from __future__ import annotations

import re

import pytest

from trace_ai.config import PROJECT_ROOT

TEMPLATE = PROJECT_ROOT / "templates" / "report-v1.md"
DECISION_LOG = PROJECT_ROOT / "docs" / "architecture" / "decision-log.md"
ARCHITECTURE = PROJECT_ROOT / "docs" / "architecture" / "current-architecture.md"
AGENT_DESIGN = PROJECT_ROOT / "docs" / "architecture" / "agent-design.md"

SECTION_COUNT = 16
AGENT_KEYS = ("executive_summary", "system_overview", "risk_summary", "limitations")

# `| 1 | Executive summary | `s01-executive-summary` | Agent — `executive_summary` | ... |`
DECISION_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|",
)
# `| 1 | Executive summary | Agent |`
ARCHITECTURE_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(Agent|Rendered)\s*\|\s*$")

TEMPLATE_ANCHOR = re.compile(r'^<a id="(s\d{2}-[a-z0-9-]+)"></a>$')
TEMPLATE_HEADING = re.compile(r"^## (\d+)\. (.+)$")
TEMPLATE_OWNER = re.compile(r"^<!-- owner: (agent|rendered) -->$")
MARKER = re.compile(r"\{\{ (agent|render|empty)\.([a-z_]+) \}\}")


def decision_entry() -> str:
    """The DEC-035 entry alone, so a table elsewhere in the log cannot satisfy these tests."""
    text = DECISION_LOG.read_text(encoding="utf-8")
    assert "## DEC-035:" in text, "DEC-035 is not in the decision log"
    entry = text.split("## DEC-035:", 1)[1]
    return entry.split("\n## DEC-0", 1)[0]


def decision_sections() -> list[tuple[int, str, str, str]]:
    """The section table: number, title, anchor, owner."""
    rows: list[tuple[int, str, str, str]] = []
    for line in decision_entry().splitlines():
        if match := DECISION_ROW.match(line):
            rows.append((int(match.group(1)), match.group(2), match.group(3), match.group(4)))
    return rows


def template_sections() -> list[tuple[int, str, str, str]]:
    """The template's sections: number, title, anchor, owner comment."""
    lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
    sections: list[tuple[int, str, str, str]] = []
    owner: str | None = None
    anchor: str | None = None
    for line in lines:
        if match := TEMPLATE_OWNER.match(line):
            owner = match.group(1)
            continue
        if match := TEMPLATE_ANCHOR.match(line):
            anchor = match.group(1)
            continue
        if match := TEMPLATE_HEADING.match(line):
            assert owner is not None and anchor is not None, (
                f"section {match.group(1)} has no owner comment or no anchor above it"
            )
            sections.append((int(match.group(1)), match.group(2), anchor, owner))
            owner = anchor = None
    return sections


def template_blocks() -> dict[int, list[tuple[str, str]]]:
    """Every marker in the template, grouped by the section number it appears under."""
    blocks: dict[int, list[tuple[str, str]]] = {}
    current = 0
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        if match := TEMPLATE_HEADING.match(line):
            current = int(match.group(1))
            continue
        for kind, name in MARKER.findall(line):
            blocks.setdefault(current, []).append((kind, name))
    return blocks


def test_the_section_table_was_found() -> None:
    """Guard the parser: an empty parse would make every comparison below vacuous."""
    assert len(decision_sections()) == SECTION_COUNT


def test_the_sections_are_numbered_from_one_without_gaps() -> None:
    """Numbering is fixed by the template rather than computed, so it has to be right once."""
    numbers = [number for number, _, _, _ in decision_sections()]
    assert numbers == list(range(1, SECTION_COUNT + 1))


def test_every_section_has_exactly_one_owner() -> None:
    """The invariant the decision exists to establish. Neither unassigned nor dual-assigned."""
    for number, title, _, owner in decision_sections():
        agent = owner.startswith("Agent")
        rendered = owner == "Rendered"
        assert agent != rendered, f"section {number} ({title}) is owned by {owner!r}"


def test_four_sections_are_model_written() -> None:
    """DEC-035's split: four prose sections, twelve rendered. The count is the cap on what a
    reviewer has to fact-check by reading."""
    owners = [owner for _, _, _, owner in decision_sections()]
    assert sum(owner.startswith("Agent") for owner in owners) == 4


def test_the_agent_sections_name_the_output_schema_fields() -> None:
    """The prose sections and `ReportSections` are the same four things under two names."""
    named = {
        owner.split("`")[1] for _, _, _, owner in decision_sections() if owner.startswith("Agent")
    }
    assert named == set(AGENT_KEYS)


def test_the_template_matches_the_decision_table() -> None:
    """Number, title, anchor, and owner, in order. The template is what the renderer follows and
    the table is what a reader of the decision sees; a difference between them is a silent one."""
    expected = [
        (number, title, anchor, "agent" if owner.startswith("Agent") else "rendered")
        for number, title, anchor, owner in decision_sections()
    ]
    assert template_sections() == expected


def test_every_anchor_encodes_its_own_section_number() -> None:
    """`s08-approved-findings` and section 8. Anchors are fixed rather than derived from headings,
    which differ between Markdown renderers and change when a title is reworded."""
    for number, title, anchor, _ in decision_sections():
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        assert anchor == f"s{number:02d}-{slug}", f"section {number} anchor is {anchor!r}"


def test_a_prose_section_carries_one_agent_marker_and_no_rendered_block() -> None:
    """Prose and rendered data are never interleaved, so a reader always knows what wrote a page."""
    blocks = template_blocks()
    for number, title, _, owner in decision_sections():
        if not owner.startswith("Agent"):
            continue
        markers = blocks.get(number, [])
        kinds = {kind for kind, _ in markers}
        assert kinds == {"agent"}, f"section {number} ({title}) mixes {sorted(kinds)}"
        assert len(markers) == 1, f"section {number} ({title}) has {len(markers)} prose markers"


def test_a_rendered_section_carries_no_agent_marker() -> None:
    blocks = template_blocks()
    for number, title, _, owner in decision_sections():
        if owner.startswith("Agent"):
            continue
        kinds = {kind for kind, _ in blocks.get(number, [])}
        assert "agent" not in kinds, f"section {number} ({title}) contains model-written prose"


def test_every_empty_marker_follows_the_block_it_replaces() -> None:
    """`{{ empty.findings }}` is what the renderer emits in place of `{{ render.findings }}`, so a
    pair that drifts apart would leave a block with no defined empty wording."""
    lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        for kind, name in MARKER.findall(line):
            if kind != "empty":
                continue
            previous = lines[index - 1] if index else ""
            assert f"{{{{ render.{name} }}}}" in previous, (
                f"empty.{name} does not follow render.{name}"
            )


def test_every_empty_marker_has_authored_wording() -> None:
    """The wording is authored in the template rather than composed at runtime, because an empty
    section is a statement about the assessment and not a blank to be filled."""
    text = TEMPLATE.read_text(encoding="utf-8")
    used = {name for kind, name in MARKER.findall(text) if kind == "empty"}
    for name in sorted(used):
        marker = f"<!-- empty.{name} -->"
        assert marker in text, f"{marker} has no wording defined"
        wording = text.split(marker, 1)[1].split("<!--", 1)[0].strip()
        assert len(wording) > 40, f"{marker} has no substantive wording"


def test_the_empty_findings_wording_refuses_both_wrong_readings() -> None:
    """Zero approved findings is a valid outcome (DEC-009 and the project's own principles). The
    wording has to read as neither a failure nor a clean bill of health, and that is the one piece
    of authored prose in this repository most likely to be softened by someone later."""
    text = TEMPLATE.read_text(encoding="utf-8")
    wording = text.split("<!-- empty.findings -->", 1)[1].split("<!--", 1)[0]
    assert "not a failure" in wording
    assert "not a statement that the reviewed system is secure" in wording


@pytest.mark.parametrize(
    "requirement",
    [
        "versions.architecture",
        "versions.workflow",
        "versions.prompts",
        "versions.requirements_catalog",
        "versions.model",
        "versions.model_configuration",
    ],
)
def test_the_manifest_carries_every_version_the_evaluation_plan_requires(
    requirement: str,
) -> None:
    """`evaluation-plan.md` section 3 lists six things every evaluation must record. A report whose
    manifest omits one cannot be compared with another run, which is what the manifest is for."""
    assert requirement in decision_entry()


def test_section_five_point_thirteen_agrees_with_the_decision() -> None:
    """The two lists that disagreed. Section 5.13 had fifteen sections and section 19 had four; the
    fifteen were sections of a document and the four were keys of an agent's output, and nothing
    said which sections the agent wrote."""
    text = ARCHITECTURE.read_text(encoding="utf-8")
    body = text.split("## 5.13 Report Generation", 1)[1].split("## 5.14", 1)[0]
    documented = [
        (int(match.group(1)), match.group(2), match.group(3))
        for line in body.splitlines()
        if (match := ARCHITECTURE_ROW.match(line))
    ]
    expected = [
        (number, title, "Agent" if owner.startswith("Agent") else "Rendered")
        for number, title, _, owner in decision_sections()
    ]
    assert documented == expected


def test_agent_design_section_nineteen_names_the_four_prose_sections() -> None:
    """Section 19's own output example is the other half of the disagreement, and it now describes
    four fields of a structure rather than a document."""
    text = AGENT_DESIGN.read_text(encoding="utf-8")
    body = text.split("# 19. Report Generation Agent", 1)[1].split("# 20.", 1)[0]
    for key in AGENT_KEYS:
        assert f"`{key}`" in body, f"section 19 does not name {key}"
    assert "template is **not** an input" in body


def test_section_fourteen_owns_the_coverage_ledger() -> None:
    """DEC-071: the ledger is deterministic content inside section 14, never a new section.

    Held in agreement from both ends: the template's section 14 is rendered-owned and carries
    the methodology block, and the renderer's methodology block is where the ledger heading
    lives — so the ledger cannot drift into agent prose or into a seventeenth section without
    failing here.
    """
    sections = template_sections()
    fourteen = next(entry for entry in sections if entry[0] == 14)
    assert fourteen[1] == "Methodology"
    assert fourteen[3] == "rendered"

    template_section = (
        TEMPLATE.read_text(encoding="utf-8").split('<a id="s14-')[1].split('<a id="s15-')[0]
    )
    assert "{{ render.methodology }}" in template_section

    renderer = (PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "report_rendering.py").read_text(
        encoding="utf-8"
    )
    methodology_block = renderer.split('"methodology": (')[1].split("),")[0]
    assert "### Source coverage" in methodology_block
    assert "_coverage_ledger_table" in methodology_block
