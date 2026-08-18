"""The diff between two assessments' approved models (DEC-097, #488).

Each side is read through its own scoped handle — two scoped reads, never a cross-assessment
query, which keeps the store's scoping rule intact. Both sides must have an approved context,
the same refusal every export makes (DEC-072): a diff over candidates would report changes no
reviewer saw.

**Matching is conservative and delegated.** Context objects match by the DEC-093 fingerprints
`matching.py` computes; findings match by their persisted DEC-066 content fingerprint; open
questions match by normalized text (the stability protocol's convention). A fingerprint that
occurs more than once on either side is ambiguous and its objects report as added and removed
rather than paired. Threats and documentation gaps are deliberately not paired in v1: a threat's
identity is its wording plus its ground, both model-authored and both expected to vary across
runs, and a guessed pairing would report an edit nobody made — they diff as counts and
added/removed lists by ground, stated as such.

**Changed means the content fields moved.** Two matched objects compare on their model dump
minus the volatile fields — identifiers (allocated per assessment), timestamps, provenance, and
cross-references that carry per-assessment identifiers. What remains is what a reviewer would
call the object's content, and the diff names the fields that differ rather than only saying
"changed".

**A rename is declared as a candidate, never applied** (#529, DEC-097 amendment). A renamed
component reads as removed-plus-added because the name is part of the fingerprint. When exactly
one removed and one added object in a named family agree on every content field except the
name, the pair is reported as a `RenameCandidate` beside — not instead of — its removed and
added entries: the Context Validation ethos, report and never correct. Any ambiguity (two
plausible partners on either side, or any other field moved) declares nothing.

**A finding↔gap shift is the signature distinction, diffed** (#529). A DocumentationGap says a
control's existence could not be determined; a Finding says evidence supports a weakness. When
the before side holds one and the after side holds the other over the same requirements and the
same ground — keyed the DEC-066 way, requirements plus normalized component names, the gap's
resolved through its related mappings — the diff reports a `ResolutionShift` in the direction
it moved. Conservative like everything here: the key must be unique on both sides and genuinely
absent from its own kind on the other side, or nothing is claimed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.question import Question, QuestionStatus
from trace_ai.domain.threat import Threat
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.services.evaluation.matching import live_context_fingerprint, normalized_name
from trace_ai.services.export.tm_bom import ExportError
from trace_ai.services.findings.approved import approved_findings
from trace_ai.workflow.context_review import current_system_context

if TYPE_CHECKING:
    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.finding import Finding
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "AssessmentDiff",
    "DiffEntry",
    "FamilyDiff",
    "RenameCandidate",
    "ResolutionShift",
    "diff_assessments",
]

# Fields that never make two objects different things: identifiers are allocated per assessment
# (DEC-018), timestamps and provenance describe the run rather than the object, and *_id fields
# reference identifiers the other assessment cannot share.
_VOLATILE_SUFFIXES = ("_id", "_ids", "_at", "_by")
_VOLATILE_FIELDS = frozenset(
    {"id", "assessment_id", "generated_by", "content_fingerprint", "status", "version"}
)

_CONTEXT_FAMILIES: tuple[tuple[str, type[DomainModel]], ...] = (
    ("components", Component),
    ("actors", Actor),
    ("assets", Asset),
    ("trust_boundaries", TrustBoundary),
    ("data_flows", DataFlow),
    ("claims", ContextClaim),
)


@dataclass(frozen=True, slots=True)
class DiffEntry:
    """One object's classification: its identity, both identifiers where matched, and what moved."""

    identity: str
    before_id: str | None = None
    after_id: str | None = None
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RenameCandidate:
    """One removed/added pair whose every content field but the name agrees (#529).

    A candidate, declared beside its removed and added entries and never applied: the diff
    reports what a rename would explain, and the reviewer decides whether it was one.
    """

    before_identity: str
    after_identity: str
    before_id: str | None = None
    after_id: str | None = None


@dataclass(frozen=True, slots=True)
class ResolutionShift:
    """A finding↔gap move over the same requirements and ground (#529).

    `direction` is `gap_to_finding` when the earlier assessment recorded an undeterminable
    control and the later one supports a weakness there, and `finding_to_gap` for the reverse.
    """

    direction: str
    requirement_ids: tuple[str, ...]
    ground: str
    before_id: str | None = None
    after_id: str | None = None


