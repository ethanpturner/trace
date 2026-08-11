"""Applying critique recommendations during consolidation, with lineage preserved (DEC-053).

The Critical Review agent returns `Critique` objects and `agent-design.md` section 16 makes
"apply critique recommendations" a Finding Consolidation responsibility. The critique validation
node has already split the recommendations by direction: `revise` and `investigate` against a
threat, control, mapping, or evidence assessment re-enter a passed phase and are the
orchestrator's budget-gated concern; everything else routes forward, and this module is the
forward half.

**The critic proposes; this module decides, and it decides from rules.** Per action: `keep`
records and changes nothing; `reject` moves the candidate to `rejected`, out of the provisional
set and never out of existence; `revise` appends the critique's description to `limitations`
under the critique's identifier and unions the critique's cited evidence — the critic's own
validated words, added, with nothing the earlier pipeline asserted rewritten; `merge` is the
DEC-052 operation's and is deferred to it; `investigate` is the reviewer's and is deferred to
checkpoint 2. Every change records the critique that caused it, and the pre-revision state is
preserved on the application record — DEC-023's `prior_value` pattern applied to a node.

**A `documentation_gap_only` critique outranks its own recommended action** (DEC-053). The type
asserts the candidate should not exist as a finding, so it routes through DEC-051's
`finding_to_documentation_gap` — minimum criteria, severity rules, and `converted_from_id` all
apply — and never through an edit that softens a description while still asserting a weakness.
The precedent is the contradiction rule in `finding_consolidation.py`: a structural signal
outranks an advisory one.

**No path here approves anything.** Approval is checkpoint 2's (DEC-005). This module writes
`rejected`, `superseded`, and revised candidates; a critique that resolves to nothing, or to a
candidate already rejected or converted, is reported as unapplied with the reason rather than
silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.base import now
from trace_ai.domain.conversions import finding_to_documentation_gap
from trace_ai.domain.critique import Critique, CritiqueSubjectType, CritiqueType, RecommendedAction
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus, Severity
from trace_ai.domain.evidence_assessment import EvidenceAssessment, SubjectType
from trace_ai.domain.finding import Finding

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "AppliedCritique",
    "CritiqueApplicationOutcome",
    "DeferredCritique",
    "RejectedOnCritique",
    "RevisionRecord",
    "UnappliedCritique",
    "apply_critiques",
    "persist_application",
]

# What `generated_by` records on objects this step creates (the converted gaps). Its own version
# for the same reason the dedup step has one: this operation can change without the routing
# changing.
GENERATED_BY: Final = "critique-application-v1"


@dataclass(frozen=True, slots=True)
class AppliedCritique:
    """One critique-driven change: which critique, which candidate, what happened."""

    critique_id: str
    target_id: str
    action: RecommendedAction
    change: str


@dataclass(frozen=True, slots=True)
class RejectedOnCritique:
    """A candidate rejected on a critique recommendation, retained with its stated reason.

    The object is kept — `agent-design.md` section 18 keeps rejected candidates available and
    `design-principles.md` section 16 requires a reviewer be able to learn why a finding
    disappeared. The persisted linkage for rejections is #103's; until then the reason lives
    here, on the outcome the caller holds.
    """

    finding: Finding
    critique_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class RevisionRecord:
    """A revision with its pre-revision state, so the difference stays visible.

    DEC-023 records reviewer edits as `prior_value` on the decision; this is the same pattern for
    a node's edit. Both objects are retrievable from the record whatever else happens to them.
    """

    critique_id: str
    before: Finding
    after: Finding


@dataclass(frozen=True, slots=True)
class DeferredCritique:
    """A recommendation this step deliberately does not act on, and whose it is instead."""

    critique_id: str
    action: RecommendedAction
    reason: str


@dataclass(frozen=True, slots=True)
class UnappliedCritique:
    """A critique that resolved to nothing actionable, reported rather than dropped."""

    critique_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class CritiqueApplicationOutcome:
    """The provisional set after application, and the records that explain every difference.

    `findings` is the provisional finding set: revised candidates in place, rejected and
    converted ones absent. Nothing is deleted — the rejected survive on `rejected`, conversion
    sources on `superseded`, and the converted gaps join `documentation_gaps`.
    """

    findings: tuple[Finding, ...] = ()
    documentation_gaps: tuple[DocumentationGap, ...] = ()
    converted: tuple[DocumentationGap, ...] = ()
    """The gaps this pass created by reclassification — the subset of `documentation_gaps` whose
    identifiers are provisional until `persist_application` re-mints them (DEC-018). Pre-existing
    gaps keep the identifiers they arrived with."""

    rejected: tuple[RejectedOnCritique, ...] = ()
    revisions: tuple[RevisionRecord, ...] = ()
    superseded: tuple[Finding, ...] = ()
    applied: tuple[AppliedCritique, ...] = ()
    deferred: tuple[DeferredCritique, ...] = ()
    unapplied: tuple[UnappliedCritique, ...] = ()


def _resolve_targets(
    critique: Critique,
    findings: Sequence[Finding],
    assessments: Sequence[EvidenceAssessment],
) -> list[Finding] | str:
    """The candidate findings a critique bears on, or the reason none does.

    Resolution reads identifiers: a finding critique names its target outright, and a critique
    of a threat, mapping, or evidence assessment reaches the candidates built from it. A control
    critique reaches no finding — `Finding` carries no control identifiers — and says so.
    """
    if critique.subject_type is CritiqueSubjectType.FINDING:
        matched = [finding for finding in findings if finding.id == critique.subject_id]
        return matched or f"{critique.subject_id} is not a candidate finding in this set"

    if critique.subject_type is CritiqueSubjectType.THREAT:
        matched = [f for f in findings if critique.subject_id in f.threat_ids]
        return matched or f"no candidate finding cites threat {critique.subject_id}"

    if critique.subject_type is CritiqueSubjectType.CONTROL_MAPPING:
        matched = [f for f in findings if critique.subject_id in f.control_mapping_ids]
        return matched or f"no candidate finding cites mapping {critique.subject_id}"

    if critique.subject_type is CritiqueSubjectType.EVIDENCE_ASSESSMENT:
        mapping_ids = {
            assessed.subject_id
            for assessed in assessments
            if assessed.id == critique.subject_id
            and assessed.subject_type is SubjectType.CONTROL_MAPPING
        }
        matched = [f for f in findings if mapping_ids.intersection(f.control_mapping_ids)]
        return matched or (
            f"no candidate finding is built on a mapping {critique.subject_id} assessed"
        )

    return (
        f"a {critique.subject_type.value} critique names no candidate finding; findings carry "
        f"no {critique.subject_type.value} identifiers"
    )


def _union(first: list[str], extra: list[str]) -> list[str]:
    return [*first, *sorted(set(extra) - set(first))]


def apply_critiques(
    critiques: Sequence[Critique],
    *,
    findings: Sequence[Finding],
    documentation_gaps: Sequence[DocumentationGap] = (),
    assessments: Sequence[EvidenceAssessment] = (),
    next_id: dict[str, int] | None = None,
) -> CritiqueApplicationOutcome:
    """Apply every forward recommendation, in critique order, and account for every critique.

    With no critiques the output is the input: same findings, same gaps, no records. Critiques
    are processed in the order given — the persisted order, which is stable — so two runs over
    identical input produce identical results.

    `next_id` is the caller-supplied counter convention `consolidate` uses; converted gaps mint
    provisional identifiers from it, and `persist_application` re-mints from the store (DEC-018).
    """
    counters = next_id if next_id is not None else {}

    def mint(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}-{counters[prefix]:03d}"

    stamp = now()
    current: dict[str, Finding] = {finding.id: finding for finding in findings}
    removed: set[str] = set()

    gaps: list[DocumentationGap] = list(documentation_gaps)
    converted: list[DocumentationGap] = []
    rejected: list[RejectedOnCritique] = []
    revisions: list[RevisionRecord] = []
    superseded: list[Finding] = []
    applied: list[AppliedCritique] = []
    deferred: list[DeferredCritique] = []
    unapplied: list[UnappliedCritique] = []

    for critique in critiques:
        if critique.recommended_action is RecommendedAction.MERGE:
            deferred.append(
                DeferredCritique(
                    critique_id=critique.id,
                    action=critique.recommended_action,
                    reason=(
                        "merge recommendations are the DEC-052 merge operation's; applying one "
                        "here would merge through a second door with no merge record"
                    ),
                )
            )
            continue
        if critique.recommended_action is RecommendedAction.INVESTIGATE:
            deferred.append(
                DeferredCritique(
                    critique_id=critique.id,
                    action=critique.recommended_action,
                    reason=(
                        "a deterministic node cannot investigate; the checkpoint 2 reviewer "
                        "can request more analysis (agent-design.md section 18)"
                    ),
                )
            )
            continue

        targets = _resolve_targets(critique, list(current.values()), assessments)
        if isinstance(targets, str):
            unapplied.append(UnappliedCritique(critique_id=critique.id, reason=targets))
            continue

        for target in targets:
            if target.id in removed:
                unapplied.append(
                    UnappliedCritique(
                        critique_id=critique.id,
                        reason=(
                            f"{target.id} was already rejected or converted by an earlier "
                            f"critique; a second change would have no object to change"
                        ),
                    )
                )
                continue

            if critique.critique_type is CritiqueType.DOCUMENTATION_GAP_ONLY:
                gap, source = finding_to_documentation_gap(
                    target,
                    gap_id=mint("gap"),
                    importance=critique.rationale,
                    severity=Severity.MEDIUM,
                    generated_by=GENERATED_BY,
                )
                gaps.append(gap)
                converted.append(gap)
                superseded.append(source)
                current[target.id] = source
                removed.add(target.id)
                applied.append(
                    AppliedCritique(
                        critique_id=critique.id,
                        target_id=target.id,
                        action=critique.recommended_action,
                        change=(
                            f"reclassified as {gap.id}: documentation_gap_only outranks the "
                            f"recommended action (DEC-053); {target.id} is superseded"
                        ),
                    )
                )
                continue

            if critique.recommended_action is RecommendedAction.KEEP:
                applied.append(
                    AppliedCritique(
                        critique_id=critique.id,
                        target_id=target.id,
                        action=critique.recommended_action,
                        change="kept; nothing changed",
                    )
                )
                continue

            if critique.recommended_action is RecommendedAction.REJECT:
                dismissed = Finding.model_validate(
                    {
                        **target.model_dump(),
                        "status": ObjectStatus.REJECTED,
                        "updated_at": stamp,
                    }
                )
                current[target.id] = dismissed
                removed.add(target.id)
                rejected.append(
                    RejectedOnCritique(
                        finding=dismissed,
                        critique_id=critique.id,
                        reason=f"{critique.id}: {critique.description}",
                    )
                )
                applied.append(
                    AppliedCritique(
                        critique_id=critique.id,
                        target_id=target.id,
                        action=critique.recommended_action,
                        change=f"rejected and retained; {critique.id} is the stated reason",
                    )
                )
                continue

            # REVISE: the one action left. Add, never rewrite (DEC-053): the critique's own
            # description joins `limitations` under its identifier, its cited evidence joins
            # the finding's, and nothing the earlier pipeline asserted is altered.
            revised = Finding.model_validate(
                {
                    **target.model_dump(),
                    "limitations": [
                        *target.limitations,
                        f"{critique.id}: {critique.description}",
                    ],
                    "evidence_ids": _union(target.evidence_ids, list(critique.evidence_ids)),
                    "updated_at": stamp,
                }
            )
            revisions.append(RevisionRecord(critique_id=critique.id, before=target, after=revised))
            current[target.id] = revised
            applied.append(
                AppliedCritique(
                    critique_id=critique.id,
                    target_id=target.id,
                    action=critique.recommended_action,
                    change=(
                        f"limitations gained the criticism under {critique.id}; the "
                        f"pre-revision state is on the revision record"
                    ),
                )
            )

    return CritiqueApplicationOutcome(
        findings=tuple(current[finding.id] for finding in findings if finding.id not in removed),
        documentation_gaps=tuple(gaps),
        converted=tuple(converted),
        rejected=tuple(rejected),
        revisions=tuple(revisions),
        superseded=tuple(superseded),
        applied=tuple(applied),
        deferred=tuple(deferred),
        unapplied=tuple(unapplied),
    )


def persist_application(
    handle: AssessmentHandle, outcome: CritiqueApplicationOutcome
) -> CritiqueApplicationOutcome:
    """Write what the application changed, re-minting only the converted gaps (DEC-018).

    Findings keep their identifiers — a revision, a rejection, and a supersession change content,
    never identity. The converted gaps are new objects, so theirs come from the store, and
    `converted_from_id` stays valid because the finding identifiers did not move. Pre-existing
    gaps are not re-minted and not re-written; they were not changed here.
    """
    repository = handle.objects
    # Identity, not equality: a provisional `gap-001` from this pass must not be confused with a
    # pre-existing gap that happens to carry the same identifier.
    passthrough = [
        gap
        for gap in outcome.documentation_gaps
        if not any(gap is minted for minted in outcome.converted)
    ]

    stored_converted: list[DocumentationGap] = []
    with repository.transaction():
        for record in outcome.revisions:
            repository.save(record.after)
        for dismissal in outcome.rejected:
            repository.save(dismissal.finding)
        for source in outcome.superseded:
            repository.save(source)
        for gap in outcome.converted:
            stored = DocumentationGap.model_validate(
                {**gap.model_dump(), "id": repository.allocate("gap")}
            )
            repository.save(stored)
            stored_converted.append(stored)

    return CritiqueApplicationOutcome(
        findings=outcome.findings,
        documentation_gaps=(*passthrough, *stored_converted),
        converted=tuple(stored_converted),
        rejected=outcome.rejected,
        revisions=outcome.revisions,
        superseded=outcome.superseded,
        applied=outcome.applied,
        deferred=outcome.deferred,
        unapplied=outcome.unapplied,
    )
