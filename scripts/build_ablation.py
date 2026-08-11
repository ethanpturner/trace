"""Regenerate the ablation table from the recorded runs (evaluation-plan section 14, DEC-012).

    uv run python scripts/build_ablation.py

Runs the ablation set — the authoritative pipeline and each removed component in turn — for every
scenario with a recording, and renders the metric deltas to docs/eval/ablation.md. Deterministic
and offline: each run replays the scenario's recording with nodes dropped, so no provider, key, or
network is involved, and a pinned generation date keeps the committed table changing only when a
number does.

The ablated runs are non-authoritative by construction (DEC-012); the table is the portfolio
narrative's central artifact, and CI regenerates it and fails if it drifts.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.ablation import render_ablation
from trace_ai.services.evaluation.registry import REGISTRY_PATH, load_registry
from trace_ai.services.evaluation.stability import AblationComparison, run_ablation_set
from trace_ai.services.requirements.loader import current_version

OUTPUT = PROJECT_ROOT / "docs" / "eval" / "ablation.md"
# Pinned so the committed table changes only when a metric does, never on the clock.
GENERATED_AT = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


def _pins() -> dict[str, str]:
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {"registry": str(registry["registry_version"]), "catalog": current_version()}


def _comparisons(results_root: Path) -> list[AblationComparison]:
    comparisons: list[AblationComparison] = []
    for entry in load_registry():
        if not entry.has_recording_for("clean"):
            continue
        comparisons.append(
            run_ablation_set(
                entry.slug,
                data_root=results_root / "work" / entry.slug,
                label="ablation",
                results_root=results_root / "feeds" / entry.slug,
            )
        )
    return comparisons


def build(results_root: Path) -> str:
    return render_ablation(_comparisons(results_root), generated_at=GENERATED_AT, pins=_pins())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and fail if it differs from the committed table, without writing",
    )
    args = parser.parse_args(argv)

    results_root = Path(tempfile.mkdtemp(prefix="trace-ablation-"))
    rendered = build(results_root)

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if rendered != current:
            print(
                "the committed ablation table is stale; run "
                "`uv run python scripts/build_ablation.py`",
                file=sys.stderr,
            )
            return 1
        print("the committed ablation table is current")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
