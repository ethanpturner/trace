"""Scorecard history: retained snapshots of the recorded-run metrics, keyed by version (DEC-081).

The scorecard is regenerated in place, so on its own it answers "what are the numbers" and never
"how did they move". A snapshot retains one build's rows together with the three identifiers that
say what produced them: the git ref the sweep ran on, a digest of the prompt tree, and the
requirements-catalog version. The history file is committed, append-only JSON lines — the page
renders from it, so regeneration stays deterministic (DEC-076) and the drift check still holds.

A snapshot is written deliberately (`build_scorecard.py --snapshot`), never as a side effect of a
build: a page rebuild that stamped the current git ref would change the committed page on every
commit and turn the drift check into noise. Appending a snapshot whose version key equals the
last one's is refused — any two retained records differ in what produced them, which is what
makes them distinguishable.

Like the scorecard itself, a snapshot carries metrics and identifiers only. No finding text, no
claim text, no document fragment: the history file is committed to a public repository and the
DEC-076 content boundary applies to it unchanged.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from trace_ai.domain.hashing import content_hash
from trace_ai.services.evaluation.scorecard import ScorecardRow
from trace_ai.services.prompts.registry import PROMPT_ROOT
from trace_ai.services.requirements.loader import current_version

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "ScorecardSnapshot",
    "SnapshotRefusedError",
    "append_snapshot",
    "load_history",
    "prompt_tree_digest",
    "snapshot_key",
]


class SnapshotRefusedError(Exception):
    """Appending was refused: the version key equals the last retained snapshot's."""


@dataclass(frozen=True, slots=True)
class ScorecardSnapshot:
    """One retained build: the rows, and the three identifiers naming what produced them."""

    recorded_at: str
    """The date the sweep ran, ISO `YYYY-MM-DD`."""
    git_ref: str
    """The commit the sweep ran on. The snapshot's own commit is that ref's child."""
    prompt_digest: str
    """`prompt_tree_digest()` over the prompt tree the sweep composed from."""
    catalog_version: str
    """The requirements-catalog version the tree declared."""
    rows: tuple[ScorecardRow, ...] = field(default_factory=tuple)

    @property
    def key(self) -> tuple[str, str, str]:
        """What produced the numbers. Two snapshots with equal keys are the same build re-run."""
        return (self.git_ref, self.prompt_digest, self.catalog_version)

    def _pooled(self) -> tuple[int, int, int]:
        authoritative = [row for row in self.rows if row.authoritative]
        return (
            sum(row.matched for row in authoritative),
            sum(row.missed for row in authoritative),
            sum(row.spurious for row in authoritative),
        )

    @property
    def precision(self) -> float | None:
        matched, _, spurious = self._pooled()
        return matched / (matched + spurious) if matched + spurious else None

    @property
    def recall(self) -> float | None:
        matched, missed, _ = self._pooled()
        return matched / (matched + missed) if matched + missed else None

    @property
    def f1(self) -> float | None:
        precision, recall = self.precision, self.recall
        if precision is None or recall is None or precision + recall == 0:
            return None
        return 2 * precision * recall / (precision + recall)

    @property
    def cost(self) -> float | None:
        priced = [row.cost for row in self.rows if row.authoritative and row.cost is not None]
        return sum(priced) if priced else None


def prompt_tree_digest(root: Path | None = None) -> str:
    """One hash over every prompt file in the tree, path-keyed so a rename moves it.

    DEC-019 hashes each *composed* prompt; composition needs per-agent substitutions, so a digest
    naming the whole tree hashes the files instead. Any edit to any prompt or shared block —
    including one that would change every composed hash at once — moves this digest.
    """
    base = root if root is not None else PROMPT_ROOT
    parts = [
        f"{path.relative_to(base).as_posix()}\n{path.read_text(encoding='utf-8')}"
        for path in sorted(base.rglob("*.md"))
    ]
    return content_hash("\n".join(parts).encode("utf-8"))


def snapshot_key() -> tuple[str, str]:
    """The tree's current (prompt digest, catalog version) pair, for building a snapshot."""
    return prompt_tree_digest(), current_version()


def load_history(path: Path) -> list[ScorecardSnapshot]:
    """Every retained snapshot, oldest first — the order they were appended."""
    if not path.is_file():
        return []
    snapshots: list[ScorecardSnapshot] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        rows = tuple(
            ScorecardRow(
                **{
                    **row,
                    # JSON has no tuples; restore the shape the dataclass declares so a
                    # reloaded snapshot compares equal to the one that was retained.
                    "compliance_by_class": tuple(
                        (str(name), float(rate))
                        for name, rate in row.get("compliance_by_class") or ()
                    ),
                }
            )
            for row in raw.pop("rows", [])
        )
        snapshots.append(ScorecardSnapshot(rows=rows, **raw))
    return snapshots


def append_snapshot(path: Path, snapshot: ScorecardSnapshot) -> None:
    """Retain one build. Refused when the last snapshot's version key is the same.

    Equal keys mean the same commit, prompts, and catalog — a re-run, not a new version — and
    retaining both would leave two records nothing distinguishes.
    """
    history = load_history(path)
    if history and history[-1].key == snapshot.key:
        raise SnapshotRefusedError(
            f"the last snapshot already records {snapshot.git_ref} with the same prompt digest "
            f"and catalog version {snapshot.catalog_version}; nothing new to retain"
        )
    payload = asdict(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