@dataclass(slots=True)
class FamilyDiff:
    """One object family's diff: matched-and-unchanged is a count, everything else is named."""

    unchanged: int = 0
    added: list[DiffEntry] = field(default_factory=list)
    removed: list[DiffEntry] = field(default_factory=list)
    changed: list[DiffEntry] = field(default_factory=list)
    rename_candidates: list[RenameCandidate] = field(default_factory=list)

    @property
    def moved(self) -> bool:
        return bool(self.added or self.removed or self.changed)


@dataclass(slots=True)
class AssessmentDiff:
    """The whole diff, keyed by family name in presentation order."""

    before: str
    after: str
    families: dict[str, FamilyDiff] = field(default_factory=dict)
    resolution_shifts: list[ResolutionShift] = field(default_factory=list)

    @property
    def moved(self) -> bool:
        return any(family.moved for family in self.families.values())


def _approved_context_objects(
    handle: AssessmentHandle, model: type[DomainModel]
) -> list[DomainModel]:
    """The approved context's members of one family, mirroring the export rule (DEC-072)."""
    return [
        obj
        for obj in handle.objects.list(model)
        if not isinstance(getattr(obj, "status", None), ObjectStatus)
        or obj.status is ObjectStatus.APPROVED  # type: ignore[attr-defined]
    ]


def _names_by_id(handle: AssessmentHandle) -> dict[str, str]:
    names: dict[str, str] = {}
    for model in (Component, Actor, Asset, TrustBoundary):
        for obj in handle.objects.list(model):
            names[obj.id] = normalized_name(obj.name)  # type: ignore[attr-defined]
    return names


def _content(obj: DomainModel) -> dict[str, Any]:
    dumped = obj.model_dump(mode="json")
    return {
        key: value
        for key, value in dumped.items()
        if key not in _VOLATILE_FIELDS and not key.endswith(_VOLATILE_SUFFIXES)
    }


def _unique(pairs: list[tuple[tuple[str, ...], DomainModel]]) -> dict[tuple[str, ...], DomainModel]:
    counts: dict[tuple[str, ...], int] = {}
    for fingerprint, _ in pairs:
        counts[fingerprint] = counts.get(fingerprint, 0) + 1
    return {fp: obj for fp, obj in pairs if counts[fp] == 1}


def _identity(fingerprint: tuple[str, ...]) -> str:
    return " / ".join(fingerprint[1:]) or fingerprint[0]


def _diff_family(
    before: list[tuple[tuple[str, ...], DomainModel]],
    after: list[tuple[tuple[str, ...], DomainModel]],
) -> FamilyDiff:
    """Classify one family: unique fingerprints pair, everything else is added or removed."""
    outcome = FamilyDiff()
    before_unique = _unique(before)
    after_unique = _unique(after)

    for fingerprint, obj in before:
        matched = after_unique.get(fingerprint) if fingerprint in before_unique else None
        if matched is None:
            outcome.removed.append(
                DiffEntry(identity=_identity(fingerprint), before_id=getattr(obj, "id", None))
            )
            continue
        changed = tuple(
            sorted(
                key
                for key in set(_content(obj)) | set(_content(matched))
                if _content(obj).get(key) != _content(matched).get(key)
            )
        )
        entry = DiffEntry(
            identity=_identity(fingerprint),
            before_id=getattr(obj, "id", None),
            after_id=getattr(matched, "id", None),
            changed_fields=changed,
        )
        if changed:
            outcome.changed.append(entry)
        else:
            outcome.unchanged += 1

    matched_fingerprints = {fp for fp in before_unique if fp in after_unique}
    for fingerprint, obj in after:
        if fingerprint in matched_fingerprints and fingerprint in after_unique:
            continue
        outcome.added.append(
            DiffEntry(identity=_identity(fingerprint), after_id=getattr(obj, "id", None))
        )
    return outcome


