"""Report-quality metrics and the reviewer rubric, recorded distinctly (#111).

`evaluation-plan.md` section 7 gives Reports four measures: two computable — unsupported
statements and consistency — and two human judgements — readability and reviewer edits' quality.
`design-principles.md` section 15 warns against scores that look precise without improving
judgement, so this module keeps the two kinds apart structurally:

- **Computed report metrics** come from the consistency validator's outcomes and the rendered
  document, carry `evaluator_type: automated`, and are arithmetic over violations — nothing here
  infers quality.
- **Rubric scores** come from a person, carry `evaluator_type: reviewer` and an
  `evaluation_method` naming the rubric version, and are constrained to section 9's one-to-five
  range. **No readability or report-quality value is ever computed**: a heuristic readability
  score presented beside measured counts would borrow their authority, which is exactly the
  section 15 failure. A test scans this module for the absence.

The per-run summary gathers the roadmap Stage 5 counts available at this point and writes them
to the assessment's `evaluation/` area, beside the metric rows and never in `outputs/`.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.base import now
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus, ReviewDisposition
from trace_ai.domain.evaluation_result import EvaluationResult, EvaluatorType
from trace_ai.domain.execution import ExecutionRecord, ExecutionStatus
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import Question
from trace_ai.domain.reviewer_decision import ReviewerDecision

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from trace_ai.domain.execution import WorkflowRun
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.workflow.report_validation import ReportValidationOutcome

__all__ = [
    "RUBRIC_CATEGORIES",
    "RUBRIC_VERSION",
    "compute_report_metrics",
    "record_rubric",
    "write_summary",
]

RUBRIC_VERSION: Final = "reviewer-rubric-v1"

# Section 9's seven categories, scored one to five, plus qualitative comments. `report_quality`
# and every readability judgement live here and only here: recorded, never inferred.
RUBRIC_CATEGORIES: Final[tuple[str, ...]] = (
    "context_accuracy",
    "threat_quality",
    "finding_usefulness",
    "false_positives",
    "evidence_quality",
    "report_quality",
    "overall_confidence",
)

_FINDING_HEADING: Final = re.compile(r"^### (fnd-\S+):", re.MULTILINE)


def _metric(
    handle: AssessmentHandle,
    run_id: str,
    name: str,
    value: float,
    *,
    unit: str,
    method: str,
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


_SENTENCE_SPLIT: Final = re.compile(r"[.!?]+(?:\s|$)")


def _sentence_count(*passages: str) -> int:
    """Naive sentence segmentation over the agent-authored prose, for the rate's denominator."""
    return sum(
        1 for passage in passages for piece in _SENTENCE_SPLIT.split(passage) if piece.strip()
    )


def compute_report_metrics(
    handle: AssessmentHandle,
    run: WorkflowRun,
    *,
    sections_outcome: ReportValidationOutcome,
    rendered_outcome: ReportValidationOutcome,
    rendered_markdown: str,
    approved_count: int,
    prose_passages: Sequence[str] = (),
) -> list[EvaluationResult]:
    """The computable half of section 7's report measures. Arithmetic over the validator.

    Readability is deliberately absent: it is a reviewer judgement (section 9's rubric) and no
    heuristic stands in for it.
    """
    prose_sentences = _sentence_count(*prose_passages)
    violations = [*sections_outcome.violations, *rendered_outcome.violations]
    # Distinct identifiers, not violation rows: one invented `fnd-009` is flagged by both the
    # sections pass and the rendered-document pass, and counting it twice would report two
    # inventions for one.
    invented_tokens: set[str] = set()
    for violation in violations:
        if violation.check in {"unknown_identifier", "unapproved_finding_identifier"}:
            token = re.search(r"'([A-Za-z]+-[A-Za-z0-9-]+)'", violation.message)
            invented_tokens.add(token.group(1) if token else violation.message)
    invented = len(invented_tokens)
    severity_drift = sum(1 for violation in violations if violation.check == "severity_drift")
    rendered_findings = len(_FINDING_HEADING.findall(rendered_markdown))
    coverage = rendered_findings / approved_count if approved_count else 1.0

    return [
        _metric(
            handle,
            run.id,
            "unsupported_claim_count",
            float(sections_outcome.unsupported_statement_count),
            unit="count",
            method="report consistency validator over the generated sections (#107)",
        ),
        *(
            [
                _metric(
                    handle,
                    run.id,
                    "unsupported_claim_rate",
                    sections_outcome.unsupported_statement_count / prose_sentences,
                    unit="percentage",
                    method=(
                        "unsupported statements over the sentences of the agent-authored "
                        "prose sections, naively segmented (#329); the count row carries the "
                        "numerator alone"
                    ),
                    sample_size=prose_sentences,
                )
            ]
            if prose_sentences
            else []
        ),
        _metric(
            handle,
            run.id,
            "report_invented_finding_count",
            float(invented),
            unit="count",
            method=(
                "identifier violations from the report consistency validator; the roadmap "
                "Stage 4 target is zero"
            ),
        ),
        *(
            [
                _metric(
                    handle,
                    run.id,
                    "report_finding_coverage",
                    coverage,
                    unit="percentage",
                    method="finding entries rendered over findings approved",
                    sample_size=approved_count,
                )
            ]
            if approved_count
            else []
        ),
        _metric(
            handle,
            run.id,
            "report_severity_inconsistency_count",
            float(severity_drift),
            unit="count",
            method="severity statements in prose or the document differing from the objects",
        ),
    ]


