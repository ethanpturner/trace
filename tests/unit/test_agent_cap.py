"""Tests pinning the six-agent cap and the severity ownership that follows from it.

`CLAUDE.md` lists the six-agent cap as a binding design constraint: a seventh requires
evidence that it improves results, which is a decision-log entry rather than an
implementation detail.

The cap was one document away from being breached without anyone deciding to. The corpus
specified a seventh agent -- Severity Support -- in more detail than most of the six: ten
evaluation factors, six outputs, five prohibited operations, a node in the pipeline diagram,
and a slot in the build order. `agent-design.md` section 36 called it "optional for the first
demonstration", which is not the same as excluded. Left there, it would have been built
because it was the most completely specified component in the repository, and specification
completeness is not evidence of need.

DEC-030 excluded it, and these tests keep the corpus consistent with that. They check
documents rather than code, because there is no code: `src/trace_ai/` is configuration and
process bootstrap, and the pipeline does not exist. The documents are the artifact under
test.

Two things are guarded.

**The agent inventory.** The node table in `agent-design.md` is the one place the corpus
enumerates every pipeline step with whether it uses a model. If a seventh model-assisted row
appears there, either the cap was breached or the table is wrong, and both are worth failing
on.

**Severity has exactly one owner.** DEC-030 assigns it to the reviewer at checkpoint 2 and
to nothing else. The failure this prevents is the one the issue found: three documents
assigning severity to three different owners, with a fourth implied by the enum. Nothing
detected that for as long as it was true.
"""

from __future__ import annotations

import re

from trace_ai.config import PROJECT_ROOT

DOCS = PROJECT_ROOT / "docs" / "architecture"
AGENT_DESIGN = DOCS / "agent-design.md"
DATA_MODEL = DOCS / "data-model.md"
ARCHITECTURE = DOCS / "current-architecture.md"
DECISION_LOG = DOCS / "decision-log.md"

# agent-design.md section 36. The cap is on model-assisted agents, not on pipeline nodes.
MVP_AGENTS = (
    "Context Extraction",
    "Threat Analysis",
    "Requirement and Control Mapping",
    "Evidence Validation",
    "Critical Review",
    "Report Generation",
)

# Rows in the node table whose second column marks them as using a model. "Optional" is a
# third state and belongs to deterministic nodes that may call a model for a sub-step; it
# does not count against the cap and is not an agent.
MODEL_ASSISTED_KINDS = ("Reasoning agent", "Constrained generation agent")


def node_table_rows() -> list[list[str]]:
    """The pipeline node table: every step, its kind, and whether it uses a model."""
    rows = []
    for line in AGENT_DESIGN.read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[2] in {"Yes", "No", "Optional"}:
            rows.append(cells)
    return rows


def test_node_table_is_found() -> None:
    """Guard the parser itself.

    Every assertion below is vacuously true if the table stops matching -- a heading change
    or a column added would silently turn this file green. This test is what makes the rest
    of it mean anything.
    """
    rows = node_table_rows()
    assert len(rows) >= 10, f"only {len(rows)} node-table rows parsed; the format likely changed"


def test_exactly_six_model_assisted_nodes() -> None:
    agents = [row[0] for row in node_table_rows() if row[1] in MODEL_ASSISTED_KINDS]
    assert len(agents) == 6, (
        f"{len(agents)} model-assisted nodes in agent-design.md's node table: {agents}. "
        f"The cap is six (CLAUDE.md, agent-design.md section 36). A seventh is a design "
        f"change requiring a decision-log entry with evidence that it improves results."
    )


def test_the_six_are_the_named_six() -> None:
    agents = {row[0] for row in node_table_rows() if row[1] in MODEL_ASSISTED_KINDS}
    assert agents == set(MVP_AGENTS)


def test_severity_support_agent_is_not_in_the_pipeline_diagram() -> None:
    """DEC-030 removed it. A diagram node is how it would come back.

    The diagram is the most-copied part of this document and the least likely place a
    reader checks against the decision log.
    """
    text = AGENT_DESIGN.read_text()
    assert "SEVERITY[" not in text
    assert "--> SEVERITY" not in text
    assert "SEVERITY -->" not in text


