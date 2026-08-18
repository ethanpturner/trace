"""The finding-quality metrics (issue #110, DEC-056).

The acceptance criteria are the spine: evidence coverage moves with resolvability, the reviewer
rates derive from decisions so an edit-then-approval counts in both, the false-negative rate is
computed against the authored ForgeFlow truth set under the documented matching rule, a
zero-finding assessment yields a valid metric set, output lands in `evaluation/` and never in
the report directory, and no model is called on the default path.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evaluation_result import EvaluationResult, EvaluatorType
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.finding import Finding
from trace_ai.domain.hashing import content_hash
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evaluation.metrics import compute_metrics, persist_metrics
from trace_ai.services.execution_ledger import start_run
from trace_ai.workflow.finding_review import (
    approve_finding,
    change_severity,
    reject_finding,
)

EXPECTED = PROJECT_ROOT / "demo" / "forgeflow" / "expected"
REVIEWER = "reviewer-local"
PASSAGE = "The comment service posts validated analysis output automatically."


@pytest.fixture
def prepared(tmp_path: Any) -> Iterator[dict[str, Any]]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Metrics", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield {"handle": handle, "run": run}


def save[ModelT](handle: AssessmentHandle, obj: ModelT) -> ModelT:
    with handle.objects.transaction():
        handle.objects.save(obj)  # type: ignore[arg-type]
    return obj


def an_evidence(handle: AssessmentHandle, evidence_id: str = "evd-001") -> EvidenceReference:
    return save(
        handle,
        EvidenceReference.model_validate(
            {
                "id": evidence_id,
                "assessment_id": handle.assessment_id,
                "source_document_id": "src-001",
                "start_line": 10,
                "end_line": 12,
                "quoted_text": PASSAGE,
                "content_hash": content_hash(PASSAGE.encode()),
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "created_at": now(),
            }
        ),
    )


def a_component(handle: AssessmentHandle, component_id: str, name: str) -> Component:
    return save(
        handle,
        Component.model_validate(
            {
                "id": component_id,
                "assessment_id": handle.assessment_id,
                "name": name,
                "component_type": "service",
                "internet_accessible": False,
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        ),
    )


def a_finding(handle: AssessmentHandle, **changes: Any) -> Finding:
    stamped = now()
    payload: dict[str, Any] = {
        "id": "fnd-001",
        "assessment_id": handle.assessment_id,
        "title": "AI output is published without adequate review",
        "summary": "Comments are posted automatically after schema validation.",
        "description": "Schema validation does not validate factual correctness.",
        "threat_ids": ["thr-001"],
        "requirement_ids": ["req-AI-002"],
        "control_mapping_ids": ["map-001"],
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "evidence_ids": ["evd-001"],
        "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
        "severity": Severity.MEDIUM,
        "impact": "Manipulated output reaches customer pull requests.",
        "recommendation": "Add a human approval gate before publication.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.CANDIDATE,
        "generated_by": "finding-consolidation-v1",
        "created_at": stamped,
        "updated_at": stamped,
    }
    payload.update(changes)
    return save(handle, Finding.model_validate(payload))


def metrics_by_name(results: list[EvaluationResult]) -> dict[str, EvaluationResult]:
    return {result.metric_name: result for result in results}


# ------------------------------------------------------------------------------------------
# Evidence coverage
# ------------------------------------------------------------------------------------------


def test_coverage_is_complete_when_every_citation_resolves(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    approve_finding(handle, a_finding(handle), reviewer_id=REVIEWER)

    named = metrics_by_name(compute_metrics(handle, prepared["run"]))
    assert named["finding_evidence_coverage"].metric_value == 1.0
    assert named["finding_evidence_coverage"].sample_size == 1


def test_coverage_drops_below_complete_when_a_citation_does_not_resolve(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    approve_finding(handle, a_finding(handle), reviewer_id=REVIEWER)
    approve_finding(
        handle,
        a_finding(handle, id="fnd-002", evidence_ids=["evd-999"], control_mapping_ids=["map-002"]),
        reviewer_id=REVIEWER,
    )

    named = metrics_by_name(compute_metrics(handle, prepared["run"]))
    assert named["finding_evidence_coverage"].metric_value == 0.5


# ------------------------------------------------------------------------------------------
# Reviewer rates derive from decisions
# ------------------------------------------------------------------------------------------


def test_an_edit_then_an_approval_counts_in_both_rates(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    finding = a_finding(handle, severity=Severity.UNASSIGNED)
    assigned, _ = change_severity(handle, finding, Severity.HIGH, reviewer_id=REVIEWER)
    approve_finding(handle, assigned, reviewer_id=REVIEWER)

    named = metrics_by_name(compute_metrics(handle, prepared["run"]))
    assert named["reviewer_edit_rate"].metric_value == 1.0
    assert named["reviewer_acceptance_rate"].metric_value == 1.0
    assert named["reviewer_rejection_rate"].metric_value == 0.0


def test_rejection_and_false_positive_rates_count_the_rejected(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    approve_finding(handle, a_finding(handle), reviewer_id=REVIEWER)
    reject_finding(
        handle,
        a_finding(handle, id="fnd-002", control_mapping_ids=["map-002"]),
        reviewer_id=REVIEWER,
        rationale="Not supported.",
    )

    named = metrics_by_name(compute_metrics(handle, prepared["run"]))
    assert named["reviewer_rejection_rate"].metric_value == 0.5
    assert named["false_positive_rate"].metric_value == 0.5
    assert named["duplicate_finding_rate"].metric_value == 0.0


# ------------------------------------------------------------------------------------------
# Benchmark metrics against the authored truth set
# ------------------------------------------------------------------------------------------


def test_false_negative_rate_matches_on_requirement_and_component(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "GitHub Comment Service")
    approve_finding(handle, a_finding(handle), reviewer_id=REVIEWER)

    named = metrics_by_name(compute_metrics(handle, prepared["run"], expected_dir=EXPECTED))
    rate = named["false_negative_rate"]
    assert rate.metric_value == pytest.approx(2 / 3), "FND-002 matched; the other two did not"
    assert rate.evaluator_type is EvaluatorType.BENCHMARK
    assert "DEC-056" in rate.evaluation_method
    assert rate.notes is not None and "FND-003" in rate.notes and "FND-004" in rate.notes


def test_a_consolidated_finding_scores_full_credit_per_matched_expectation(
    prepared: dict[str, Any],
) -> None:
    """DEC-056: FND-002 and FND-004 matched by one finding is two matches and no penalty."""
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "GitHub Comment Service")
    a_component(handle, "cmp-002", "Analysis Worker")
    consolidated = a_finding(
        handle,
        requirement_ids=["req-AI-002", "req-AI-001"],
        affected_component_ids=["cmp-001", "cmp-002"],
    )
    approve_finding(handle, consolidated, reviewer_id=REVIEWER)

    named = metrics_by_name(compute_metrics(handle, prepared["run"], expected_dir=EXPECTED))
    rate = named["false_negative_rate"]
    assert rate.metric_value == pytest.approx(1 / 3), "only FND-003 is unmatched"
    assert rate.notes is not None
    assert "more than one expectation: 1" in rate.notes


def test_documentation_gap_precision_matches_through_the_requirement(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    save(
        handle,
        ControlMapping.model_validate(
            {
                "id": "map-010",
                "assessment_id": handle.assessment_id,
                "threat_id": "thr-001",
                "requirement_id": "req-WEBHOOK-002",
                "applicability_status": ApplicabilityStatus.APPLICABLE,
                "applicability_reason": "The system accepts external webhook events.",
                "satisfaction_status": SatisfactionStatus.UNVERIFIED,
                "confidence": ConfidenceLevel.MEDIUM,
                "generated_by": "mapping-v1",
                "reviewer_status": ObjectStatus.CANDIDATE,
            }
        ),
    )
    save(
        handle,
        DocumentationGap.model_validate(
            {
                "id": "gap-001",
                "assessment_id": handle.assessment_id,
                "title": "Webhook replay handling is undocumented",
                "description": "The documents do not establish replay handling.",
                "importance": "A replayed event costs duplicate model work.",
                "related_object_ids": ["thr-001", "map-010"],
                "severity": Severity.MEDIUM,
                "status": ObjectStatus.CANDIDATE,
                "generated_by": "finding-consolidation-v1",
            }
        ),
    )
    save(
        handle,
        DocumentationGap.model_validate(
            {
                "id": "gap-002",
                "assessment_id": handle.assessment_id,
                "title": "An unexpected gap",
                "description": "A gap the truth set does not expect.",
                "importance": "It matters to nobody in the benchmark.",
                "severity": Severity.LOW,
                "status": ObjectStatus.CANDIDATE,
                "generated_by": "finding-consolidation-v1",
            }
        ),
    )

    named = metrics_by_name(compute_metrics(handle, prepared["run"], expected_dir=EXPECTED))
    assert named["documentation_gap_precision"].metric_value == 0.5


# ------------------------------------------------------------------------------------------
# The duplicate-miss instrument (#536, DEC-110)
# ------------------------------------------------------------------------------------------


def _duplicates_dir(tmp_path: Any, *, from_dir: Any = EXPECTED) -> Any:
    """A truth directory that adds one authored duplicate pair to the ForgeFlow set."""
    import shutil

    target = tmp_path / "expected"
    shutil.copytree(from_dir, target)
    (target / "expected-duplicates.yaml").write_text(
        "duplicate_pairs:\n"
        "  - note: one weakness, two lenses\n"
        "    first:\n"
        "      requirement_id: req-AI-002\n"
        "      affected_component: Comment Service\n"
        "    second:\n"
        "      requirement_id: req-AI-001\n"
        "      affected_component: Comment Service\n",
        encoding="utf-8",
    )
    return target


def test_a_split_weakness_scores_as_a_duplicate_miss(
    prepared: dict[str, Any], tmp_path: Any
) -> None:
    """Two unmerged findings on the pair's two lenses: the deterministic rule missed a merge."""
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "Comment Service")
    a_finding(handle, id="fnd-001", requirement_ids=["req-AI-002"])
    a_finding(handle, id="fnd-002", requirement_ids=["req-AI-001"])

    named = metrics_by_name(
        compute_metrics(handle, prepared["run"], expected_dir=_duplicates_dir(tmp_path))
    )
    assert named["duplicate_miss_rate"].metric_value == 1.0
    assert named["duplicate_miss_rate"].sample_size == 1
    assert "req-AI-002+req-AI-001" in (named["duplicate_miss_rate"].notes or "")