def record_rubric(
    handle: AssessmentHandle,
    run: WorkflowRun,
    scores: dict[str, int],
    *,
    reviewer_id: str,
    comments: str | None = None,
) -> list[EvaluationResult]:
    """Store section 9's rubric: seven categories, one to five, from a person.

    Every category is required and every score bounded — a partial rubric or an out-of-range
    value is refused by name rather than stored looking complete. The rows carry
    `evaluator_type: reviewer` and the rubric version, so a judgement is never mistaken for a
    computed measure (`design-principles.md` section 15).
    """
    missing = sorted(set(RUBRIC_CATEGORIES) - set(scores))
    unknown = sorted(set(scores) - set(RUBRIC_CATEGORIES))
    if missing or unknown:
        raise ValueError(
            f"the rubric scores exactly the seven section 9 categories: missing {missing}, "
            f"not in the rubric {unknown}."
        )
    out_of_range = {name: value for name, value in scores.items() if not 1 <= value <= 5}
    if out_of_range:
        raise ValueError(f"rubric scores are one to five: {out_of_range}")

    results = [
        _metric(
            handle,
            run.id,
            f"rubric_{category}",
            float(scores[category]),
            unit="score",
            method=f"{RUBRIC_VERSION}: {category.replace('_', ' ')}, scored 1-5 by a reviewer",
            evaluator=EvaluatorType.REVIEWER,
            notes=(
                f"reviewer {reviewer_id}: {comments}" if comments else f"reviewer {reviewer_id}"
            ),
        )
        for category in RUBRIC_CATEGORIES
    ]
    with handle.objects.transaction():
        for result in results:
            handle.objects.save(result)
    return results


def write_summary(
    handle: AssessmentHandle,
    run: WorkflowRun,
    results: list[EvaluationResult],
) -> Path:
    """The per-run summary: every roadmap Stage 5 count available at this point.

    Counts come from the persisted objects and the run's own records; metric values come from
    the rows already computed, keyed by name so the summary cannot disagree with them. Written
    to `evaluation/`, never to the report directory.
    """
    repository = handle.objects
    findings = repository.list(Finding)
    decisions = [
        decision
        for decision in repository.list(ReviewerDecision)
        if decision.subject_type == "finding"
    ]
    records = repository.list(ExecutionRecord)
    by_name = {result.metric_name: result.metric_value for result in results}

    summary: dict[str, Any] = {
        "assessment_id": handle.assessment_id,
        "workflow_run_id": run.id,
        "counts": {
            "findings_proposed": len(findings),
            "findings_approved": sum(
                1
                for finding in findings
                if finding.status is ObjectStatus.APPROVED and finding.duplicate_of_id is None
            ),
            "findings_rejected": sum(
                1 for finding in findings if finding.status is ObjectStatus.REJECTED
            ),
            "findings_edited": len(
                {
                    decision.subject_id
                    for decision in decisions
                    if decision.disposition is ReviewDisposition.EDIT
                }
            ),
            "questions_generated": len(repository.list(Question)),
            "documentation_gaps": len(repository.list(DocumentationGap)),
            "model_calls": run.total_model_calls,
            "input_tokens": run.total_input_tokens or 0,
            "output_tokens": run.total_output_tokens or 0,
            "failures": sum(1 for record in records if record.status is ExecutionStatus.FAILED),
            "retries": sum(record.retry_number for record in records),
        },
        "metrics": {
            name: by_name[name]
            for name in (
                "finding_evidence_coverage",
                "false_positive_rate",
                "false_negative_rate",
                "unsupported_claim_count",
                "report_invented_finding_count",
                "execution_duration",
                "estimated_cost",
            )
            if name in by_name
        },
    }

    path = handle.artifacts.area("evaluation") / f"summary-{run.id}.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return path
