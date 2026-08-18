"""The transition-table drift guard (DEC-016 amendment, #602).

DEC-016 admitted it on the day the framework was rejected: a hand-written transition table can
drift from the phases documented in `current-architecture.md` section 5.3, and nothing checked
that they agree. This is the check, in the #540 doc-guard tradition: the document's numbered
list is parsed and compared to the code, in both directions, so a phase renamed in either place
fails here rather than surfacing as a run that stops on a transition nobody meant to forbid.

The pipeline is a fixed sequence with no analytical branching, and the guard holds that too:
every phase's permitted successors are exactly the next phase in the documented order, and the
last phase's are none.
"""

from __future__ import annotations

import re

from trace_ai.config import PROJECT_ROOT
from trace_ai.workflow.phases import TRANSITIONS, Phase

ARCHITECTURE = PROJECT_ROOT / "docs" / "architecture" / "current-architecture.md"


def documented_phases() -> list[str]:
    """Section 5.3's numbered phase list, normalized to the enum's spelling."""
    text = ARCHITECTURE.read_text(encoding="utf-8")
    start = text.index("### Proposed workflow phases")
    section = text[start:]
    end = section.index("\n## ")
    entries = re.findall(r"(?m)^\d+\.\s+(.+?)\s*$", section[:end])
    return [entry.lower().replace(" ", "_") for entry in entries]


def test_the_documented_phase_list_and_the_enum_agree_in_order() -> None:
    documented = documented_phases()
    declared = [phase.value for phase in Phase]

    assert documented == declared, (
        "current-architecture.md section 5.3 and workflow/phases.py disagree about the fourteen "
        "phases. Whichever changed, the other is now wrong; a run built on the code answers to a "
        "document that describes a different pipeline."
    )


def test_the_transition_table_is_the_documented_linear_chain() -> None:
    ordered = list(Phase)

    assert set(TRANSITIONS) == set(ordered), "a phase is missing from the transition table"
    for position, phase in enumerate(ordered):
        expected = (
            frozenset({ordered[position + 1]}) if position + 1 < len(ordered) else frozenset()
        )
        assert TRANSITIONS[phase] == expected, (
            f"{phase.value} permits {sorted(p.value for p in TRANSITIONS[phase])}; the documented "
            f"pipeline is a linear chain with no analytical branching (DEC-016)."
        )
