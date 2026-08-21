"""Regenerate the benchmark package manifest from the corpus (DEC-146, #574).

    uv run python scripts/build_benchmark_manifest.py

Walks every registered scenario and writes benchmarks/manifest.yaml: the files each carries, the
catalog and workflow versions it pins, the models its recordings attribute to (DEC-136), and a
digest over each group. Deterministic and offline — it reads committed files and hashes them, so no
provider, key, or network is involved, and a pinned generation stamp keeps the committed manifest
changing only when the corpus does.

`--check` regenerates and fails without writing when the committed manifest and the corpus disagree.
CI runs it beside the other currency checks: a promoted capture that does not regenerate the
manifest leaves the package describing a corpus that no longer exists, which is the drift the
manifest exists to prevent.
"""

from __future__ import annotations

import argparse
import sys

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.package import MANIFEST_PATH, render_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and fail if it differs from the committed manifest, without writing",
    )
    args = parser.parse_args(argv)

    rendered = render_manifest()

    if args.check:
        current = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.is_file() else ""
        if rendered != current:
            print(
                "the committed benchmark manifest is stale; run "
                "`uv run python scripts/build_benchmark_manifest.py`",
                file=sys.stderr,
            )
            return 1
        print("the committed benchmark manifest is current")
        return 0

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
