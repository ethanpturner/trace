"""Duplicate detection and merge over provisional findings (DEC-052, issue #99).

The acceptance criteria are the spine: a shared threat and requirement merges, a shared component
alone does not, every merge writes a record, merged findings are retained and retrievable, a
finding and a documentation gap are never merged, and two runs over identical input agree.

The semantic-proposer seam is exercised with a stub, per the issue: a model-assisted comparison,
if one is ever wired in, proposes candidate pairs and merges nothing. No test here reaches a
provider.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import pytest

from trace_ai.domain.base import now
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, Severity, ValidationStatus
from trace_ai.domain.finding import Finding
from trace_ai.domain.finding_merge_record import FindingMergeRecord, MergeDecision
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.workflow.finding_dedup import (
    GENERATED_BY,
    DedupOutcome,
    SemanticMergeProposal,
    dedupe_findings,
    detect_duplicates,
    persist_dedup,
)


def a_finding(**changes: Any) -> Finding:
    stamped = now()
    payload: dict[str, Any] = {
        "id": "fnd-001",
        "assessment_id": "asm-001",
        "title": "Webhook requests may be processed without verified authenticity",
        "summary": "The receiver may accept events without verifying their origin.",
        "description": "The documents describe validation as structural, not cryptographic.",
        "threat_ids": ["thr-001"],
        "requirement_ids": ["req-WEBHOOK-001"],
        "control_mapping_ids": ["map-001"],
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "evidence_ids": ["evd-001"],
        "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
        "severity": Severity.UNASSIGNED,
        "impact": "Unauthorized job execution and resource exhaustion.",
        "recommendation": "Verify each event with the platform's signature mechanism.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "finding-consolidation-v1",
        "created_at": stamped,
        "updated_at": stamped,
    }
    payload.update(changes)
    return Finding.model_validate(payload)


def a_duplicate_pair() -> list[Finding]:
    """Two findings asserting the same shortfall: same threat, same requirement."""
    return [
        a_finding(),
        a_finding(
            id="fnd-002",
            control_mapping_ids=["map-002"],
            evidence_ids=["evd-002", "evd-003"],
            affected_component_ids=["cmp-002"],
        ),
    ]


# ------------------------------------------------------------------------------------------
# Detection: what merges and what does not
# ------------------------------------------------------------------------------------------


def test_a_shared_threat_and_requirement_is_a_duplicate() -> None:
    groups = detect_duplicates(a_duplicate_pair())
    assert len(groups) == 1
    assert groups[0].finding_ids == ("fnd-001", "fnd-002")


def test_a_shared_component_alone_is_not_a_duplicate() -> None:
    """One component hosting two distinct weaknesses is the ordinary case (DEC-052)."""
    findings = [
        a_finding(),
        a_finding(
            id="fnd-002",
            threat_ids=["thr-002"],
            requirement_ids=["req-TLS-001"],
            control_mapping_ids=["map-002"],
        ),
    ]
    assert detect_duplicates(findings) == ()


def test_a_shared_threat_alone_is_not_a_duplicate() -> None:
    """Two requirements failing against one scenario are two findings, not one."""
    findings = [
        a_finding(),
        a_finding(id="fnd-002", requirement_ids=["req-TLS-001"], control_mapping_ids=["map-002"]),
    ]
    assert detect_duplicates(findings) == ()


def test_a_shared_requirement_alone_is_not_a_duplicate() -> None:
    findings = [
        a_finding(),
        a_finding(id="fnd-002", threat_ids=["thr-002"], control_mapping_ids=["map-002"]),
    ]
    assert detect_duplicates(findings) == ()


def test_grouping_is_transitive() -> None:
    """A~B and B~C is one group: the survivor carries B's references, which made B match C."""
    findings = [
        a_finding(),
        a_finding(id="fnd-002", threat_ids=["thr-001", "thr-002"]),
        a_finding(id="fnd-003", threat_ids=["thr-002"], control_mapping_ids=["map-003"]),
    ]
    groups = detect_duplicates(findings)
    assert len(groups) == 1
    assert groups[0].finding_ids == ("fnd-001", "fnd-002", "fnd-003")


