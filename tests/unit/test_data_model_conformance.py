"""The guard that makes "`data-model.md` is authoritative" true rather than aspirational.

`CLAUDE.md` says the document is authoritative for field names and types, and
`tests/unit/test_requirements_catalog.py` already holds hand-maintained data to it. The same
drift is available to the Pydantic models, in both directions: a field renamed in the document
and not in the code, or a field added to the code the document never sanctioned. Neither shows up
as a test failure anywhere else, because every other test asserts what the code does.

So this file reads the document and compares.

**Almost nothing is compared yet, and that is the point of the registry.** None of the objects in
sections 5 to 31 is implemented -- `Assessment`, `SourceDocument`, and `EvidenceReference` arrive
with #49, #52, and #51. A conformance test whose comparison loop runs zero times is the most
dangerous kind of green, so the registry classifies every section explicitly and a test asserts
that the classification covers the whole range with nothing missing. When a model lands, moving
one registry line switches the guard on for it.

The comparison machinery is proven now rather than when the first model arrives. `Section5Shape`
is a throwaway model written to match section 5's table exactly, and five mutations of it -- an
added field, a removed one, a rename, and a required flag flipped each way -- are asserted to
fail. That is the evidence the acceptance criteria ask for, obtained without waiting for
`Assessment` to exist.

Two things the parser found on the way, handled differently because they are different problems.
`SourceObservation` is documented as section `10a` and was on neither of section 40's lists, which
predate DEC-021; that was an omission with a settled answer, so section 40 gained the entry in the
same change. `Actor` was on neither list either, and open question 4 asked whether it was a
first-class object at all, so it stayed `UNRESOLVED` and nothing here decided it. "The plan forgot
it" and "nobody has decided" call for different fixes, which is why the registry keeps them
apart. DEC-037 has since answered the second one, and `Actor` moved to `IMPLEMENTED` with the
section 40 entry and `SystemContext.actor_ids` in the same change — which is what `UNRESOLVED` was
holding the place for.

Section 4's enum conformance moved here from `test_domain_enums.py`, so that every
document-versus-code comparison lives in one file and shares one parser. Issue #45.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

import pytest
from pydantic import BaseModel, create_model

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.actor import Actor
from trace_ai.domain.assessment import Assessment, AssessmentConfiguration
from trace_ai.domain.asset import Asset
from trace_ai.domain.base import DomainModel
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    ReviewDisposition,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import ExecutionRecord, WorkflowRun
from trace_ai.domain.source_document import SourceDocument
from trace_ai.domain.trust_boundary import TrustBoundary

DATA_MODEL = PROJECT_ROOT / "docs" / "architecture" / "data-model.md"

# `# 5. Assessment`, at any heading depth.
_SECTION = re.compile(r"^#+\s+(\d+[a-z]?)\.\s+(.+?)\s*$")
# `## 4.1 ObjectStatus`
_SUBSECTION = re.compile(r"^#+\s+(4\.\d)\s+(\S+)\s*$")
# A bare value line in section 4. Prose there always carries spaces, punctuation, or Markdown.
_ENUM_MEMBER = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class DocumentedField:
    """One row of an object's `## Fields` table."""

    name: str
    type_: str
    required: bool
    description: str


def _rows(cells: list[str]) -> DocumentedField:
    return DocumentedField(
        name=cells[0], type_=cells[1], required=cells[2] == "Yes", description=cells[3]
    )


def documented_objects() -> dict[str, str]:
    """Section number to object name, for every numbered section in the document."""
    found: dict[str, str] = {}
    for line in DATA_MODEL.read_text(encoding="utf-8").splitlines():
        if match := _SECTION.match(line.strip()):
            found[match.group(1)] = match.group(2)
    return found


def documented_fields() -> dict[str, list[DocumentedField]]:
    """Section number to its `## Fields` table.

    Rows are taken only between a `## Fields` heading and the next heading, rather than from
    anywhere in the section. Several sections carry a second four-column table -- vocabularies,
    status meanings, worked examples -- and a looser rule would fold those in as fields.
    """
    tables: dict[str, list[DocumentedField]] = {}
    section: str | None = None
    in_fields = False

    for line in DATA_MODEL.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if match := _SECTION.match(stripped):
            section, in_fields = match.group(1), False
            continue
        if stripped.startswith("#"):
            in_fields = stripped.lstrip("#").strip().casefold().startswith("fields")
            continue
        if not (in_fields and section and stripped.startswith("|")):
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 4 or cells[2] not in {"Yes", "No"}:
            continue  # header row, separator row, or a row that is not a field
        tables.setdefault(section, []).append(_rows(cells))

    return tables


