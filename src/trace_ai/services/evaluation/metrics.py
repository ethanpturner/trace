"""The finding-quality metrics, computed deterministically from persisted objects (#110).

`evaluation-plan.md` section 8 defines the primary metrics and roadmap Stage 4 sets the targets;
this module is what makes them reportable. Every metric on the default path is a computation over
rows — no model is called — and each result is persisted as an `EvaluationResult` (DEC-056) and
written to the assessment's `evaluation/` area, separate from the user-facing report.

**The matching rule (DEC-056), stated here because the metric means nothing without it:**

- An expected finding matches an approved finding when the finding cites the expected
  `requirement_id` **and** names an affected component whose name — resolved through the run's
  own `Component` objects, compared case-insensitively after whitespace normalization — equals
  the expected `affected_component`. Title wording is never compared.
- One approved finding may match several expected entries (`allow_consolidation`), and each
  matched expectation scores **full credit**: DEC-029 makes a well-reasoned consolidation
  defensible rather than wrong, so it is observed (the consolidation count is recorded in the
  metric's notes) and never penalised.
- An expected documentation gap matches a produced gap through the requirement it bears on: the
  produced gap's related mapping resolves to a `requirement_id`, which must equal the expected
  entry's. Gap wording is never compared.

**What the rule does not catch:** a produced finding that addresses an expected weakness under a
different requirement scores as a false negative plus an unexpected finding, and a gap raised
outside any mapping cannot match. Both are conservative in the direction that keeps the
false-negative rate honest.

**Zero findings is a successful outcome and the metrics say so**: coverage is vacuously complete,
the rates are 0 with a stated zero sample, and nothing divides by zero or reports a failure.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

import yaml

from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus, ReviewDisposition
from trace_ai.domain.evaluation_result import EvaluationResult, EvaluatorType
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import ExecutionRecord, ExecutionStatus
from trace_ai.domain.finding import Finding
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.services.evaluation.matching import match_findings, match_gaps

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.domain.execution import WorkflowRun
    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["compute_benchmark_metrics", "compute_metrics", "persist_metrics"]

_AUTOMATED_METHOD: Final = "deterministic computation over persisted objects"


def _normalized(name: str) -> str:
    return " ".join(name.split()).casefold()


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _metric(
    handle: AssessmentHandle,
    run_id: str,
    name: str,
    value: float,
    *,
    unit: str,
    method: str = _AUTOMATED_METHOD,
    evaluator: EvaluatorType = EvaluatorType.AUTOMATED,
    sample_size: int | None = None,
    notes: str | None = None,
) -> EvaluationResult:
    return EvaluationResult.model_validate(
        {
            "id": handle.objects.allocate("eval"),
            "assessment_id": handle.assessment_id,
            "workflow_run_id": run_id,
            "metric_name": name,
            "metric_value": value,
            "unit": unit,
            "evaluator_type": evaluator,
            "evaluation_method": method,
            "sample_size": sample_size,
            "notes": notes,
            "created_at": now(),
        }
    )


def _expected_entries(expected_dir: Path, filename: str, key: str) -> list[dict[str, Any]]:
    parsed: Any = yaml.safe_load((expected_dir / filename).read_text(encoding="utf-8"))
    return list(parsed[key])


def compute_metrics(
    handle: AssessmentHandle,
    run: WorkflowRun,
    *,
    expected_dir: Path | None = None,
) -> list[EvaluationResult]:
    """Compute every finding-quality and workflow metric this run supports.

    The benchmark metrics — false-negative rate and documentation-gap precision — are computed
    only when `expected_dir` points at an authored truth set; an ordinary assessment has no
    ground truth to compare against and simply gets the run-derived metrics.

    Identifiers are allocated as the results are built, so callers persist through
    `persist_metrics` in the same repository the handle carries.
    """
    from trace_ai.services.findings.approved import approved_findings

    repository = handle.objects
    all_findings = repository.list(Finding)
    approved = approved_findings(handle)
    decisions = [
        decision
        for decision in repository.list(ReviewerDecision)
        if decision.subject_type == "finding"
    ]
    stored_evidence = {reference.id for reference in repository.list(EvidenceReference)}
    results: list[EvaluationResult] = []

    # --- finding_evidence_coverage: every approved finding cites resolvable evidence.
    covered = [
        finding
        for finding in approved
        if all(evidence_id in stored_evidence for evidence_id in finding.evidence_ids)
    ]
    results.append(
        _metric(
            handle,
            run.id,
            "finding_evidence_coverage",
            _ratio(len(covered), len(approved)) if approved else 1.0,
            unit="percentage",
            sample_size=len(approved),
            notes=(
                "vacuously complete: zero approved findings is a successful outcome"
                if not approved
                else None
            ),
        )
    )

    # --- reviewer rates, derived from decisions rather than status alone. A finding edited and
    # then approved counts in both rates: the subjects are per-disposition sets.
    decided_subjects = {decision.subject_id for decision in decisions}
    by_disposition: dict[ReviewDisposition, set[str]] = {}
    for decision in decisions:
        by_disposition.setdefault(decision.disposition, set()).add(decision.subject_id)

    for name, disposition in (
        ("reviewer_acceptance_rate", ReviewDisposition.APPROVE),
        ("reviewer_rejection_rate", ReviewDisposition.REJECT),
        ("reviewer_edit_rate", ReviewDisposition.EDIT),
    ):
        results.append(
            _metric(
                handle,
                run.id,
                name,
                _ratio(len(by_disposition.get(disposition, set())), len(decided_subjects)),
                unit="percentage",
                method="ReviewerDecision records per subject; an edit then an approval counts "
                "in both rates",
                sample_size=len(decided_subjects),
                notes="no decided findings" if not decided_subjects else None,
            )
        )

    # --- duplicate and false-positive rates over the proposed set.
    duplicates = [finding for finding in all_findings if finding.duplicate_of_id is not None]
    rejected = [finding for finding in all_findings if finding.status is ObjectStatus.REJECTED]
    results.append(
        _metric(
            handle,
            run.id,
            "duplicate_finding_rate",
            _ratio(len(duplicates), len(all_findings)),
            unit="percentage",
            sample_size=len(all_findings),
        )
    )
    results.append(
        _metric(
            handle,
            run.id,
            "false_positive_rate",
            _ratio(len(rejected), len(all_findings)),
            unit="percentage",
            method="rejected candidates over proposed findings; the reviewer is the judge",
            sample_size=len(all_findings),
        )
    )

    # --- benchmark metrics, only against an authored truth set.
    if expected_dir is not None:
        results.extend(_benchmark_metrics(handle, run, expected_dir, approved))

    # --- workflow measures from the run and its executions.
    records = repository.list(ExecutionRecord)
    failed = [record for record in records if record.status is ExecutionStatus.FAILED]
    duration_ms = sum(record.duration_ms or 0 for record in records)
    results.append(
        _metric(
            handle,
            run.id,
            "execution_duration",
            duration_ms / 1000,
            unit="seconds",
            sample_size=len(records),
        )
    )
    results.append(
        _metric(
            handle,
            run.id,
            "model_call_count",
            float(run.total_model_calls),
            unit="count",
        )
    )
    results.append(
        _metric(
            handle,
            run.id,
            "estimated_cost",
            float(run.estimated_cost or 0),
            unit="dollars",
        )
    )
    results.append(
        _metric(
            handle,
            run.id,
            "node_failure_rate",
            _ratio(len(failed), len(records)),
            unit="percentage",
            sample_size=len(records),
        )
    )

    return results


def _benchmark_metrics(
    handle: AssessmentHandle,
    run: WorkflowRun,
    expected_dir: Path,
    approved: list[Finding],
) -> list[EvaluationResult]:
    """False-negative rate and documentation-gap precision, per DEC-056's matching rule."""
    repository = handle.objects
    component_names = {
        component.id: _normalized(component.name) for component in repository.list(Component)
    }
    requirement_by_mapping = {
        mapping.id: mapping.requirement_id for mapping in repository.list(ControlMapping)
    }

    expected_findings = _expected_entries(expected_dir, "expected-findings.yaml", "findings")
    finding_matches = match_findings(approved, expected_findings, component_names=component_names)
    unmatched_expected = finding_matches.missed
    consolidated = finding_matches.consolidated_count
    results = [
        _metric(
            handle,
            run.id,
            "false_negative_rate",
            _ratio(len(unmatched_expected), len(expected_findings)),
            unit="percentage",
            evaluator=EvaluatorType.BENCHMARK,
            method=(
                "expected findings unmatched over expected findings; a finding matches on the "
                "expected requirement_id and an affected component whose name matches "
                "(DEC-056); a consolidated finding scores full credit per matched expectation"
            ),
            sample_size=len(expected_findings),
            notes=(
                f"unmatched: {unmatched_expected or 'none'}; consolidated findings matching "
                f"more than one expectation: {consolidated}"
            ),
        )
    ]

    expected_gaps = _expected_entries(
        expected_dir, "expected-documentation-gaps.yaml", "documentation_gaps"
    )
    expected_gap_requirements = {str(entry["requirement_id"]) for entry in expected_gaps}
    produced_gaps = [
        gap
        for gap in repository.list(DocumentationGap)
        if gap.status is not ObjectStatus.SUPERSEDED
    ]
    gap_matches = match_gaps(
        produced_gaps, expected_gap_requirements, requirement_by_mapping=requirement_by_mapping
    )
    results.append(
        _metric(
            handle,
            run.id,
            "documentation_gap_precision",
            _ratio(len(gap_matches.matching), len(produced_gaps)),
            unit="percentage",
            evaluator=EvaluatorType.BENCHMARK,
            method=(
                "produced gaps matching an expected gap over produced gaps; a gap matches "
                "through the requirement its related mapping resolves to (DEC-056)"
            ),
            sample_size=len(produced_gaps),
            notes="no gaps produced" if not produced_gaps else None,
        )
    )
    return results


