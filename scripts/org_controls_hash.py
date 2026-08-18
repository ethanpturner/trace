"""Rewrite an org-controls catalog version's `content_hash` line (#528, DEC-115).

The `catalog_hash.py` pattern for the smaller sibling: the hash covers the parsed catalog
(DEC-019) with the hash field excluded from its own input, so comments and formatting never
move it. Without `--write`, prints the recomputed value and exits non-zero when the declared
line is stale.

    uv run python scripts/org_controls_hash.py --version 0.1 --write
"""

from __future__ import annotations

import argparse
import re
import sys

from trace_ai.services.org_controls.loader import ORG_CONTROLS_ROOT, compute_org_hash

_LINE = re.compile(r"^(\s*content_hash:\s*)(\S+)\s*$", flags=re.MULTILINE)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", default="0.1", help="the catalog version to hash")
    parser.add_argument(
        "--write", action="store_true", help="rewrite the content_hash line in place"
    )
    args = parser.parse_args(argv)

    path = ORG_CONTROLS_ROOT / f"{args.version}.yaml"
    recomputed = compute_org_hash(args.version)
    text = path.read_text(encoding="utf-8")
    match = _LINE.search(text)
    if match is None:
        print(f"error: {path.name} has no content_hash line", file=sys.stderr)
        return 1
    declared = match.group(2)
    if args.write:
        if declared != recomputed:
            path.write_text(_LINE.sub(rf"\g<1>{recomputed}", text, count=1), encoding="utf-8")
            print(f"wrote: {recomputed}")
        else:
            print("already current")
        return 0
    print(recomputed)
    return 0 if declared == recomputed else 1


if __name__ == "__main__":
    raise SystemExit(main())