def documented_enum_values() -> dict[str, list[str]]:
    """Section 4's subsections, each mapped to the values listed under it."""
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in DATA_MODEL.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            match = _SUBSECTION.match(stripped)
            current = match.group(1) if match else None
            if current is not None:
                sections[current] = []
            continue
        if current is not None and _ENUM_MEMBER.match(stripped):
            sections[current].append(stripped)

    return sections


def implementation_priority() -> tuple[list[str], list[str]]:
    """Section 40's two lists: build first, and add once the workflow operates.

    Parsed rather than retyped so the registry cannot disagree with the document about which
    objects are deferred.
    """
    text = DATA_MODEL.read_text(encoding="utf-8")
    section_40 = text.split("# 40. Initial Implementation Priority", 1)[1]

    first = [
        match.group(1)
        for match in re.finditer(r"^\d+\.\s+(\S+)\s*$", section_40, flags=re.MULTILINE)
    ]
    sentence = re.search(r"^Add (.+?) once the main workflow", section_40, flags=re.MULTILINE)
    assert sentence is not None, "section 40's deferred sentence changed shape"
    later = [name.strip() for name in sentence.group(1).replace("and ", "").split(",")]

    return first, later


class Status(StrEnum):
    """Why a section is or is not being compared against a model."""

    IMPLEMENTED = "implemented"
    PLANNED = "planned"  # section 40's build-first list; the model does not exist yet
    DEFERRED = "deferred"  # section 40: add once the main workflow begins operating
    UNRESOLVED = "unresolved"  # in neither list; an open question decides whether it exists
    UNLISTED = "unlisted"  # a documented object section 40 never gained an entry for
    NOT_AN_OBJECT = "not_an_object"  # a section with no field table


@dataclass(frozen=True, slots=True)
class Registration:
    """What this file knows about one section."""

    name: str
    status: Status
    model: type[BaseModel] | None = None


# Every section from 5 to 31, classified. Nothing is skipped by omission: a section absent from
# this table fails `test_the_registry_covers_every_object_section`, so a new object added to the
# document arrives here as a decision.
#
# To switch the guard on for an object, change its status to IMPLEMENTED and name the model.
REGISTRY: dict[str, Registration] = {
    "5": Registration("Assessment", Status.IMPLEMENTED, Assessment),
    "6": Registration("AssessmentConfiguration", Status.IMPLEMENTED, AssessmentConfiguration),
    "7": Registration("SourceDocument", Status.IMPLEMENTED, SourceDocument),
    "8": Registration("EvidenceReference", Status.IMPLEMENTED, EvidenceReference),
    "9": Registration("SystemContext", Status.PLANNED),
    "10": Registration("ContextClaim", Status.IMPLEMENTED, ContextClaim),
    # Documented as `10a` rather than as its own numbered section, because DEC-021 added it after
    # the rest were numbered. This guard found it absent from section 40's priority list as well;
    # that was repaired in the same change, and it is `PLANNED` because the list now says so.
    "10a": Registration("SourceObservation", Status.PLANNED),
    "11": Registration("Component", Status.IMPLEMENTED, Component),
    "12": Registration("Asset", Status.IMPLEMENTED, Asset),
    # Was UNRESOLVED: section 40 listed neither Actor nor a replacement, and open question 4
    # asked whether actors are first-class objects at all. DEC-037 answers both, so the section 40
    # entry and `SystemContext.actor_ids` arrived with the model.
    "13": Registration("Actor", Status.IMPLEMENTED, Actor),
    "14": Registration("DataFlow", Status.IMPLEMENTED, DataFlow),
    "15": Registration("TrustBoundary", Status.IMPLEMENTED, TrustBoundary),
    "16": Registration("Threat", Status.PLANNED),
    "17": Registration("Requirement", Status.PLANNED),
    "18": Registration("Control", Status.PLANNED),
    "19": Registration("ControlMapping", Status.PLANNED),
    "20": Registration("EvidenceAssessment", Status.DEFERRED),
    "21": Registration("Finding", Status.PLANNED),
    "22": Registration("Question", Status.PLANNED),
    "23": Registration("DocumentationGap", Status.PLANNED),
    "24": Registration("Critique", Status.DEFERRED),
    "25": Registration("ReviewerDecision", Status.PLANNED),
    "26": Registration("WorkflowRun", Status.IMPLEMENTED, WorkflowRun),
    "27": Registration("ExecutionRecord", Status.IMPLEMENTED, ExecutionRecord),
    "28": Registration("EvaluationResult", Status.DEFERRED),
    "29": Registration("PromptDefinition", Status.DEFERRED),
    "30": Registration("RequirementsCatalog", Status.DEFERRED),
    # Workflow state, described as a proposed structure rather than a field table. It is not a
    # persisted object and has nothing to conform to.
    "31": Registration("Assessment State", Status.NOT_AN_OBJECT),
}

