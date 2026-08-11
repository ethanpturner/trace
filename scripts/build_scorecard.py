"""Regenerate the evaluation scorecard from the recorded runs (DEC-076).

    uv run python scripts/build_scorecard.py

Runs every recorded scenario through the harness, every baseline over every scenario with an
outcome truth set, writes the metrics-only feeds to a temporary results tree, and renders the
static scorecard to docs/eval/scorecard.html. Deterministic and offline: no provider, no key, no
network, and a pinned generation date so the committed page changes only when a number does.

The feeds are the real input and are regenerable (gitignored); the rendered page is committed so
its history is the git history. CI regenerates it and fails if it drifts from the committed copy.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.baselines import BASELINES, run_baseline
from trace_ai.services.evaluation.harness import run_scenario
from trace_ai.services.evaluation.registry import load_registry
from trace_ai.services.evaluation.scorecard import render_scorecard

OUTPUT = PROJECT_ROOT / "docs" / "eval" / "scorecard.html"
# Pinned so the committed page changes only when a metric does, never on the clock.
GENERATED_AT = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


def _baseline_response(scenario_path: Path, condition: str) -> Path | None:
    recording = scenario_path / "recorded" / "baselines" / f"{condition}.json"
    return recording if recording.is_file() else None


def build(results_root: Path) -> str:
    feeds: list[dict[str, object]] = []

    for entry in load_registry():
        if entry.has_recording:
            outcome = run_scenario(
                entry.slug,
                data_root=results_root / "work" / entry.slug,
                label="scorecard",
                results_root=results_root / "feeds",
            )
            if outcome.feed_path is not None:
                feeds.append(json.loads(outcome.feed_path.read_text(encoding="utf-8")))

        if not entry.has_outcome_truth:
            continue
        for condition in sorted(BASELINES):
            from trace_ai.domain.proposals.baseline import BaselineFindings

            recording = _baseline_response(entry.path, condition)
            if recording is None:
                continue
            response = BaselineFindings.model_validate_json(recording.read_text(encoding="utf-8"))
            baseline = run_baseline(
                entry.slug,
                condition,
                label="scorecard",
                response=response,
                results_root=results_root / "feeds",
            )
            if baseline.feed_path is not None:
                feeds.append(json.loads(baseline.feed_path.read_text(encoding="utf-8")))

    return render_scorecard(feeds, generated_at=GENERATED_AT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and fail if it differs from the committed page, without writing",
    )
    args = parser.parse_args(argv)

    results_root = Path(tempfile.mkdtemp(prefix="trace-scorecard-"))
    rendered = build(results_root)

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if rendered != current:
            print(
                "the committed scorecard is stale; run `uv run python scripts/build_scorecard.py`",
                file=sys.stderr,
            )
            return 1
        print("the committed scorecard is current")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
