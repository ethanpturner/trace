"""Tests for the identifier registry, both DEC-018 forms, and the allocator.

Section 2.1 lists the prefixes; DEC-018 splits identifiers into two classes with different rules.
The tests below are organized around the distinction, because it is the thing most likely to be
lost: authored identifiers are globally unique, stable across catalog versions, and the only ones
a benchmark expected-output file may reference, while generated identifiers are unique only within
their assessment and may be numbered differently on a re-run.

Two properties get more attention than their size suggests.

**The registry is closed.** A prefix outside section 2.1 is rejected, and the error names the
registry, because the failure it catches is a typo in a field that is otherwise free text.

**The in-memory allocator restarts.** It is the convenient thing to reach for and it is wrong for
an assessment, so the restart is asserted rather than left for someone to discover. Issue #44.
"""

from __future__ import annotations

import re

import pytest
import yaml
from pydantic import ValidationError

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import DomainModel
from trace_ai.domain.identifiers import (
    PREFIX_BY_TERM,
    PREFIXES,
    AssessmentId,
    FindingId,
    IdentifierKind,
    InMemoryAllocator,
    RequirementId,
    ThreatId,
    format_id,
    parse_id,
)

DATA_MODEL = PROJECT_ROOT / "docs" / "architecture" / "data-model.md"
CATALOG = PROJECT_ROOT / "requirements" / "catalog.yaml"

# Section 2.1 lists prefixes as `asm- Assessment`. Parsed rather than retyped, so a prefix added
# to the document without being added here fails.
DOCUMENTED_PREFIX = re.compile(r"^([a-z]+)-\s+([A-Z][A-Za-z ]+)$")

# The name form DEC-034 gives authored configuration: a lowercase slug, no number, no prefix.
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def documented_prefixes() -> dict[str, str]:
    """The prefix list in section 2.1, mapped to the object each names."""
    found: dict[str, str] = {}
    inside = False
    for line in DATA_MODEL.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("### 2.1"):
            inside = True
            continue
        if inside and stripped.startswith(("## ", "### ")):
            break
        if inside and (match := DOCUMENTED_PREFIX.match(stripped)):
            found[match.group(1)] = match.group(2).strip()
    return found


def test_the_prefix_list_was_found() -> None:
    """Guard the parser: an empty parse would make the comparison below vacuous."""
    assert len(documented_prefixes()) == 26


def test_the_registry_matches_section_two_point_one() -> None:
    """The document is authoritative for which prefixes exist.

    There are twenty-four. The issue asking for this module said nineteen and omitted `obs`, which
    DEC-021 added with SourceObservation after the backlog was written. DEC-034 added `act`, `eas`,
    and `crq` — three assessment-scoped objects that carry an `id` and had no prefix, which only
    became visible once section 2.1 stated what the scheme governs. DEC-052 added `mrg` with
    FindingMergeRecord.
    """
    documented = documented_prefixes()
    assert set(PREFIXES) == set(documented), (
        f"registry and section 2.1 disagree: only in code {sorted(set(PREFIXES) - set(documented))}, "
        f"only in the document {sorted(set(documented) - set(PREFIXES))}"
    )


def test_every_prefix_names_the_object_the_document_names() -> None:
    """`obs` naming SourceObservation rather than Observation is the kind of drift this catches."""
    for prefix, object_type in documented_prefixes().items():
        assert PREFIXES[prefix].lower() == object_type.replace(" ", "").lower()


@pytest.mark.parametrize("prefix", sorted(PREFIXES))
def test_a_generated_identifier_round_trips(prefix: str) -> None:
    parsed = parse_id(format_id(prefix, 7))
    assert parsed.prefix == prefix
    assert parsed.kind is IdentifierKind.GENERATED
    assert parsed.number == 7
    assert parsed.category is None
    assert parsed.object_type == PREFIXES[prefix]


def test_numbers_are_zero_padded_to_three_digits() -> None:
    assert format_id("asm", 1) == "asm-001"
    assert format_id("thr", 42) == "thr-042"
    assert format_id("fnd", 999) == "fnd-999"


def test_numbering_widens_past_999_rather_than_wrapping() -> None:
    """DEC-018 widens. The mixed width sorts badly in a lexical sort, and it is recorded there."""
    assert format_id("evd", 1000) == "evd-1000"
    assert parse_id("evd-1000").number == 1000


def test_a_number_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="start at 1"):
        format_id("asm", 0)


def test_an_unregistered_prefix_is_rejected_by_name() -> None:
    """The message names the registry, because the caller's next question is 'what is allowed'."""
    with pytest.raises(ValueError, match=re.escape("data-model.md section 2.1")) as caught:
        format_id("xyz", 1)
    assert "xyz" in str(caught.value)


