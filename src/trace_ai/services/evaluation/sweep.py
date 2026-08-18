"""The one offline sweep the committed evaluation pages read (DEC-076).

The scorecard renders it per scenario and condition; the comparison table collapses it per tool.
Both stay in step because they consume the same feeds from the same runs. `collect_feeds` runs the
sweep; `dump_feeds`/`load_feeds` let a caller run it once and render more than one page from the
result, which is how CI avoids sweeping the same recordings twice per pull request.

Offline throughout: the recorded runs need no provider key, which the CI constraint requires.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from trace_ai.services.evaluation.baselines import BASELINES, run_baseline
from trace_ai.services.evaluation.harness import run_scenario
from trace_ai.services.evaluation.registry import load_registry

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["collect_feeds", "dump_feeds", "load_feeds"]


def _baseline_response(scenario_path: Path, condition: str) -> Path | None:
    recording = scenario_path / "recorded" / "baselines" / f"{condition}.json"
    return recording if recording.is_file() else None


def collect_feeds(results_root: Path) -> list[dict[str, object]]:
    """Run every recorded scenario and baseline into `results_root`, and return their feeds."""
    feeds: list[dict[str, object]] = []

    for entry in load_registry():
        for condition in ("clean", *entry.conditions):
            if not entry.has_recording_for(condition):
                continue
            outcome = run_scenario(
                entry.slug,
                data_root=results_root / "work" / entry.slug / condition,
                label="scorecard",
                condition=condition,
                results_root=results_root / "feeds",
            )
            if outcome.feed_path is not None:
                feeds.append(json.loads(outcome.feed_path.read_text(encoding="utf-8")))

        if not entry.has_outcome_truth:
            continue
        for condition in sorted(BASELINES):
            from trace_ai.services.evaluation.baselines import BASELINE_SCHEMAS

            recording = _baseline_response(entry.path, condition)
            if recording is None:
                continue
            response = BASELINE_SCHEMAS[condition].model_validate_json(
                recording.read_text(encoding="utf-8")
            )
            baseline = run_baseline(
                entry.slug,
                condition,
                label="scorecard",
                response=response,
                results_root=results_root / "feeds",
            )
            if baseline.feed_path is not None:
                feeds.append(json.loads(baseline.feed_path.read_text(encoding="utf-8")))

    return feeds


def dump_feeds(feeds: list[dict[str, object]], path: Path) -> None:
    """Write a swept feed list so another process can render from it without re-sweeping."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(feeds), encoding="utf-8")


def load_feeds(path: Path) -> list[dict[str, object]]:
    """Read a feed list written by `dump_feeds`. Both renderers sort feeds, so order is immaterial."""
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError(f"{path} does not hold a feed list")
    return loaded
