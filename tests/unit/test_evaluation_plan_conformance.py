"""Evaluation-plan section 5 and the committed truth sets agree on the file classes (DEC-131).

Born of DEC-110's honesty: `expected-duplicates.yaml` fell outside the 0.1 plan's derived-file
rule, and the decision flagged the gap rather than silently widening the rule. The 0.2 plan
widened it by decision, into three named classes, and this test is what keeps the widening the
last one that happens silently: every file committed under a scenario's `expected/` must be
admitted by a class section 5 states. The direction is deliberate — committed reality must be
covered by the document; the document may name classes that do not exist yet (the second
annotation set exists only once a human pass does), so the reverse direction is not asserted.
"""

from __future__ import annotations

import re

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.registry import load_registry

PLAN = PROJECT_ROOT / "docs" / "architecture" / "evaluation-plan.md"


def _section_5() -> str:
    text = PLAN.read_text(encoding="utf-8")
    start = text.index("\n# 5.")
    end = text.index("\n# 6.")
    return text[start:end]


def test_every_committed_truth_set_file_is_admitted_by_a_documented_class() -> None:
    section = _section_5()
    documented_yaml = set(re.findall(r"expected-[a-z-]+\.yaml", section))
    assert documented_yaml, "section 5 names no expected-*.yaml classes; the parse is broken"
    apparatus = {"evaluation-contract.yaml", "reviewer-notes.md", "README.md"}
    for name in apparatus:
        assert name in section, f"section 5 no longer names {name}"

    unadmitted: list[str] = []
    for entry in load_registry():
        expected_dir = entry.path / "expected"
        if not expected_dir.is_dir():
            continue
        for path in sorted(expected_dir.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(expected_dir).as_posix()
            if relative.startswith("annotations/second/"):
                # The instrument-annotation class (DEC-112, DEC-119): the second set and its
                # adjudication record, admitted as a directory rather than per file.
                continue
            if path.name in apparatus or path.name in documented_yaml:
                continue
            unadmitted.append(f"{entry.slug}: {relative}")

    assert not unadmitted, (
        f"truth-set files no section 5 class admits: {unadmitted}. Either the file is a new "
        f"class the plan must decide (the DEC-110 precedent), or it does not belong under "
        f"expected/."
    )