def test_parsing_an_unregistered_prefix_names_the_registry() -> None:
    with pytest.raises(ValueError, match=re.escape("data-model.md section 2.1")):
        parse_id("xyz-001")


@pytest.mark.parametrize(
    "value",
    [
        "asm",  # no number
        "asm-",  # empty number
        "asm-1",  # too few digits for a generated identifier
        "asm-01",
        "asm-abc",
        "ASM-001",  # prefixes are lowercase
        "asm-001-extra",
        " asm-001",
        "asm_001",
        "",
    ],
)
def test_a_malformed_identifier_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        parse_id(value)


def test_an_authored_identifier_parses_as_authored() -> None:
    """`req-AUTH-001`: the shape the requirements catalog already uses (DEC-010)."""
    parsed = parse_id("req-AUTH-001")
    assert parsed.kind is IdentifierKind.AUTHORED
    assert parsed.prefix == "req"
    assert parsed.category == "AUTH"
    assert parsed.number == 1


def test_the_authored_form_is_tried_before_the_generated_one() -> None:
    """`req-AUTH-001` contains a prefix followed by digits, so order matters in the parser."""
    assert parse_id("req-AUTH-001").kind is IdentifierKind.AUTHORED
    assert parse_id("req-001").kind is IdentifierKind.GENERATED


def test_a_lowercase_category_is_not_an_authored_identifier() -> None:
    """The catalog's categories are uppercase; accepting both spellings would allow two ids for
    one requirement."""
    with pytest.raises(ValueError):
        parse_id("req-auth-001")


def catalog_requirement_ids() -> list[str]:
    loaded = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    ids = loaded["catalog"]["requirement_ids"]
    assert isinstance(ids, list) and ids, "the catalog lists no requirement identifiers"
    return [str(value) for value in ids]


@pytest.mark.parametrize("identifier", catalog_requirement_ids())
def test_every_catalog_requirement_identifier_validates(identifier: str) -> None:
    """The real data, not a fixture of it.

    DEC-010 makes these stable across catalog versions, and DEC-018 makes them the only
    identifiers a benchmark expected-output file may reference. A scheme that rejected one would
    invalidate the catalog.
    """
    parsed = parse_id(identifier)
    assert parsed.prefix == "req"
    assert parsed.kind is IdentifierKind.AUTHORED


def test_section_two_point_one_states_what_the_scheme_governs() -> None:
    """The omission DEC-034 closed, and the one that produced `cat-core` in the first place.

    A prefix list with no statement of its scope invites every object with an `id` field to acquire
    a prefix by resemblance. The sentence is what stops the next authored object doing it, so its
    absence is worth a test even though prose is what is being asserted.
    """
    text = DATA_MODEL.read_text(encoding="utf-8")
    assert "## What the scheme governs" in text
    governs = text.split("## What the scheme governs", 1)[1].split("## Two classes", 1)[0]
    assert "RequirementsCatalog" in governs
    assert "PromptDefinition" in governs


def test_the_catalog_is_named_rather_than_identified() -> None:
    """`requirements/catalog.yaml` calls itself `core`, and that is a name, not an identifier.

    DEC-034 puts authored configuration outside the scheme: a catalog is not scoped to an
    assessment, is not minted by the persistence layer, and is referenced by version rather than by
    identifier. `(id, version)` is its identity.

    The assertion that matters is the second one. The value was `cat-core` until DEC-034, which read
    as an identifier from a registry that does not contain `cat`; a name that does not parse cannot
    be mistaken for one.
    """
    loaded = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    catalog_id = loaded["catalog"]["id"]
    assert catalog_id == "core"
    assert SLUG.match(catalog_id), f"a catalog name is a lowercase slug, got {catalog_id!r}"

    with pytest.raises(ValueError, match=re.escape("data-model.md section 2.1")):
        parse_id(catalog_id)


class Sample(DomainModel):
    """Fields typed by prefix, the way a real object declares them."""

    id: FindingId
    assessment_id: AssessmentId


def test_an_annotated_field_accepts_its_own_prefix() -> None:
    sample = Sample(id="fnd-003", assessment_id="asm-001")
    assert sample.id == "fnd-003"


def test_an_annotated_field_rejects_another_objects_identifier() -> None:
    """The reason these are types and not `str`: `thr-007` in a finding field is a real mistake."""
    with pytest.raises(ValidationError, match="names a Threat"):
        Sample(id="thr-007", assessment_id="asm-001")


def test_an_annotated_field_rejects_a_malformed_identifier() -> None:
    with pytest.raises(ValidationError):
        Sample(id="fnd-3", assessment_id="asm-001")


