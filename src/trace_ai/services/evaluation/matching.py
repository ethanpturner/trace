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
    "FindingMatchOutcome",
    "GapMatchOutcome",
    "finding_fingerprint",
    "gap_fingerprint",
    "match_findings",
    "match_gaps",
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
