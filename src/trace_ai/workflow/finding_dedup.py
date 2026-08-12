"""Duplicate detection and merge over provisional findings, decided on identifiers (DEC-052).

`agent-design.md` section 16 makes "merge duplicate issues" a Finding Consolidation
responsibility, and section 11's constraint governs how: the merge decision stays explicit and
traceable. Here that means the decision is a deterministic rule over identifier sets, and every
merge persists a `FindingMergeRecord` naming what matched.

**The rule is a conjunction: shared threat and shared requirement.** A provisional finding names
its threats and requirements outright, so where the identifiers agree, two findings assert the
same shortfall against the same scenario — the exact question DEC-043 has to approximate with
scored text overlap for threats, answered exactly here. Shared components, assets, and control
mappings are recorded when present and decide nothing alone: one component hosting two distinct
weaknesses is the ordinary case, not a duplicate.

**The survivor is the earliest-allocated finding, and the choice is made not to matter.** The
survivor takes the union of every reference list from everything merged into it, so whichever
member survived would carry identical evidence; allocation order is the tiebreak because it is
stable and smuggles in no quality judgment nobody defined. Merged findings are retained with
`duplicate_of_id` set — a reviewer asking "why did this finding disappear" gets a record and the
object, not silence (`design-principles.md` section 16).

**A semantic comparison, if one is ever wired in, proposes pairs and merges nothing.** The
`SemanticPairProposer` seam is the whole provision for it: proposals are recorded on the outcome
as proposals, and a merge from one happens only through a reviewer decision reusing
`merge_findings` — which is why that operation takes a decision mode this module's automatic path
never varies. The MVP wires no model here (DEC-052, for DEC-043's reasons).

**A `Finding` and a `DocumentationGap` are never merged.** `dedupe_findings` refuses non-`Finding`
input by type before anything is compared, and `FindingMergeRecord`'s identifier fields refuse a
gap identifier by schema. Merging across that boundary would collapse "evidence supports a
weakness" into "this could not be determined", which is the DEC-009 failure through the side door.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

from trace_ai.domain.base import now
from trace_ai.domain.finding import Finding
from trace_ai.domain.finding_merge_record import (
    MERGE_FEATURES,
    FindingMergeRecord,
    MergeDecision,
)
from trace_ai.services.findings.fingerprints import (
    component_name_index,
    fingerprinted_finding,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from datetime import datetime

    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "DedupOutcome",
    "DuplicateGroup",
    "SemanticMergeProposal",
    "SemanticPairProposer",
    "dedupe_findings",
    "detect_duplicates",
    "merge_findings",
    "persist_dedup",
    "shared_features",
]

# What `generated_by` records on every merge record the automatic path writes. The dedup step is
# part of the Finding Consolidation phase, and the version is its own: this operation can change
# without the routing changing.
GENERATED_BY: Final = "finding-dedup-v1"

# The deciding features. The record's vocabulary in `MERGE_FEATURES` is wider; these two are the
# conjunction DEC-052 merges on, and everything else corroborates.
_DECIDING: Final = ("threats", "requirements")


class SemanticPairProposer(Protocol):
    """A comparison that may propose candidate duplicate pairs, and may do nothing else.

    DEC-052 confines any model-assisted comparison to this shape: it sees the canonical findings,
    returns pairs of finding identifiers, and its proposals are recorded as proposals. It cannot
    merge, select a survivor, or edit a finding, because nothing downstream of it accepts those.
    """

    def propose(self, findings: Sequence[Finding]) -> Sequence[tuple[str, str]]:
        """Candidate duplicate pairs, each a pair of finding identifiers from `findings`."""
        ...


@dataclass(frozen=True, slots=True)
class SemanticMergeProposal:
    """A model-proposed candidate pair, recorded and not acted on.

    The analogue of DEC-043's threat `MergeProposal`: ephemeral, because it merges nothing. A
    reviewer who agrees merges through `merge_findings`, and that merge writes the persisted
    record with `decision` saying a model proposed it.
    """

    finding_ids: tuple[str, str]
    proposed_by: str


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    """Findings the structural rule says are one finding, and what matched.

    `finding_ids` is sorted with the survivor first — earliest-allocated, which for the store's
    zero-padded identifiers is the lowest one. `matched_features` follows section 21a's
    vocabulary order, and `shared` keeps the identifiers behind each feature so the record's
    detail can name them.
    """

    finding_ids: tuple[str, ...]
    matched_features: tuple[str, ...]
    shared: dict[str, tuple[str, ...]]

    @property
    def survivor_id(self) -> str:
        return self.finding_ids[0]

    @property
    def merged_ids(self) -> tuple[str, ...]:
        return self.finding_ids[1:]


@dataclass(frozen=True, slots=True)
class DedupOutcome:
    """What one dedup pass produced: the full finding set, and the records that explain it.

    `findings` is every input finding in input order, with survivors carrying their unions and
    merged findings carrying `duplicate_of_id`. Nothing is dropped: retention is the point
    (`design-principles.md` section 16).
    """

    findings: tuple[Finding, ...] = ()
    records: tuple[FindingMergeRecord, ...] = ()
    proposals: tuple[SemanticMergeProposal, ...] = ()


def _allocation_order(finding_id: str) -> tuple[int, str]:
    """Earliest-allocated first: shorter before longer, then lexicographic.

    The store zero-pads to three digits and widens past 999 rather than wrapping (DEC-018), so
    length-then-lexicographic is numeric order without parsing."""
    return (len(finding_id), finding_id)


def shared_features(a: Finding, b: Finding) -> dict[str, frozenset[str]]:
    """The identifier overlap between two findings, one entry per section 21a feature."""
    return {
        "threats": frozenset(a.threat_ids) & frozenset(b.threat_ids),
        "requirements": frozenset(a.requirement_ids) & frozenset(b.requirement_ids),
        "control_mappings": frozenset(a.control_mapping_ids) & frozenset(b.control_mapping_ids),
        "components": frozenset(a.affected_component_ids) & frozenset(b.affected_component_ids),
        "assets": frozenset(a.affected_asset_ids) & frozenset(b.affected_asset_ids),
    }


def _refuse_non_findings(findings: Sequence[Finding]) -> None:
    """The type half of the DEC-009 boundary: nothing that is not a `Finding` is compared.

    A `DocumentationGap` has a title and evidence and would duck-type far enough to be dangerous.
    Refusing by type here, before any comparison, is what makes "a finding and a gap are never
    merged" a property of the operation rather than a property of today's callers.
    """
    for candidate in findings:
        if not isinstance(candidate, Finding):
            raise TypeError(
                f"dedupe compares findings only, got {type(candidate).__name__}. A finding "
                f"asserts a weakness and a documentation gap asserts that something could not "
                f"be determined; merging them would collapse the DEC-009 separation."
            )


def detect_duplicates(findings: Sequence[Finding]) -> tuple[DuplicateGroup, ...]:
    """Group provisional findings the structural rule says are one finding.

    Pairwise over canonical findings only — one already merged into a survivor is not a candidate
    for merging again. Grouping is transitive: if A and B are duplicates and B and C are, all
    three are one group, because a survivor carrying B's references has everything that made B a
    duplicate of C. Groups are ordered by survivor for a deterministic outcome.
    """
    _refuse_non_findings(findings)
    canonical = [finding for finding in findings if finding.duplicate_of_id is None]

    parent: dict[str, str] = {finding.id: finding.id for finding in canonical}

    def root(finding_id: str) -> str:
        while parent[finding_id] != finding_id:
            parent[finding_id] = parent[parent[finding_id]]
            finding_id = parent[finding_id]
        return finding_id

    pair_shared: dict[tuple[str, str], dict[str, frozenset[str]]] = {}
    for index, first in enumerate(canonical):
        for second in canonical[index + 1 :]:
            shared = shared_features(first, second)
            if all(shared[feature] for feature in _DECIDING):
                pair_shared[(first.id, second.id)] = shared
                parent[root(first.id)] = root(second.id)

    members: dict[str, list[str]] = {}
    for finding in canonical:
        members.setdefault(root(finding.id), []).append(finding.id)

    groups: list[DuplicateGroup] = []
    for grouped in members.values():
        if len(grouped) < 2:
            continue
        ordered = sorted(grouped, key=_allocation_order)
        shared_by_feature: dict[str, set[str]] = {feature: set() for feature in MERGE_FEATURES}
        for pair, shared in pair_shared.items():
            if pair[0] in grouped:
                for feature, values in shared.items():
                    shared_by_feature[feature] |= values
        groups.append(
            DuplicateGroup(
                finding_ids=tuple(ordered),
                matched_features=tuple(
                    feature for feature in MERGE_FEATURES if shared_by_feature[feature]
                ),
                shared={
                    feature: tuple(sorted(values))
                    for feature, values in shared_by_feature.items()
                    if values
                },
            )
        )

    return tuple(sorted(groups, key=lambda group: _allocation_order(group.survivor_id)))


def _union(survivor: list[str], merged: Iterable[list[str]]) -> list[str]:
    """The survivor's list, then everything the merged findings add, sorted. Nothing is lost."""
    extra = sorted({value for values in merged for value in values} - set(survivor))
    return [*survivor, *extra]