def test_an_already_merged_finding_is_not_reconsidered() -> None:
    """A finding carrying `duplicate_of_id` was merged once; merging it again would fork lineage."""
    findings = [
        a_finding(),
        a_finding(id="fnd-002", duplicate_of_id="fnd-001"),
    ]
    assert detect_duplicates(findings) == ()


def test_matched_features_name_the_corroboration_too() -> None:
    """The deciding features decide; a shared asset is recorded when present."""
    groups = detect_duplicates(a_duplicate_pair())
    assert groups[0].matched_features == ("threats", "requirements", "assets")


# ------------------------------------------------------------------------------------------
# The merge: survivor, unions, retention
# ------------------------------------------------------------------------------------------


def test_the_survivor_carries_the_union_of_both_evidence_sets() -> None:
    outcome = dedupe_findings(a_duplicate_pair())
    survivor = outcome.findings[0]
    assert survivor.id == "fnd-001"
    assert survivor.evidence_ids == ["evd-001", "evd-002", "evd-003"]
    assert survivor.control_mapping_ids == ["map-001", "map-002"]
    assert survivor.affected_component_ids == ["cmp-001", "cmp-002"]


def test_the_survivor_is_the_earliest_allocated_finding() -> None:
    """Reversed input, same survivor: allocation order decides, not input order."""
    outcome = dedupe_findings(list(reversed(a_duplicate_pair())))
    assert outcome.records[0].surviving_finding_id == "fnd-001"


def test_a_merged_finding_is_retained_and_points_at_the_survivor() -> None:
    outcome = dedupe_findings(a_duplicate_pair())
    merged = [finding for finding in outcome.findings if finding.id == "fnd-002"]
    assert len(merged) == 1
    assert merged[0].duplicate_of_id == "fnd-001"
    assert merged[0].evidence_ids == ["evd-002", "evd-003"], "the merged finding keeps its own"


def test_every_merge_writes_a_record_naming_what_matched() -> None:
    outcome = dedupe_findings(a_duplicate_pair())
    assert len(outcome.records) == 1
    record = outcome.records[0]
    assert record.surviving_finding_id == "fnd-001"
    assert record.merged_finding_ids == ["fnd-002"]
    assert record.matched_features == ["threats", "requirements", "assets"]
    assert record.decision is MergeDecision.STRUCTURAL
    assert record.generated_by == GENERATED_BY


def test_the_record_detail_names_the_shared_identifiers() -> None:
    record = dedupe_findings(a_duplicate_pair()).records[0]
    assert "thr-001" in record.detail
    assert "req-WEBHOOK-001" in record.detail


def test_merge_results_are_identical_across_two_runs() -> None:
    """Same input, same merges, same records — timestamps aside, which `now()` moves."""
    first = dedupe_findings(a_duplicate_pair())
    second = dedupe_findings(a_duplicate_pair())

    def stable(outcome: DedupOutcome) -> object:
        return (
            [
                finding.model_dump(exclude={"created_at", "updated_at"})
                for finding in outcome.findings
            ],
            [record.model_dump(exclude={"created_at"}) for record in outcome.records],
        )

    assert stable(first) == stable(second)


def test_a_single_finding_changes_nothing() -> None:
    single = [a_finding()]
    outcome = dedupe_findings(single)
    assert outcome.findings == tuple(single)
    assert outcome.records == ()


def test_an_empty_set_changes_nothing() -> None:
    outcome = dedupe_findings([])
    assert outcome == DedupOutcome()


# ------------------------------------------------------------------------------------------
# The DEC-009 boundary: a finding and a gap are never merged
# ------------------------------------------------------------------------------------------


def test_a_documentation_gap_is_refused_before_anything_is_compared() -> None:
    from trace_ai.domain.documentation_gap import DocumentationGap

    gap = DocumentationGap.model_validate(
        {
            "id": "gap-001",
            "assessment_id": "asm-001",
            "title": "TLS termination is not described",
            "description": "No document states where TLS terminates.",
            "importance": "Whether transit encryption covers the internal hop is undetermined.",
            "severity": Severity.MEDIUM,
            "status": ObjectStatus.CANDIDATE,
            "generated_by": "finding-consolidation-v1",
        }
    )
    with pytest.raises(TypeError, match="DEC-009"):
        dedupe_findings([a_finding(), gap])  # type: ignore[list-item]


