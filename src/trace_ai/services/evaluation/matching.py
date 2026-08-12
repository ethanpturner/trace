"""The DEC-056 structural matcher, exposed per item, and the DEC-066 fingerprint.

The metrics module needs rates; the DEC-073 run diff needs the sets behind them — which expected
item matched, which produced finding matched nothing, and what identity each match carried. This
module is the one implementation both read, so the diff can never disagree with the rate it
explains.

Matching is structural through the contract's fields: an expected finding matches a produced one
on `requirement_id` plus a normalized affected-component name, and a consolidated finding scores
full credit per matched expectation (DEC-056). Titles and wording are never compared.

The fingerprint is DEC-066's cross-run identity: the DEC-019 hash over the finding's sorted
requirement identifiers and its affected components' normalized *names* — names rather than
identifiers, because identifiers are allocated per run and the fingerprint exists to say two runs
produced the same finding. It is derived from the identity fields and persisted on the object as
`content_fingerprint` (`services/findings/fingerprints.py` is the persistence-side caller); it
never replaces the allocated identifier. This module stays the one implementation, so the stored
value and the evaluation matcher cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from trace_ai.domain.hashing import content_hash

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import Any

    from trace_ai.domain.documentation_gap import DocumentationGap
    from trace_ai.domain.finding import Finding

__all__ = [
    "ContextMatchOutcome",
    "CoverageOutcome",
    "FindingMatchOutcome",
    "GapMatchOutcome",
    "finding_fingerprint",
    "gap_fingerprint",
    "match_context",
    "match_expected_mappings",
    "match_findings",
    "match_gaps",
    "match_questions",
    "match_threats",
    "normalized_name",
]


def normalized_name(name: str) -> str:
    """DEC-056's comparison form: whitespace collapsed, case folded. Never written back."""
    return " ".join(name.split()).casefold()


def finding_fingerprint(finding: Finding, component_names: Mapping[str, str]) -> str:
    """DEC-066: `sha256:` over sorted requirement ids and sorted normalized component names.

    `component_names` maps component identifiers to their already-normalized names, the same
    mapping the matcher uses. An identifier with no name contributes its identifier, which keeps
    the fingerprint total rather than silently narrowing it.
    """
    requirements = sorted(finding.requirement_ids)
    components = sorted(
        component_names.get(component_id, component_id)
        for component_id in finding.affected_component_ids
    )
    material = "\n".join(["finding", *requirements, *components])
    return content_hash(material.encode("utf-8"))


def gap_fingerprint(
    gap: DocumentationGap,
    *,
    requirement_by_mapping: Mapping[str, str],
    component_names_by_mapping: Mapping[str, Sequence[str]],
) -> str:
    """DEC-066 for a gap: the requirements its related mappings reach, plus their component names.

    A gap carries no requirement or component fields of its own, so identity is resolved the way
    `match_gaps` already resolves it — through the related mapping (DEC-056's path). A mapping
    carries no components directly either; `component_names_by_mapping` maps each mapping
    identifier to the already-normalized component names of the threat it evaluates, which is the
    resolution DEC-066 left to the implementing change. Related identifiers that are not mappings
    (threats, components, assets — a converted gap carries all of them) contribute nothing here,
    because the mapping is what ties a requirement to the ground it was evaluated against.
    """
    requirements = sorted(
        {
            requirement_by_mapping[related]
            for related in gap.related_object_ids
            if related in requirement_by_mapping
        }
    )
    components = sorted(
        {
            name
            for related in gap.related_object_ids
            for name in component_names_by_mapping.get(related, ())
        }
    )
    material = "\n".join(["gap", *requirements, *components])
    return content_hash(material.encode("utf-8"))


@dataclass(slots=True)
class FindingMatchOutcome:
    """Every expected finding and every produced finding, classified.

    `matched` maps each expected key to the produced finding identifiers that satisfy it;
    `missed` is every expected key nothing satisfied; `spurious` is every produced finding that
    satisfied no expectation. `fingerprints` carries DEC-066 identity for each produced finding
    that matched, keyed by expected key, so a later run can say *which* finding answered an
    expectation and not merely that one did.
    """

    matched: dict[str, list[str]] = field(default_factory=dict)
    missed: list[str] = field(default_factory=list)
    spurious: list[str] = field(default_factory=list)
    fingerprints: dict[str, list[str]] = field(default_factory=dict)
    expected_count: int = 0

    @property
    def consolidated_count(self) -> int:
        """Findings matching more than one expectation — full credit per match (DEC-056)."""
        by_finding: dict[str, int] = {}
        for finding_ids in self.matched.values():
            for finding_id in finding_ids:
                by_finding[finding_id] = by_finding.get(finding_id, 0) + 1
        return sum(1 for count in by_finding.values() if count > 1)