def merge_findings(
    findings: Sequence[Finding],
    group: DuplicateGroup,
    *,
    record_id: str,
    decision: MergeDecision = MergeDecision.STRUCTURAL,
    generated_by: str = GENERATED_BY,
    stamped: datetime | None = None,
) -> tuple[list[Finding], FindingMergeRecord]:
    """Perform one merge: rebuild the survivor with the unions, mark the rest, write the record.

    This is the single merge operation DEC-052 names. The automatic path calls it with
    `structural`; a reviewer-initiated merge at checkpoint 2 (issue #99's out-of-scope, #102's
    concern) reuses it with the mode that says so. Domain objects are frozen, so every changed
    finding is rebuilt through `model_validate` under its existing identifier — the one path a
    schema rule cannot be skipped on.
    """
    _refuse_non_findings(findings)
    by_id = {finding.id: finding for finding in findings}
    survivor = by_id[group.survivor_id]
    merged = [by_id[merged_id] for merged_id in group.merged_ids]
    stamp = stamped if stamped is not None else now()

    updated_survivor = Finding.model_validate(
        {
            **survivor.model_dump(),
            "threat_ids": _union(survivor.threat_ids, (m.threat_ids for m in merged)),
            "requirement_ids": _union(
                survivor.requirement_ids, (m.requirement_ids for m in merged)
            ),
            "control_mapping_ids": _union(
                survivor.control_mapping_ids, (m.control_mapping_ids for m in merged)
            ),
            "affected_component_ids": _union(
                survivor.affected_component_ids, (m.affected_component_ids for m in merged)
            ),
            "affected_asset_ids": _union(
                survivor.affected_asset_ids, (m.affected_asset_ids for m in merged)
            ),
            "evidence_ids": _union(survivor.evidence_ids, (m.evidence_ids for m in merged)),
            "updated_at": stamp,
        }
    )

    marked = [
        Finding.model_validate(
            {**m.model_dump(), "duplicate_of_id": survivor.id, "updated_at": stamp}
        )
        for m in merged
    ]

    described = "; ".join(
        f"shared {feature}: {', '.join(group.shared[feature])}"
        for feature in group.matched_features
    )
    record = FindingMergeRecord.model_validate(
        {
            "id": record_id,
            "assessment_id": survivor.assessment_id,
            "surviving_finding_id": survivor.id,
            "merged_finding_ids": list(group.merged_ids),
            "matched_features": list(group.matched_features),
            "decision": decision,
            "detail": (f"{', '.join(group.merged_ids)} merged into {survivor.id}: {described}."),
            "generated_by": generated_by,
            "created_at": stamp,
        }
    )

    return [updated_survivor, *marked], record


