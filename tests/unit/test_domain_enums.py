"""Behavioural tests for the shared enums.

**Conformance to `data-model.md` section 4 is not here.** It moved to
`tests/unit/test_data_model_conformance.py` in #45, so that every document-versus-code comparison
in the repository shares one parser and one place to look. That file owns the three-way check:
the code against a literal, the literal against the document, and the parser against a member
count it cannot reach by accident.

What remains is what the enums *do* rather than what they contain. Mostly that they are `StrEnum`
and not `Enum`, which is the property that lets a member be written to SQLite, dropped into a
prompt, or compared against a value read back from YAML without a conversion at each boundary --
and which nothing else would notice if it changed, because `Enum` works everywhere until the
moment something serializes.
"""

from __future__ import annotations

import re
from enum import StrEnum

import pytest

from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    ReviewDisposition,
    Severity,
    SourceOrigin,
    ValidationStatus,
)

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

ENUMS = (
    ObjectStatus,
    ConfidenceLevel,
    EvidenceStrength,
    SourceOrigin,
    Severity,
    ReviewDisposition,
    ValidationStatus,
)


def test_all_seven_shared_types_exist() -> None:
    """Section 4 defines seven. Importing six and testing six would pass quietly."""
    assert len(ENUMS) == 7
    assert len({enum.__name__ for enum in ENUMS}) == 7


@pytest.mark.parametrize("enum", ENUMS)
def test_every_member_is_lowercase_snake_case(enum: type[StrEnum]) -> None:
    """The serialized form is the corpus vocabulary, not a Python spelling of it."""
    for member in enum:
        assert SNAKE_CASE.match(member.value), f"{enum.__name__}.{member.name} is not snake_case"


@pytest.mark.parametrize("enum", ENUMS)
def test_a_member_compares_equal_to_its_string(enum: type[StrEnum]) -> None:
    """`StrEnum`, not `Enum`: a member is its value wherever a string is expected."""
    for member in enum:
        assert member == member.value
        assert f"{member}" == member.value
        assert enum(member.value) is member


@pytest.mark.parametrize("enum", ENUMS)
def test_a_member_survives_a_round_trip_through_json(enum: type[StrEnum]) -> None:
    """DEC-020 persists generated objects as JSON payloads, so this is the real storage path."""
    import json

    for member in enum:
        assert enum(json.loads(json.dumps(member))) is member


@pytest.mark.parametrize("enum", ENUMS)
def test_an_undocumented_value_is_rejected(enum: type[StrEnum]) -> None:
    with pytest.raises(ValueError, match="is not a valid"):
        enum("not_a_documented_value")


@pytest.mark.parametrize("enum", ENUMS)
def test_lookup_is_case_sensitive(enum: type[StrEnum]) -> None:
    """Accepting `APPROVED` and `approved` would put two spellings of one state in the store."""
    for member in enum:
        with pytest.raises(ValueError, match="is not a valid"):
            enum(member.value.upper())


def test_severity_carries_no_default() -> None:
    """`unassigned` is a member; nothing here makes it a default.

    DEC-030 gives severity to the reviewer at checkpoint 2. A default on the enum would be the
    first step back toward a pipeline node assigning it.
    """
    assert Severity.UNASSIGNED in Severity
    assert not hasattr(Severity, "default")


def test_validation_status_keeps_absence_and_contradiction_apart() -> None:
    """The DEC-009 separation, one layer below Finding and DocumentationGap.

    Evidence that says nothing is `unsupported`; evidence that says the opposite is
    `contradicted`; material never examined is `not_evaluated`. Collapsing any two is how missing
    documentation becomes an asserted weakness.
    """
    assert len({ValidationStatus.UNSUPPORTED, ValidationStatus.CONTRADICTED}) == 2
    assert ValidationStatus.NOT_EVALUATED not in {
        ValidationStatus.UNSUPPORTED,
        ValidationStatus.CONTRADICTED,
    }


def test_review_disposition_has_no_change_severity() -> None:
    """DEC-030 and DEC-023: a severity change is an `edit` carrying prior and updated values.

    `current-architecture.md` section 5.12 lists changing severity among the reviewer's actions,
    which is what would tempt someone to add this value. That list names actions a reviewer takes;
    this enum names dispositions the system records, and the two do not correspond one to one.
    """
    assert "change_severity" not in {member.value for member in ReviewDisposition}
    assert ReviewDisposition.EDIT in ReviewDisposition


def test_the_dec_009_conversions_exist() -> None:
    """The escape hatches a reviewer needs when a proposed finding rests on silence."""
    assert ReviewDisposition.CONVERT_TO_QUESTION in ReviewDisposition
    assert ReviewDisposition.CONVERT_TO_DOCUMENTATION_GAP in ReviewDisposition
