"""Object identifiers: the registry, the two forms, and the allocator interface.

`data-model.md` section 2.1 requires every important object to carry a stable identifier and
lists the prefixes. DEC-018 settles what those identifiers look like, and the part that governs
this module is that there are **two classes**, not one:

**Authored identifiers** are written by hand and carry meaning. `req-AUTH-001` is the shape: the
prefix names the object type, the middle segment names a category, and the number is assigned by
the author. They are globally unique and stable across catalog versions, and they are the only
identifiers a benchmark expected-output file may reference.

**Generated identifiers** are minted during an assessment as `<prefix>-<NNN>` -- `thr-007`,
`fnd-003` -- zero-padded to three digits and widening past 999. They are unique **within their
assessment**, not globally: `thr-007` in two assessments is two different objects, and an
identifier is fully qualified only by `(assessment_id, id)`.

**The scheme governs objects an assessment produces** (DEC-034): scoped to one assessment,
persisted by the assessment store, and referred to by identifier from somewhere else. `Requirement`
is the one authored member, because assessment objects cite `req-AUTH-001` by identifier. Authored
configuration -- `RequirementsCatalog`, `PromptDefinition` -- is outside it and carries a name
rather than an identifier: `core`, `extract-context`, referenced by version. Nothing here validates
those, and a prefixed value in one of them would be a name imitating an identifier.

**Allocation is a store operation, not a pure function.** DEC-018 assigns a generated identifier
at insert, from a monotonic counter per `(assessment_id, prefix)`. That is why this module defines
`IdentifierAllocator` as a protocol rather than exposing a module-level allocator function: a
process-global counter would be a second source of numbers that works in every test and silently
collides with the store in the one place it matters. `InMemoryAllocator` implements the protocol
for tests and for code that has no store yet; the store-backed implementation belongs with the
persistence layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Final, Protocol

from pydantic import AfterValidator

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "PREFIXES",
    "PREFIX_BY_TERM",
    "ActorId",
    "AssessmentId",
    "AssetId",
    "CatalogGapCandidateId",
    "ComponentId",
    "ContextClaimId",
    "ControlId",
    "ControlMappingId",
    "CritiqueId",
    "DataFlowId",
    "DocumentationGapId",
    "EvaluationResultId",
    "EvidenceAssessmentId",
    "EvidenceReferenceId",
    "ExecutionRecordId",
    "FindingId",
    "FindingMergeRecordId",
    "IdentifierAllocator",
    "IdentifierKind",
    "InMemoryAllocator",
    "ParsedIdentifier",
    "QuestionId",
    "RequirementId",
    "ReviewSessionId",
    "ReviewerDecisionId",
    "SourceDocumentId",
    "SourceObservationId",
    "ThreatId",
    "TrustBoundaryId",
    "WorkflowRunId",
    "format_id",
    "parse_id",
]

# Every prefix data-model.md section 2.1 lists, mapped to the object it identifies. The mapping
# is carried rather than a bare set so that a validation error can name the object type, which is
# the thing a reader of the error actually needs.
#
# There are twenty-five. The issue that asked for this module said nineteen and omitted `obs`,
# which DEC-021 added along with SourceObservation after the backlog was written. DEC-034 added
# `act`, `eas`, and `crq`: all three name assessment-scoped objects that carry an `id` and had no
# prefix, which a rule saying what the scheme governs made visible. DEC-052 added `mrg` with
# FindingMergeRecord, and DEC-065 added `cgc` with CatalogGapCandidate. Section 2.1 is
# authoritative and lists them.
PREFIXES: Final[Mapping[str, str]] = {
    "asm": "Assessment",
    "src": "SourceDocument",
    "evd": "EvidenceReference",
    "cmp": "Component",
    "ast": "Asset",
    "df": "DataFlow",
    "tb": "TrustBoundary",
    "ctx": "ContextClaim",
    "thr": "Threat",
    "req": "Requirement",
    "ctl": "Control",
    "map": "ControlMapping",
    "fnd": "Finding",
    "qst": "Question",
    "gap": "DocumentationGap",
    "obs": "SourceObservation",
    "act": "Actor",
    "eas": "EvidenceAssessment",
    "crq": "Critique",
    "dec": "ReviewerDecision",
    "run": "WorkflowRun",
    "exe": "ExecutionRecord",
    "eval": "EvaluationResult",
    "mrg": "FindingMergeRecord",
    "cgc": "CatalogGapCandidate",
    "rvs": "ReviewSession",
}


def _term(object_type: str) -> str:
    """`ContextClaim` -> `context_claim`: the object type as a vocabulary term.

    Several objects name the type of another object in a free-text field -- `ContextClaim.
    subject_type`, `Question.related_object_type`, `ReviewerDecision.subject_type` -- and every one
    of them has to agree with the accompanying identifier about what kind of thing is being talked
    about. One conversion, so the three cannot disagree about how `ContextClaim` is spelled.
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", object_type).casefold()