# ------------------------------------------------------------------------------------------
# The semantic seam: proposals are recorded, never acted on
# ------------------------------------------------------------------------------------------


class StubProposer:
    """The shape DEC-052 confines a model-assisted comparison to: pairs out, nothing else."""

    def __init__(self, pairs: Sequence[tuple[str, str]]) -> None:
        self.pairs = pairs
        self.saw: list[str] = []

    def propose(self, findings: Sequence[Finding]) -> Sequence[tuple[str, str]]:
        self.saw = [finding.id for finding in findings]
        return self.pairs


def test_a_semantic_proposal_is_recorded_and_not_merged() -> None:
    """The pair shares nothing structural, so nothing merges — the proposal is the whole output."""
    findings = [
        a_finding(),
        a_finding(
            id="fnd-002",
            threat_ids=["thr-002"],
            requirement_ids=["req-TLS-001"],
            control_mapping_ids=["map-002"],
        ),
    ]
    proposer = StubProposer([("fnd-002", "fnd-001")])
    outcome = dedupe_findings(findings, proposer=proposer)

    assert outcome.records == (), "a proposal is not a merge"
    assert all(finding.duplicate_of_id is None for finding in outcome.findings)
    assert outcome.proposals == (
        SemanticMergeProposal(finding_ids=("fnd-001", "fnd-002"), proposed_by="StubProposer"),
    )


def test_the_proposer_sees_only_canonical_findings() -> None:
    """Structural merging runs first, so a model is not asked about already-merged findings."""
    proposer = StubProposer([])
    dedupe_findings(a_duplicate_pair(), proposer=proposer)
    assert proposer.saw == ["fnd-001"]


def test_a_proposal_naming_an_unknown_finding_is_refused() -> None:
    with pytest.raises(ValueError, match="fnd-999"):
        dedupe_findings([a_finding()], proposer=StubProposer([("fnd-001", "fnd-999")]))


def test_no_proposer_means_no_proposals_and_no_model() -> None:
    assert dedupe_findings(a_duplicate_pair()).proposals == ()


def test_the_module_reaches_no_provider() -> None:
    """The dedup pass is deterministic; any live comparison would be `integration`-marked."""
    from trace_ai.config import PROJECT_ROOT

    module = PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "finding_dedup.py"
    source = module.read_text(encoding="utf-8")
    assert "anthropic" not in source
    assert "StructuredModel" not in source


# ------------------------------------------------------------------------------------------
# Persistence: records re-minted from the store, findings upserted (DEC-018)
# ------------------------------------------------------------------------------------------


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Dedup", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


def test_persist_dedup_stores_the_record_and_the_changed_findings(
    handle: AssessmentHandle,
) -> None:
    repository = handle.objects
    with repository.transaction():
        first_id = repository.allocate("fnd")
        second_id = repository.allocate("fnd")
    findings = [
        a_finding(id=first_id, assessment_id=handle.assessment_id),
        a_finding(
            id=second_id,
            assessment_id=handle.assessment_id,
            control_mapping_ids=["map-002"],
            evidence_ids=["evd-002"],
        ),
    ]
    with repository.transaction():
        for finding in findings:
            repository.save(finding)

    stored = persist_dedup(handle, dedupe_findings(findings))

    assert len(stored.records) == 1
    record = stored.records[0]
    assert record.id.startswith("mrg-"), "the record identifier comes from the store"
    assert repository.get(FindingMergeRecord, record.id) == record

    survivor = repository.get(Finding, first_id)
    assert survivor.evidence_ids == ["evd-001", "evd-002"]
    merged = repository.get(Finding, second_id)
    assert merged.duplicate_of_id == first_id, "merged findings remain retrievable"


def test_persist_dedup_with_no_merges_writes_nothing(handle: AssessmentHandle) -> None:
    repository = handle.objects
    with repository.transaction():
        finding_id = repository.allocate("fnd")
    finding = a_finding(id=finding_id, assessment_id=handle.assessment_id)
    with repository.transaction():
        repository.save(finding)

    stored = persist_dedup(handle, dedupe_findings([finding]))

    assert stored.records == ()
    assert repository.count(FindingMergeRecord) == 0
