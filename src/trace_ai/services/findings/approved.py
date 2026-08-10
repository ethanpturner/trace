"""The approved set, from one accessor — and the retained candidates beside it (DEC-055).

`agent-design.md` section 18's workflow rule is that only approved findings may appear in the
final findings section, and the rule only holds if every consumer agrees about what "approved"
means. This module is that agreement: report generation, rendering, and evaluation read
`approved_findings`, and a source-scan test holds every other module to it — no consumer
assembles its own idea of the approved set, because two assemblies is how one report and one
metric quietly disagree.

**Rejected, deferred, and superseded candidates are retained, with their reasons.** They are
preserved for evaluation without being displayed as results (`design-principles.md` section 9),
and `retained_candidates` is the query surface: the reviewer's rationale where a decision
exists, the rejecting critique's description where consolidation applied one (the persisted
linkage DEC-053 deferred to this issue). A candidate that disappeared with no reason anybody can
retrieve is the failure `design-principles.md` section 16 names.

**An empty approved set is a valid terminal state.** The accessor returns it without comment; a
successful assessment may approve nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from trace_ai.domain.critique import Critique, RecommendedAction
from trace_ai.domain.enums import ObjectStatus, ReviewDisposition
from trace_ai.domain.finding import Finding
from trace_ai.domain.reviewer_decision import ReviewerDecision

if TYPE_CHECKING:
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "ApprovalIntegrityError",
    "RetainedCandidate",
    "approved_findings",
    "retained_candidates",
]


class ApprovalIntegrityError(RuntimeError):
    """An approved finding with no `ReviewerDecision` behind it: a state nothing may consume."""


def approved_findings(handle: AssessmentHandle) -> list[Finding]:
    """The approved set: what the report's findings section and the metrics draw from.

    Canonical findings only — a duplicate whose survivor was approved is the survivor's content
    already, and returning both would report one conclusion twice. This is the only module that
    queries findings by approved status; `tests/unit/test_finding_gate.py` scans the source tree
    to keep it that way.

    **An approved finding without a `ReviewerDecision` is refused, not returned.** Approval is a
    human act (DEC-005); a row that claims it happened with no record of who did it is a state
    the gate cannot have produced, and every consumer of this accessor would otherwise present
    it as reviewed. Refusing here is what makes "a finding lacking a linked decision cannot
    become official" hold against writers that bypassed the gate.
    """
    decided = {decision.subject_id for decision in handle.objects.list(ReviewerDecision)}
    approved = [
        finding
        for finding in handle.objects.list(Finding, status=ObjectStatus.APPROVED.value)
        if finding.duplicate_of_id is None
    ]
    undecided = [finding.id for finding in approved if finding.id not in decided]
    if undecided:
        raise ApprovalIntegrityError(
            f"{undecided} are marked approved with no ReviewerDecision. Approval is a recorded "
            f"human act (DEC-005); an approved finding nobody decided cannot be consumed as one."
        )
    return approved


@dataclass(frozen=True, slots=True)
class RetainedCandidate:
    """A candidate that did not become an approved finding, and why.

    `disposition` names what happened — rejected, deferred, superseded, merged — and `reason`
    is the stated cause: the reviewer's rationale, or the critique consolidation applied, or the
    survivor a merge kept. "No recorded reason" is stated as itself rather than hidden, because
    a silent gap in the record is the thing this surface exists to make visible.
    """

    finding: Finding
    disposition: str
    reason: str


def _latest_decision(decisions: list[ReviewerDecision], finding_id: str) -> ReviewerDecision | None:
    about = [decision for decision in decisions if decision.subject_id == finding_id]
    return about[-1] if about else None


def retained_candidates(handle: AssessmentHandle) -> list[RetainedCandidate]:
    """Everything that was a candidate and is not approved, with its stated reason.

    Excluded from the approved set by construction, and queryable for evaluation: rejected and
    superseded findings, candidates a reviewer deferred, and duplicates merged into a survivor.
    """
    decisions = handle.objects.list(ReviewerDecision)
    critiques = handle.objects.list(Critique)
    retained: list[RetainedCandidate] = []

    for finding in handle.objects.list(Finding):
        if finding.status is ObjectStatus.APPROVED and finding.duplicate_of_id is None:
            continue

        decision = _latest_decision(decisions, finding.id)
        if finding.duplicate_of_id is not None:
            disposition, reason = (
                "merged",
                f"merged into {finding.duplicate_of_id}; the merge record names what matched",
            )
        elif finding.status is ObjectStatus.REJECTED:
            rejecting = next(
                (
                    critique
                    for critique in critiques
                    if critique.subject_id == finding.id
                    and critique.recommended_action is RecommendedAction.REJECT
                ),
                None,
            )
            if decision is not None and decision.rationale:
                reason = decision.rationale
            elif rejecting is not None:
                reason = f"{rejecting.id}: {rejecting.description}"
            else:
                reason = "no recorded reason; the rejection predates the retention rule"
            disposition = "rejected"
        elif finding.status is ObjectStatus.SUPERSEDED:
            disposition = "superseded"
            reason = (
                f"converted; the successor carries converted_from_id {finding.id}"
                if decision is None or not decision.rationale
                else decision.rationale
            )
        elif decision is not None and decision.disposition is ReviewDisposition.DEFER:
            disposition = "deferred"
            reason = decision.rationale or "deferred without a stated reason"
        else:
            continue

        retained.append(RetainedCandidate(finding=finding, disposition=disposition, reason=reason))

    return retained
