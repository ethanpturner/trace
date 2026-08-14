"""DEC-064's precedent feed: rationale-bearing dismissals, matched to a lineage deterministically.

The question the block puts to the critic is "this was dismissed for reason X — does X apply
here?", so everything selected must carry an X: a dismissal is a `ReviewerDecision` whose
disposition is `reject`, `convert_to_question`, or `convert_to_documentation_gap` **with a
recorded rationale**. A bare rejection supplies no X and is simply not precedent.

Matching is DEC-064's rule and no model call computes similarity — a hidden model call here is
the seventh agent the cap refuses. A dismissed finding matches the lineage under review when it
shares a `requirement_id` with the lineage's mappings, or names an affected component whose name
matches one of the lineage's under DEC-056's normalization (identifier resolved to name,
case-insensitive, whitespace normalized).

The cap and ordering are DEC-080's: at most ten precedents, requirement-sharing matches before
name-only matches, most recent dismissal first within each class, and the block names what the
cap excluded rather than truncating silently.

Scope is the assessment (DEC-064). Everything here reads objects already inside one
`AssessmentHandle`'s boundary; in a first run the assessment has no dismissed findings and the
selection is empty, which is the decided dormancy, not a defect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.enums import ReviewDisposition

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

    from trace_ai.domain.finding import Finding
    from trace_ai.domain.reviewer_decision import ReviewerDecision
    from trace_ai.services.critique.input_package import SelectedObjects

__all__ = [
    "DISMISSAL_DISPOSITIONS",
    "PRECEDENT_CAP",
    "DismissalPrecedent",
    "PrecedentSelection",
    "select_precedents",
]

DISMISSAL_DISPOSITIONS: Final = frozenset(
    {
        ReviewDisposition.REJECT,
        ReviewDisposition.CONVERT_TO_QUESTION,
        ReviewDisposition.CONVERT_TO_DOCUMENTATION_GAP,
    }
)

PRECEDENT_CAP: Final = 10
"""DEC-080. A constant, not configuration: a knob nobody has evidence to turn (DEC-012)."""


@dataclass(frozen=True, slots=True)
class DismissalPrecedent:
    """One dismissed finding with the reviewer's reason, matched to the lineage under review.

    `shared_requirement_ids` and `matched_component_names` record *why* this precedent is in
    front of the critic, so the block can say what matched instead of asserting relevance.
    """

    finding_id: str
    finding_title: str
    decision_id: str
    disposition: str
    rationale: str
    decided_at: datetime
    shared_requirement_ids: tuple[str, ...]
    matched_component_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrecedentSelection:
    """What DEC-064's rule selected for one review group, under DEC-080's cap.

    `excluded_finding_ids` is every matching precedent the cap displaced — named, never silently
    dropped, the same rule the evidence fence follows on a budget overrun.
    """

    precedents: tuple[DismissalPrecedent, ...] = ()
    excluded_finding_ids: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.precedents or self.excluded_finding_ids)


def _latest_dismissal(
    decisions: Sequence[ReviewerDecision], finding_id: str
) -> ReviewerDecision | None:
    """The most recent rationale-bearing dismissal of this finding, if any.

    A finding dismissed twice — rejected in one run, converted in a revision — is one precedent,
    and the latest reason is the reviewer's standing one.
    """
    dismissals = [
        decision
        for decision in decisions
        if decision.subject_id == finding_id
        and decision.disposition in DISMISSAL_DISPOSITIONS
        and decision.rationale is not None
        and decision.rationale.strip()
    ]
    if not dismissals:
        return None
    return max(dismissals, key=lambda decision: (decision.created_at, decision.id))


def select_precedents(
    *,
    selected: SelectedObjects,
    findings: Sequence[Finding],
    decisions: Sequence[ReviewerDecision],
    component_names: Mapping[str, str],
) -> PrecedentSelection:
    """DEC-064's deterministic match, as a function so a test can assert what it excludes.

    `component_names` maps component identifiers to already-normalized names — the same index the
    DEC-066 fingerprints read, so "the same component" means the same thing in both places. An
    identifier with no name contributes its identifier, which keeps the match total rather than
    silently narrowing it.
    """
    lineage_requirements = {mapping.requirement_id for mapping in selected.mappings}
    lineage_names = {
        component_names.get(component_id, component_id)
        for component_id in selected.threat.affected_component_ids
    }

    matches: list[DismissalPrecedent] = []
    for finding in findings:
        dismissal = _latest_dismissal(decisions, finding.id)
        if dismissal is None or not dismissal.rationale:
            continue

        shared_requirements = sorted(set(finding.requirement_ids) & lineage_requirements)
        matched_names = sorted(
            {
                component_names.get(component_id, component_id)
                for component_id in finding.affected_component_ids
            }
            & lineage_names
        )
        if not shared_requirements and not matched_names:
            continue

        matches.append(
            DismissalPrecedent(
                finding_id=finding.id,
                finding_title=finding.title,
                decision_id=dismissal.id,
                disposition=dismissal.disposition.value,
                rationale=dismissal.rationale,
                decided_at=dismissal.created_at,
                shared_requirement_ids=tuple(shared_requirements),
                matched_component_names=tuple(matched_names),
            )
        )

    # DEC-080: requirement-sharing before name-only, most recent dismissal first within each
    # class. Two stable sorts: recency (identifier tiebreak), then tightness on top.
    matches.sort(key=lambda precedent: (precedent.decided_at, precedent.decision_id), reverse=True)
    matches.sort(key=lambda precedent: 0 if precedent.shared_requirement_ids else 1)

    return PrecedentSelection(
        precedents=tuple(matches[:PRECEDENT_CAP]),
        excluded_finding_ids=tuple(precedent.finding_id for precedent in matches[PRECEDENT_CAP:]),
    )