def _rename_candidates(
    family: FamilyDiff,
    before: list[tuple[tuple[str, ...], DomainModel]],
    after: list[tuple[tuple[str, ...], DomainModel]],
) -> list[RenameCandidate]:
    """Removed/added pairs a rename alone would explain: identical content, different name.

    The key is the object's content minus `name`, serialized canonically. Exactly one removed
    and one added object per key declares a candidate; any other count is ambiguity, and
    ambiguity declares nothing. Objects without a `name` field never participate.
    """
    import json

    removed_ids = {entry.before_id for entry in family.removed}
    added_ids = {entry.after_id for entry in family.added}

    def keyed(
        pairs: list[tuple[tuple[str, ...], DomainModel]], ids: set[str | None]
    ) -> dict[str, list[DomainModel]]:
        table: dict[str, list[DomainModel]] = {}
        for _, obj in pairs:
            if getattr(obj, "id", None) not in ids or not hasattr(obj, "name"):
                continue
            content = {k: v for k, v in _content(obj).items() if k != "name"}
            table.setdefault(json.dumps(content, sort_keys=True), []).append(obj)
        return table

    removed_by_key = keyed(before, removed_ids)
    added_by_key = keyed(after, added_ids)
    candidates = []
    for key, removed_objects in sorted(removed_by_key.items()):
        added_objects = added_by_key.get(key, [])
        if len(removed_objects) == 1 and len(added_objects) == 1:
            gone, came = removed_objects[0], added_objects[0]
            candidates.append(
                RenameCandidate(
                    before_identity=str(getattr(gone, "name", "")),
                    after_identity=str(getattr(came, "name", "")),
                    before_id=getattr(gone, "id", None),
                    after_id=getattr(came, "id", None),
                )
            )
    return candidates


def _finding_keys(
    handle: AssessmentHandle,
) -> list[tuple[tuple[tuple[str, ...], tuple[str, ...]], Finding]]:
    """Each approved finding under its DEC-066 identity: requirements and normalized ground."""
    names = _names_by_id(handle)
    keys = []
    for finding in approved_findings(handle):
        requirements = tuple(sorted(finding.requirement_ids))
        ground = tuple(sorted(names.get(cid, cid) for cid in finding.affected_component_ids))
        keys.append(((requirements, ground), finding))
    return keys


def _gap_keys(
    handle: AssessmentHandle,
) -> list[tuple[tuple[tuple[str, ...], tuple[str, ...]], DocumentationGap]]:
    """Each approved gap under the same identity, resolved through its related mappings —
    `gap_fingerprint`'s resolution, unhashed so it can meet a finding's key across kinds."""
    names = _names_by_id(handle)
    mappings = {mapping.id: mapping for mapping in handle.objects.list(ControlMapping)}
    threats = {threat.id: threat for threat in handle.objects.list(Threat)}
    keys = []
    for gap in handle.objects.list(DocumentationGap):
        if gap.status is not ObjectStatus.APPROVED:
            continue
        related = [mappings[r] for r in gap.related_object_ids if r in mappings]
        requirements = tuple(sorted({mapping.requirement_id for mapping in related}))
        ground = tuple(
            sorted(
                {
                    names.get(cid, cid)
                    for mapping in related
                    if mapping.threat_id in threats
                    for cid in threats[mapping.threat_id].affected_component_ids
                }
            )
        )
        if requirements:
            keys.append(((requirements, ground), gap))
    return keys


