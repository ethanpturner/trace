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
from datetime import date
from pathlib import Path

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.history import (
    ScorecardSnapshot,
    SnapshotRefusedError,
    append_snapshot,
    load_history,
    snapshot_key,
)
from trace_ai.services.evaluation.scorecard import render_scorecard, rows_from_feeds
from trace_ai.services.evaluation.stamps import DETERMINISTIC_STAMP
from trace_ai.services.evaluation.sweep import collect_feeds, dump_feeds, load_feeds

OUTPUT = PROJECT_ROOT / "docs" / "eval" / "scorecard.html"
HISTORY = PROJECT_ROOT / "docs" / "eval" / "history.jsonl"
LIVE_STABILITY = PROJECT_ROOT / "docs" / "eval" / "live-stability.json"
"""The committed DEC-077 summary, written by an operator after a manual live protocol run.
Read like the history file — never regenerated, because the drift checks cannot re-run a live
measurement — and absent until the first measurement is committed."""
# Pinned so the committed page changes only when a metric does, never on the clock.
GENERATED_AT = DETERMINISTIC_STAMP


def build_page(feeds: list[dict[str, object]], *, snapshot_date: str | None = None) -> str:
    """Render the page from already-collected feeds and the committed history (DEC-081).

    With `snapshot_date` set, the feeds' rows are first retained as a history snapshot keyed by
    the current git ref, prompt-tree digest, and catalog version — the deliberate step; a plain
    build reads history and never writes it, which is what keeps `--check` deterministic.
    """
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


def _render(args: argparse.Namespace) -> str:
    """The rendered page, from a pre-swept feed file when given one, otherwise a fresh sweep."""
    if args.from_feeds:
        return build_page(load_feeds(args.from_feeds))
    # The sweep's results tree is intermediate: nothing after the render needs it, so it is a
    # temporary that is cleaned up rather than left in /tmp per run.
    with tempfile.TemporaryDirectory(prefix="trace-scorecard-") as tmp:
        return build_page(collect_feeds(Path(tmp)), snapshot_date=args.snapshot)


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
    parser.add_argument(
        "--sweep-to",
        metavar="PATH",
        type=Path,
        help=(
            "run the offline sweep once, write the feeds to PATH, and exit without rendering; the "
            "companion of --from-feeds, so CI can sweep once and render both pages from the result"
        ),
    )
    parser.add_argument(
        "--from-feeds",
        metavar="PATH",
        type=Path,
        help="render from a feed file written by --sweep-to instead of running the sweep again",
    )
    args = parser.parse_args(argv)
    if args.check and args.snapshot:
        parser.error("--check reads the committed history and cannot also write a snapshot")
    if args.sweep_to and (args.check or args.snapshot or args.from_feeds):
        parser.error("--sweep-to only sweeps; it cannot also render, check, or snapshot")
    if args.from_feeds and args.snapshot:
        parser.error("--snapshot records a fresh sweep and cannot read --from-feeds")
    if args.snapshot:
        date.fromisoformat(args.snapshot)

    if args.sweep_to:
        with tempfile.TemporaryDirectory(prefix="trace-scorecard-") as tmp:
            dump_feeds(collect_feeds(Path(tmp)), args.sweep_to)
        print(f"wrote feeds to {args.sweep_to}")
        return 0

    try:
        rendered = _render(args)
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