# In document order, so a failure reads the way the document does. `10a` is not a typo: see the
# registry entry above.
OBJECT_SECTIONS = [
    *(str(number) for number in range(5, 11)),
    "10a",
    *(str(number) for number in range(11, 32)),
]


# --------------------------------------------------------------------------------------------
# The parser, guarded before anything trusts it
# --------------------------------------------------------------------------------------------


def test_every_object_section_was_found() -> None:
    documented = documented_objects()
    missing = [section for section in OBJECT_SECTIONS if section not in documented]
    assert not missing, f"sections {missing} did not parse; the heading format likely changed"


def test_field_tables_parse_for_every_section_that_has_one() -> None:
    """Section 31 is the only one without a field table, and that is a stated fact about it."""
    tables = documented_fields()
    expected = [s for s in OBJECT_SECTIONS if REGISTRY[s].status is not Status.NOT_AN_OBJECT]
    parsed = [section for section in OBJECT_SECTIONS if section in tables]
    assert parsed == expected


def test_the_first_four_tables_have_the_row_counts_the_document_shows() -> None:
    """Anchors the parser against literal counts, so a silently truncated table is caught.

    These four are the ones M1 implements, and they are checked by number because a parser that
    returns three rows of a fifteen-row table produces a conformance test that passes for the
    wrong reason.
    """
    tables = documented_fields()
    assert len(tables["5"]) == 15, "Assessment"
    assert len(tables["6"]) == 8, "AssessmentConfiguration"
    assert len(tables["7"]) == 14, "SourceDocument"
    assert len(tables["8"]) == 14, "EvidenceReference"


def test_the_parser_excludes_tables_that_are_not_field_tables() -> None:
    """Section 4.2 carries a `| Level | Meaning |` table and section 10 a status vocabulary.

    Both would corrupt a field list if the parser took any table in the section.
    """
    fields = {field.name for field in documented_fields()["10"]}
    assert "Documented" not in fields
    assert "Status" not in fields
    assert "id" in fields


def test_field_names_are_unique_within_an_object() -> None:
    for section, fields in documented_fields().items():
        names = [field.name for field in fields]
        assert len(names) == len(set(names)), f"section {section} lists a field twice: {names}"


def test_every_field_row_has_a_description() -> None:
    """An undescribed field is a row someone added mid-thought."""
    for section, fields in documented_fields().items():
        for field in fields:
            assert field.description, f"section {section}: {field.name} has no description"


def test_section_forty_parses_into_two_lists() -> None:
    first, later = implementation_priority()
    assert len(first) == 22, first
    assert later == [
        "Critique",
        "EvidenceAssessment",
        "PromptDefinition",
        "RequirementsCatalog",
        "EvaluationResult",
    ]


# --------------------------------------------------------------------------------------------
# The registry: nothing falls out of view
# --------------------------------------------------------------------------------------------


def test_the_registry_covers_every_object_section() -> None:
    """The test that stops this file from being vacuously green.

    Every section from 5 to 31 is classified. A new object added to the document is unregistered
    and fails here, rather than being silently unguarded.
    """
    assert list(REGISTRY) == OBJECT_SECTIONS


def test_the_registry_names_match_the_document() -> None:
    documented = documented_objects()
    for section, registration in REGISTRY.items():
        assert registration.name == documented[section], (
            f"section {section}: the registry calls it {registration.name!r}, "
            f"the document calls it {documented[section]!r}"
        )


def test_deferred_objects_are_exactly_the_ones_section_forty_defers() -> None:
    _, later = implementation_priority()
    deferred = {r.name for r in REGISTRY.values() if r.status is Status.DEFERRED}
    assert deferred == set(later)


def test_planned_and_implemented_objects_are_on_section_forty_s_first_list() -> None:
    first, _ = implementation_priority()
    building = {
        r.name for r in REGISTRY.values() if r.status in {Status.PLANNED, Status.IMPLEMENTED}
    }
    assert building == set(first), (
        f"registry says build {sorted(building - set(first))} that section 40 does not list, "
        f"and omits {sorted(set(first) - building)} that it does"
    )


def test_unresolved_objects_appear_on_neither_list() -> None:
    """`UNRESOLVED` is a claim about the document, so it is checked against the document."""
    first, later = implementation_priority()
    for registration in REGISTRY.values():
        if registration.status is Status.UNRESOLVED:
            assert registration.name not in first
            assert registration.name not in later


