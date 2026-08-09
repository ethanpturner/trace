"""Tests keeping the shared enums identical to `data-model.md` section 4.

Section 4 is authoritative for these seven vocabularies. That is easy to state and hard to keep
true: the document and the code are edited by different activities months apart, and an enum that
has quietly drifted from its specification still passes every test written about its behaviour.

So the specification is parsed and compared, member for member. A value added or removed in
section 4 without the same change here fails, and so does the reverse.

The literal tuples below are the second half of the check. Parsing prose is brittle by nature, and
a parser that stops matching would otherwise turn this whole file vacuously green -- comparing an
empty set to an empty set. Every vocabulary is therefore asserted three ways: the code against a
literal written out here, the literal against the document, and the parser against a member count
it cannot reach by accident.

The values matter as much as the members. They are the exact lowercase strings the document uses,
so a persisted `status: approved` reads the same in the database, in a report, and in the
specification -- rather than becoming `ObjectStatus.APPROVED` in one place and `approved` in
another. Issue #43.
"""

from __future__ import annotations

import re
from enum import StrEnum

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    ReviewDisposition,
    Severity,
    SourceOrigin,
    ValidationStatus,
)

DATA_MODEL = PROJECT_ROOT / "docs" / "architecture" / "data-model.md"

# Section 4 lists members as bare lines. Prose in the same sections always carries spaces,
# punctuation, or Markdown, and table rows start with a pipe, so a line that is nothing but a
# lowercase snake_case token is a member.
MEMBER_LINE = re.compile(r"^[a-z][a-z0-9_]*$")

# The subsection heading each vocabulary is defined under, and every value it should carry.
SPECIFICATION: dict[str, tuple[type[StrEnum], tuple[str, ...]]] = {
    "4.1": (
        ObjectStatus,
        ("draft", "candidate", "pending_review", "approved", "rejected", "superseded", "archived"),
    ),
    "4.2": (ConfidenceLevel, ("low", "medium", "high")),
    "4.3": (EvidenceStrength, ("direct", "indirect", "contextual", "contradictory")),
    "4.4": (
        SourceOrigin,
        (
            "uploaded_document",
            "structured_input",
            "user_response",
            "requirements_catalog",
            "system_generated",
            "reviewer_edit",
            "external_tool",
        ),
    ),
    "4.5": (Severity, ("informational", "low", "medium", "high", "critical", "unassigned")),
    "4.6": (
        ReviewDisposition,
        (
            "approve",
            "reject",
            "edit",
            "defer",
            "request_more_analysis",
            "convert_to_question",
            "convert_to_documentation_gap",
        ),
    ),
    "4.7": (
        ValidationStatus,
        (
            "supported",
            "partially_supported",
            "unsupported",
            "contradicted",
            "requires_confirmation",
            "not_evaluated",
        ),
    ),
}

# 7 + 3 + 4 + 7 + 6 + 7 + 6. Stated independently of the table above so that deleting an entry
# from it cannot also lower the bar the parser has to clear.
TOTAL_MEMBERS = 40


def documented_members() -> dict[str, list[str]]:
    """Section 4's subsections, each mapped to the values listed under it.

    A subsection runs from its own `## 4.N` heading to the next heading at any level, so prose
    that follows the value list -- section 4.5's severity rules, section 4.6's note on
    `change_severity` -- is inside the block and has to be excluded by line shape rather than by
    position.
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in DATA_MODEL.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = re.match(r"^#+\s+(4\.\d)\s", stripped)
            current = heading.group(1) if heading else None
            if current is not None:
                sections[current] = []
            continue
        if current is not None and MEMBER_LINE.match(stripped):
            sections[current].append(stripped)

    return sections


def test_the_parser_found_section_four() -> None:
    """Guard the parser before trusting anything it produced.

    Every comparison below is vacuously true if the document stops matching -- a heading style
    change, a switch to bulleted lists, a renumbering. This test is what makes the rest mean
    something.
    """
    sections = documented_members()
    assert set(sections) == set(SPECIFICATION), (
        f"expected subsections {sorted(SPECIFICATION)}, parsed {sorted(sections)}. "
        f"data-model.md section 4 changed shape, or the parser stopped matching it."
    )
    assert sum(len(values) for values in sections.values()) == TOTAL_MEMBERS, (
        f"parsed {sum(len(v) for v in sections.values())} members, expected {TOTAL_MEMBERS}"
    )


def test_the_parser_rejects_prose() -> None:
    """The line shape has to exclude the sentences sitting among the values.

    Section 4.5 and 4.6 both put explanatory paragraphs after their lists, and 4.2 puts a table
    there. If any of those parsed as a member the counts above would drift without saying why.
    """
    assert not MEMBER_LINE.match("Possible values:")
    assert not MEMBER_LINE.match("Not every object needs every status.")
    assert not MEMBER_LINE.match("| Low | Significant uncertainty or weak evidence |")
    assert not MEMBER_LINE.match("**`unassigned` is the value a finding is created with.**")
    assert MEMBER_LINE.match("convert_to_documentation_gap")


@pytest.mark.parametrize(("section", "expected"), [(k, v[1]) for k, v in SPECIFICATION.items()])
def test_the_document_lists_exactly_these_values(section: str, expected: tuple[str, ...]) -> None:
    documented = documented_members()[section]
    assert tuple(documented) == expected, (
        f"data-model.md section {section} lists {documented}, this test expects {list(expected)}. "
        f"The document is authoritative: if it changed deliberately, update the enum and this "
        f"test together."
    )


@pytest.mark.parametrize(("enum", "expected"), list(SPECIFICATION.values()))
def test_the_enum_carries_exactly_these_values(
    enum: type[StrEnum], expected: tuple[str, ...]
) -> None:
    assert tuple(member.value for member in enum) == expected


@pytest.mark.parametrize("enum", [entry[0] for entry in SPECIFICATION.values()])
def test_members_are_lowercase_snake_case(enum: type[StrEnum]) -> None:
    """The serialized form is the corpus vocabulary, not a Python spelling of it."""
    for member in enum:
        assert MEMBER_LINE.match(member.value), f"{enum.__name__}.{member.name} is not snake_case"


@pytest.mark.parametrize("enum", [entry[0] for entry in SPECIFICATION.values()])
def test_a_member_compares_equal_to_its_string(enum: type[StrEnum]) -> None:
    """`StrEnum`, not `Enum`: a member is its value wherever a string is expected.

    This is what lets a member be written to SQLite, dropped into a prompt, or compared against a
    value read back from YAML without a conversion step at each boundary.
    """
    for member in enum:
        assert member == member.value
        assert f"{member}" == member.value
        assert enum(member.value) is member


@pytest.mark.parametrize("enum", [entry[0] for entry in SPECIFICATION.values()])
def test_an_undocumented_value_is_rejected(enum: type[StrEnum]) -> None:
    with pytest.raises(ValueError, match="is not a valid"):
        enum("not_a_documented_value")


def test_severity_defaults_are_not_encoded_here() -> None:
    """`unassigned` exists as a member; nothing in this module makes it a default.

    DEC-030 gives severity to the reviewer at checkpoint 2. A default living on the enum would be
    the first step back toward a pipeline node assigning it.
    """
    assert Severity.UNASSIGNED in Severity
    assert not hasattr(Severity, "default")
