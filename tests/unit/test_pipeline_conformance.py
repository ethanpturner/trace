"""`agent-design.md` sections 3 and 4, held to `NODES_BY_PHASE`.

Every other disagreement between the corpus and the code surfaces as a red test.
`data-model.md`'s field tables go through `test_data_model_conformance.py`, section 24's prompt
structure through the five prompt tests, section 40's priority list through the registry. Section
3's workflow diagram had no such guard, and it cost exactly what an unguarded document costs: the
Evidence Assessment Validation node and the Critique Validation node were both built, both were the
only path to persistence for what their agent proposes, and neither was drawn. DEC-048 records the
first omission and the second was found by re-reading rather than by running anything.

**A diagram is not a schema, so nothing fails when it goes stale.** This file is the substitute.

## Why there is an explicit alias table

The three places name the same node differently, and the differences are real rather than
typographical: the diagram says "Normalization and Evidence Indexing Node" where section 4's table
says "Evidence Indexing", and the diagram says "Human Context Review" where the table says "Context
Review". `NODE_LABELS` states each correspondence once, so a mismatch is a decision somebody makes
rather than a join that silently drops a row.

The alias table is also the guard's teeth. A node added to `NODES_BY_PHASE` with no entry here
fails; a node drawn in section 3 with no entry here fails; a row added to section 4 with no entry
here fails. There is no way to add a node to one of the three and not the other two.

## Why the parser is duplicated

`tests/unit/test_agent_cap.py` parses the same table for a different reason -- the six-agent cap
and severity ownership -- and `tests/` is not a package, so a module cannot import another's
harness. The repository's other injection and fixture files duplicate for the same reason. A third
module needing this parse is the point at which a `conftest.py` earns itself.
"""

from __future__ import annotations

import re
from typing import Final

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.workflow.phases import NODES_BY_PHASE, Phase

AGENT_DESIGN = PROJECT_ROOT / "docs" / "architecture" / "agent-design.md"

# node name -> (the label section 3's diagram uses, the label section 4's table uses).
#
# Three entries differ across the three places and the divergence is stated rather than
# normalized away: a rule that stripped "Normalization and" to make one of them match would
# also quietly accept a genuinely wrong label.
NODE_LABELS: Final[dict[str, tuple[str, str]]] = {
    "assessment-initialization": ("Assessment Initialization", "Assessment Initialization"),
    "document-ingestion": ("Document Ingestion Node", "Document Ingestion"),
    "evidence-indexing": ("Normalization and Evidence Indexing Node", "Evidence Indexing"),
    "context-extraction": ("Context Extraction Agent", "Context Extraction"),
    "context-validation": ("Context Validation Node", "Context Validation"),
    "human-context-review": ("Human Context Review", "Context Review"),
    "threat-analysis": ("Threat Analysis Agent", "Threat Analysis"),
    "threat-validation": ("Threat Validation Node", "Threat Validation"),
    "requirement-and-control-mapping": (
        "Requirement and Control Mapping Agent",
        "Requirement and Control Mapping",
    ),
    "mapping-validation": ("Mapping Validation Node", "Mapping Validation"),
    "evidence-validation": ("Evidence Validation Agent", "Evidence Validation"),
    "evidence-assessment-validation": (
        "Evidence Assessment Validation Node",
        "Evidence Assessment Validation",
    ),
    "critical-review": ("Critical Review Agent", "Critical Review"),
    "critique-validation": ("Critique Validation Node", "Critique Validation"),
    "finding-consolidation": ("Finding Consolidation Node", "Finding Consolidation"),
    "human-finding-review": ("Human Finding Review", "Finding Review"),
    "report-generation": ("Report Generation Agent", "Report Generation"),
    "report-rendering": ("Report Rendering Node", "Report Rendering"),
    "evaluation": ("Evaluation Node", "Evaluation"),
}


def section(number: str, following: str) -> str:
    text = AGENT_DESIGN.read_text(encoding="utf-8")
    return text.split(f"# {number}.", 1)[1].split(f"# {following}.", 1)[0]


def diagram_nodes() -> dict[str, str]:
    """Section 3's declarations: `START[Assessment Initialization]` -> `{START: "..."}`."""
    body = section("3", "4")
    return dict(re.findall(r"^([A-Z_]+)\[([^\]]+)\]\s*$", body, flags=re.MULTILINE))


def diagram_edges() -> list[tuple[str, str]]:
    """Section 3's edges, as pairs of the identifiers on either side of the arrow."""
    body = section("3", "4")
    return [
        (left, right)
        for left, right in re.findall(r"^([A-Z_]+)\s*-->\s*([A-Z_]+)\s*$", body, flags=re.MULTILINE)
    ]


def table_rows() -> list[list[str]]:
    """Section 4's component table, one list of cells per row."""
    body = section("4", "5")
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in body.splitlines()
        if line.strip().startswith("|")
    ]
    # Drop the header and the `|---|` separator.
    return [row for row in rows if row and row[0] not in {"Component", ""} and "---" not in row[0]]


def node_names() -> set[str]:
    return {name for names in NODES_BY_PHASE.values() for name in names}


# The parsers found something


def test_the_diagram_was_parsed() -> None:
    """An empty parse makes every comparison below vacuous, which is the dangerous green."""
    assert len(diagram_nodes()) >= 15
    assert len(diagram_edges()) >= 15


def test_the_table_was_parsed() -> None:
    rows = table_rows()

    assert len(rows) >= 15
    assert all(len(row) == 4 for row in rows), "section 4's table is not four columns"


def test_the_registry_is_not_empty() -> None:
    assert len(node_names()) >= 15


# The three places agree