def test_nothing_is_unlisted() -> None:
    """`UNLISTED` is the escape hatch for a documented object section 40 does not plan.

    It had exactly one occupant when this guard was written. `SourceObservation` carries a full
    field table at section `10a` and the `obs-` prefix in section 2.1, DEC-021 makes contradictions
    and detected injection attempts one object of this type, the context step produces them, and
    DEC-027 grades them from `expected-observations.yaml` -- and section 40, written before
    DEC-021, listed neither it nor a reason for its absence. Adding it to the list was part of the
    same change as this test.

    The status stays because the state can recur: the next object added to the document after a
    decision will arrive the same way. An empty set is the assertion, so a recurrence has to be
    classified deliberately rather than absorbed.
    """
    assert not [r.name for r in REGISTRY.values() if r.status is Status.UNLISTED]


def test_source_observation_is_planned_and_ordered_after_the_claims_it_references() -> None:
    """The placement is a claim about the object, so it is asserted rather than left to the eye.

    `subject_claim_ids` references `ContextClaim`, so building observations first would mean
    building a reference to something that does not exist.
    """
    first, _ = implementation_priority()
    assert "SourceObservation" in first
    assert first.index("SourceObservation") > first.index("ContextClaim")

    fields = {field.name for field in documented_fields()["10a"]}
    assert {"id", "assessment_id", "kind", "summary", "subject_claim_ids"} <= fields


def test_an_implemented_registration_carries_a_model() -> None:
    for section, registration in REGISTRY.items():
        if registration.status is Status.IMPLEMENTED:
            assert registration.model is not None, f"section {section} claims a model and has none"
        else:
            assert registration.model is None, (
                f"section {section} names a model but is not marked implemented"
            )


def test_the_guard_is_switched_on_for_something() -> None:
    """The inverse of the test this replaces.

    Until #49 there was no implemented object, and a test asserted that so the switch could not be
    forgotten. Now that one exists, the risk runs the other way: an implemented object left at
    `PLANNED` is unguarded, and the file goes quiet about it.
    """
    implemented = [s for s, r in REGISTRY.items() if r.status is Status.IMPLEMENTED]
    assert implemented, "nothing is registered; the conformance comparison runs zero times"


# --------------------------------------------------------------------------------------------
# The comparison, and proof that it fails when it should
# --------------------------------------------------------------------------------------------


def compare(section: str, model: type[BaseModel]) -> None:
    """Assert a model's field set and required flags match the document's table for `section`.

    Types are not compared. The document's `Type` column mixes model names, primitives, and prose
    -- `map[string, any]`, `list[string]`, `AssessmentConfiguration` -- and turning that into
    Python types would encode a mapping the document does not define.
    """
    documented = {field.name: field for field in documented_fields()[section]}
    implemented = model.model_fields

    assert set(implemented) == set(documented), (
        f"section {section} ({model.__name__}): "
        f"fields in the model the document does not list: {sorted(set(implemented) - set(documented))}; "
        f"fields in the document the model does not have: {sorted(set(documented) - set(implemented))}"
    )

    for name, field in documented.items():
        assert implemented[name].is_required() == field.required, (
            f"section {section} ({model.__name__}): {name} is "
            f"{'required' if field.required else 'optional'} in the document and "
            f"{'required' if implemented[name].is_required() else 'optional'} in the model"
        )


@pytest.mark.parametrize(
    ("section", "registration"),
    [(s, r) for s, r in REGISTRY.items() if r.status is Status.IMPLEMENTED],
)
def test_an_implemented_model_conforms(section: str, registration: Registration) -> None:
    assert registration.model is not None
    compare(section, registration.model)


class Section5Shape(DomainModel):
    """A throwaway model written to match section 5's table exactly.

    It exists to prove `compare` works before any real object does. It is not `Assessment` and
    must not become it: #49 builds that, with real types, validators, and identifier annotations.
    """

    id: str
    name: str
    description: str | None = None
    status: str
    created_at: str
    updated_at: str
    created_by: str | None = None
    architecture_version: str
    data_model_version: str
    workflow_version: str
    requirements_catalog_version: str | None = None
    configuration: str
    active_workflow_run_id: str | None = None
    final_report_path: str | None = None
    tags: list[str] | None = None


