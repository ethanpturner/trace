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
import re
from typing import TYPE_CHECKING, Any, Final, cast

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
from trace_ai.services.evaluation.matching import (
    match_context,
    match_expected_mappings,
    match_findings,
    match_gaps,
    match_questions,
    match_threats,
    normalized_name,
)
from trace_ai.services.execution_ledger import ExecutionLedger

if TYPE_CHECKING:
    from decimal import Decimal
    from pathlib import Path

    from trace_ai.domain.execution import WorkflowRun
    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["compute_benchmark_metrics", "compute_metrics", "persist_metrics"]

_AUTOMATED_METHOD: Final = "deterministic computation over persisted objects"


def _normalized(name: str) -> str:
    return " ".join(name.split()).casefold()


_SEVERITY_RANK: dict[str, int] = {
    "informational": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _severity_concordance(
    approved: list[Finding],
    expected_findings: list[dict[str, Any]],
    matched: dict[str, list[str]],
) -> tuple[int, int, int] | None:
    """Reviewer severity against the truth set's guidance, over matched findings (#507, DEC-030).

    Returns `(matched_with_guidance, exact_agreements, within_one_level)`, or `None` when no
    matched finding carries guidance — a scenario without `severity_guidance` measures nothing
    here rather than scoring a spurious zero. A finding matching more than one expectation is
    held to the strictest guidance among them: under-rating the worst thing it stands for is the
    error that matters. `unassigned` cannot appear — the approval gate refuses it (DEC-030).
    """
    guidance_by_key = {
        str(entry["key"]): str(entry["severity_guidance"])
        for entry in expected_findings
        if entry.get("severity_guidance")
    }
    by_id = {finding.id: finding for finding in approved}
    matched_count = exact = adjacent = 0
    for key, finding_ids in matched.items():
        guidance = guidance_by_key.get(key)
        if guidance is None or guidance not in _SEVERITY_RANK:
            continue
        wanted = _SEVERITY_RANK[guidance]
        for finding_id in finding_ids:
            finding = by_id.get(finding_id)
            if finding is None or finding.severity.value not in _SEVERITY_RANK:
                continue
            matched_count += 1
            assigned = _SEVERITY_RANK[finding.severity.value]
            if assigned == wanted:
                exact += 1
            if abs(assigned - wanted) <= 1:
                adjacent += 1
    if matched_count == 0:
        return None
    return matched_count, exact, adjacent


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
    # The run row's totals are a snapshot written at the last pause, and this code runs inside
    # the final segment -- before complete() writes the closing counters -- so the segment's own
    # calls, cost, and tokens are missing from the row (#388). The ledger's counters() is the one
    # authoritative computation over the records this run wrote; reading it here keeps one
    # implementation, which is the property its own docstring asks for.
    counters = ExecutionLedger(handle, run).counters()
    results.append(
        _metric(
            handle,
            run.id,
            "model_call_count",
            float(cast("int", counters["total_model_calls"])),
            unit="count",
        )
    )
    results.append(
        _metric(
            handle,
            run.id,
            "estimated_cost",
            float(cast("Decimal | None", counters["estimated_cost"]) or 0),
            unit="dollars",
        )
    )
    counted_input = cast("int | None", counters["total_input_tokens"])
    counted_output = cast("int | None", counters["total_output_tokens"])
    if counted_input is not None or counted_output is not None:
        # Reported only when a provider actually reported spans (#329): an offline replay has
        # no token truth, and a zero row would be a default wearing a measurement's clothes.
        input_tokens = counted_input or 0
        output_tokens = counted_output or 0
        cache_read = cast("int | None", counters["total_cache_read_tokens"])
        cache_creation = cast("int | None", counters["total_cache_creation_tokens"])
        results.append(
            _metric(
                handle,
                run.id,
                "token_usage",
                float(input_tokens + output_tokens),
                unit="tokens",
                method="execution-record token totals as the provider reported them",
                notes=(
                    f"input {input_tokens}, output {output_tokens}, cache read "
                    f"{cache_read if cache_read is not None else 'unreported'}, "
                    f"cache creation "
                    f"{cache_creation if cache_creation is not None else 'unreported'}"
                ),
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


def _duplicate_miss_metrics(
    handle: AssessmentHandle,
    run: WorkflowRun,
    expected_dir: Path,
    *,
    component_names: dict[str, str],
) -> list[EvaluationResult]:
    """DEC-043's revisit trigger, given its instrument (#536, DEC-110).

    `duplicate_finding_rate` counts merges the deterministic rule *performed*, which structurally
    cannot measure a miss. A miss is only measurable against authored truth:
    `expected-duplicates.yaml` names pairs of finding identities — one weakness a run could
    plausibly split across two requirement lenses — and this scores the produced set against
    them. A pair is **evaluable** when both identities matched produced findings; a **miss**
    when the two sides resolve to distinct canonical findings (two unmerged statements of one
    weakness); **detected** when they share a canonical finding — consolidation or an explicit
    merge. No file, or no evaluable pair, yields no metric: unmeasured, never zero.
    """
    from trace_ai.domain.finding import canonical_finding_id

    path = expected_dir / "expected-duplicates.yaml"
    if not path.is_file():
        return []
    parsed: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    pairs: list[dict[str, Any]] = list((parsed or {}).get("duplicate_pairs", []))
    if not pairs:
        return []

    produced = handle.objects.list(Finding)

    def matching(identity: dict[str, Any]) -> list[Finding]:
        wanted_requirement = str(identity["requirement_id"])
        wanted_component = _normalized(str(identity["affected_component"]))
        return [
            finding
            for finding in produced
            if wanted_requirement in finding.requirement_ids
            and any(
                component_names.get(component_id) == wanted_component
                for component_id in finding.affected_component_ids
            )
        ]

    evaluable = 0
    missed: list[str] = []
    for pair in pairs:
        first = matching(pair["first"])
        second = matching(pair["second"])
        if not first or not second:
            continue
        evaluable += 1
        first_canonical = {canonical_finding_id(finding, produced) for finding in first}
        second_canonical = {canonical_finding_id(finding, produced) for finding in second}
        if not (first_canonical & second_canonical):
            missed.append(f"{pair['first']['requirement_id']}+{pair['second']['requirement_id']}")
    if not evaluable:
        return []
    return [
        _metric(
            handle,
            run.id,
            "duplicate_miss_rate",
            _ratio(len(missed), evaluable),
            unit="percentage",
            evaluator=EvaluatorType.BENCHMARK,
            method=(
                "authored duplicate pairs whose two identities resolved to distinct canonical "
                "findings, over pairs where both identities matched produced findings "
                "(DEC-110). Detection is consolidation or an explicit duplicate_of_id merge; "
                "a pair with an unmatched side is unevaluable and excluded"
            ),
            sample_size=evaluable,
            notes=f"missed pairs: {', '.join(missed) or 'none'}",
        )
    ]


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

    concordance = _severity_concordance(approved, expected_findings, finding_matches.matched)
    if concordance is not None:
        matched_count, exact, adjacent = concordance
        results.append(
            _metric(
                handle,
                run.id,
                "severity_concordance",
                _ratio(exact, matched_count),
                unit="percentage",
                evaluator=EvaluatorType.BENCHMARK,
                method=(
                    "matched findings whose reviewer-assigned severity equals the truth set's "
                    "severity_guidance, over matched findings with guidance (DEC-030's open "
                    "question, answered without a second reviewer). A finding matching more "
                    "than one expectation takes the strictest guidance among them"
                ),
                sample_size=matched_count,
                notes=(
                    f"exact: {exact}/{matched_count}; within one level: "
                    f"{adjacent}/{matched_count}. Severity is the reviewer's judgment "
                    f"(DEC-030); this measures agreement with the authored guidance, not "
                    f"correctness"
                ),
            )
        )

    results.extend(
        _duplicate_miss_metrics(handle, run, expected_dir, component_names=component_names)
    )

    # Annotator agreement (#530, DEC-112): a statement about the truth set itself, computed
    # beside the run metrics because the feed is where per-scenario numbers travel. Gates
    # nothing; absent while no second annotation set exists — unmeasured, never zero.
    from trace_ai.services.evaluation.agreement import compute_agreement, second_annotation_dir

    agreement = compute_agreement(expected_dir, second_annotation_dir(expected_dir.parent))
    if agreement is not None and agreement.pooled is not None:
        per_artifact = "; ".join(
            f"{entry.artifact}: {entry.in_both} shared, {entry.only_first} first-only, "
            f"{entry.only_second} second-only"
            for entry in agreement.artifacts
        )
        results.append(
            _metric(
                handle,
                run.id,
                "annotation_agreement",
                agreement.pooled,
                unit="percentage",
                evaluator=EvaluatorType.BENCHMARK,
                method=(
                    "Jaccard agreement between the authoritative truth set and the second "
                    "annotation set over DEC-056 identity forms, pooled across artifacts "
                    "(DEC-112). A statement about the truth set, not the run; the first set "
                    "stays authoritative and the statistic gates nothing"
                ),
                sample_size=sum(entry.union for entry in agreement.artifacts),
                notes=per_artifact,
            )
        )

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
    results.extend(_truth_metrics(handle, run, expected_dir))
    return results


def _truth_metrics(
    handle: AssessmentHandle,
    run: WorkflowRun,
    expected_dir: Path,
) -> list[EvaluationResult]:
    """The reserved truth-set metrics (#329), each emitted only where its truth is authored.

    A scenario without one of these files simply lacks the metric — absence is reported by the
    scorecard as unmeasured, never defaulted to a value nobody computed.
    """
    from trace_ai.domain.actor import Actor
    from trace_ai.domain.asset import Asset
    from trace_ai.domain.context_claim import ContextClaim
    from trace_ai.domain.data_flow import DataFlow
    from trace_ai.domain.question import Question
    from trace_ai.domain.threat import Threat
    from trace_ai.domain.trust_boundary import TrustBoundary

    repository = handle.objects
    results: list[EvaluationResult] = []

    component_names = {
        component.id: normalized_name(component.name) for component in repository.list(Component)
    }
    actor_names = {actor.id: normalized_name(actor.name) for actor in repository.list(Actor)}
    asset_names = {asset.id: normalized_name(asset.name) for asset in repository.list(Asset)}
    subject_names = {**component_names, **actor_names, **asset_names}

    context_file = expected_dir / "expected-context.yaml"
    if context_file.is_file():
        expected_document: dict[str, Any] = yaml.safe_load(context_file.read_text(encoding="utf-8"))
        produced_names = {
            "components": set(component_names.values()),
            "actors": set(actor_names.values()),
            "assets": set(asset_names.values()),
            "trust_boundaries": {
                normalized_name(boundary.name) for boundary in repository.list(TrustBoundary)
            },
        }
        produced_flows = {
            (
                component_names.get(flow.source_component_id, ""),
                component_names.get(flow.destination_component_id, ""),
            )
            for flow in repository.list(DataFlow)
        }
        produced_claims = {
            (
                subject_names.get(claim.subject_id or "", "system"),
                claim.predicate,
            )
            for claim in repository.list(ContextClaim)
        }
        context = match_context(
            expected_document,
            produced_names=produced_names,
            produced_flows=produced_flows,
            produced_claims=produced_claims,
        )
        breakdown = "; ".join(
            f"{name} {context.matched_by_type[name]}/{context.expected_by_type[name]}"
            for name in sorted(context.expected_by_type)
        )
        results.append(
            _metric(
                handle,
                run.id,
                "context_accuracy",
                _ratio(context.matched_count, context.expected_count)
                if context.expected_count
                else 1.0,
                unit="percentage",
                evaluator=EvaluatorType.BENCHMARK,
                method=(
                    "expected context entries matched over expected, by the truth file's own "
                    "keys: names for components, actors, assets, and boundaries; endpoint "
                    "names for flows; (subject, predicate) for claims. Extraction presence "
                    "only — field agreement is the checkpoint-1 reviewer's judgment"
                ),
                sample_size=context.expected_count,
                notes=breakdown,
            )
        )

    threats_file = expected_dir / "expected-threats.yaml"
    if threats_file.is_file():
        expected_threats = _expected_entries(expected_dir, "expected-threats.yaml", "threats")
        produced_references = [
            (
                {component_names.get(cid, "") for cid in threat.affected_component_ids},
                {asset_names.get(aid, "") for aid in threat.affected_asset_ids},
            )
            for threat in repository.list(Threat)
        ]
        threats = match_threats(expected_threats, produced_references=produced_references)
        results.append(
            _metric(
                handle,
                run.id,
                "threat_coverage",
                _ratio(threats.matched_count, threats.expected_count)
                if threats.expected_count
                else 1.0,
                unit="percentage",
                evaluator=EvaluatorType.BENCHMARK,
                method=(
                    "expected threats matched over expected; a produced threat matches when "
                    "its affected components and assets cover the entry's must_reference "
                    "lists by normalized name. Structural only — wording is never compared "
                    "(DEC-043 defers semantic comparison)"
                ),
                sample_size=threats.expected_count,
                notes=f"missed: {threats.missed_keys or 'none'}",
            )
        )

    mappings_file = expected_dir / "expected-control-mappings.yaml"
    if mappings_file.is_file():
        expected_mapping_doc: dict[str, Any] = yaml.safe_load(
            mappings_file.read_text(encoding="utf-8")
        )
        expected_entries = [
            (
                f"{entry.get('threat_key', '?')}:{applicable['requirement_id']}",
                str(applicable["requirement_id"]),
                str(applicable["expected_satisfaction"]),
            )
            for entry in expected_mapping_doc.get("mappings") or []
            for applicable in entry.get("applicable") or []
        ]
        produced_pairs = {
            (mapping.requirement_id, mapping.satisfaction_status.value)
            for mapping in repository.list(ControlMapping)
        }
        mappings_outcome = match_expected_mappings(expected_entries, produced=produced_pairs)
        results.append(
            _metric(
                handle,
                run.id,
                "requirement_mapping_accuracy",
                _ratio(mappings_outcome.matched_count, mappings_outcome.expected_count)
                if mappings_outcome.expected_count
                else 1.0,
                unit="percentage",
                evaluator=EvaluatorType.BENCHMARK,
                method=(
                    "expected (requirement, satisfaction) pairs matched by a produced mapping "
                    "stating both, over expected pairs; threat identity is not bound and the "
                    "must_not_conclude negatives are asserted by tests, not scored here"
                ),
                sample_size=mappings_outcome.expected_count,
                notes=f"missed: {mappings_outcome.missed_keys or 'none'}",
            )
        )

    questions_file = expected_dir / "expected-questions.yaml"
    if questions_file.is_file():
        expected_questions = _expected_entries(expected_dir, "expected-questions.yaml", "questions")
        gaps_file = expected_dir / "expected-documentation-gaps.yaml"
        paired_keys = (
            {
                str(entry["paired_question"])
                for entry in _expected_entries(
                    expected_dir, "expected-documentation-gaps.yaml", "documentation_gaps"
                )
                if entry.get("paired_question")
            }
            if gaps_file.is_file()
            else set()
        )
        requirements_by_threat: dict[str, set[str]] = {}
        for mapping in repository.list(ControlMapping):
            requirements_by_threat.setdefault(mapping.threat_id, set()).add(mapping.requirement_id)
        requirement_token = re.compile(r"req-[A-Z]+-\d+")
        produced_requirement_sets = [
            requirements_by_threat.get(question.related_object_id or "", set())
            | set(requirement_token.findall(question.question))
            for question in repository.list(Question)
        ]
        questions_outcome = match_questions(
            expected_questions,
            paired_keys=paired_keys,
            produced_requirement_sets=produced_requirement_sets,
        )
        results.append(
            _metric(
                handle,
                run.id,
                "clarifying_question_usefulness",
                _ratio(questions_outcome.matched_count, questions_outcome.expected_count)
                if questions_outcome.expected_count
                else 1.0,
                unit="percentage",
                evaluator=EvaluatorType.BENCHMARK,
                method=(
                    "expected questions a produced question bears on, over expected; a "
                    "produced question bears on its related threat's mapped requirements plus "
                    "any requirement its text names. Questions paired to a documentation gap "
                    "are excluded: one mapping routes to a gap or a question, never both "
                    "(DEC-013), and the pair documents the gap's conversion"
                ),
                sample_size=questions_outcome.expected_count,
                notes=(
                    "every expected question is a gap's paired question"
                    if not questions_outcome.expected_count
                    else f"missed: {questions_outcome.missed_keys or 'none'}"
                ),
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