def test_severity_support_agent_appears_only_as_excluded() -> None:
    """Section 17 is retained deliberately, so its name still appears.

    The exclusion argument depends on reading what the agent would have produced -- four of
    its six outputs already exist as Finding fields. So the test cannot require the name to
    be absent; it requires every mention to sit near an exclusion marker.
    """
    offenders = []
    for path in (AGENT_DESIGN, ARCHITECTURE, DATA_MODEL, PROJECT_ROOT / "README.md"):
        lines = path.read_text().splitlines()
        for number, line in enumerate(lines):
            if "Severity Support" not in line:
                continue
            window = " ".join(lines[max(0, number - 2) : number + 6])
            if not re.search(r"not built|DEC-030|excluded|~~", window):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{number + 1}")
    assert not offenders, (
        f"{offenders} mention the Severity Support Agent without marking it excluded. "
        f"DEC-030 excluded it rather than deferring it."
    )


def test_consolidation_does_not_assign_severity() -> None:
    """current-architecture.md section 5.11 used to list this as a responsibility.

    It was one of the three conflicting owners issue #37 found. A deterministic node has the
    same problem an agent has -- no business context -- and less judgment to apply.
    """
    text = ARCHITECTURE.read_text()
    assert "- Assign preliminary severity" not in text


def test_findings_are_created_unassigned_and_cannot_be_approved_that_way() -> None:
    """The load-bearing half of DEC-030.

    Reviewer-assigned severity without a rule forcing assignment at approval degrades into
    nobody assigning severity, and the report has no ordering. The enum value and the
    approval rule only work as a pair.
    """
    data_model = DATA_MODEL.read_text()
    assert "unassigned" in data_model
    assert "A severity other than `unassigned` (DEC-030)" in data_model, (
        "the approval rule is what makes reviewer-assigned severity work rather than "
        "leaving every finding unassigned"
    )


def test_no_change_severity_disposition() -> None:
    """DEC-023 settled the mechanism: an edit with prior_value and updated_value.

    A `change_severity` disposition would be a second way to record the same edit, and the
    two would disagree the first time one of them was extended.

    Section 4.6 names the value in order to say it is deliberately absent, so this cannot
    assert the string is missing -- only that it never appears as an enum member. Enum
    values in that section are bare lines.
    """
    section = DATA_MODEL.read_text().split("## 4.6 ReviewDisposition", 1)[1]
    section = section.split("## 4.7", 1)[0]
    members = {line.strip() for line in section.splitlines() if line.strip()}
    assert "change_severity" not in members, (
        "change_severity was added as a ReviewDisposition value. DEC-023 settled the "
        "mechanism: an edit carrying prior_value and updated_value."
    )


def test_dec_030_is_recorded() -> None:
    text = DECISION_LOG.read_text()
    assert "## DEC-030:" in text
    heading = next(line for line in text.splitlines() if line.startswith("## DEC-030:"))
    assert "severity" in heading.lower()


def test_every_decision_is_accepted_or_rejected() -> None:
    """CLAUDE.md states that no decision-log entry is Proposed. Keep it true.

    An entry left Proposed is a decision that reads as made and is not, which is how the
    severity conflict survived: section 36 called the seventh agent "optional", and optional
    is not a decision either.
    """
    statuses = re.findall(r"^Status: (.+)$", DECISION_LOG.read_text(), re.MULTILINE)
    assert statuses, "no Status lines parsed from the decision log"
    # A status may carry a trailing clause -- DEC-007 reads "Rejected -- superseded by
    # DEC-016". The first word is the state.
    unsettled = sorted(
        {s for s in statuses if s.strip().split()[0].rstrip(",") not in {"Accepted", "Rejected"}}
    )
    assert not unsettled, f"decision-log entries with unsettled status: {unsettled}"