# Vocabulary term to prefix: `component` -> `cmp`, `context_claim` -> `ctx`. Derived from the
# registry so a prefix added to section 2.1 is covered without a second list to maintain.
PREFIX_BY_TERM: dict[str, str] = {_term(name): prefix for prefix, name in PREFIXES.items()}

# DEC-018's zero-padding. Three digits, widening rather than wrapping past 999.
NUMBER_WIDTH = 3

_PREFIX = "|".join(sorted(PREFIXES, key=len, reverse=True))
_GENERATED = re.compile(rf"^(?P<prefix>{_PREFIX})-(?P<number>\d{{{NUMBER_WIDTH},}})$")
_AUTHORED = re.compile(rf"^(?P<prefix>{_PREFIX})-(?P<category>[A-Z][A-Z0-9]*)-(?P<number>\d+)$")


class IdentifierKind(StrEnum):
    """Which of DEC-018's two classes an identifier belongs to."""

    GENERATED = "generated"
    AUTHORED = "authored"


@dataclass(frozen=True, slots=True)
class ParsedIdentifier:
    """An identifier taken apart, so callers read fields rather than re-parse strings."""

    value: str
    prefix: str
    kind: IdentifierKind
    number: int
    category: str | None = None

    @property
    def object_type(self) -> str:
        """The domain object this identifier names, per section 2.1."""
        return PREFIXES[self.prefix]

    @property
    def object_term(self) -> str:
        """The same object type as a vocabulary term: `context_claim` rather than `ContextClaim`.

        What a `subject_type` or `related_object_type` field holds, so a coherence check compares
        one spelling rather than two.
        """
        return _term(self.object_type)


def _registry_hint(prefix: str) -> str:
    return (
        f"'{prefix}' is not one of the {len(PREFIXES)} prefixes in data-model.md section 2.1: "
        f"{', '.join(sorted(PREFIXES))}"
    )


def parse_id(value: str) -> ParsedIdentifier:
    """Take an identifier apart, or explain why it is not one.

    Both DEC-018 classes are accepted. The authored form is tried first: `req-AUTH-001` also
    contains a valid prefix followed by digits, so a generated-first parse would have to
    backtrack out of a partial match rather than simply fail.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("an identifier must be a non-empty string")

    if authored := _AUTHORED.match(value):
        return ParsedIdentifier(
            value=value,
            prefix=authored["prefix"],
            kind=IdentifierKind.AUTHORED,
            number=int(authored["number"]),
            category=authored["category"],
        )

    if generated := _GENERATED.match(value):
        return ParsedIdentifier(
            value=value,
            prefix=generated["prefix"],
            kind=IdentifierKind.GENERATED,
            number=int(generated["number"]),
        )

    prefix = value.split("-", 1)[0]
    if prefix not in PREFIXES:
        raise ValueError(f"{value!r} is not a valid identifier: {_registry_hint(prefix)}")
    raise ValueError(
        f"{value!r} is not a valid identifier. A generated identifier is "
        f"'{prefix}-NNN' with at least {NUMBER_WIDTH} digits; an authored one is "
        f"'{prefix}-CATEGORY-NNN' with an uppercase category."
    )


def format_id(prefix: str, number: int) -> str:
    """Render a generated identifier. Pure; the number comes from an allocator, not from here."""
    if prefix not in PREFIXES:
        raise ValueError(_registry_hint(prefix))
    if number < 1:
        raise ValueError(f"identifier numbers start at 1, got {number}")
    return f"{prefix}-{number:0{NUMBER_WIDTH}d}"


def _article(word: str) -> str:
    """`a` or `an`, so an error message about an Assessment does not read "a Assessment"."""
    return "an" if word[:1].upper() in "AEIOU" else "a"


def _validator(prefix: str) -> AfterValidator:
    """Build the field validator for one prefix's annotated type."""
    expected = PREFIXES[prefix]

    def check(value: str) -> str:
        parsed = parse_id(value)
        if parsed.prefix != prefix:
            raise ValueError(
                f"expected {_article(expected)} {expected} identifier ('{prefix}-...'), "
                f"got {value!r}, which names "
                f"{_article(parsed.object_type)} {parsed.object_type}"
            )
        return value

    return AfterValidator(check)


