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
    EvidenceStrength,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evaluation_result import EvaluationResult, EvaluatorType
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import (
    EvidenceAssessment,
    Recommendation,
    SubjectType,
)
from trace_ai.domain.finding import Finding
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
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


def a_resolved_contradiction(handle: AssessmentHandle) -> SourceObservation:
    """A contradiction the reviewer resolved: the DEC-133 signal that makes conditional
    expectations reachable. Two evidence references, per the contradiction minimum."""
    an_evidence(handle, "evd-002")
    return save(
        handle,
        SourceObservation.model_validate(
            {
                "id": "obs-001",
                "assessment_id": handle.assessment_id,
                "kind": ObservationKind.CONTRADICTION,
                "summary": "Two documents disagree, and the reviewer settled it.",
                "evidence_ids": ["evd-001", "evd-002"],
                "reviewer_notes": "Resolved: the posting behaviour is authoritative.",
                "status": ObjectStatus.APPROVED,
                "created_at": now(),
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


def a_mapping(handle: AssessmentHandle, mapping_id: str) -> ControlMapping:
    return save(
        handle,
        ControlMapping.model_validate(
            {
                "id": mapping_id,
                "assessment_id": handle.assessment_id,
                "threat_id": "thr-001",
                "requirement_id": "req-AI-002",
                "control_ids": [],
                "applicability_status": ApplicabilityStatus.APPLICABLE,
                "applicability_reason": "The threat concerns published AI output.",
                "satisfaction_status": SatisfactionStatus.PARTIALLY_SATISFIED,
                "evidence_ids": ["evd-001"],
                "confidence": ConfidenceLevel.MEDIUM,
                "generated_by": "mapping-v1",
                "reviewer_status": ObjectStatus.CANDIDATE,
            }
        ),
    )


def an_assessment_of(handle: AssessmentHandle, subject_id: str) -> EvidenceAssessment:
    return save(
        handle,
        EvidenceAssessment.model_validate(
            {
                "id": f"eas-{subject_id[-3:]}",
                "assessment_id": handle.assessment_id,
                "subject_type": SubjectType.CONTROL_MAPPING,
                "subject_id": subject_id,
                "evidence_ids": ["evd-001"],
                "evidence_strengths": {"evd-001": EvidenceStrength.DIRECT},
                "validation_status": ValidationStatus.PARTIALLY_SUPPORTED,
                "rationale": "The passage states the posting behaviour but not the review step.",
                "confidence": ConfidenceLevel.MEDIUM,
                "recommendation": Recommendation.CONTINUE,
                "generated_by": "evidence-validation-v1",
                "created_at": now(),
            }
        ),
    )


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


def test_evidence_assessment_coverage_names_the_unassessed(prepared: dict[str, Any]) -> None:
    """An unassessed subject resolves to no output (DEC-013) with nothing recording the
    omission; the metric is what makes the truncation visible (#564)."""
    handle = prepared["handle"]
    an_evidence(handle)
    a_mapping(handle, "map-001")
    a_mapping(handle, "map-002")
    an_assessment_of(handle, "map-001")

    named = metrics_by_name(compute_metrics(handle, prepared["run"]))
    coverage = named["evidence_assessment_coverage"]
    assert coverage.metric_value == 0.5
    assert coverage.sample_size == 2
    assert coverage.notes is not None
    assert "1 of 2" in coverage.notes


def test_full_assessment_coverage_carries_no_note(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    a_mapping(handle, "map-001")
    an_assessment_of(handle, "map-001")

    named = metrics_by_name(compute_metrics(handle, prepared["run"]))
    coverage = named["evidence_assessment_coverage"]
    assert coverage.metric_value == 1.0
    assert coverage.notes is None


def test_no_assessable_subjects_emits_no_coverage_rate(prepared: dict[str, Any]) -> None:
    """A run with nothing to assess has no coverage ratio, not a coverage ratio of 1.0.

    DEC-150: the denominator is empty, so the rate is unmeasured. The scorecard renders an
    absent metric as a dash, which is what "unmeasured, never zero" means on the page.
    """
    named = metrics_by_name(compute_metrics(prepared["handle"], prepared["run"]))
    assert "evidence_assessment_coverage" not in named


# ------------------------------------------------------------------------------------------
# Benchmark metrics against the authored truth set
# ------------------------------------------------------------------------------------------


def test_false_negative_rate_matches_on_requirement_and_component(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "GitHub Comment Service")
    a_resolved_contradiction(handle)
    approve_finding(handle, a_finding(handle), reviewer_id=REVIEWER)

    named = metrics_by_name(compute_metrics(handle, prepared["run"], expected_dir=EXPECTED))
    rate = named["false_negative_rate"]
    assert rate.metric_value == pytest.approx(2 / 3), "FND-002 matched; the other two did not"
    assert rate.evaluator_type is EvaluatorType.BENCHMARK
    assert "DEC-056" in rate.evaluation_method
    assert rate.notes is not None and "FND-003" in rate.notes and "FND-004" in rate.notes


def test_a_component_divergent_finding_stays_missed_and_is_not_spurious(
    prepared: dict[str, Any],
) -> None:
    """DEC-148: the expectation's requirement is cited under a name it does not carry.

    Recall must not move — the matcher did not establish that the two name the same ground — and
    the finding must not be called spurious, which would assert a false positive the requirement
    match is evidence against. This is translation-gateway's shape, built here from the ForgeFlow
    fixture: the finding cites req-AI-002 (FND-002's requirement) but names a component the
    expectation does not.
    """
    from trace_ai.services.evaluation.matching import match_findings

    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-009", "Comment Posting Service")
    finding, _ = approve_finding(
        handle, a_finding(handle, affected_component_ids=["cmp-009"]), reviewer_id=REVIEWER
    )

    expected = [
        {
            "key": "FND-002",
            "requirement_id": "req-AI-002",
            "affected_component": "GitHub Comment Service",
        }
    ]
    outcome = match_findings(
        [finding], expected, component_names={"cmp-009": "comment posting service"}
    )

    assert outcome.matched == {}, "the component name does not match, so nothing is credited"
    assert outcome.missed == ["FND-002"], "recall is unmoved: the expectation stays missed"
    assert outcome.divergent == {"FND-002": [finding.id]}, "the near-match is named"
    assert outcome.spurious == [], "a finding on the expected requirement is not a false positive"


def test_a_finding_on_no_expected_requirement_is_still_spurious(
    prepared: dict[str, Any],
) -> None:
    """DEC-148 narrows `spurious`; it does not empty it."""
    from trace_ai.services.evaluation.matching import match_findings

    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "GitHub Comment Service")
    finding, _ = approve_finding(
        handle, a_finding(handle, requirement_ids=["req-LOG-001"]), reviewer_id=REVIEWER
    )

    expected = [
        {
            "key": "FND-002",
            "requirement_id": "req-AI-002",
            "affected_component": "GitHub Comment Service",
        }
    ]
    outcome = match_findings(
        [finding], expected, component_names={"cmp-001": "github comment service"}
    )

    assert outcome.divergent == {}, "no produced finding stands on the expected requirement"
    assert outcome.spurious == [finding.id]


def test_a_consolidated_finding_scores_full_credit_per_matched_expectation(
    prepared: dict[str, Any],
) -> None:
    """DEC-056: FND-002 and FND-004 matched by one finding is two matches and no penalty."""
    handle = prepared["handle"]
    an_evidence(handle)
    a_resolved_contradiction(handle)
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


def test_a_conditional_expectation_is_unreached_without_a_resolution(
    prepared: dict[str, Any],
) -> None:
    """DEC-133: without a resolved contradiction, FND-002 and FND-003 leave the denominator
    and a finding on their identity scores spurious, not matched — the run's correct output
    was their paired questions, and the notes say which entries were unreached."""
    handle = prepared["handle"]
    an_evidence(handle)
    a_component(handle, "cmp-001", "GitHub Comment Service")
    approve_finding(handle, a_finding(handle), reviewer_id=REVIEWER)

    named = metrics_by_name(compute_metrics(handle, prepared["run"]))
    # No benchmark dir on this call: the run-derived metrics are unaffected. The benchmark
    # pass below is the assertion that matters.
    assert "false_negative_rate" not in named

    named = metrics_by_name(compute_metrics(handle, prepared["run"], expected_dir=EXPECTED))
    rate = named["false_negative_rate"]
    assert rate.sample_size == 1, "only FND-004 is reachable"
    assert rate.metric_value == pytest.approx(1.0), "FND-004 is missed; nothing else is graded"
    assert rate.notes is not None
    assert "FND-002" in rate.notes and "FND-003" in rate.notes
    assert "conditional" in rate.notes


def test_documentation_gap_recall_counts_the_expected_side_and_ignores_the_rest(
    prepared: dict[str, Any],
) -> None:
    """DEC-147: recall is denominated on the expected set, and an extra gap is not an error.

    `gap-001` reaches an expected requirement through its mapping; `gap-002` reaches none.
    The truth set is a must-include list, so `gap-002` is unscored rather than wrong — it
    moves the produced count and nothing else.
    """
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
    assert "documentation_gap_precision" not in named
    assert named["documentation_gap_recall"].metric_value == 0.25
    assert named["documentation_gap_recall"].sample_size == 4
    assert named["documentation_gaps_produced"].metric_value == 2.0
    assert named["documentation_gaps_produced"].unit == "count"


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

    # The rates whose denominator is the finding set are absent, not zero or one (DEC-150):
    # a run that approved nothing has no coverage rate and no reviewer rate.
    assert "finding_evidence_coverage" not in named
    assert "reviewer_acceptance_rate" not in named
    assert "false_positive_rate" not in named
    assert "duplicate_finding_rate" not in named
    # The truth set authors expectations, so the rate denominated on them survives.
    assert named["false_negative_rate"].metric_value == 1.0
    assert named["documentation_gap_recall"].metric_value == 0.0
    # A count of zero is a measurement and stays.
    assert named["documentation_gaps_produced"].metric_value == 0.0
    # The fixture run records no node executions, so there is no failure rate to take.
    assert "node_failure_rate" not in named


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
    a_resolved_contradiction(handle)
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
    a_resolved_contradiction(handle)
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


# ------------------------------------------------------------------------------------------
# DEC-150: a rate with an empty denominator is not emitted
# ------------------------------------------------------------------------------------------


def test_no_rate_is_emitted_over_an_empty_denominator(prepared: dict[str, Any]) -> None:
    """The invariant, checked over every metric a bare run produces.

    A percentage is a claim about a population. Emitted over an empty one it is not a small
    number or a large one, it is not a number — and on the scorecard it renders identically to
    a rate that was measured. This is the same failure DEC-147 retired
    `documentation_gap_precision` for, one level up: the instrument reporting a value it had no
    data for. Counts are exempt: a count of zero is a measurement.
    """
    offenders = [
        (result.metric_name, result.metric_value)
        for result in compute_metrics(prepared["handle"], prepared["run"], expected_dir=EXPECTED)
        if result.unit == "percentage" and result.sample_size == 0
    ]
    assert not offenders, (
        f"rates emitted over an empty denominator: {offenders}. A percentage over no population "
        f"is unmeasured; omit it and let the scorecard render its dash (DEC-150)."
    )
