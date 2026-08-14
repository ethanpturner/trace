"""The baseline comparisons: a single model call over the same documents (DEC-074).

Roadmap Stage 4's decision gate asks whether the multi-stage pipeline beats a simpler prompt. The
two prompt baselines answer it honestly: each is one call through the same seam, over the same
source documents and the same requirements catalog the pipeline sees, emitting a schema-forced
findings list scored by the same structural matcher (DEC-056). No context model, no evidence
validation, no critical review, no human checkpoint — the difference between a baseline and Trace
is the pipeline, and the comparison is built so a skeptic re-running it from the repository finds
nothing tuned in Trace's favour.

**Schema-forced, never hand-normalized.** The baseline emits `BaselineFindings`; a response that
fails to validate is a schema failure recorded in the schema-validity rate, which is a result, not
an excuse. **Fairness ties go to the baseline** (DEC-074): it gets the catalog so it can cite
requirements, and it never gets the curated context — the checkpoint-ablated run is the
like-for-like comparator, and the full pipeline is the system as operated.

The result feed lands in the same tree as a pipeline run, keyed by the baseline as its condition
(`baseline-generic`, `baseline-structured`), so the scorecard reads baselines and Trace through one
format. STRIDE GPT is not here: it cannot run through the seam, and a wrapper would measure the
wrapper (DEC-074) — it belongs in the portfolio write-up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

from trace_ai.domain.proposals.baseline import BaselineFindings
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

__all__ = ["BASELINES", "BaselineOutcome", "run_baseline"]

# The two prompt baselines DEC-074 fixes, by the condition name their feed is keyed under and the
# prompt each composes. The ablation family (the third baseline group) is the harness's own, run
# through `trace evaluate --ablate` rather than here.
BASELINES: dict[str, str] = {
    "baseline-generic": "generic-security-review",
    "baseline-structured": "structured-single-pass",
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
    response: BaselineFindings | None = None,
) -> BaselineOutcome:
    """Run one baseline over one scenario and score it against the truth set.

    `response` supplies a recorded baseline output for offline replay; without it the baseline
    calls the resolved profile's model. Either way the call goes through the seam, so a recorded
    baseline and a live one are the same path with a different source (DEC-074).
    """
    if baseline not in BASELINES:
        raise BaselineError(
            f"{baseline!r} is not a baseline; the two are {', '.join(sorted(BASELINES))}"
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
        schema=BaselineFindings,
        settings=GenerationSettings(creativity=Creativity.LOW),
    )

    schema_valid = outcome.succeeded
    produced = list(outcome.value.findings) if isinstance(outcome, ModelSuccess) else []
    scored = _score(entry, produced)
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
    expected = yaml.safe_load(
        (entry.expected_dir / "expected-findings.yaml").read_text(encoding="utf-8")
    )["findings"]

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
    return {"matched": matched, "missed": missed, "spurious": spurious, "metrics": metrics}


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
    feed = {
        "feed_version": "1",
        "scenario": entry.slug,
        "condition": baseline,
        "label": label,
        "baseline": baseline,
        "authoritative": False,
        "schema_valid": schema_valid,
        "metrics": {
            "schema_validity_rate": {"value": 1.0 if schema_valid else 0.0},
            "false_negative_rate": {"value": scored["metrics"]["false_negative_rate"]},
            "spurious_finding_count": {"value": scored["metrics"]["spurious_finding_count"]},
        },
        "items": {
            "findings": {
                "matched": scored["matched"],
                "missed": scored["missed"],
                "spurious": [entry_["title"] for entry_ in scored["spurious"]],
            }
        },
    }
    target = root / entry.slug / baseline / f"{label}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(feed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
