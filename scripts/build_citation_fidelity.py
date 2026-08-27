"""Measure whether a baseline's cited passage resolves against the documents it was given.

    uv run python scripts/build_citation_fidelity.py
    uv run python scripts/build_citation_fidelity.py --check

Reads the committed baseline recordings, looks for each `evidence_quote` in the scenario's input
documents under `services/evaluation/citations.py`'s shallow normalization, and renders the counts
to docs/eval/citation-fidelity.md. Nothing is replayed and no model is called -- the recordings
and the inputs are both committed, so this is a file comparison and needs no provider, key, or
network. A pinned generation date keeps the committed page changing only when a count does.

The page answers a claim the comparison table used to make about its own schema: baselines *do*
cite passages, and the difference is that theirs cannot be resolved automatically. CI regenerates
it and fails if it drifts.
"""

from __future__ import annotations

import argparse
import sys

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.citations import measure_corpus, render_citation_fidelity
from trace_ai.services.evaluation.registry import REGISTRY_PATH, catalog_version_summary
from trace_ai.services.evaluation.stamps import DETERMINISTIC_STAMP

OUTPUT = PROJECT_ROOT / "docs" / "eval" / "citation-fidelity.md"
# Pinned so the committed page changes only when a count does, never on the clock.
GENERATED_AT = DETERMINISTIC_STAMP


def _pins() -> list[str]:
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    return [
        f"registry {registry['registry_version']}",
        f"catalog {catalog_version_summary()}",
    ]


def build() -> str:
    return render_citation_fidelity(measure_corpus(), generated_at=GENERATED_AT, pins=_pins())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and fail if it differs from the committed page, without writing",
    )
    args = parser.parse_args(argv)

    rendered = build()

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if rendered != current:
            print(
                "the committed citation-fidelity page is stale; run "
                "`uv run python scripts/build_citation_fidelity.py`",
                file=sys.stderr,
            )
            return 1
        print("the committed citation-fidelity page is current")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
