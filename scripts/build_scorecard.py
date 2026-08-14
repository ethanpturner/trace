"""Regenerate the evaluation scorecard from the recorded runs (DEC-076).

    uv run python scripts/build_scorecard.py
    uv run python scripts/build_scorecard.py --snapshot 2026-08-12

Runs every recorded scenario through the harness, every baseline over every scenario with an
outcome truth set, writes the metrics-only feeds to a temporary results tree, and renders the
static scorecard to docs/eval/scorecard.html. Deterministic and offline: no provider, no key, no
network, and a pinned generation date so the committed page changes only when a number does.

The feeds are the real input and are regenerable (gitignored); the rendered page is committed so
its history is the git history. CI regenerates it and fails if it drifts from the committed copy.

`--snapshot` retains the build in docs/eval/history.jsonl, keyed by git ref, prompt-tree digest,
and catalog version (DEC-081); the page renders that committed history alongside the current
table. A plain build reads history and never writes it — that is what keeps `--check` and the
snapshot step from fighting each other.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.baselines import BASELINES, run_baseline
from trace_ai.services.evaluation.harness import run_scenario
from trace_ai.services.evaluation.history import (
    ScorecardSnapshot,
    SnapshotRefusedError,
    append_snapshot,
    load_history,
    snapshot_key,
)
from trace_ai.services.evaluation.registry import load_registry
from trace_ai.services.evaluation.scorecard import render_scorecard, rows_from_feeds

OUTPUT = PROJECT_ROOT / "docs" / "eval" / "scorecard.html"
HISTORY = PROJECT_ROOT / "docs" / "eval" / "history.jsonl"
LIVE_STABILITY = PROJECT_ROOT / "docs" / "eval" / "live-stability.json"
"""The committed DEC-077 summary, written by an operator after a manual live protocol run.
Read like the history file — never regenerated, because the drift checks cannot re-run a live
measurement — and absent until the first measurement is committed."""
# Pinned so the committed page changes only when a metric does, never on the clock.
GENERATED_AT = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


def _baseline_response(scenario_path: Path, condition: str) -> Path | None:
    recording = scenario_path / "recorded" / "baselines" / f"{condition}.json"
    return recording if recording.is_file() else None


def collect_feeds(results_root: Path) -> list[dict[str, object]]:
    """Run every recorded scenario and baseline into `results_root`, and return their feeds.

    This is the one sweep both committed artifacts read: the scorecard renders it per scenario and
    condition, and the comparison table (`scripts/build_comparison.py`) collapses it per tool. Both
    stay in step because they consume the same feeds from the same runs.
    """
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

    return feeds


def build(results_root: Path, *, snapshot_date: str | None = None) -> str:
    """Render the page from a fresh sweep and the committed history (DEC-081).

    With `snapshot_date` set, the sweep's rows are first retained as a history snapshot keyed by
    the current git ref, prompt-tree digest, and catalog version — the deliberate step; a plain
    build reads history and never writes it, which is what keeps `--check` deterministic.
    """
    feeds = collect_feeds(results_root)
    if snapshot_date is not None:
        prompt_digest, catalog_version = snapshot_key()
        append_snapshot(
            HISTORY,
            ScorecardSnapshot(
                recorded_at=snapshot_date,
                git_ref=_git_ref(),
                prompt_digest=prompt_digest,
                catalog_version=catalog_version,
                rows=tuple(rows_from_feeds(feeds)),
            ),
        )
    live_stability = (
        json.loads(LIVE_STABILITY.read_text(encoding="utf-8")) if LIVE_STABILITY.is_file() else None
    )
    return render_scorecard(
        feeds,
        generated_at=GENERATED_AT,
        history=load_history(HISTORY),
        live_stability=live_stability,
    )


def _git_ref() -> str:
    import subprocess

    found = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return found.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and fail if it differs from the committed page, without writing",
    )
    parser.add_argument(
        "--snapshot",
        metavar="YYYY-MM-DD",
        help=(
            "retain this build in docs/eval/history.jsonl before rendering, dated as given and "
            "keyed by git ref, prompt digest, and catalog version (DEC-081); refused when the "
            "last snapshot has the same key"
        ),
    )
    args = parser.parse_args(argv)
    if args.check and args.snapshot:
        parser.error("--check reads the committed history and cannot also write a snapshot")
    if args.snapshot:
        date.fromisoformat(args.snapshot)

    results_root = Path(tempfile.mkdtemp(prefix="trace-scorecard-"))
    try:
        rendered = build(results_root, snapshot_date=args.snapshot)
    except SnapshotRefusedError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

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
    if args.snapshot:
        print(f"retained snapshot {args.snapshot} in {HISTORY.relative_to(PROJECT_ROOT)}")
    print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
