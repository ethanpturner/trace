"""Regenerate the per-tool comparison table from the recorded runs (DEC-074, DEC-076).

    uv run python scripts/build_comparison.py

Runs the same offline sweep as the scorecard — every recorded scenario through the harness, every
baseline over every scenario with an outcome truth set — and collapses the feeds to one row per
tool: the generic-prompt baseline, the structured single-pass baseline, and Trace. Writes the
Markdown table to docs/eval/comparison.md. Deterministic and offline: no provider, no key, no
network, and a pinned generation date so the committed table changes only when a number does.

The feeds are the real input and are regenerable (gitignored); the rendered table is committed so
its history is the git history. CI regenerates it and fails if it drifts from the committed copy.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml
from build_scorecard import collect_feeds

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.comparison import render_comparison
from trace_ai.services.evaluation.registry import REGISTRY_PATH
from trace_ai.services.requirements.loader import current_version

OUTPUT = PROJECT_ROOT / "docs" / "eval" / "comparison.md"
# Pinned so the committed table changes only when a metric does, never on the clock.
GENERATED_AT = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


def _pins() -> dict[str, str]:
    """The version identifiers that qualify what the numbers are of, read from the corpus."""
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {
        "registry": str(registry["registry_version"]),
        "catalog": current_version(),
    }


def build(results_root: Path) -> str:
    live_path = PROJECT_ROOT / "docs" / "eval" / "live-stability.json"
    live = json.loads(live_path.read_text(encoding="utf-8")) if live_path.is_file() else None
    return render_comparison(
        collect_feeds(results_root),
        generated_at=GENERATED_AT,
        pins=_pins(),
        live_stability=live,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and fail if it differs from the committed table, without writing",
    )
    args = parser.parse_args(argv)

    results_root = Path(tempfile.mkdtemp(prefix="trace-comparison-"))
    rendered = build(results_root)

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if rendered != current:
            print(
                "the committed comparison is stale; run "
                "`uv run python scripts/build_comparison.py`",
                file=sys.stderr,
            )
            return 1
        print("the committed comparison is current")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
