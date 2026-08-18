"""The longitudinal release record (evaluation-plan section 17, #524).

Section 17 says every release records six things — version, date, major changes, evaluation
summary, known regressions, outstanding issues — and that the record "creates a history of
improvement." The record lives in `docs/eval/releases.md`, one section per release, authored by
a person for everything judgment-shaped. The one part a person must not author is the
evaluation summary: hand-written numbers drift toward flattery, so that block is assembled here
from the committed artifacts — the latest retained scorecard snapshot (DEC-081) and the DEC-077
live-stability summary — and rewritten in place between markers. `--check` fails when the
committed block no longer matches what the artifacts say.

Nothing here runs a sweep or spends a call: the inputs are committed files, which is what keeps
the check deterministic and CI-safe.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.history import load_history

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.services.evaluation.history import ScorecardSnapshot

__all__ = [
    "RELEASES",
    "ReleaseEntry",
    "inject_summary",
    "parse_releases",
    "render_evaluation_summary",
]

RELEASES = PROJECT_ROOT / "docs" / "eval" / "releases.md"
HISTORY = PROJECT_ROOT / "docs" / "eval" / "history.jsonl"
LIVE_STABILITY = PROJECT_ROOT / "docs" / "eval" / "live-stability.json"

BLOCK_START = "<!-- evaluation-summary -->"
BLOCK_END = "<!-- /evaluation-summary -->"

_HEADING = re.compile(r"^## (v\d+\.\d+(?:\.\d+)?) — (\d{4}-\d{2}-\d{2})$", re.MULTILINE)

_REQUIRED_PARTS = (
    "### Major changes",
    "### Evaluation summary",
    "### Known regressions",
    "### Outstanding issues",
)


class ReleaseEntry:
    """One release's section: the version, the date, and the section text."""

    def __init__(self, version: str, date: str, text: str) -> None:
        self.version = version
        self.date = date
        self.text = text

    def missing_parts(self) -> list[str]:
        """The section-17 parts this entry does not carry (version and date are the heading)."""
        return [part for part in _REQUIRED_PARTS if part not in self.text]


def parse_releases(text: str) -> list[ReleaseEntry]:
    """Every release section in the record, newest first as the file orders them."""
    matches = list(_HEADING.finditer(text))
    entries = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entries.append(ReleaseEntry(match.group(1), match.group(2), text[match.start() : end]))
    return entries


def _pct(value: float | None) -> str:
    return "unmeasured" if value is None else f"{value * 100:.0f}%"


def render_evaluation_summary(
    *, history_path: Path | None = None, live_path: Path | None = None
) -> str:
    """The generated block: the latest retained snapshot's pooled numbers, and the live
    measurement where one is committed. Assembled, never authored — the numbers a release
    claims are the numbers the artifacts hold."""
    history = load_history(history_path if history_path is not None else HISTORY)
    if not history:
        raise ValueError(
            "no retained scorecard snapshot exists; run "
            "`uv run python scripts/build_scorecard.py --snapshot YYYY-MM-DD` first — a release "
            "entry without a snapshot would have nothing honest to summarize"
        )
    latest: ScorecardSnapshot = history[-1]
    authoritative = [row for row in latest.rows if row.authoritative]
    scenarios = sorted({row.scenario for row in authoritative})
    lines = [
        BLOCK_START,
        f"- Retained snapshot {latest.recorded_at} (git `{latest.git_ref}`, catalog "
        f"{latest.catalog_version}), the latest in `docs/eval/history.jsonl`.",
        f"- Pooled over {len(authoritative)} authoritative rows across {len(scenarios)} "
        f"scenarios: precision {_pct(latest.precision)}, recall {_pct(latest.recall)}, "
        f"F1 {_pct(latest.f1)}.",
    ]
    live_file = live_path if live_path is not None else LIVE_STABILITY
    if live_file.is_file():
        live: dict[str, Any] = json.loads(live_file.read_text(encoding="utf-8"))
        means = live.get("metric_mean", {})
        cost = means.get("estimated_cost")
        cost_text = "unmeasured" if cost is None else f"${float(cost):.2f}"
        lines.append(
            f"- Live stability (DEC-077): {live.get('n')} runs of `{live.get('scenario')}` on "
            f"`{live.get('profile')}`, {live.get('failed_runs')} failed, mean cost {cost_text} "
            f"per completed run. Everything else replays offline; a dash on the scorecard is "
            f"unmeasured, never zero."
        )
    else:
        lines.append("- No live-stability measurement is committed; every number above replays.")
    lines.append(BLOCK_END)
    return "\n".join(lines)


def inject_summary(text: str, version: str, block: str) -> str:
    """The record with `version`'s evaluation-summary block replaced by `block`.

    The block must already exist between markers inside that release's section — the section
    itself is authored, and inventing one here would put generated text where a person decides
    structure.
    """
    entries = parse_releases(text)
    entry = next((candidate for candidate in entries if candidate.version == version), None)
    if entry is None:
        raise ValueError(f"the release record has no section for {version}")
    start = entry.text.find(BLOCK_START)
    end = entry.text.find(BLOCK_END)
    if start < 0 or end < 0:
        raise ValueError(f"the {version} section carries no evaluation-summary markers to rewrite")
    replaced = entry.text[:start] + block + entry.text[end + len(BLOCK_END) :]
    return text.replace(entry.text, replaced)