# One annotated type per prefix, so a field is `AssessmentId` rather than `str` and a threat
# identifier cannot be assigned to a finding's field without the schema noticing. Written out
# rather than generated in a loop: twenty-five explicit names type-check, and a dict comprehension
# producing them would be invisible to mypy and to anyone reading for the type they want.
AssessmentId = Annotated[str, _validator("asm")]
SourceDocumentId = Annotated[str, _validator("src")]
EvidenceReferenceId = Annotated[str, _validator("evd")]
ComponentId = Annotated[str, _validator("cmp")]
AssetId = Annotated[str, _validator("ast")]
DataFlowId = Annotated[str, _validator("df")]
TrustBoundaryId = Annotated[str, _validator("tb")]
ContextClaimId = Annotated[str, _validator("ctx")]
ThreatId = Annotated[str, _validator("thr")]
RequirementId = Annotated[str, _validator("req")]
ControlId = Annotated[str, _validator("ctl")]
ControlMappingId = Annotated[str, _validator("map")]
FindingId = Annotated[str, _validator("fnd")]
QuestionId = Annotated[str, _validator("qst")]
DocumentationGapId = Annotated[str, _validator("gap")]
SourceObservationId = Annotated[str, _validator("obs")]
ActorId = Annotated[str, _validator("act")]
EvidenceAssessmentId = Annotated[str, _validator("eas")]
CritiqueId = Annotated[str, _validator("crq")]
ReviewerDecisionId = Annotated[str, _validator("dec")]
WorkflowRunId = Annotated[str, _validator("run")]
ExecutionRecordId = Annotated[str, _validator("exe")]
EvaluationResultId = Annotated[str, _validator("eval")]
FindingMergeRecordId = Annotated[str, _validator("mrg")]
CatalogGapCandidateId = Annotated[str, _validator("cgc")]
ReviewSessionId = Annotated[str, _validator("rvs")]


class IdentifierAllocator(Protocol):
    """Mints generated identifiers for one assessment.

    DEC-018 puts allocation in the persistence layer, from a monotonic counter per
    `(assessment_id, prefix)`, assigned at insert. The protocol is what domain and service code
    depends on; the store-backed implementation lives behind it.
    """

    def allocate(self, prefix: str) -> str:
        """The next identifier for `prefix`. Monotonic: a number is never handed out twice."""
        ...


class InMemoryAllocator:
    """An allocator holding its counters in the process, for tests and for code without a store.

    **It is not the mechanism DEC-018 specifies, and it is not a substitute for it.** Counters
    live in this object, so a fresh instance restarts at 001 and two instances hand out the same
    numbers. That is correct for a unit test and wrong for an assessment, where the numbering has
    to survive the process that produced it -- a resumed workflow (DEC-017 pauses by persisting
    the run and exiting) would otherwise re-mint identifiers that already exist.

    `test_identifiers.py` asserts the restart rather than hiding it, because a reader who does not
    know it will reach for this class the moment a store is inconvenient.
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def allocate(self, prefix: str) -> str:
        if prefix not in PREFIXES:
            raise ValueError(_registry_hint(prefix))
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return format_id(prefix, self._counters[prefix])

    def issued(self, prefix: str) -> int:
        """How many identifiers this allocator has handed out for `prefix`."""
        return self._counters.get(prefix, 0)