def match_findings(
    approved: Sequence[Finding],
    expected_findings: Sequence[Mapping[str, Any]],
    *,
    component_names: Mapping[str, str],
) -> FindingMatchOutcome:
    """Classify every expected entry and every approved finding under DEC-056's rule."""
    outcome = FindingMatchOutcome(expected_count=len(expected_findings))
    matched_finding_ids: set[str] = set()

    for entry in expected_findings:
        key = str(entry["key"])
        wanted_requirement = str(entry["requirement_id"])
        wanted_component = normalized_name(str(entry["affected_component"]))
        matched = [
            finding
            for finding in approved
            if wanted_requirement in finding.requirement_ids
            and any(
                component_names.get(component_id) == wanted_component
                for component_id in finding.affected_component_ids
            )
        ]
        if matched:
            outcome.matched[key] = [finding.id for finding in matched]
            outcome.fingerprints[key] = [
                finding_fingerprint(finding, component_names) for finding in matched
            ]
            matched_finding_ids.update(finding.id for finding in matched)
        else:
            outcome.missed.append(key)

    outcome.spurious = [finding.id for finding in approved if finding.id not in matched_finding_ids]
    return outcome


@dataclass(slots=True)
class GapMatchOutcome:
    """Produced documentation gaps, classified against the expected requirement set."""

    matching: list[str] = field(default_factory=list)
    non_matching: list[str] = field(default_factory=list)
    produced_count: int = 0


def match_gaps(
    produced_gaps: Sequence[DocumentationGap],
    expected_gap_requirements: set[str],
    *,
    requirement_by_mapping: Mapping[str, str],
) -> GapMatchOutcome:
    """A gap matches through the requirement its related mapping resolves to (DEC-056)."""
    outcome = GapMatchOutcome(produced_count=len(produced_gaps))
    for gap in produced_gaps:
        requirements = {
            requirement_by_mapping[related]
            for related in gap.related_object_ids
            if related in requirement_by_mapping
        }
        if requirements & expected_gap_requirements:
            outcome.matching.append(gap.id)
        else:
            outcome.non_matching.append(gap.id)
    return outcome


# ------------------------------------------------------------------------------------------
# The reserved truth-set metrics' matchers (#329): context, threats, mappings, questions.
# Structural throughout, like the finding matcher: names and identifiers, never wording.
# ------------------------------------------------------------------------------------------


@dataclass(slots=True)
class CoverageOutcome:
    """Expected entries classified as matched or missed, by their authored keys."""

    matched_keys: list[str] = field(default_factory=list)
    missed_keys: list[str] = field(default_factory=list)

    @property
    def expected_count(self) -> int:
        return len(self.matched_keys) + len(self.missed_keys)

    @property
    def matched_count(self) -> int:
        return len(self.matched_keys)


@dataclass(slots=True)
class ContextMatchOutcome:
    """Expected context entries matched per object type, pooled for the accuracy rate."""

    matched_by_type: dict[str, int] = field(default_factory=dict)
    expected_by_type: dict[str, int] = field(default_factory=dict)

    @property
    def matched_count(self) -> int:
        return sum(self.matched_by_type.values())

    @property
    def expected_count(self) -> int:
        return sum(self.expected_by_type.values())


_CONTEXT_NAME_TYPES: tuple[str, ...] = ("components", "actors", "assets", "trust_boundaries")


