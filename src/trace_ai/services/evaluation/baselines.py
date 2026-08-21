"""The baseline comparisons: a single model call over the same documents (DEC-074).

Roadmap Stage 4's decision gate asks whether the multi-stage pipeline beats a simpler prompt. The
prompt baselines answer it honestly: each is one call through the same seam, over the same
source documents and the same requirements catalog the pipeline sees, emitting a schema-forced
output scored by the same parallel matchers (DEC-056). No context model, no evidence
validation, no critical review, no human checkpoint — the difference between a baseline and Trace
is the pipeline, and the comparison is built so a skeptic re-running it from the repository finds
nothing tuned in Trace's favour.

The two DEC-074 baselines emit `BaselineFindings`: findings only, the pipeline's discipline
priced. The third — `baseline-single-pass` — prices the pipeline's *structure*: the whole
assessment in one call, one combined `BaselineAssessment` schema (DEC-074's open question,
decided), so a disciplined single pass can express a gap or a question where a finding is not
supported, and its restraint is measurable rather than only an empty list.

**Schema-forced, never hand-normalized.** A response that fails to validate is a schema failure
recorded in the schema-validity rate, which is a result, not an excuse. **Fairness ties go to
the baseline** (DEC-074): it gets the catalog so it can cite requirements, and it never gets the
curated context — the checkpoint-ablated run is the like-for-like comparator, and the full
pipeline is the system as operated.

The result feed lands in the same tree as a pipeline run, keyed by the baseline as its condition
(`baseline-generic`, `baseline-structured`, `baseline-single-pass`), so the scorecard reads
baselines and Trace through one format. STRIDE GPT is not here: it cannot run through the seam,
and a wrapper would measure the wrapper (DEC-074) — it belongs in the portfolio write-up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

from trace_ai.domain.proposals.baseline import BaselineAssessment, BaselineFindings
from trace_ai.infrastructure.model.factory import build_model
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.seam import Creativity, GenerationSettings, ModelSuccess
from trace_ai.services.evaluation.matching import normalized_name
from trace_ai.services.evaluation.registry import scenario as load_scenario
from trace_ai.services.prompts import PromptRegistry
from trace_ai.services.requirements.loader import current_version, load_catalog

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from trace_ai.services.evaluation.registry import Scenario

__all__ = ["BASELINES", "BASELINE_SCHEMAS", "BaselineOutcome", "run_baseline"]

# The prompt baselines, by the condition name their feed is keyed under and the prompt each
# composes. The first two are DEC-074's; the third prices the agent-set structure itself — the
# whole assessment in one call, one combined schema, DEC-074's open question decided. The
# ablation family (the remaining baseline group) is the harness's own, run through
# `trace evaluate --ablate` rather than here.
BASELINES: dict[str, str] = {
    "baseline-generic": "generic-security-review",
    "baseline-structured": "structured-single-pass",
    "baseline-single-pass": "single-pass-assessment",
}

# What each baseline is schema-forced to. The finding-only shape is the two DEC-074 baselines'
# comparison surface; the combined shape is the structural baseline's whole job.
BASELINE_SCHEMAS: dict[str, type[BaselineFindings] | type[BaselineAssessment]] = {
    "baseline-generic": BaselineFindings,
    "baseline-structured": BaselineFindings,
    "baseline-single-pass": BaselineAssessment,
}


class BaselineError(RuntimeError):
    """A baseline the runner cannot execute, with the reason stated."""


@dataclass(slots=True)
class BaselineOutcome:
    """What one baseline run produced, and where its feed landed."""

    scenario: str
    baseline: str
    label: str
    schema_valid: bool
    matched: dict[str, list[str]] = field(default_factory=dict)
    missed: list[str] = field(default_factory=list)
    spurious: list[dict[str, str]] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    feed_path: Path | None = None


def _catalog_text(catalog_version: str) -> str:
    """The requirement identifiers and titles, the citation surface the baseline is given."""
    catalog = load_catalog(catalog_version)
    lines = [f"- {req.id}: {req.title}" for req in catalog.requirements]
    return "\n".join(lines)


def _documents_text(entry: Scenario) -> str:
    """Every input document, fenced by filename, the same material the pipeline ingests."""
    blocks: list[str] = []
    for path in sorted(entry.input_dir.iterdir()):
        if path.is_file():
            blocks.append(f"### {path.name}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(blocks)


def run_baseline(
    slug: str,
    baseline: str,
    *,
    label: str,
    profile_name: str = "offline-fake",
    registry_path: Path | None = None,
    results_root: Path | None = None,
    response: BaselineFindings | BaselineAssessment | None = None,
    record_to: Path | None = None,
) -> BaselineOutcome:
    """Run one baseline over one scenario and score it against the truth set.

    `response` supplies a recorded baseline output for offline replay; without it the baseline
    calls the resolved profile's model. Either way the call goes through the seam, so a recorded
    baseline and a live one are the same path with a different source (DEC-074).

    `record_to` writes the successful response where the replay reads baseline recordings
    (DEC-100): the bare `BaselineFindings` shape `recorded/baselines/` already holds, not the
    #461 envelope — the baseline replay path predates the envelope and reads this shape. A
    failed call records nothing; the schema failure is the recorded result, in the feed.
    """
    if baseline not in BASELINES:
        raise BaselineError(
            f"{baseline!r} is not a baseline; the baselines are {', '.join(sorted(BASELINES))}"
        )
    entry = load_scenario(slug, registry_path=registry_path)
    if not entry.has_outcome_truth:
        raise BaselineError(
            f"scenario {slug!r} has no outcome-side truth to score a baseline against"
        )

    prompt_id = BASELINES[baseline]
    catalog_version = _contract_catalog_version(entry) or current_version()
    registry = PromptRegistry()
    composed = registry.compose(
        prompt_id,
        "v1",
        {
            "input.catalog": _catalog_text(catalog_version),
            "input.documents": _documents_text(entry),
        },
    )

    profile = resolve_profile(profile_name)
    responses = [response] if response is not None else []
    model = build_model(profile, responses=responses)
    outcome = model.generate(
        prompt=composed.text,
        schema=BASELINE_SCHEMAS[baseline],
        settings=GenerationSettings(creativity=Creativity.LOW),
    )

    schema_valid = outcome.succeeded
    value = outcome.value if isinstance(outcome, ModelSuccess) else None
    produced = (
        list(value.findings) if isinstance(value, (BaselineFindings, BaselineAssessment)) else []
    )
    if record_to is not None and value is not None:
        record_to.parent.mkdir(parents=True, exist_ok=True)
        record_to.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")
    scored = _score(entry, produced)
    if isinstance(value, BaselineAssessment):
        scored = _score_assessment_extras(entry, value, scored)
    feed_path = _export_feed(
        entry,
        baseline=baseline,
        label=label,
        schema_valid=schema_valid,
        scored=scored,
        results_root=results_root,
    )
    return BaselineOutcome(
        scenario=entry.slug,
        baseline=baseline,
        label=label,
        schema_valid=schema_valid,
        matched=scored["matched"],
        missed=scored["missed"],
        spurious=scored["spurious"],
        metrics=scored["metrics"],
        feed_path=feed_path,
    )


def _contract_catalog_version(entry: Scenario) -> str | None:
    contract = entry.expected_dir / "evaluation-contract.yaml"
    if not contract.is_file():
        return None
    parsed = yaml.safe_load(contract.read_text(encoding="utf-8"))
    version = parsed.get("catalog_version")
    return str(version) if version is not None else None


def _score(entry: Scenario, produced: Sequence[Any]) -> dict[str, Any]:
    """Match baseline findings to the expected set on requirement and component name (DEC-056).

    A baseline finding carries the component *name*, so the match is a direct comparison against
    the expected `affected_component` — no context model, no identifiers to resolve.
    """
    expected_all = yaml.safe_load(
        (entry.expected_dir / "expected-findings.yaml").read_text(encoding="utf-8")
    )["findings"]
    # A baseline has no reviewer and can never resolve a contradiction, so an expectation
    # conditioned on resolution (DEC-133) is never reachable here: it leaves the denominator,
    # and a baseline finding naming the pair chose a side of an unresolved contradiction
    # silently — scenario section 16's stated failure — so it falls through to spurious.
    from trace_ai.services.evaluation.matching import partition_conditional

    expected, conditional_unreached = partition_conditional(expected_all, resolution_supplied=False)

    produced_keys = [
        (finding.requirement_id, normalized_name(finding.affected_component))
        for finding in produced
    ]
    matched: dict[str, list[str]] = {}
    missed: list[str] = []
    consumed: set[int] = set()
    for entry_ in expected:
        key = str(entry_["key"])
        want = (str(entry_["requirement_id"]), normalized_name(str(entry_["affected_component"])))
        hits = [i for i, produced_key in enumerate(produced_keys) if produced_key == want]
        if hits:
            matched[key] = [produced[i].title for i in hits]
            consumed.update(hits)
        else:
            missed.append(key)

    spurious = [
        {
            "requirement_id": produced[i].requirement_id,
            "affected_component": produced[i].affected_component,
            "title": produced[i].title,
        }
        for i in range(len(produced))
        if i not in consumed
    ]
    denominator = len(expected)
    metrics = {
        "false_negative_rate": (len(missed) / denominator) if denominator else 0.0,
        "spurious_finding_count": float(len(spurious)),
    }
    return {
        "matched": matched,
        "missed": missed,
        "spurious": spurious,
        "conditional_unreached": conditional_unreached,
        "metrics": metrics,
    }


def _score_assessment_extras(
    entry: Scenario, value: BaselineAssessment, scored: dict[str, Any]
) -> dict[str, Any]:
    """Score the single-pass baseline's gaps and questions against the truth set, in parallel.

    The same shape as the finding scorer: requirement-identifier matching, no wording compared,
    no identifiers to resolve. `documentation_gap_recall` mirrors the pipeline metric —
    expected gap requirements reached, over the expected set (DEC-147) — and
    `question_usefulness` mirrors the pipeline's: expected questions matched by requirement,
    over the expected questions that are not another gap's `paired_question` (the pipeline's
    denominator rule, applied here so the two columns mean the same thing). Threats and
    components are counted, never matched: the finding, gap, and question layers are where the
    truth sets bind, and a parallel threat matcher would be a second implementation of
    `match_threats` waiting to drift.
    """
    expected_gaps = (
        yaml.safe_load(
            (entry.expected_dir / "expected-documentation-gaps.yaml").read_text(encoding="utf-8")
        ).get("documentation_gaps")
        or []
    )
    expected_questions_doc = (
        yaml.safe_load(
            (entry.expected_dir / "expected-questions.yaml").read_text(encoding="utf-8")
        ).get("questions")
        or []
    )

    expected_gap_requirements = {str(gap["requirement_id"]) for gap in expected_gaps}
    produced_gap_requirements = [gap.requirement_id for gap in value.documentation_gaps]
    covered_gap_requirements = expected_gap_requirements & set(produced_gap_requirements)

    paired = {str(gap["paired_question"]) for gap in expected_gaps if gap.get("paired_question")}
    scoreable_questions = [
        question for question in expected_questions_doc if str(question.get("key")) not in paired
    ]
    produced_question_requirements = {question.requirement_id for question in value.questions}
    question_hits = [
        str(question["key"])
        for question in scoreable_questions
        if str(question.get("requirement_id")) in produced_question_requirements
    ]

    metrics = dict(scored["metrics"])
    if expected_gap_requirements:
        metrics["documentation_gap_recall"] = len(covered_gap_requirements) / len(
            expected_gap_requirements
        )
    metrics["documentation_gaps_produced"] = float(len(produced_gap_requirements))
    metrics["question_usefulness"] = (
        len(question_hits) / len(scoreable_questions) if scoreable_questions else 0.0
    )
    metrics["component_count"] = float(len(value.components))
    metrics["threat_count"] = float(len(value.threats))
    return {
        **scored,
        "metrics": metrics,
        "extra_items": {
            "documentation_gaps": {
                "produced": produced_gap_requirements,
                "matched_requirements": sorted(covered_gap_requirements),
            },
            "questions": {"matched_expected": question_hits},
        },
    }


def _export_feed(
    entry: Scenario,
    *,
    baseline: str,
    label: str,
    schema_valid: bool,
    scored: dict[str, Any],
    results_root: Path | None,
) -> Path:
    from trace_ai.services.evaluation.harness import RESULTS_ROOT

    root = results_root if results_root is not None else RESULTS_ROOT
    metrics: dict[str, dict[str, float]] = {
        "schema_validity_rate": {"value": 1.0 if schema_valid else 0.0},
    }
    for name, metric_value in scored["metrics"].items():
        metrics[name] = {"value": metric_value}
    items: dict[str, Any] = {
        "findings": {
            "matched": scored["matched"],
            "missed": scored["missed"],
            "spurious": [entry_["title"] for entry_ in scored["spurious"]],
            "conditional_unreached": scored.get("conditional_unreached") or [],
        }
    }
    items.update(scored.get("extra_items") or {})
    feed = {
        "feed_version": "1",
        "scenario": entry.slug,
        "condition": baseline,
        "label": label,
        "baseline": baseline,
        "authoritative": False,
        "schema_valid": schema_valid,
        "metrics": metrics,
        "items": items,
    }
    target = root / entry.slug / baseline / f"{label}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(feed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