def dedupe_findings(
    findings: Sequence[Finding],
    *,
    proposer: SemanticPairProposer | None = None,
    next_id: dict[str, int] | None = None,
) -> DedupOutcome:
    """Detect, merge, and record — the whole pass, deterministic over identical input.

    With one finding or none, nothing changes and nothing is written: zero duplicates is the
    ordinary case, not an edge case. `next_id` is the same caller-supplied counter convention
    `consolidate` uses for tests without a store; in the workflow, `persist_dedup` re-mints record
    identifiers from the repository (DEC-018).

    A `proposer`, if supplied, sees the canonical findings after structural merging and its
    proposals are carried on the outcome — recorded, and acted on by nobody here.
    """
    _refuse_non_findings(findings)
    counters = next_id if next_id is not None else {}

    def mint(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}-{counters[prefix]:03d}"

    stamp = now()
    current: dict[str, Finding] = {finding.id: finding for finding in findings}
    records: list[FindingMergeRecord] = []

    for group in detect_duplicates(findings):
        changed, record = merge_findings(
            list(current.values()), group, record_id=mint("mrg"), stamped=stamp
        )
        for finding in changed:
            current[finding.id] = finding
        records.append(record)

    proposals: list[SemanticMergeProposal] = []
    if proposer is not None:
        canonical = [f for f in current.values() if f.duplicate_of_id is None]
        canonical_ids = {f.id for f in canonical}
        for pair in proposer.propose(canonical):
            unknown = [finding_id for finding_id in pair if finding_id not in canonical_ids]
            if unknown:
                raise ValueError(
                    f"the semantic proposer named {unknown}, which is not a canonical finding "
                    f"in this set. A proposal about nothing cannot be reviewed."
                )
            first, second = sorted(pair)
            proposals.append(
                SemanticMergeProposal(
                    finding_ids=(first, second), proposed_by=type(proposer).__name__
                )
            )

    return DedupOutcome(
        findings=tuple(current[finding.id] for finding in findings),
        records=tuple(records),
        proposals=tuple(proposals),
    )