def compute_benchmark_metrics(
    handle: AssessmentHandle, run: WorkflowRun, *, expected_dir: Path
) -> list[EvaluationResult]:
    """The truth-set metrics alone, for a run whose run-derived metrics already exist.

    The evaluation node computes and persists the run-derived metrics inside the pipeline, where
    no truth set is available (nothing under `expected/` reaches a run, DEC-027). The harness
    tops the same run up with the benchmark metrics afterwards; computing everything again would
    duplicate the rows the node already persisted.
    """
    from trace_ai.services.findings.approved import approved_findings

    return _benchmark_metrics(handle, run, expected_dir, approved_findings(handle))


def persist_metrics(
    handle: AssessmentHandle, run: WorkflowRun, results: list[EvaluationResult]
) -> Path:
    """Store the rows and write the JSON summary to the `evaluation/` area.

    Separate from the user-facing report by directory (`current-architecture.md` section 5.16):
    `outputs/` is what a customer reads, `evaluation/` is what the project measures itself with.
    """
    with handle.objects.transaction():
        for result in results:
            handle.objects.save(result)

    summary = {
        "assessment_id": handle.assessment_id,
        "workflow_run_id": run.id,
        "metrics": [
            {
                "metric_name": result.metric_name,
                "metric_value": result.metric_value,
                "unit": result.unit,
                "evaluator_type": result.evaluator_type.value,
                "sample_size": result.sample_size,
                "notes": result.notes,
            }
            for result in results
        ],
    }
    path = handle.artifacts.area("evaluation") / f"metrics-{run.id}.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return path
