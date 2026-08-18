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

    from trace_ai.services.evaluation.history import ScorecardSnapshot

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

    compliance_by_class: tuple[tuple[str, float], ...] = ()
    """The rate per payload class, sorted by class name. DEC-075's tradeoff is explicit: the
    rate "is meaningful per class and meaningless as a universal claim, and the scorecard must
    label it per class" — so the aggregate never appears without this breakdown (#403)."""

    attack_detected: bool | None = None
    """Whether the run recorded the injection as an observation — the detection axis. None on
    non-adversarial conditions."""

    context_accuracy: float | None = None
    threat_coverage: float | None = None
    mapping_accuracy: float | None = None
    question_usefulness: float | None = None
    unsupported_claim_rate: float | None = None
    token_usage: float | None = None
    severity_concordance: float | None = None
    duplicate_miss_rate: float | None = None
    """The reserved truth-set and run metrics (#329, #507, #536). None where the scenario
    authors no truth for the metric or the run reported no measurement — unmeasured, never
    zero. `severity_concordance` (DEC-030) is None when no matched finding carries scalar
    guidance; `duplicate_miss_rate` (DEC-110) is None when the scenario authors no duplicate
    pairs or none was evaluable."""

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
            compliance_by_class=tuple(
                sorted(
                    (str(name), float(rate))
                    for name, rate in (feed.get("adversarial") or {})
                    .get("compliance_by_class", {})
                    .items()
                )
            ),
            attack_detected=(
                bool((feed.get("adversarial") or {}).get("attack_detected"))
                if feed.get("adversarial") is not None
                else None
            ),
            context_accuracy=_metric(feed, "context_accuracy"),
            threat_coverage=_metric(feed, "threat_coverage"),
            mapping_accuracy=_metric(feed, "requirement_mapping_accuracy"),
            question_usefulness=_metric(feed, "clarifying_question_usefulness"),
            unsupported_claim_rate=_metric(feed, "unsupported_claim_rate"),
            token_usage=_metric(feed, "token_usage"),
            severity_concordance=_metric(feed, "severity_concordance"),
            duplicate_miss_rate=_metric(feed, "duplicate_miss_rate"),
        )
        for feed in feeds
    ]
    return sorted(rows, key=lambda row: (row.scenario, row.condition))


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _cost(value: float | None) -> str:
    """A dash for unmeasured cost (#431): offline replays estimate nothing, and a column of
    0.0000 reads as instrumentation failure rather than as the deliberate absence it is."""
    return "—" if not value else f"{value:.4f}"


def _grade(value: float | None) -> str:
    """F1 with the defined colors finally used (#431): the page's best and worst cells should
    draw the eye, and a monochrome grid argues for nothing."""
    if value is None:
        return "—"
    rendered = _pct(value)
    if value >= 0.999:
        return f'<span class="good">{rendered}</span>'
    if value <= 0.001:
        return f'<span class="bad">{rendered}</span>'
    return rendered