def match_context(
    expected_document: Mapping[str, Any],
    *,
    produced_names: Mapping[str, set[str]],
    produced_flows: set[tuple[str, str]],
    produced_claims: set[tuple[str, str]],
) -> ContextMatchOutcome:
    """Expected context entries matched by the truth file's own keys (its `matching` block).

    Components, actors, assets, and trust boundaries match on normalized name; data flows on
    normalized (source, destination) component names; context claims on (normalized subject,
    predicate), where a system-level claim's subject is the literal `system`. Values and
    descriptions are never compared — this measures whether the object was extracted, not
    whether every field agrees, which is the reviewer's judgment at checkpoint 1.
    """
    outcome = ContextMatchOutcome()
    for type_name in _CONTEXT_NAME_TYPES:
        entries = list(expected_document.get(type_name) or [])
        names = produced_names.get(type_name, set())
        outcome.expected_by_type[type_name] = len(entries)
        outcome.matched_by_type[type_name] = sum(
            1 for entry in entries if normalized_name(str(entry["name"])) in names
        )

    flows = list(expected_document.get("data_flows") or [])
    outcome.expected_by_type["data_flows"] = len(flows)
    outcome.matched_by_type["data_flows"] = sum(
        1
        for entry in flows
        if (
            normalized_name(str(entry["source_component"])),
            normalized_name(str(entry["destination_component"])),
        )
        in produced_flows
    )

    claims = list(expected_document.get("context_claims") or [])
    outcome.expected_by_type["context_claims"] = len(claims)
    outcome.matched_by_type["context_claims"] = sum(
        1
        for entry in claims
        if (normalized_name(str(entry["subject"])), str(entry["predicate"])) in produced_claims
    )
    return outcome


def match_threats(
    expected_threats: Sequence[Mapping[str, Any]],
    *,
    produced_references: Sequence[tuple[set[str], set[str]]],
) -> CoverageOutcome:
    """An expected threat matches a produced one that references everything it must.

    `must_reference` names the components and assets a threat has to be grounded in; a produced
    threat matches when its affected components and assets (normalized names) are supersets of
    both lists. Titles, categories, and wording are never compared (DEC-043 defers semantic
    comparison; this is the structural floor beneath it).
    """
    outcome = CoverageOutcome()
    for entry in expected_threats:
        must = entry.get("must_reference") or {}
        wanted_components = {normalized_name(str(name)) for name in must.get("components") or []}
        wanted_assets = {normalized_name(str(name)) for name in must.get("assets") or []}
        matched = any(
            wanted_components <= components and wanted_assets <= assets
            for components, assets in produced_references
        )
        (outcome.matched_keys if matched else outcome.missed_keys).append(str(entry["key"]))
    return outcome


def match_expected_mappings(
    expected_entries: Sequence[tuple[str, str, str]],
    *,
    produced: set[tuple[str, str]],
) -> CoverageOutcome:
    """An expected (requirement, satisfaction) pair matches a produced mapping stating both.

    Entries are (key, requirement_id, expected_satisfaction); the produced set holds
    (requirement_id, satisfaction_status). Threat identity is deliberately not bound: the
    expected file keys entries by threat, but binding them would make this metric depend on the
    threat matcher's outcome, and a mapping drawn under a differently-framed threat is still
    the same conclusion about the same requirement.
    """
    outcome = CoverageOutcome()
    for key, requirement_id, expected_satisfaction in expected_entries:
        matched = (requirement_id, expected_satisfaction) in produced
        (outcome.matched_keys if matched else outcome.missed_keys).append(key)
    return outcome


def match_questions(
    expected_questions: Sequence[Mapping[str, Any]],
    *,
    paired_keys: set[str],
    produced_requirement_sets: Sequence[set[str]],
) -> CoverageOutcome:
    """An expected question matches a produced question bearing on its requirement.

    A produced question bears on the requirements of its related threat's mappings, plus any
    requirement identifier its own text names. Expected questions named as a documentation
    gap's `paired_question` are excluded from the denominator: a paired question documents how
    its gap converts once answered, and DEC-013 routes one mapping to a gap *or* a question —
    producing both from the same silence is structurally impossible, so counting the pair twice
    would penalise the gap route the truth set itself expects.
    """
    outcome = CoverageOutcome()
    for entry in expected_questions:
        key = str(entry["key"])
        if key in paired_keys:
            continue
        wanted = str(entry.get("requirement_id", ""))
        matched = bool(wanted) and any(
            wanted in requirements for requirements in produced_requirement_sets
        )
        (outcome.matched_keys if matched else outcome.missed_keys).append(key)
    return outcome