def test_a_requirement_field_accepts_the_authored_form() -> None:
    """Catalog identifiers have to pass the same typed field a generated one would."""

    class WithRequirement(DomainModel):
        requirement_id: RequirementId

    assert WithRequirement(requirement_id="req-AUTH-001").requirement_id == "req-AUTH-001"
    assert WithRequirement(requirement_id="req-001").requirement_id == "req-001"


def test_the_allocator_numbers_from_one_and_increments() -> None:
    allocator = InMemoryAllocator()
    assert [allocator.allocate("thr") for _ in range(3)] == ["thr-001", "thr-002", "thr-003"]


def test_counters_are_independent_per_prefix() -> None:
    allocator = InMemoryAllocator()
    assert allocator.allocate("thr") == "thr-001"
    assert allocator.allocate("fnd") == "fnd-001"
    assert allocator.allocate("thr") == "thr-002"


def test_no_number_is_issued_twice() -> None:
    """Monotonic per DEC-018: a discarded object's number is never handed back."""
    allocator = InMemoryAllocator()
    issued = [allocator.allocate("evd") for _ in range(500)]
    assert len(set(issued)) == 500
    assert allocator.issued("evd") == 500


def test_the_allocator_rejects_an_unregistered_prefix() -> None:
    with pytest.raises(ValueError, match=re.escape("data-model.md section 2.1")):
        InMemoryAllocator().allocate("xyz")


def test_a_fresh_allocator_restarts_and_collides() -> None:
    """Asserted because it is the trap, not because it is the behaviour anyone wants.

    DEC-018 puts allocation in the persistence layer precisely so numbering survives the process.
    DEC-017 pauses a workflow by persisting the run and exiting, so a resumed assessment backed by
    this allocator would re-mint identifiers that already exist. Anyone who reaches for this class
    because a store is inconvenient should find this test when they look for why.
    """
    first, second = InMemoryAllocator(), InMemoryAllocator()
    assert first.allocate("thr") == second.allocate("thr") == "thr-001"


def test_the_allocator_satisfies_the_protocol() -> None:
    """Structural, so the store-backed implementation can be substituted without inheritance."""
    from trace_ai.domain.identifiers import IdentifierAllocator

    allocator: IdentifierAllocator = InMemoryAllocator()
    assert parse_id(allocator.allocate("run")).prefix == "run"


def test_identifiers_do_not_depend_on_a_display_name() -> None:
    """Section 2.1: identifiers must not depend on mutable display names.

    The allocator takes a prefix and nothing else, so there is no name for one to depend on. This
    states the property rather than testing a mechanism, so that adding a name argument later
    fails a test whose docstring says why it exists.
    """
    import inspect

    signature = inspect.signature(InMemoryAllocator.allocate)
    assert list(signature.parameters) == ["self", "prefix"]


def test_a_typed_field_is_still_a_string() -> None:
    """The annotated types stay `str` at runtime, so they serialize and compare as identifiers."""
    sample = Sample(id="fnd-003", assessment_id="asm-001")
    assert isinstance(sample.id, str)
    assert sample.model_dump() == {"id": "fnd-003", "assessment_id": "asm-001"}
    assert ThreatId is not FindingId


def test_an_object_type_has_one_vocabulary_spelling() -> None:
    """Three objects name another object's type in a free-text field — `ContextClaim.subject_type`,
    `Question.related_object_type`, `ReviewerDecision.subject_type` — and each has to agree with an
    accompanying identifier about what kind of thing is meant. One conversion, so they cannot
    disagree about how `ContextClaim` is spelled."""
    assert parse_id("ctx-001").object_term == "context_claim"
    assert parse_id("cmp-001").object_term == "component"
    assert parse_id("src-001").object_term == "source_document"


def test_every_prefix_is_reachable_by_its_term() -> None:
    assert set(PREFIX_BY_TERM.values()) == set(PREFIXES)
    assert PREFIX_BY_TERM["evidence_reference"] == "evd"


def test_every_prefix_has_an_exported_annotated_alias() -> None:
    """`PREFIXES`, `__all__`, and the `Annotated` aliases are hand-written (mypy visibility, stated
    in the module). Nothing checked they agreed, so a prefix added to `PREFIXES` with no alias
    validated as `str` everywhere. Each prefix's object type must have a `{ObjectType}Id` alias,
    exported and defined, and no `*Id` alias exists without a prefix behind it."""
    import trace_ai.domain.identifiers as ids

    expected = {f"{object_type}Id" for object_type in PREFIXES.values()}
    exported = {name for name in ids.__all__ if name.endswith("Id")}
    assert exported == expected, "an alias and a prefix have drifted out of step"
    for name in expected:
        assert hasattr(ids, name), f"{name} is exported but not defined"
