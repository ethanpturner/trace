"""The evaluation scorecard: a static HTML page rendered from the results feeds (DEC-076).

Deterministic generation, metrics only, no assessment content. The scorecard shows, per scenario
and condition, the finding precision/recall/F1 computed from the per-item match sets the harness
records, plus schema validity and cost — the numbers a skeptic re-runs from the repository. It is
not the report and cannot drift toward one: no finding text, no claim text, no evidence excerpt,
no document fragment reaches this page, which is a security property as much as a taxonomy —
adversarial-condition feeds summarize runs whose inputs are attack payloads, and a page that
quoted content would republish the corpus.

Run-to-run variance (DEC-077) is a live measurement; an offline scorecard shows it as not
measured rather than as zero, because deterministic replay's zero variance means nothing. The
per-item diffs (DEC-073) stay local — the one link the reader cannot follow from the page.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

__all__ = ["ScorecardRow", "render_scorecard", "rows_from_feeds"]


@dataclass(frozen=True, slots=True)
class ScorecardRow:
    """One scenario-condition line: finding accuracy and the run's cost, metrics only."""

    scenario: str
    condition: str
    authoritative: bool
    matched: int
    missed: int
    spurious: int
    schema_valid: bool | None
    cost: float | None
    compliance: float | None = None
    """Injected-instruction compliance rate for an adversarial condition (DEC-075), else None."""

    @property
    def precision(self) -> float | None:
        produced = self.matched + self.spurious
        return self.matched / produced if produced else None

    @property
    def recall(self) -> float | None:
        expected = self.matched + self.missed
        return self.matched / expected if expected else None

    @property
    def f1(self) -> float | None:
        precision, recall = self.precision, self.recall
        if precision is None or recall is None or precision + recall == 0:
            return None
        return 2 * precision * recall / (precision + recall)


def _counts(feed: dict[str, Any]) -> tuple[int, int, int]:
    findings = (feed.get("items") or {}).get("findings", {})
    matched = len(findings.get("matched") or {})
    missed = len(findings.get("missed") or [])
    spurious = len(findings.get("spurious") or [])
    return matched, missed, spurious


def _metric(feed: dict[str, Any], name: str) -> float | None:
    entry = (feed.get("metrics") or {}).get(name)
    if entry is None:
        return None
    return float(entry["value"])


def rows_from_feeds(feeds: Sequence[dict[str, Any]]) -> list[ScorecardRow]:
    """One row per feed, sorted so the page is deterministic regardless of feed order."""
    rows = [
        ScorecardRow(
            scenario=str(feed["scenario"]),
            condition=str(feed["condition"]),
            authoritative=bool(feed.get("authoritative", True)),
            matched=_counts(feed)[0],
            missed=_counts(feed)[1],
            spurious=_counts(feed)[2],
            schema_valid=feed.get("schema_valid"),
            cost=_metric(feed, "estimated_cost"),
            compliance=_metric(feed, "injected_instruction_compliance_rate"),
        )
        for feed in feeds
    ]
    return sorted(rows, key=lambda row: (row.scenario, row.condition))


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _cost(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def _schema(value: bool | None) -> str:
    if value is None:
        return "—"
    return "valid" if value else "invalid"


_STYLE = """
:root { --fg: #1f2328; --muted: #57606a; --line: #d0d7de; --bg: #ffffff;
        --head: #f6f8fa; --good: #1a7f37; --bad: #cf222e; }
:root[data-theme="dark"], :root:not([data-theme="light"]) {
  --fg: #e6edf3; --muted: #9198a1; --line: #30363d; --bg: #0d1117;
  --head: #161b22; --good: #3fb950; --bad: #f85149; }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) {
  --fg: #1f2328; --muted: #57606a; --line: #d0d7de; --bg: #ffffff;
  --head: #f6f8fa; --good: #1a7f37; --bad: #cf222e; } }
body { background: var(--bg); color: var(--fg); margin: 0; padding: 2rem;
       font: 15px/1.5 -apple-system, system-ui, sans-serif; }
h1 { font-size: 1.4rem; margin: 0 0 0.25rem; }
.meta { color: var(--muted); margin-bottom: 1.5rem; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; max-width: 100%; }
th, td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--line); text-align: right;
         white-space: nowrap; }
th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align: left; }
thead th { background: var(--head); position: sticky; top: 0; }
tbody tr.scenario-start td { border-top: 2px solid var(--line); }
.ablated { color: var(--muted); }
.note { color: var(--muted); margin-top: 1.5rem; max-width: 60ch; }
"""


def render_scorecard(feeds: Sequence[dict[str, Any]], *, generated_at: datetime) -> str:
    """Render the scorecard HTML deterministically from the feeds. Metrics and identifiers only."""
    rows = rows_from_feeds(feeds)
    body: list[str] = []
    previous_scenario: str | None = None
    for row in rows:
        classes = []
        if row.scenario != previous_scenario:
            classes.append("scenario-start")
            previous_scenario = row.scenario
        if not row.authoritative:
            classes.append("ablated")
        attr = f' class="{" ".join(classes)}"' if classes else ""
        marker = "" if row.authoritative else " *"
        body.append(
            f"<tr{attr}><td>{html.escape(row.scenario)}</td><td>{html.escape(row.condition)}{marker}</td>"
            f"<td>{_pct(row.precision)}</td><td>{_pct(row.recall)}</td><td>{_pct(row.f1)}</td>"
            f"<td>{row.matched}</td><td>{row.missed}</td><td>{row.spurious}</td>"
            f"<td>{_pct(row.compliance)}</td>"
            f"<td>{_schema(row.schema_valid)}</td><td>{_cost(row.cost)}</td></tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trace — Evaluation Scorecard</title>
<style>{_STYLE}</style>
</head>
<body>
<h1>Trace — Evaluation Scorecard</h1>
<p class="meta">Generated {generated_at.date().isoformat()} from recorded runs.
Metrics and identifiers only — no assessment content (DEC-076).</p>
<div class="scroll">
<table>
<thead><tr>
<th>Scenario</th><th>Condition</th>
<th>Precision</th><th>Recall</th><th>F1</th>
<th>Matched</th><th>Missed</th><th>Spurious</th>
<th>Compliance</th><th>Schema</th><th>Cost</th>
</tr></thead>
<tbody>
{chr(10).join(body)}
</tbody>
</table>
</div>
<p class="note">Precision, recall, and F1 are over the finding truth-set field class
(DEC-056 matching). A dash is an undefined ratio — recall where the scenario expects no findings,
precision where a run produced none. Compliance is the injected-instruction compliance rate under
attack (DEC-075) — zero is the target — shown only for adversarial conditions. Rows marked * are
non-authoritative (baselines and ablations, DEC-012). Run-to-run variance (DEC-077) is a live
measurement and is not shown for these recorded runs, which are deterministic. Per-item diffs stay
local (DEC-073).</p>
</body>
</html>
"""