def persist_dedup(handle: AssessmentHandle, outcome: DedupOutcome) -> DedupOutcome:
    """Re-mint the records' identifiers from the store and write everything changed (DEC-018).

    Findings keep the identifiers they already have — a merge changes content, never identity —
    so only the merge records are re-minted. Each record's finding references are already store
    identifiers, and the upserts and the counter increments commit together.

    Identity here means the allocated identifier. The DEC-066 `content_fingerprint` is the other
    identity, and a merge *does* move it where the survivor's unions widened the requirement or
    component sets — so every merged-into or merged-away finding is re-fingerprinted before the
    write, idempotently where nothing structural changed.
    """
    repository = handle.objects
    changed = {
        finding_id
        for record in outcome.records
        for finding_id in (record.surviving_finding_id, *record.merged_finding_ids)
    }
    names = component_name_index(handle)
    stored_findings = tuple(
        fingerprinted_finding(finding, names) if finding.id in changed else finding
        for finding in outcome.findings
    )

    stored_records: list[FindingMergeRecord] = []
    with repository.transaction():
        for finding in stored_findings:
            if finding.id in changed:
                repository.save(finding)
        for record in outcome.records:
            stored = FindingMergeRecord.model_validate(
                {**record.model_dump(), "id": repository.allocate("mrg")}
            )
            repository.save(stored)
            stored_records.append(stored)

    return DedupOutcome(
        findings=stored_findings,
        records=tuple(stored_records),
        proposals=outcome.proposals,
    )
