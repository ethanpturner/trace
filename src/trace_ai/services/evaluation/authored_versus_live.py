"""What changed when the recordings stopped being written by the person who wrote the answers.

The corpus was scored twice against the same truth sets, by the same matcher, over the same
scenarios. The first time, thirteen of fourteen recordings were written offline by the person who
wrote the answers; the second time, every one was captured from a model. The pooled numbers moved
by more than sixty points in both directions, and nothing in `docs/eval/` put them side by side.

**The discriminator is mechanical, not asserted.** DEC-136 gives every scorecard row a model
attribution read from the recording's own usage or the execution ledger, and a dash where no model
produced the responses. Every authoritative row in the retained 2026-08-18 snapshot attributes to
nothing. That is what makes this a comparison of provenance rather than of dates: the earlier
figure is not older, it is *authored*, and the record says so per row without anybody characterising
it.

The page exists because the earlier figure is still the one a reader meets first —
`docs/eval/releases.md` leads its v0.1 evaluation summary with it, correctly, as a dated snapshot
at a named git ref. A snapshot is not a wrong thing to retain. Leaving it as the only pooled number
a reader encounters is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from pathlib import Path

    from trace_ai.services.evaluation.scorecard import ScorecardRow

__all__ = ["Pooled", "pool_rows", "pool_snapshot", "render_authored_versus_live"]


@dataclass(slots=True)
class Pooled:
    """One arm's authoritative rows collapsed to the three counts and their two ratios."""

    label: str
    rows: int
    matched: int
    missed: int
    spurious: int
    attributed: int
    """Rows whose recording attributes to a model. Zero means every row was authored."""

    @property
    def precision(self) -> float | None:
        produced = self.matched + self.spurious
        return self.matched / produced if produced else None

    @property
    def recall(self) -> float | None:
        reachable = self.matched + self.missed
        return self.matched / reachable if reachable else None


def pool_snapshot(history: Path, label: str) -> Pooled | None:
    """Pool the most recent retained snapshot's authoritative rows.

    Returns `None` when no history has been retained — the page then says so rather than
    rendering an arm with no data behind it.
    """
    entries = [
        json.loads(line)
        for line in history.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not entries:
        return None
    latest = entries[-1]
    # The same population the scorecard's stratified table pools: authoritative *clean* rows
    # (DEC-143). Two pooled numbers on two pages that quietly pool different sets is the defect
    # this page exists to expose, and it would be an embarrassing one to introduce here.
    rows = [
        row
        for row in latest["rows"]
        if row.get("authoritative") and row.get("condition") == "clean"
    ]
    return Pooled(
        label=f"{label} ({latest['recorded_at']}, `{str(latest['git_ref'])[:7]}`)",
        rows=len(rows),
        matched=sum(int(row["matched"]) for row in rows),
        missed=sum(int(row["missed"]) for row in rows),
        spurious=sum(int(row["spurious"]) for row in rows),
        attributed=sum(1 for row in rows if row.get("model")),
    )


def pool_rows(rows: Sequence[ScorecardRow], label: str) -> Pooled:
    """Pool current scorecard rows over the same population its stratified table uses."""
    authoritative = [row for row in rows if row.authoritative and row.condition == "clean"]
    return Pooled(
        label=label,
        rows=len(authoritative),
        matched=sum(row.matched for row in authoritative),
        missed=sum(row.missed for row in authoritative),
        spurious=sum(row.spurious for row in authoritative),
        attributed=sum(1 for row in authoritative if row.model),
    )


def _ratio(value: float | None, matched: int, denominator: int) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.0f}% ({matched}/{denominator})"


def _line(pooled: Pooled) -> str:
    # What the data supports is "attributes to a model", not "was authored" — the two differ by
    # one row and the difference is named on the page rather than rounded into the cell.
    provenance = f"{pooled.attributed} of {pooled.rows} attribute to a model"
    return (
        f"| {pooled.label} | {pooled.rows} | {provenance} | {pooled.matched} | {pooled.missed} | "
        f"{pooled.spurious} | "
        f"{_ratio(pooled.precision, pooled.matched, pooled.matched + pooled.spurious)} | "
        f"{_ratio(pooled.recall, pooled.matched, pooled.matched + pooled.missed)} |"
    )


def render_authored_versus_live(
    arms: Sequence[Pooled], *, generated_at: datetime, notes: Sequence[str] = ()
) -> str:
    """Render the two arms as Markdown. Counts and identifiers only (DEC-076)."""
    body = chr(10).join(_line(arm) for arm in arms)
    note_text = chr(10).join(f"- {note}" for note in notes)
    return f"""<!-- Generated by scripts/build_authored_versus_live.py -- do not edit by hand. -->
# Authored recordings against live captures

The same fifteen scenarios, the same authored truth sets, the same structural matcher — scored
once when most recordings were written offline, and again once every one was captured from a
model. This is the corpus's own answer to the question a reader should ask of any benchmark whose
scenarios and answer key share an author: **how much of the score was the author?**

Generated {generated_at.date().isoformat()}. Counts and identifiers only, no assessment content
(DEC-076).

| Arm | Rows | Recordings | Matched | Missed | Spurious | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- | --- |
{body}

**The Recordings column is the whole argument.** DEC-136 attributes every row to the model whose
responses produced it, reading the recording's own usage or the execution ledger, and leaves it
empty where none was involved. Not one row in the earlier arm attributes to a model. The later
arm's rows almost all do. Nobody had to characterise either set; the record already did.

**One row's empty attribution means something else, and the column cannot tell you which.** At the
earlier snapshot thirteen recordings were authored offline and the fourteenth — ForgeFlow — was a
genuine live capture whose usage predated the attribution format, so it reports nothing for a
different reason. That is a caveat against the *mechanism*, not against the comparison: it makes
the earlier arm marginally more live than the column can show, and the gap it is being read for is
sixty points wide.

**What this does and does not establish.** It does not show that the pipeline got worse: the
authored recordings were written to exercise the truth set, so scoring well against it was the
property they were built for, and reading them as a measurement of the pipeline was always a
category error. What it establishes is the size of that error — and therefore how much weight a
single-author benchmark's headline number can carry before an independent annotation set exists
(DEC-112, still unauthored). It is the most useful number this corpus owns about itself.

{note_text}
"""
