"""Rewrite a release's evaluation-summary block from the committed artifacts (#524).

The record itself (`docs/eval/releases.md`) is authored; the numbers are not. This script
regenerates the block between the evaluation-summary markers in one release's section from the
latest retained scorecard snapshot and the committed live-stability summary, so what a release
claims is what the artifacts hold. `--check` regenerates without writing and fails on drift,
the `build_scorecard.py --check` pattern.
"""

from __future__ import annotations

import argparse
import sys

from trace_ai.services.evaluation.release_record import (
    RELEASES,
    inject_summary,
    render_evaluation_summary,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the release section to rewrite, e.g. v0.1")
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and fail if the committed block differs, without writing",
    )
    args = parser.parse_args(argv)

    text = RELEASES.read_text(encoding="utf-8")
    try:
        rewritten = inject_summary(text, args.version, render_evaluation_summary())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.check:
        if rewritten != text:
            print(
                f"the {args.version} evaluation summary is stale; run "
                f"`uv run python scripts/build_release_record.py {args.version}`",
                file=sys.stderr,
            )
            return 1
        print(f"the {args.version} evaluation summary is current")
        return 0

    RELEASES.write_text(rewritten, encoding="utf-8")
    print(f"rewrote the {args.version} evaluation summary in {RELEASES.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
