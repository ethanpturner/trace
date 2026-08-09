"""Tests for `EvidenceReference`.

Field names and required-ness are checked by `test_data_model_conformance.py` against
`data-model.md` section 8. This file covers the validation rules and one property that is not a
rule at all but a design statement: **an evidence reference cannot express absence.**

That last group is the reason this object matters more than its size suggests. Ten other objects
carry `evidence_ids`, and every conclusion Trace defends is defended through this one. If a
reference could be created with no quotation — or with a quotation of blank space, or with a
convention meaning "nothing here" — then "the document does not say" would have a way to travel as
though it were evidence, which is precisely the DEC-009 failure the project exists to avoid.
Section 22's `Question` and section 23's `DocumentationGap` are where silence goes. Issue #51.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from trace_ai.domain.base import now
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.evidence import JSON_POINTER_KEY, EvidenceReference
from trace_ai.domain.hashing import content_hash

PASSAGE = "Users authenticate through the corporate OIDC provider."


def an_evidence_reference(**overrides: object) -> EvidenceReference:
    fields: dict[str, object] = {
        "id": "evd-014",
        "assessment_id": "asm-001",
        "source_document_id": "src-002",
        "section_title": "Authentication",
        "start_line": 41,
        "end_line": 46,
        "quoted_text": PASSAGE,
        "content_hash": content_hash(PASSAGE.encode()),
        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
        "created_at": now(),
    }
    return EvidenceReference.model_validate(fields | overrides)


# ------------------------------------------------------------------------------------------
# Evidence cites text that exists
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("empty", ["", " ", "\n", "\t  \n "])
def test_an_empty_quotation_is_rejected(empty: str) -> None:
    """The DEC-009 separation, expressed in the schema.

    `DomainModel` strips surrounding whitespace before the length constraint applies, so a
    whitespace-only quotation collapses to empty and is refused rather than stored as a citation
    of blank space.
    """
    with pytest.raises(ValidationError):
        an_evidence_reference(quoted_text=empty)


def test_quoted_text_is_required() -> None:
    fields = {
        "id": "evd-014",
        "assessment_id": "asm-001",
        "source_document_id": "src-002",
        "start_line": 41,
        "content_hash": content_hash(b""),
        "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
        "created_at": now(),
    }
    with pytest.raises(ValidationError):
        EvidenceReference.model_validate(fields)


def test_no_field_expresses_absence() -> None:
    """There must be no flag meaning "the document is silent here".

    A reference that could say that would let missing documentation travel as evidence. Section
    22's Question and section 23's DocumentationGap are where silence goes, and they are separate
    objects for exactly this reason.
    """
    suspicious = [
        name
        for name in EvidenceReference.model_fields
        if any(
            word in name
            for word in ("absent", "missing", "silent", "not_found", "negative", "unstated")
        )
    ]
    assert not suspicious, f"{suspicious} would let an evidence reference assert an absence"


def test_no_construction_path_yields_an_empty_quotation() -> None:
    """Including the ones that bypass `__init__`.

    `model_construct` skips validation entirely, so it is the path a caller reaches for when the
    schema is inconvenient. It is checked here so the guarantee is about the object rather than
    about one constructor.
    """
    with pytest.raises(ValidationError):
        an_evidence_reference(quoted_text="")

    reconstructed = EvidenceReference.model_validate_json(an_evidence_reference().model_dump_json())
    assert reconstructed.quoted_text.strip()


# ------------------------------------------------------------------------------------------
# Addressability
# ------------------------------------------------------------------------------------------


def test_the_documented_example_constructs_as_written() -> None:
    """Section 8's example: `evd-014`, Authentication, lines 41 to 46, uploaded_document."""
    reference = an_evidence_reference()
    assert reference.id == "evd-014"
    assert reference.section_title == "Authentication"
    assert (reference.start_line, reference.end_line) == (41, 46)
    assert reference.source_origin is SourceOrigin.UPLOADED_DOCUMENT


def test_a_reference_with_no_location_is_rejected() -> None:
    """Section 2.2: a source document alone is not sufficiently precise.

    Such a reference would still carry a quotation, so nothing downstream would notice it names a
    document rather than a place in one.
    """
    with pytest.raises(ValidationError, match="must address a passage") as caught:
        an_evidence_reference(section_title=None, start_line=None, end_line=None)
    message = str(caught.value)
    for field in ("section_title", "chunk_index", "start_line", "end_line", "page_number"):
        assert field in message, f"the message does not name {field}"
    assert JSON_POINTER_KEY in message


@pytest.mark.parametrize(
    "location",
    [
        {"section_title": "Authentication"},
        {"chunk_index": 0},
        {"start_line": 41},
        {"end_line": 46},
        {"page_number": 3},
        {"metadata": {JSON_POINTER_KEY: "/components/0/name"}},
    ],
)
def test_any_single_location_field_suffices(location: dict[str, object]) -> None:
    cleared: dict[str, object] = {
        "section_title": None,
        "start_line": None,
        "end_line": None,
    }
    assert an_evidence_reference(**(cleared | location)) is not None


def test_a_chunk_index_of_zero_counts_as_a_location() -> None:
    """`chunk_index` is contiguous from zero, so a falsy value must not read as absent."""
    reference = an_evidence_reference(
        section_title=None, start_line=None, end_line=None, chunk_index=0
    )
    assert reference.chunk_index == 0