def _compliance(value: float | None) -> str:
    """Injected-instruction compliance, where zero is the target (DEC-075)."""
    if value is None:
        return "—"
    rendered = _pct(value)
    css = "good" if value <= 0.001 else "bad"
    return f'<span class="{css}">{rendered}</span>'


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
h2 { font-size: 1.15rem; margin: 2rem 0 0.25rem; }
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
.good { color: var(--good); font-weight: 600; }
.bad { color: var(--bad); font-weight: 600; }
"""


def _short_digest(digest: str) -> str:
    return digest.removeprefix("sha256:")[:12]


def _count(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f}"


def _adversarial_section(rows: Sequence[ScorecardRow]) -> str:
    """The two-axis attack detail per payload class, for the adversarial rows (#403).

    DEC-075's own tradeoff: the compliance rate "is meaningful per class and meaningless as a
    universal claim, and the scorecard must label it per class". Detection is the other axis —
    a run that resists an attack it never noticed is a different result from one that named it.
    Rows with no per-class data are omitted; the section disappears when nothing adversarial ran.
    """
    carrying = [row for row in rows if row.compliance_by_class]
    if not carrying:
        return ""
    lines = []
    for row in carrying:
        marker = "" if row.authoritative else " *"
        detected = {True: "yes", False: "no", None: "—"}[row.attack_detected]
        first = True
        for name, rate in row.compliance_by_class:
            scenario_cells = (
                f"<td rowspan={len(row.compliance_by_class)}>{html.escape(row.scenario)}</td>"
                f"<td rowspan={len(row.compliance_by_class)}>{html.escape(row.condition)}{marker}</td>"
                f"<td rowspan={len(row.compliance_by_class)}>{detected}</td>"
                if first
                else ""
            )
            attr = ' class="scenario-start"' if first else ""
            lines.append(
                f"<tr{attr}>{scenario_cells}<td>{html.escape(name)}</td><td>{_pct(rate)}</td></tr>"
            )
            first = False
    return f"""<h2>Adversarial payload classes</h2>
<p class="note">The two attack axes per payload class (DEC-075): whether the run recorded the
injection as an observation, and the injected-instruction compliance rate — zero is the target.
The rate is meaningful per class and meaningless as a universal claim; the aggregate column
above never appears without this breakdown. One class, checkpoint bypass, is structural: a
checkpoint advances only on a recorded reviewer decision (DEC-005), so its zero is shown with
its basis rather than measured each run.</p>
<div class="scroll">
<table>
<thead><tr>
<th>Scenario</th><th>Condition</th><th>Attack detected</th>
<th>Payload class</th><th>Compliance</th>
</tr></thead>
<tbody>
{chr(10).join(lines)}
</tbody>
</table>
</div>"""


def _truth_section(rows: Sequence[ScorecardRow]) -> str:
    """The reserved truth-set and run metrics (#329), for the rows that carry any.

    A dash is unmeasured, never zero: the scenario authors no truth for that metric, or the
    run reported no measurement (offline replays report no tokens). Rows carrying none of the
    six are omitted — baselines run one model call and author nothing these measure.
    """
    carrying = [
        row
        for row in rows
        if any(
            value is not None
            for value in (
                row.context_accuracy,
                row.threat_coverage,
                row.mapping_accuracy,
                row.question_usefulness,
                row.unsupported_claim_rate,
                row.token_usage,
            )
        )
    ]
    if not carrying:
        return ""
    lines = []
    previous_scenario: str | None = None
    for row in carrying:
        classes = []
        if row.scenario != previous_scenario:
            classes.append("scenario-start")
            previous_scenario = row.scenario
        if not row.authoritative:
            classes.append("ablated")
        attr = f' class="{" ".join(classes)}"' if classes else ""
        marker = "" if row.authoritative else " *"
        lines.append(
            f"<tr{attr}><td>{html.escape(row.scenario)}</td>"
            f"<td>{html.escape(row.condition)}{marker}</td>"
            f"<td>{_pct(row.context_accuracy)}</td><td>{_pct(row.threat_coverage)}</td>"
            f"<td>{_pct(row.mapping_accuracy)}</td><td>{_pct(row.question_usefulness)}</td>"
            f"<td>{_pct(row.unsupported_claim_rate)}</td>"
            f"<td>{_pct(row.severity_concordance)}</td>"
            f"<td>{_pct(row.duplicate_miss_rate)}</td>"
            f"<td>{_count(row.token_usage)}</td></tr>"
        )
    return f"""
<h2>Truth-set coverage</h2>
<p class="meta">The reserved metrics (#329), each computed only where the scenario authors its
truth source. Context accuracy, threat coverage, and mapping accuracy are recall against the
expected-context, expected-threats, and expected-control-mappings files; question usefulness
covers the expected questions not paired to a documentation gap; the unsupported-claim rate is
over the report's prose sentences. A dash is unmeasured, never zero — tokens are unreported by
offline replays and populate from live runs. Context and threat matching are exact-name
structural checks: forgeflow's context and threat rows reflect naming divergence between the
live run and the independently authored truth set (its components and flows match fully;
actors, assets, and claims differ by name), not extraction omission — the per-type breakdown
is recorded in each metric's notes.</p>
<div class="scroll">
<table>
<thead><tr>
<th>Scenario</th><th>Condition</th>
<th>Context</th><th>Threats</th><th>Mappings</th><th>Questions</th>
<th>Unsupported</th><th>Severity</th><th>Dup miss</th><th>Tokens</th>
</tr></thead>
<tbody>
{chr(10).join(lines)}
</tbody>
</table>
</div>"""


def _live_stability_section(live: dict[str, Any] | None) -> str:
    """The DEC-077 measurement, rendered from the committed summary artifact.

    Read, never regenerated: live runs are manual and priced (DEC-077), so the drift checks
    cannot re-run them — the committed `docs/eval/live-stability.json` is the record, the way
    the history file is. Absent artifact, absent section. Cost and runtime are the two cells
    the offline table cannot carry (its replays cost nothing by construction), which is why
    they render here with the profile named.
    """
    if not live:
        return ""
    means = live.get("metric_mean", {})
    stdevs = live.get("metric_stdev", {})
    shown = [
        ("estimated_cost", "Cost (USD)"),
        ("execution_duration", "Runtime (s)"),
        ("model_call_count", "Model calls"),
        ("token_usage", "Tokens"),
        ("finding_evidence_coverage", "Evidence coverage"),
        ("false_positive_rate", "False-positive rate"),
        ("false_negative_rate", "False-negative rate"),
    ]
    rows = [
        f"<tr><td>{label}</td><td>{means[name]:.4g}</td><td>{stdevs.get(name, 0.0):.4g}</td></tr>"
        for name, label in shown
        if name in means
    ]
    agreement = ", ".join(
        f"{html.escape(str(key))} {count}/{live.get('n', 0)}"
        for key, count in sorted((live.get("item_agreement") or {}).items())
    )
    failed = int(live.get("failed_runs", 0))
    attempted = int(live.get("n", 0)) + failed
    agreement_text = agreement or "no expected item matched in any run"
    return f"""<h2>Live stability</h2>
<p class="note">DEC-077's measurement: {live.get("n", 0)} live runs of
{html.escape(str(live.get("scenario", "")))} on {html.escape(str(live.get("profile", "")))}
({failed} of {attempted} attempts failed), identical input, checkpoint decisions from the named
default policy with {int(live.get("defaulted_decisions", 0))} defaulted decisions across the
runs. Reported, never gated. Item agreement: {agreement_text}.</p>
<div class="scroll">
<table>
<thead><tr><th>Metric</th><th>Mean</th><th>Std dev</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</div>"""


def _history_section(history: Sequence[ScorecardSnapshot]) -> str:
    """The retained snapshots (DEC-081), newest first: version keys and pooled numbers only.

    Pooling is over authoritative rows — the history tracks the pipeline, so baselines and
    ablations stay out of it. The per-row detail every snapshot retains lives in the committed
    history file this section is rendered from.
    """
    if not history:
        return ""
    lines = [
        f"<tr><td>{html.escape(snapshot.recorded_at)}</td>"
        f"<td>{html.escape(snapshot.git_ref)}</td>"
        f"<td>{html.escape(_short_digest(snapshot.prompt_digest))}</td>"
        f"<td>{html.escape(snapshot.catalog_version)}</td>"
        f"<td>{_pct(snapshot.precision)}</td><td>{_pct(snapshot.recall)}</td>"
        f"<td>{_pct(snapshot.f1)}</td><td>{_cost(snapshot.cost)}</td></tr>"
        for snapshot in reversed(list(history))
    ]
    return f"""
<h2>History</h2>
<p class="meta">Retained snapshots (DEC-081), newest first. Precision, recall, and F1 are pooled
over the authoritative rows of each snapshot; per-row detail is retained in
<code>docs/eval/history.jsonl</code>.</p>
<div class="scroll">
<table>
<thead><tr>
<th>Recorded</th><th>Git ref</th><th>Prompts</th><th>Catalog</th>
<th>Precision</th><th>Recall</th><th>F1</th><th>Cost</th>
</tr></thead>
<tbody>
{chr(10).join(lines)}
</tbody>
</table>
</div>"""


def _trend_section(history: Sequence[ScorecardSnapshot]) -> str:
    """Per-scenario F1 across the retained snapshots (#535): the across-versions view
    evaluation-plan section 16 asks for.

    The history table pools each snapshot, and pooling is exactly what hides a single scenario
    regressing while the pool barely moves. This matrix keeps the scenario axis: one row per
    authoritative scenario-condition pair, one column per snapshot, oldest first so a row reads
    left to right as the pipeline's history. A cell is a dash where that snapshot did not run
    the pair, or where F1 is undefined for it. It takes two snapshots to make a trend; with
    fewer, the section is absent rather than a one-column table pretending otherwise.
    """
    if len(history) < 2:
        return ""
    ordered = list(history)
    pairs = sorted(
        {
            (row.scenario, row.condition)
            for snap in ordered
            for row in snap.rows
            if row.authoritative
        }
    )
    columns = "".join(
        f"<th>{html.escape(snap.recorded_at)}<br><code>{html.escape(snap.git_ref)}</code></th>"
        for snap in ordered
    )
    lines = []
    for scenario, condition in pairs:
        cells = []
        for snap in ordered:
            row = next(
                (
                    candidate
                    for candidate in snap.rows
                    if candidate.authoritative
                    and candidate.scenario == scenario
                    and candidate.condition == condition
                ),
                None,
            )
            cells.append(f"<td>{_pct(row.f1) if row is not None else '—'}</td>")
        lines.append(
            f"<tr><td>{html.escape(scenario)}</td><td>{html.escape(condition)}</td>"
            f"{''.join(cells)}</tr>"
        )
    return f"""
<h2>F1 across versions</h2>
<p class="meta">One row per authoritative scenario and condition, one column per retained
snapshot, oldest first (#535). The pooled History table hides a single scenario regressing while
the pool barely moves; this matrix keeps the scenario axis. A dash is a pair the snapshot did
not run, or an undefined ratio.</p>
<div class="scroll">
<table>
<thead><tr><th>Scenario</th><th>Condition</th>{columns}</tr></thead>
<tbody>
{chr(10).join(lines)}
</tbody>
</table>
</div>"""


def render_scorecard(
    feeds: Sequence[dict[str, Any]],
    *,
    generated_at: datetime,
    history: Sequence[ScorecardSnapshot] = (),
    live_stability: dict[str, Any] | None = None,
) -> str:
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
            f"<td>{_pct(row.precision)}</td><td>{_pct(row.recall)}</td>"
            f"<td>{_grade(row.f1)}</td>"
            f"<td>{row.matched}</td><td>{row.missed}</td><td>{row.spurious}</td>"
            f"<td>{_compliance(row.compliance)}</td>"
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
measurement is recorded per DEC-077 where a live protocol ran; deterministic replays show none.
Per-item diffs stay local (DEC-073). The forgeflow row is the live-model run scored against an
independently authored truth set: it approved four defensible findings under different requirement
identifiers than the truth set names and matched none of the three expected — real weaknesses,
wrong requirement lens (<code>demo/forgeflow/recorded/provenance.md</code>). Cost shows a dash
where the run was an offline replay that measured nothing.</p>
{_adversarial_section(rows)}
{_truth_section(rows)}
{_live_stability_section(live_stability)}
{_history_section(history)}
{_trend_section(history)}
</body>
</html>
"""
