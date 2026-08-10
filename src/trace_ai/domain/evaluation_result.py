"""`EvaluationResult`: one measured quality or performance result (section 28).

Promoted from `data-model.md` section 40's deferred list by DEC-056, because #110's metrics made
the promotion unavoidable: a metric with no persisted object is a print statement, and
`evaluation-plan.md` section 3 requires every evaluation to be comparable across versions — which
is a property of rows, not of console output.

**`evaluator_type` says who judged.** `automated` is a deterministic computation over persisted
objects; `benchmark` is a comparison against an authored truth set; `reviewer` is a human rubric
score. A model-based comparative evaluator, where one is ever used, is labelled model-generated
in `evaluation_method` and never presented as ground truth (`agent-design.md` section 21).

**`metric_name` is section 28's vocabulary.** The initial names are documented there and carried
as `INITIAL_METRIC_NAMES`; the field accepts others because the document's list is explicitly
"initial", but the known set is what dashboards and regressions key on.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.identifiers import AssessmentId, EvaluationResultId, WorkflowRunId

__all__ = ["INITIAL_METRIC_NAMES", "EvaluationResult", "EvaluatorType"]


class EvaluatorType(StrEnum):
    """Who produced the judgment (section 28's field description)."""

    AUTOMATED = "automated"
    REVIEWER = "reviewer"
    BENCHMARK = "benchmark"


# Section 28's initial metric names, as documented. Others are permitted; these are the ones the
# evaluation plan's targets and regressions key on.
INITIAL_METRIC_NAMES: Final[tuple[str, ...]] = (
    "finding_evidence_coverage",
    "unsupported_claim_count",
    "reviewer_acceptance_rate",
    "reviewer_rejection_rate",
    "reviewer_edit_rate",
    "duplicate_finding_rate",
    "clarifying_question_usefulness",
    "threat_coverage",
    "requirement_mapping_accuracy",
    "execution_duration",
    "model_call_count",
    "estimated_cost",
    "node_failure_rate",
)


class EvaluationResult(DomainModel):
    """A measured quality or performance result (section 28)."""

    id: EvaluationResultId
    assessment_id: AssessmentId
    workflow_run_id: WorkflowRunId

    metric_name: str = Field(min_length=1)
    metric_value: float
    unit: str | None = None
    """Percentage, count, seconds, dollars."""

    evaluator_type: EvaluatorType
    evaluation_method: str = Field(min_length=1)
    """How the result was measured — the matching rule, the formula, or the rubric. A metric
    means nothing without it (DEC-056)."""

    sample_size: int | None = Field(default=None, ge=0)
    notes: str | None = None
    created_at: datetime