def variant_of_section_5(**changes: tuple[object, object] | None) -> type[BaseModel]:
    """`Section5Shape` with fields added, removed, or re-declared.

    Built with `create_model` rather than by subclassing, because the interesting mutations are
    ones a subclass cannot express: widening a required field to optional narrows nothing and is
    rejected by the type checker, and removing an inherited field is not possible at all.

    A change of `None` deletes the field; otherwise it is an `(annotation, default)` pair, with
    `...` as the default meaning required.
    """
    definitions: dict[str, tuple[object, object]] = {
        name: (info.annotation, ... if info.is_required() else info.default)
        for name, info in Section5Shape.model_fields.items()
    }
    for name, change in changes.items():
        if change is None:
            definitions.pop(name)
        else:
            definitions[name] = change
    return create_model("Section5Variant", __base__=DomainModel, **definitions)  # type: ignore[call-overload, no-any-return]


def test_a_conforming_model_passes() -> None:
    compare("5", Section5Shape)


def test_the_variant_builder_reproduces_the_original() -> None:
    """Guard the mutation helper: if it silently dropped fields, every test below would pass."""
    compare("5", variant_of_section_5())


def test_an_extra_field_fails() -> None:
    """The field an agent invents, or that a developer adds without touching the document."""
    with pytest.raises(AssertionError, match="the document does not list"):
        compare("5", variant_of_section_5(severity_rationale=(str | None, None)))


def test_a_missing_field_fails() -> None:
    with pytest.raises(AssertionError, match="the model does not have"):
        compare("5", variant_of_section_5(tags=None))


def test_a_renamed_field_fails() -> None:
    """A rename is an addition and a removal at once, and must be reported as both."""
    renamed = variant_of_section_5(name=None, assessment_name=(str, ...))
    with pytest.raises(AssertionError) as caught:
        compare("5", renamed)
    assert "assessment_name" in str(caught.value), "the added name is not reported"
    assert "'name'" in str(caught.value), "the removed name is not reported"


def test_making_an_optional_field_required_fails() -> None:
    """`description` is optional in the document."""
    with pytest.raises(AssertionError, match="optional in the document"):
        compare("5", variant_of_section_5(description=(str, ...)))


def test_making_a_required_field_optional_fails() -> None:
    """`name` is required in the document."""
    with pytest.raises(AssertionError, match="required in the document"):
        compare("5", variant_of_section_5(name=(str | None, None)))


def test_the_failure_message_names_the_section_and_the_field() -> None:
    """Acceptance criterion: every failure says which section and which field."""
    with pytest.raises(AssertionError) as caught:
        compare("5", variant_of_section_5(invented=(str | None, None)))
    assert "section 5" in str(caught.value)
    assert "invented" in str(caught.value)


# --------------------------------------------------------------------------------------------
# Section 4: the enums
# --------------------------------------------------------------------------------------------

# Moved here from test_domain_enums.py, which now covers behaviour only. Both halves of the
# comparison live in one file so a single parser serves them: the literal below is an
# independent second source, and the document is the authority the literal is checked against.
ENUMS: dict[str, tuple[type[StrEnum], tuple[str, ...]]] = {
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

# 7 + 3 + 4 + 7 + 6 + 7 + 6, stated independently of the table above so that deleting an entry
# from it cannot also lower the bar the parser has to clear.
TOTAL_ENUM_MEMBERS = 40


def test_the_enum_parser_found_section_four() -> None:
    parsed = documented_enum_values()
    assert set(parsed) == set(ENUMS), f"parsed subsections {sorted(parsed)}"
    assert sum(len(values) for values in parsed.values()) == TOTAL_ENUM_MEMBERS


def test_the_enum_parser_rejects_prose() -> None:
    """Sections 4.2, 4.5, and 4.6 put tables and paragraphs among their values."""
    assert not _ENUM_MEMBER.match("Possible values:")
    assert not _ENUM_MEMBER.match("| Low | Significant uncertainty or weak evidence |")
    assert not _ENUM_MEMBER.match("**`unassigned` is the value a finding is created with.**")
    assert _ENUM_MEMBER.match("convert_to_documentation_gap")


@pytest.mark.parametrize(("subsection", "expected"), [(k, v[1]) for k, v in ENUMS.items()])
def test_the_document_lists_exactly_these_enum_values(
    subsection: str, expected: tuple[str, ...]
) -> None:
    documented = documented_enum_values()[subsection]
    assert tuple(documented) == expected, (
        f"section {subsection} lists {documented}, this test expects {list(expected)}. "
        f"The document is authoritative: if it changed deliberately, update the enum and this "
        f"test together."
    )


@pytest.mark.parametrize(("enum", "expected"), list(ENUMS.values()))
def test_the_enum_carries_exactly_these_values(
    enum: type[StrEnum], expected: tuple[str, ...]
) -> None:
    assert tuple(member.value for member in enum) == expected
