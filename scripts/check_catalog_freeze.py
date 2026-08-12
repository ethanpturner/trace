"""Fail when a change touches a released catalog version's directory (DEC-057).

A released catalog version is immutable: any content change, however small, is a new minor
version. The loader's hash check refuses a drifted catalog at read time, but that failure
surfaces at the next load, in whatever process happens to load it. This guard fails at review
time instead — the AISVS `LOCKED` pattern — and documents the freeze in-repo rather than in a
stack trace.

    uv run python scripts/check_catalog_freeze.py --base origin/develop

Released versions are read from `requirements/versions.yaml` (DEC-057's governance registry): a
version is frozen once its status is anything but `draft`. Changed files come from
`git diff --name-only <base>...HEAD`, the same span a pull request shows. CI passes the pull
request's base ref; locally the default compares against `origin/develop`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

import yaml

from trace_ai.config import PROJECT_ROOT

REGISTRY = PROJECT_ROOT / "requirements" / "versions.yaml"


def frozen_versions() -> list[str]:
    if not REGISTRY.is_file():
        return []
    document = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    versions = document.get("versions", {}) if isinstance(document, dict) else {}
    return sorted(
        version
        for version, entry in versions.items()
        if isinstance(entry, dict) and entry.get("status") != "draft"
    )


def changed_files(base: str) -> list[str]:
    # A fixed argv running the repository's own git over a caller-supplied ref: the ref is the
    # operator's input to the operator's own guard, not untrusted data crossing a boundary.
    completed = subprocess.run(  # noqa: S603
        ["git", "diff", "--name-only", f"{base}...HEAD"],  # noqa: S607
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/develop", help="ref the change diffs against")
    arguments = parser.parse_args()

    frozen = frozen_versions()
    if not frozen:
        print("no released catalog versions; nothing is frozen")
        return 0

    violations = [
        path
        for path in changed_files(arguments.base)
        if any(path.startswith(f"requirements/{version}/") for version in frozen)
    ]
    if violations:
        print(
            f"released catalog versions are immutable (DEC-057): {', '.join(frozen)} are "
            f"frozen, and this change touches:",
            file=sys.stderr,
        )
        for path in violations:
            print(f"  {path}", file=sys.stderr)
        print(
            "A content change to a released version is a new minor version: author it in a new "
            "directory with its own manifest, record the fates, and leave the frozen one as "
            "recorded runs verify it.",
            file=sys.stderr,
        )
        return 1

    print(f"frozen versions untouched: {', '.join(frozen)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