def test_an_empty_json_pointer_does_not_count_as_a_location() -> None:
    with pytest.raises(ValidationError, match="must address a passage"):
        an_evidence_reference(
            section_title=None, start_line=None, end_line=None, metadata={JSON_POINTER_KEY: ""}
        )


# ------------------------------------------------------------------------------------------
# Locations address the original document (DEC-015)
# ------------------------------------------------------------------------------------------


def test_a_yaml_location_is_a_json_pointer_in_metadata() -> None:
    """DEC-015 adds no field: `metadata` is already "additional location details" in section 8."""
    reference = an_evidence_reference(
        section_title="components.0.name",
        metadata={JSON_POINTER_KEY: "/components/0/name"},
    )
    assert reference.json_pointer == "/components/0/name"
    assert "json_pointer" not in EvidenceReference.model_fields, (
        "DEC-015 declines to add a field; section 8 is authoritative"
    )


def test_line_numbers_are_populated_for_a_structured_source() -> None:
    """So a reviewer can find the passage, even though the pointer is the address.

    A line range is not an address in a structured document: two sequence elements can be
    textually identical.
    """
    reference = an_evidence_reference(
        start_line=12, end_line=12, metadata={JSON_POINTER_KEY: "/components/0"}
    )
    assert reference.start_line == 12
    assert reference.json_pointer == "/components/0"


def test_json_pointer_is_none_when_absent_or_not_a_string() -> None:
    assert an_evidence_reference().json_pointer is None
    assert an_evidence_reference(metadata={JSON_POINTER_KEY: 3}).json_pointer is None


def test_a_reversed_line_range_is_rejected() -> None:
    with pytest.raises(ValidationError, match="precedes start_line"):
        an_evidence_reference(start_line=46, end_line=41)


def test_a_single_line_range_is_allowed() -> None:
    assert an_evidence_reference(start_line=41, end_line=41).start_line == 41


@pytest.mark.parametrize(
    ("field", "value"), [("start_line", 0), ("end_line", 0), ("page_number", 0)]
)
def test_line_and_page_numbers_start_at_one(field: str, value: int) -> None:
    """Documents are numbered from one; a zero would be an off-by-one reaching a reviewer."""
    with pytest.raises(ValidationError):
        an_evidence_reference(**{field: value})


def test_a_negative_chunk_index_is_rejected() -> None:
    with pytest.raises(ValidationError):
        an_evidence_reference(chunk_index=-1)


# ------------------------------------------------------------------------------------------
# Immutability and integrity
# ------------------------------------------------------------------------------------------


def test_quoted_text_cannot_be_modified() -> None:
    """Section 8: evidence text is not modified after creation; corrections create a new reference.

    A quotation that can change is not a citation. The frozen model is what enforces it, and
    `content_hash` over `quoted_text` (DEC-019) is what would detect a change made another way.
    """
    reference = an_evidence_reference()
    with pytest.raises(ValidationError, match="frozen"):
        reference.quoted_text = "something else"  # type: ignore[misc]


def test_the_content_hash_covers_the_quotation() -> None:
    reference = an_evidence_reference()
    assert reference.content_hash == content_hash(reference.quoted_text.encode())


def test_a_malformed_content_hash_is_rejected() -> None:
    with pytest.raises(ValidationError, match="not a content hash"):
        an_evidence_reference(content_hash="sha256:example")


def test_the_identifiers_must_name_the_right_objects() -> None:
    with pytest.raises(ValidationError, match="names a Threat"):
        an_evidence_reference(source_document_id="thr-007")
    with pytest.raises(ValidationError, match="names an Assessment"):
        an_evidence_reference(id="asm-001")


def test_an_undocumented_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        an_evidence_reference(evidence_strength="direct")


def test_evidence_strength_is_not_carried_here() -> None:
    """DEC-022: strength is relational, not intrinsic.

    The same passage can be direct evidence for one claim and merely contextual for another, so it
    lives on `EvidenceAssessment.evidence_strengths` and never on the reference itself.
    """
    assert "evidence_strength" not in EvidenceReference.model_fields
    assert "evidence_strengths" not in EvidenceReference.model_fields


def test_a_reference_round_trips_through_json() -> None:
    """DEC-020 persists it as a JSON payload, so this is the storage path."""
    original = an_evidence_reference(metadata={JSON_POINTER_KEY: "/components/0"})
    restored = EvidenceReference.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.json_pointer == "/components/0"
    assert restored.created_at.tzinfo is not None


def test_a_timezone_aware_timestamp_survives() -> None:
    stamp = datetime(2026, 8, 5, 20, 10, tzinfo=UTC)
    assert an_evidence_reference(created_at=stamp).created_at == stamp


def test_references_are_not_hashable_despite_being_frozen() -> None:
    """Recorded because it is the opposite of what `frozen=True` suggests.

    `metadata` is a `dict`, and a frozen model containing an unhashable field is still unhashable.
    So the indexing step (#55) cannot deduplicate evidence with a set: it has to key on
    `content_hash` and location, which is the better key anyway -- two references to the same
    passage should collapse whether or not their metadata matches.
    """
    with pytest.raises(TypeError, match="unhashable"):
        {an_evidence_reference()}

    stamp = datetime(2026, 8, 5, 20, 10, tzinfo=UTC)
    first = an_evidence_reference(created_at=stamp)
    second = an_evidence_reference(created_at=stamp)
    assert first == second, "equality still works; only hashing does not"
    assert (first.content_hash, first.start_line) == (second.content_hash, second.start_line)
