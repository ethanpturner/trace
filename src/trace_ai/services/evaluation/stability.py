"""Ablation sets and run-to-run stability (evaluation-plan section 14, DEC-077).

Two measurements share this module because both are families of harness runs read together.

**The ablation set** runs the pipeline with each removed component in turn — evidence
validation, critical review, context approval — against the authoritative run, so the decision
gate's question (does each stage earn its place?) is answered per scenario. Every ablated run is
non-authoritative and named (DEC-012, DEC-031); the comparison is what each removal changed.

**Stability is measured from live runs, never replay.** DEC-077 is explicit that recorded-replay
stability measures nothing — replay is deterministic by construction, so its variance is zero and
means nothing. `run_stability` therefore refuses the offline profile rather than reporting a zero
that reads as a result: five identical replays are not evidence of a stable system. The
aggregation `summarize_runs` is a pure function over run feeds, so the protocol's machinery is
tested on synthetic inputs and runs for real only when an operator drives it live, manually,
having seen the cost — which is where DEC-077 puts it.

Stability gates nothing (DEC-077): the summary is reported, never thresholded. A gate would create
pressure to reduce *measured* variance, and the cheapest reductions reduce the measurement rather
than the instability.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from trace_ai.services.evaluation.harness import run_scenario
from trace_ai.services.evaluation.registry import scenario as load_scenario

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = [
    "ABLATION_SET",
    "AblationComparison",
    "StabilityError",
    "StabilitySummary",
    "run_ablation_set",
    "run_stability",
    "summarize_runs",
]

# The section-14 ablation family, in report order. Each is one removed component; the empty tuple
# is the authoritative run the others are read against.
ABLATION_SET: tuple[str, ...] = (
    "no-evidence-validation",
    "no-critical-review",
    "no-context-approval",
)

_OFFLINE_PROFILE = "offline-fake"


class StabilityError(RuntimeError):
    """A stability run the protocol refuses, with the reason stated."""


# -- ablation set ------------------------------------------------------------------------------


@dataclass(slots=True)
class AblationComparison:
    """The authoritative run and each ablation, read together for one scenario."""

    scenario: str
    label: str
    authoritative: dict[str, float] = field(default_factory=dict)
    ablations: dict[str, dict[str, float]] = field(default_factory=dict)

    def delta(self, ablation: str, metric: str) -> float | None:
        """How the ablation moved a metric from the authoritative run, or None if either lacks it."""
        base = self.authoritative.get(metric)
        removed = self.ablations.get(ablation, {}).get(metric)
        if base is None or removed is None:
            return None
        return removed - base


def _metrics_of(feed_path: Path | None) -> dict[str, float]:
    if feed_path is None:
        return {}
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    return {name: entry["value"] for name, entry in feed.get("metrics", {}).items()}


def run_ablation_set(
    slug: str,
    *,
    data_root: Path,
    label: str,
    results_root: Path | None = None,
    profile_name: str = _OFFLINE_PROFILE,
    ablations: Sequence[str] = ABLATION_SET,
) -> AblationComparison:
    """Run the authoritative pipeline and each ablation for a scenario, and read them together.

    Offline by construction: each run replays the scenario's recording. An ablation removes
    nodes rather than changing the model, so the same recording drives the authoritative run and
    the ablations — the harness drops the recordings the removed agents would have consumed.
    """
    comparison = AblationComparison(scenario=slug, label=label)
    authoritative = run_scenario(
        slug,
        data_root=data_root / "authoritative",
        label=label,
        condition="authoritative",
        profile_name=profile_name,
        results_root=results_root,
        stop_after_findings=True,
    )
    comparison.authoritative = _metrics_of(authoritative.feed_path)

    for ablation in ablations:
        run = run_scenario(
            slug,
            data_root=data_root / ablation,
            label=label,
            condition=ablation,
            ablations=[ablation],
            profile_name=profile_name,
            results_root=results_root,
            stop_after_findings=True,
        )
        comparison.ablations[ablation] = _metrics_of(run.feed_path)
    return comparison


# -- stability ---------------------------------------------------------------------------------


@dataclass(slots=True)
class StabilitySummary:
    """Variance per metric and agreement per expected item, over n runs (DEC-077)."""

    scenario: str
    n: int
    metric_mean: dict[str, float] = field(default_factory=dict)
    metric_stdev: dict[str, float] = field(default_factory=dict)
    item_agreement: dict[str, int] = field(default_factory=dict)
    """Each expected finding key mapped to the number of the n runs that matched it."""

    defaulted_decisions: int = 0
    """Reviewer decisions that fell back to approve-as-generated because no recorded decision
    matched the run's regenerated subject (DEC-077). Part of the result so the substitution is
    visible."""

    @property
    def unanimous(self) -> list[str]:
        return sorted(key for key, count in self.item_agreement.items() if count == self.n)

    @property
    def flickering(self) -> list[str]:
        return sorted(key for key, count in self.item_agreement.items() if 0 < count < self.n)


def summarize_runs(scenario: str, feeds: Sequence[dict[str, Any]]) -> StabilitySummary:
    """Aggregate n run feeds into per-metric variance and per-item agreement.

    A pure function over feeds so the protocol is testable without live runs. The per-item
    agreement counts, over which expected finding each run matched, are what make a variance
    number diagnosable — "F1 std-dev 0.04" cannot be acted on and "FND-UW-01 matched in 3 of 5"
    can.
    """
    if not feeds:
        raise StabilityError("no runs to summarize")
    summary = StabilitySummary(scenario=scenario, n=len(feeds))

    metric_names = {name for feed in feeds for name in feed.get("metrics", {})}
    for name in sorted(metric_names):
        values = [
            float(feed["metrics"][name]["value"])
            for feed in feeds
            if name in feed.get("metrics", {})
        ]
        summary.metric_mean[name] = statistics.fmean(values)
        summary.metric_stdev[name] = statistics.pstdev(values) if len(values) > 1 else 0.0

    for feed in feeds:
        matched = (feed.get("items") or {}).get("findings", {}).get("matched", {})
        for key in matched:
            summary.item_agreement[key] = summary.item_agreement.get(key, 0) + 1
        summary.defaulted_decisions += int(feed.get("defaulted_decisions", 0))
    return summary


def run_stability(
    slug: str,
    *,
    n: int,
    data_root: Path,
    label: str,
    profile_name: str,
    results_root: Path | None = None,
) -> StabilitySummary:
    """Run a scenario n times live and summarize the variance (DEC-077).

    Refuses the offline profile: replay is deterministic, so n identical replays report zero
    variance and measure nothing. Live runs are manual and priced up front; this is the path an
    operator drives, and the summary it returns gates nothing.
    """
    if profile_name == _OFFLINE_PROFILE:
        raise StabilityError(
            "stability measures live run-to-run variance and refuses the offline profile: "
            "replay is deterministic, so its variance is zero by construction and measures "
            "nothing (DEC-077). Drive it with a live model profile, manually."
        )
    _ = load_scenario(slug)  # refuse an unknown slug before spending anything
    feeds: list[dict[str, Any]] = []
    for index in range(n):
        outcome = run_scenario(
            slug,
            data_root=data_root / f"run-{index + 1}",
            label=f"{label}-{index + 1}",
            condition="stability",
            profile_name=profile_name,
            results_root=results_root,
        )
        if outcome.feed_path is not None:
            feeds.append(json.loads(outcome.feed_path.read_text(encoding="utf-8")))
    return summarize_runs(slug, feeds)