def test_a_merged_or_consolidated_pair_is_detected_not_missed(
    prepared: dict[str, Any], tmp_path: Any
) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "Comment Service")
    # Merged: the second finding resolves to the first through duplicate_of_id.
    a_finding(handle, id="fnd-001", requirement_ids=["req-AI-002"])
    a_finding(handle, id="fnd-002", requirement_ids=["req-AI-001"], duplicate_of_id="fnd-001")

    named = metrics_by_name(
        compute_metrics(handle, prepared["run"], expected_dir=_duplicates_dir(tmp_path))
    )
    assert named["duplicate_miss_rate"].metric_value == 0.0


def test_a_consolidated_finding_carrying_both_lenses_is_detected(
    prepared: dict[str, Any], tmp_path: Any
) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "Comment Service")
    a_finding(handle, id="fnd-001", requirement_ids=["req-AI-001", "req-AI-002"])

    named = metrics_by_name(
        compute_metrics(handle, prepared["run"], expected_dir=_duplicates_dir(tmp_path))
    )
    assert named["duplicate_miss_rate"].metric_value == 0.0


def test_an_unevaluable_pair_yields_no_metric(prepared: dict[str, Any], tmp_path: Any) -> None:
    """One side never matched: the run did not split the weakness, and nothing is measured —
    unmeasured, never zero."""
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "Comment Service")
    a_finding(handle, id="fnd-001", requirement_ids=["req-AI-002"])

    named = metrics_by_name(
        compute_metrics(handle, prepared["run"], expected_dir=_duplicates_dir(tmp_path))
    )
    assert "duplicate_miss_rate" not in named


