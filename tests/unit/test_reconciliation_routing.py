"""The divergence-routing rule stays where an author meets it (DEC-149).

DEC-149 says plainly that no test can detect a truth set edited toward a run: the edit's
evidence is exactly the score it produces. What a test *can* hold is that the rule remains
readable at the moment of temptation — in the evaluation plan's fixture-design section, and
pointed at from the corpus directory an author is standing in when they open an `expected/`
file. A rule that survives only in the decision log is one nobody meets.

So this pins presence and reachability, not compliance: the five classes are named, the
standing rule and its presumption are stated, and the README's link resolves to a heading that
exists. The rot these guard against is silent deletion and a broken anchor, both of which have
precedent in documentation that no test held.
"""

from __future__ import annotations

import re

from trace_ai.config import PROJECT_ROOT

PLAN = PROJECT_ROOT / "docs" / "architecture" / "evaluation-plan.md"
CORPUS_README = PROJECT_ROOT / "benchmarks" / "README.md"
DECISION_LOG = PROJECT_ROOT / "docs" / "architecture" / "decision-log.md"

ANCHOR = "editing-an-authored-expectation"
HEADING = "## Editing an authored expectation"


def _editing_section() -> str:
    text = PLAN.read_text(encoding="utf-8")
    assert HEADING in text, (
        f"evaluation-plan.md no longer carries '{HEADING}'. DEC-149 put the truth-set editing "
        f"rule there because it is where a fixture author reads; moving it needs a decision, "
        f"not a deletion."
    )
    start = text.index(HEADING)
    end = text.index("\n# 11.", start)
    return text[start:end]


def test_the_editing_rule_names_every_divergence_class() -> None:
    section = _editing_section()
    for phrase in (
        "Instrument definition",
        "Matcher classification",
        "Truth-set inconsistency",
        "Pipeline divergence",
        "Run-to-run variance",
    ):
        assert phrase in section, (
            f"the editing rule no longer names the '{phrase}' class. DEC-149's taxonomy is "
            f"five classes and routing depends on all of them being available to the reader."
        )


def test_the_editing_rule_states_the_standing_rule_and_the_presumption() -> None:
    # Collapsed, because the document is hard-wrapped and every clause below spans a line break.
    section = " ".join(_editing_section().lower().split())

    assert "never an argument for changing an expectation" in section, (
        "the editing rule no longer states that a run's output is never an argument for "
        "changing an expectation — the load-bearing sentence of DEC-149."
    )
    assert "the only class an edit answers" in section, (
        "the editing rule no longer marks truth-set inconsistency as the only class an edit "
        "answers; without it the taxonomy reads as five equally editable options."
    )
    assert "presumed class 4 or class 5" in section, (
        "the editing rule no longer states where the burden sits. DEC-149 presumes a "
        "divergence is a fact about the run until the truth set is shown wrong on its own terms."
    )


def test_the_corpus_readme_points_at_a_heading_that_exists() -> None:
    readme = CORPUS_README.read_text(encoding="utf-8")
    links = re.findall(r"evaluation-plan\.md#([a-z0-9-]+)", readme)

    assert ANCHOR in links, (
        f"benchmarks/README.md no longer links to #{ANCHOR}. The corpus directory is where an "
        f"author stands when they open a truth set, so the pointer is the rule's reach."
    )

    heading_slug = HEADING.removeprefix("## ").lower().replace(" ", "-")
    assert heading_slug == ANCHOR, (
        f"the plan's heading slugifies to '{heading_slug}' but the README links to "
        f"'#{ANCHOR}'; the anchor is broken and the pointer leads nowhere."
    )


def test_the_decision_records_the_rule_the_plan_summarises() -> None:
    log = DECISION_LOG.read_text(encoding="utf-8")
    assert "## DEC-149:" in log, "DEC-149 is missing; the plan's editing rule cites it."
    start = log.index("## DEC-149:")
    entry = " ".join(log[start:].split())
    assert "A run's output is never an argument for changing an expectation" in entry, (
        "DEC-149 no longer carries the standing rule the evaluation plan summarises; the two "
        "must not drift, because the plan is the summary and the entry is the reasoning."
    )
