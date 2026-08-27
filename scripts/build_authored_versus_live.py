"""Put the authored-recording snapshot beside the live-capture corpus (DEC-153).

    uv run python scripts/build_authored_versus_live.py
    uv run python scripts/build_authored_versus_live.py --check
    uv run python scripts/build_authored_versus_live.py --check --from-feeds feeds.json

Pools the most recent retained snapshot in docs/eval/history.jsonl against the current recorded
runs and renders both to docs/eval/authored-versus-live.md. Deterministic and offline: the history
file is committed and the current arm replays the committed recordings, so no provider, key, or
network is involved, and a pinned generation date keeps the page changing only when a count does.

`--from-feeds` reuses a sweep another renderer already ran, the same way the scorecard and
comparison share one in CI.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.authored_versus_live import (
    pool_rows,
    pool_snapshot,
    render_authored_versus_live,
)
from trace_ai.services.evaluation.scorecard import rows_from_feeds
from trace_ai.services.evaluation.stamps import DETERMINISTIC_STAMP
from trace_ai.services.evaluation.sweep import collect_feeds, load_feeds

OUTPUT = PROJECT_ROOT / "docs" / "eval" / "authored-versus-live.md"
HISTORY = PROJECT_ROOT / "docs" / "eval" / "history.jsonl"
# Pinned so the committed page changes only when a count does, never on the clock.
GENERATED_AT = DETERMINISTIC_STAMP

NOTES = (
    "`docs/eval/releases.md` retains the earlier figure as its v0.1 evaluation summary, keyed to "
    "the git ref above. That is a correct thing to retain and this page does not replace it; it "
    "supplies the second number a reader needs to read the first one.",
    "The release record reads 80% / 84% where this page reads 78% / 82% for the same snapshot. It "
    "pools all sixteen authoritative rows; this page pools the fourteen clean ones, matching the "
    "population the scorecard's stratified table uses (DEC-143), so the two arms here and the "
    "scorecard's own pooled row cannot disagree.",
    "The remaining single-author limitation is unchanged and is the larger one: every truth set "
    "is one person's judgment, and DEC-112's agreement instrument is built and holds no data "
    "until a second annotation set is authored (#565).",
)


def build(feeds: list[dict[str, object]]) -> str:
    arms = []
    snapshot = pool_snapshot(HISTORY, "Authored recordings")
    if snapshot is not None:
        arms.append(snapshot)
    arms.append(pool_rows(rows_from_feeds(feeds), "Live captures (current)"))
    return render_authored_versus_live(arms, generated_at=GENERATED_AT, notes=NOTES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and fail if it differs from the committed page, without writing",
    )
    parser.add_argument(
        "--from-feeds",
        type=Path,
        help="render from a feed list another renderer swept, instead of sweeping again",
    )
    args = parser.parse_args(argv)

    if args.from_feeds:
        rendered = build(load_feeds(args.from_feeds))
    else:
        # Intermediate sweep tree: cleaned up rather than left in /tmp per run.
        with tempfile.TemporaryDirectory(prefix="trace-authored-live-") as tmp:
            rendered = build(collect_feeds(Path(tmp)))

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if rendered != current:
            print(
                "the committed authored-versus-live page is stale; run "
                "`uv run python scripts/build_authored_versus_live.py`",
                file=sys.stderr,
            )
            return 1
        print("the committed authored-versus-live page is current")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