def _resolution_shifts(before: AssessmentHandle, after: AssessmentHandle) -> list[ResolutionShift]:
    """Finding↔gap moves over the same identity, both directions, uniqueness required.

    A shift is claimed only when the key is unique among its kind on its own side and its kind
    is genuinely absent from the other side — a gap that persists beside a new finding is two
    statements coexisting, not one resolving into the other.
    """

    def unique(pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
        counts: dict[Any, int] = {}
        for key, _ in pairs:
            counts[key] = counts.get(key, 0) + 1
        return {key: obj for key, obj in pairs if counts[key] == 1}

    before_gaps = unique(list(_gap_keys(before)))
    before_findings = unique(list(_finding_keys(before)))
    after_gaps = unique(list(_gap_keys(after)))
    after_findings = unique(list(_finding_keys(after)))

    shifts = []
    for key, gap in sorted(before_gaps.items()):
        finding = after_findings.get(key)
        if finding is not None and key not in after_gaps and key not in before_findings:
            requirements, ground = key
            shifts.append(
                ResolutionShift(
                    direction="gap_to_finding",
                    requirement_ids=requirements,
                    ground=", ".join(ground) or "-",
                    before_id=gap.id,
                    after_id=finding.id,
                )
            )
    for key, finding in sorted(before_findings.items()):
        gap = after_gaps.get(key)
        if gap is not None and key not in after_findings and key not in before_gaps:
            requirements, ground = key
            shifts.append(
                ResolutionShift(
                    direction="finding_to_gap",
                    requirement_ids=requirements,
                    ground=", ".join(ground) or "-",
                    before_id=finding.id,
                    after_id=gap.id,
                )
            )
    return shifts


def _context_pairs(
    handle: AssessmentHandle, model: type[DomainModel]
) -> list[tuple[tuple[str, ...], DomainModel]]:
    names = _names_by_id(handle)
    pairs: list[tuple[tuple[str, ...], DomainModel]] = []
    for obj in _approved_context_objects(handle, model):
        fingerprint = live_context_fingerprint(obj, names)
        if fingerprint is not None:
            pairs.append((fingerprint, obj))
    return pairs


def _finding_pairs(handle: AssessmentHandle) -> list[tuple[tuple[str, ...], DomainModel]]:
    pairs: list[tuple[tuple[str, ...], DomainModel]] = []
    for finding in approved_findings(handle):
        if finding.content_fingerprint is not None:
            pairs.append((("findings", finding.content_fingerprint), finding))
        else:
            # A finding without a stored fingerprint cannot be paired; it reports as
            # added/removed under its title rather than being matched by guesswork.
            pairs.append((("findings", "unfingerprinted", finding.id), finding))
    return pairs


def _question_pairs(handle: AssessmentHandle) -> list[tuple[tuple[str, ...], DomainModel]]:
    return [
        (("questions", normalized_name(question.question)), question)
        for question in handle.objects.list(Question)
        if question.status is QuestionStatus.OPEN
    ]


def _ground(handle: AssessmentHandle, obj: Threat | DocumentationGap) -> str:
    names = _names_by_id(handle)
    if isinstance(obj, Threat):
        grounded = sorted(
            names.get(identifier, identifier)
            for identifier in [*obj.affected_component_ids, *obj.affected_asset_ids]
        )
        return ", ".join(grounded) or obj.id
    return obj.title


def diff_assessments(before: AssessmentHandle, after: AssessmentHandle) -> AssessmentDiff:
    """Compare two assessments' approved models, conservatively.

    Both sides must hold an approved context (the DEC-072 refusal): a diff over candidates
    would report changes no reviewer saw.
    """
    for handle in (before, after):
        try:
            context = current_system_context(handle)
        except ValueError as missing:
            raise ExportError(
                f"{handle.assessment_id} has no extracted context to diff: {missing}"
            ) from None
        if not context.is_approved:
            raise ExportError(
                f"{handle.assessment_id} has no approved system context; a diff compares "
                f"approved models only (DEC-097)."
            )

    diff = AssessmentDiff(before=before.assessment_id, after=after.assessment_id)
    for family_name, model in _CONTEXT_FAMILIES:
        before_pairs = _context_pairs(before, model)
        after_pairs = _context_pairs(after, model)
        family = _diff_family(before_pairs, after_pairs)
        family.rename_candidates = _rename_candidates(family, before_pairs, after_pairs)
        diff.families[family_name] = family
    diff.families["findings"] = _diff_family(_finding_pairs(before), _finding_pairs(after))
    diff.families["open_questions"] = _diff_family(_question_pairs(before), _question_pairs(after))

    # Threats and gaps: counts and grounds only, never paired (module docstring). They reuse
    # the added/removed lists with the ground as identity, and "changed" stays empty by
    # construction.
    for family_name, model, statuses in (
        ("threats", Threat, (ObjectStatus.APPROVED,)),
        ("documentation_gaps", DocumentationGap, (ObjectStatus.APPROVED,)),
    ):
        family = FamilyDiff()
        before_grounds = [
            _ground(before, obj)  # type: ignore[arg-type]
            for obj in before.objects.list(model)
            if getattr(obj, "status", None) in statuses
        ]
        after_grounds = [
            _ground(after, obj)  # type: ignore[arg-type]
            for obj in after.objects.list(model)
            if getattr(obj, "status", None) in statuses
        ]
        remaining = list(after_grounds)
        for ground in before_grounds:
            if ground in remaining:
                remaining.remove(ground)
                family.unchanged += 1
            else:
                family.removed.append(DiffEntry(identity=ground))
        family.added.extend(DiffEntry(identity=ground) for ground in remaining)
        diff.families[family_name] = family

    diff.resolution_shifts = _resolution_shifts(before, after)
    return diff
