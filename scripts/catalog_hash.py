"""Compute, check, or rewrite `content_hash` in `requirements/catalog.yaml`.

DEC-019 makes the catalog's `content_hash` SHA-256 over a canonical re-serialization of the
parsed catalog, computed and verified at catalog load. The loader does both; this exists because
a value that is verified at load has to be *written* somewhere when the catalog changes, and
recomputing it by hand is not a thing anyone can do.

The hash covers meaning rather than formatting, so most edits do not move it: comments,
indentation, YAML block style, and key order are invisible to it. Editing a `statement`, adding a
requirement, or removing one does move it, and the loader then refuses to read the catalog until
this is run.

    uv run python scripts/catalog_hash.py            # print the current and computed hashes
    uv run python scripts/catalog_hash.py --write    # rewrite the line in catalog.yaml
    uv run python scripts/catalog_hash.py --check    # exit non-zero if it is stale

`--check` is what a hook or CI step would call. Nothing calls it today: `uv run pytest` already
fails on a stale hash, because every test that reads the catalog goes through the loader.
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Final

from trace_ai.services.requirements.loader import MANIFEST_FILE, compute_hash, current_version

# The one line this script owns. Anchored to the two-space indent the manifest uses for the
# fields of its `catalog:` mapping, so a `content_hash` appearing anywhere else is not rewritten.
_LINE: Final = re.compile(r"^  content_hash: .*$", re.MULTILINE)


def declared_hash() -> str | None:
    match = _LINE.search(MANIFEST_FILE.read_text(encoding="utf-8"))
    if match is None:
        return None
    return match.group(0).split(":", 1)[1].strip()


def write(value: str) -> bool:
    """Rewrite the `content_hash` line. Returns whether the file changed."""
    text = MANIFEST_FILE.read_text(encoding="utf-8")
    replacement = f"  content_hash: {value}"
    if _LINE.search(text) is None:
        raise SystemExit(
            f"{MANIFEST_FILE} has no 'content_hash:' line to rewrite. Add "
            f"'{replacement}' under 'catalog:' and run this again."
        )
    updated = _LINE.sub(replacement, text, count=1)
    if updated == text:
        return False
    MANIFEST_FILE.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite the line in catalog.yaml")
    parser.add_argument("--check", action="store_true", help="exit non-zero if the hash is stale")
    arguments = parser.parse_args()

    expected = compute_hash(current_version())
    current = declared_hash()

    if arguments.write:
        changed = write(expected)
        print(f"{'wrote' if changed else 'unchanged'}: {expected}")
        return 0

    print(f"declared: {current}")
    print(f"computed: {expected}")

    if arguments.check and current != expected:
        print("stale; run with --write", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