# ------------------------------------------------------------------------------------------
# Zero findings is a successful outcome
# ------------------------------------------------------------------------------------------


def test_zero_findings_yields_a_valid_metric_set(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    results = compute_metrics(handle, prepared["run"], expected_dir=EXPECTED)
    named = metrics_by_name(results)

    assert named["finding_evidence_coverage"].metric_value == 1.0
    assert named["finding_evidence_coverage"].notes is not None
    assert "successful outcome" in named["finding_evidence_coverage"].notes
    assert named["reviewer_acceptance_rate"].metric_value == 0.0
    assert named["false_negative_rate"].metric_value == 1.0
    assert named["documentation_gap_precision"].metric_value == 0.0
    assert named["node_failure_rate"].metric_value == 0.0


# ------------------------------------------------------------------------------------------
# Persistence and separation from the report
# ------------------------------------------------------------------------------------------


def test_results_are_persisted_and_written_to_the_evaluation_area(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    approve_finding(handle, a_finding(handle), reviewer_id=REVIEWER)

    results = compute_metrics(handle, prepared["run"])
    path = persist_metrics(handle, prepared["run"], results)

    assert path.parent == handle.artifacts.area("evaluation")
    assert path.parent != handle.artifacts.area("outputs")
    assert list(handle.artifacts.area("outputs").iterdir()) == []

    stored = handle.objects.list(EvaluationResult)
    assert len(stored) == len(results)
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["workflow_run_id"] == prepared["run"].id
    assert {entry["metric_name"] for entry in summary["metrics"]} == {
        result.metric_name for result in results
    }


def test_no_metric_computation_calls_a_model() -> None:
    module = PROJECT_ROOT / "src" / "trace_ai" / "services" / "evaluation" / "metrics.py"
    source = module.read_text(encoding="utf-8")
    assert "StructuredModel" not in source
    assert "anthropic" not in source
    assert "generate(" not in source


# ------------------------------------------------------------------------------------------
# Severity concordance (#507, DEC-030's open question)
# ------------------------------------------------------------------------------------------


def test_severity_concordance_is_one_when_the_reviewer_matches_the_guidance(
    prepared: dict[str, Any],
) -> None:
    """FND-003's guidance is `medium`; a finding approved at medium agrees exactly."""
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "Managed Object Storage")
    approve_finding(
        handle,
        a_finding(
            handle,
            requirement_ids=["req-DATA-002"],
            affected_component_ids=["cmp-001"],
            severity=Severity.MEDIUM,
        ),
        reviewer_id=REVIEWER,
    )

    named = metrics_by_name(compute_metrics(handle, prepared["run"], expected_dir=EXPECTED))
    concordance = named["severity_concordance"]
    assert concordance.metric_value == pytest.approx(1.0)
    assert concordance.evaluator_type is EvaluatorType.BENCHMARK
    assert "DEC-030" in concordance.evaluation_method
    assert concordance.sample_size == 1


def test_severity_concordance_falls_when_the_reviewer_differs_from_the_guidance(
    prepared: dict[str, Any],
) -> None:
    """Approved at informational against `medium` guidance: not exact, and not within one level."""
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "Managed Object Storage")
    approve_finding(
        handle,
        a_finding(
            handle,
            requirement_ids=["req-DATA-002"],
            affected_component_ids=["cmp-001"],
            severity=Severity.INFORMATIONAL,
        ),
        reviewer_id=REVIEWER,
    )

    named = metrics_by_name(compute_metrics(handle, prepared["run"], expected_dir=EXPECTED))
    concordance = named["severity_concordance"]
    assert concordance.metric_value == pytest.approx(0.0)
    assert concordance.notes is not None and "within one level: 0/1" in concordance.notes


def test_severity_concordance_is_absent_when_no_matched_finding_has_guidance(
    prepared: dict[str, Any],
) -> None:
    """A matched finding whose expectation carries a non-scalar guidance measures nothing here
    rather than scoring a spurious zero; FND-001's guidance is `medium-or-high`."""
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "GitHub Comment Service")
    approve_finding(
        handle,
        a_finding(handle, requirement_ids=["req-AI-001"], severity=Severity.HIGH),
        reviewer_id=REVIEWER,
    )

    named = metrics_by_name(compute_metrics(handle, prepared["run"], expected_dir=EXPECTED))
    assert "severity_concordance" not in named