def test_every_registered_node_is_drawn_in_the_diagram() -> None:
    """The failure DEC-048 records, and the one this file exists to catch.

    A node the code registers against a phase and the diagram does not draw is a pipeline step
    nobody reading the corpus would know exists.
    """
    drawn = set(diagram_nodes().values())

    missing = sorted(
        name for name in node_names() if NODE_LABELS.get(name, ("", ""))[0] not in drawn
    )
    assert not missing, f"these nodes are registered and undrawn in section 3: {missing}"


def test_every_drawn_node_is_registered() -> None:
    """The other direction, which is the one DEC-016 insists on for the transition table.

    A node in the diagram that no phase lists is a step nobody can execute: the orchestrator
    refuses a node whose name is not listed for its phase, so an undrawn-in-code node is a
    documented step the pipeline cannot run.
    """
    by_diagram_label = {diagram: name for name, (diagram, _) in NODE_LABELS.items()}

    unregistered = sorted(
        label
        for label in diagram_nodes().values()
        if by_diagram_label.get(label) not in node_names()
    )
    assert not unregistered, f"these nodes are drawn and unregistered: {unregistered}"


def test_every_registered_node_is_classified_in_section_four() -> None:
    classified = {row[0] for row in table_rows()}

    missing = sorted(
        name for name in node_names() if NODE_LABELS.get(name, ("", ""))[1] not in classified
    )
    assert not missing, f"these nodes are registered and unclassified in section 4: {missing}"


def test_every_classified_component_is_registered() -> None:
    by_table_label = {table: name for name, (_, table) in NODE_LABELS.items()}

    unregistered = sorted(
        row[0] for row in table_rows() if by_table_label.get(row[0]) not in node_names()
    )
    assert not unregistered, f"these components are classified and unregistered: {unregistered}"


# The alias table has no slack in it


def test_every_alias_entry_names_a_registered_node() -> None:
    """An alias for a node nobody registers is a row that stopped meaning anything."""
    stale = sorted(set(NODE_LABELS) - node_names())

    assert not stale, f"these alias entries name no registered node: {stale}"


def test_every_registered_node_has_an_alias_entry() -> None:
    """This is what makes adding a node to one place and not the others impossible."""
    unnamed = sorted(node_names() - set(NODE_LABELS))

    assert not unnamed, f"these nodes have no entry in NODE_LABELS: {unnamed}"


def test_no_two_nodes_share_a_label() -> None:
    diagram_labels = [diagram for diagram, _ in NODE_LABELS.values()]
    table_labels = [table for _, table in NODE_LABELS.values()]

    assert len(set(diagram_labels)) == len(diagram_labels)
    assert len(set(table_labels)) == len(table_labels)


# Every reasoning agent is followed by a deterministic node


def test_every_reasoning_agent_has_a_node_behind_it() -> None:
    """DEC-048's substantive claim, checked against the diagram rather than asserted.

    Section 22 states that agents never write authoritative records, and section 33 requires
    validation after model-generated structured output. Together they mean a reasoning agent with
    nothing behind it has either written its own output or lost it. Report Generation is the
    exception the table itself names: its successor is the rendering node, which is deterministic
    and is what validates the composed document.
    """
    kinds = {row[0]: row[1] for row in table_rows()}
    by_identifier = diagram_nodes()
    successors: dict[str, list[str]] = {}
    for left, right in diagram_edges():
        successors.setdefault(left, []).append(right)

    by_table_label = {table: diagram for _, (diagram, table) in NODE_LABELS.items()}
    agents = [
        by_table_label[component]
        for component, kind in kinds.items()
        if kind in {"Reasoning agent", "Constrained generation agent"}
    ]
    assert len(agents) == 6, f"section 4 classifies {len(agents)} agents, not six"

    for agent in agents:
        identifier = next(key for key, label in by_identifier.items() if label == agent)
        following = [by_identifier[target] for target in successors.get(identifier, [])]
        assert following, f"{agent} has no successor in section 3"
        assert any(label.endswith("Node") for label in following), (
            f"{agent} is followed only by {following}, none of which is a node"
        )


# The diagram is one path, like the phases are


def test_the_diagram_is_a_single_chain() -> None:
    """`current-architecture.md` section 5.3 and DEC-016: no analytical branching.

    One successor each and one predecessor each, so the drawn pipeline cannot disagree with the
    transition table about whether the pipeline forks.
    """
    edges = diagram_edges()
    sources = [left for left, _ in edges]
    targets = [right for _, right in edges]

    assert len(set(sources)) == len(sources), "a node in section 3 has two successors"
    assert len(set(targets)) == len(targets), "a node in section 3 has two predecessors"


def test_the_diagram_has_one_start_and_one_end() -> None:
    nodes = set(diagram_nodes())
    edges = diagram_edges()

    starts = nodes - {right for _, right in edges}
    ends = nodes - {left for left, _ in edges}

    assert len(starts) == 1, f"section 3 has {len(starts)} entry points: {sorted(starts)}"
    assert len(ends) == 1, f"section 3 has {len(ends)} exit points: {sorted(ends)}"


def test_the_two_checkpoints_are_drawn() -> None:
    """DEC-005 makes them structural, so they are steps in the diagram rather than conditionals."""
    drawn = set(diagram_nodes().values())

    assert "Human Context Review" in drawn
    assert "Human Finding Review" in drawn


@pytest.mark.parametrize(
    "phase, expected",
    [
        (Phase.EVIDENCE_VALIDATION, "evidence-assessment-validation"),
        (Phase.CRITICAL_REVIEW, "critique-validation"),
    ],
)
def test_the_two_nodes_dec_048_added_are_registered(phase: Phase, expected: str) -> None:
    """Named individually, so deleting one from the registry fails with its own name."""
    assert expected in NODES_BY_PHASE[phase]
