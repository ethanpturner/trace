"""Seed the initial GitHub issue backlog from a version-controlled manifest.

The manifest is split across ``scripts/backlog_manifest_m*.yaml``, one fragment per
milestone. Issue bodies live as plain Markdown under ``scripts/backlog_bodies/`` so they
are reviewable in a diff and are never passed through a shell string.

Creation runs in two phases because a dependency cannot be expressed until both issues
exist. Phase one creates every issue with its milestone, labels, and project. Phase two
applies the ``blocked_by`` relationships.

The script is idempotent. Every body is published with a hidden seed marker, and a local
ledger records the seed-to-issue-number mapping, so a re-run skips what already exists.
Writes are opt-in: without ``--apply`` the script prints the commands it would run.

    uv run python scripts/seed_backlog.py --check     # validate the manifest only
    uv run python scripts/seed_backlog.py             # dry run
    uv run python scripts/seed_backlog.py --apply     # create issues
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO: Final = "ethanpturner/trace"
ROOT: Final = Path(__file__).resolve().parent
BODIES: Final = ROOT / "backlog_bodies"
LEDGER: Final = ROOT / "backlog-ledger.json"
STAGING: Final = ROOT / ".staged"
MARKER: Final = "trace-seed"
PACE_SECONDS: Final = 1.5

REQUIRED_HEADINGS: Final = (
    "## Context",
    "## Scope",
    "## Acceptance criteria",
    "## Out of scope",
    "## References",
)


class SeedError(RuntimeError):
    """A manifest or command failure that should stop the run."""


# Resolved once so no command runs on a partial executable path. Falling back to the bare
# name keeps --check usable on a machine with no gh installed; the failure then surfaces
# at the first real call rather than at import.
GH: Final = shutil.which("gh") or "gh"


def manifest_paths() -> list[Path]:
    return sorted(ROOT.glob("backlog_manifest_m*.yaml"))


def load_manifest() -> list[dict[str, Any]]:
    """Merge every milestone fragment into one ordered list of issue specs."""
    specs: list[dict[str, Any]] = []
    paths = manifest_paths()
    if not paths:
        raise SeedError(f"no manifest fragments found in {ROOT}")
    for path in paths:
        loaded: Any = yaml.safe_load(path.read_text())
        if not isinstance(loaded, dict) or "issues" not in loaded:
            raise SeedError(f"{path.name}: expected a mapping with an 'issues' key")
        issues: Any = loaded["issues"]
        if not isinstance(issues, list):
            raise SeedError(f"{path.name}: 'issues' must be a list")
        for issue in issues:
            if not isinstance(issue, dict):
                raise SeedError(f"{path.name}: every issue must be a mapping")
            issue["_source"] = path.name
            specs.append(issue)
    return specs


def validate(specs: list[dict[str, Any]]) -> list[str]:
    """Return every problem found in the manifest. An empty list means it is well formed."""
    problems: list[str] = []
    seeds = [str(spec.get("seed", "")) for spec in specs]

    duplicates = {seed for seed in seeds if seeds.count(seed) > 1}
    problems.extend(f"duplicate seed key: {seed}" for seed in sorted(duplicates))

    known = set(seeds)
    for spec in specs:
        seed = str(spec.get("seed", "<missing>"))
        source = spec.get("_source", "?")
        for field in ("seed", "title", "milestone", "labels", "body_file"):
            if not spec.get(field):
                problems.append(f"{source}: {seed}: missing required field '{field}'")

        title = str(spec.get("title", ""))
        if len(title) > 80:
            problems.append(f"{seed}: title is {len(title)} characters, over the 80 limit")

        body = ROOT / str(spec.get("body_file", ""))
        if not body.is_file():
            problems.append(f"{seed}: body file not found: {body}")
        else:
            text = body.read_text()
            missing = [h for h in REQUIRED_HEADINGS if h not in text]
            problems.extend(f"{seed}: body is missing heading '{h}'" for h in missing)
            if MARKER in text:
                problems.append(f"{seed}: body already contains a {MARKER} marker")

        for blocker in spec.get("blocked_by", []) or []:
            if str(blocker) not in known:
                problems.append(f"{seed}: blocked_by references unknown seed '{blocker}'")
            if str(blocker) == seed:
                problems.append(f"{seed}: blocked_by references itself")

    return problems


def run(argv: list[str], *, apply: bool) -> str:
    if not apply:
        print("DRY RUN:", " ".join(argv))
        return ""
    # argv is a list, never a shell string, and every element comes from a
    # version-controlled manifest or a resolved executable path. No shell is invoked.
    result = subprocess.run(  # noqa: S603
        argv, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise SeedError(f"{' '.join(argv)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def load_ledger() -> dict[str, int]:
    if LEDGER.is_file():
        loaded: Any = json.loads(LEDGER.read_text())
        return {str(k): int(v) for k, v in loaded.items()}
    return {}


def save_ledger(ledger: dict[str, int]) -> None:
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")


def find_existing(seed: str) -> int | None:
    """Look an issue up by its hidden seed marker so re-runs do not duplicate it."""
    result = subprocess.run(  # noqa: S603
        [
            GH,
            "issue",
            "list",
            "--repo",
            REPO,
            "--state",
            "all",
            "--limit",
            "200",
            "--search",
            f'"{MARKER}: {seed}" in:body',
            "--json",
            "number",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    rows: Any = json.loads(result.stdout or "[]")
    if isinstance(rows, list) and rows:
        first: Any = rows[0]
        return int(first["number"])
    return None


def stage_body(spec: dict[str, Any]) -> Path:
    """Write the body with its seed marker appended, outside the reviewable source."""
    source = ROOT / str(spec["body_file"])
    seed = str(spec["seed"])
    text = source.read_text().rstrip() + f"\n\n<!-- {MARKER}: {seed} -->\n"
    STAGING.mkdir(exist_ok=True)
    staged = STAGING / f"{seed}.md"
    staged.write_text(text)
    return staged


def phase_one(specs: list[dict[str, Any]], project: str | None, *, apply: bool) -> dict[str, int]:
    """Create every issue with milestone, labels, and project. No relationships yet."""
    ledger = load_ledger()
    for spec in specs:
        seed = str(spec["seed"])
        if seed in ledger:
            print(f"skip {seed}: ledger has #{ledger[seed]}")
            continue
        if apply:
            existing = find_existing(seed)
            if existing is not None:
                print(f"skip {seed}: already present as #{existing}")
                ledger[seed] = existing
                save_ledger(ledger)
                continue

        argv = [
            GH,
            "issue",
            "create",
            "--repo",
            REPO,
            "--title",
            str(spec["title"]),
            "--body-file",
            str(stage_body(spec)),
            "--milestone",
            str(spec["milestone"]),
            "--label",
            ",".join(str(label) for label in spec["labels"]),
        ]
        if project:
            argv += ["--project", project]

        url = run(argv, apply=apply)
        if apply:
            ledger[seed] = int(url.rsplit("/", 1)[-1])
            save_ledger(ledger)
            time.sleep(PACE_SECONDS)
    return ledger


def phase_two(
    specs: list[dict[str, Any]],
    ledger: dict[str, int],
    *,
    apply: bool,
    planned: set[str] | None = None,
) -> None:
    """Apply blocked-by relationships once every issue exists.

    On a dry run no issue numbers exist yet, so links are previewed by seed key against
    ``planned`` -- the set of seeds this invocation would create. Without that the dry run
    would silently report nothing for the whole second phase.
    """
    for spec in specs:
        seed = str(spec["seed"])
        number = ledger.get(seed)
        blockers = [str(b) for b in (spec.get("blocked_by") or [])]
        if not blockers:
            continue

        if not apply:
            if planned is not None and seed not in planned:
                continue
            resolvable = [b for b in blockers if planned is None or b in planned or b in ledger]
            deferred = [b for b in blockers if b not in resolvable]
            if resolvable:
                print(f"DRY RUN: link {seed} blocked-by {', '.join(resolvable)}")
            for blocker in deferred:
                print(f"  defer {seed}: blocker '{blocker}' is not in this batch")
            continue

        if number is None:
            continue
        argv = [GH, "issue", "edit", str(number), "--repo", REPO]
        for blocker in blockers:
            target = ledger.get(blocker)
            if target is None:
                print(f"warn {seed}: blocker '{blocker}' has no issue number yet")
                continue
            argv += ["--add-blocked-by", str(target)]
        if len(argv) > 6:
            run(argv, apply=apply)
            if apply:
                time.sleep(PACE_SECONDS)


def summarize(specs: list[dict[str, Any]]) -> Iterator[str]:
    by_milestone: dict[str, int] = {}
    for spec in specs:
        milestone = str(spec.get("milestone", "?"))
        by_milestone[milestone] = by_milestone.get(milestone, 0) + 1
    for milestone in sorted(by_milestone):
        yield f"  {milestone}: {by_milestone[milestone]} issues"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate the manifest and exit.")
    parser.add_argument("--apply", action="store_true", help="Perform writes. Off by default.")
    parser.add_argument("--project", default=None, help="Project title to add each issue to.")
    parser.add_argument(
        "--milestone",
        action="append",
        default=None,
        help=(
            "Create only issues in this milestone. Repeatable. Validation still runs over "
            "the whole manifest, so cross-milestone dependencies are checked either way."
        ),
    )
    args = parser.parse_args()

    try:
        specs = load_manifest()
    except SeedError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    problems = validate(specs)
    if problems:
        print(f"{len(problems)} manifest problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"{len(specs)} issues across {len(manifest_paths())} manifest fragments:")
    for line in summarize(specs):
        print(line)

    if args.check:
        print("manifest is well formed")
        return 0

    selected = specs
    if args.milestone:
        wanted = set(args.milestone)
        unknown = wanted - {str(spec.get("milestone", "")) for spec in specs}
        if unknown:
            print(f"error: unknown milestone(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 1
        selected = [spec for spec in specs if str(spec.get("milestone", "")) in wanted]
        print(f"\nselecting {len(selected)} of {len(specs)} issues: {', '.join(sorted(wanted))}")

    try:
        ledger = phase_one(selected, args.project, apply=args.apply)
        # Pass the full manifest so a later batch can still link back to this one. A
        # blocker that has no issue number yet is reported and skipped, not failed.
        phase_two(
            specs,
            ledger,
            apply=args.apply,
            planned={str(spec["seed"]) for spec in selected},
        )
    except SeedError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.apply:
        print(f"{len(ledger)} issues tracked in {LEDGER.name}")
    else:
        print("dry run complete. Re-run with --apply to create issues.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
