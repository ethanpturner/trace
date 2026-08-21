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

from trace_ai.services.evaluation.stability import agreement_text as stability_agreement
from trace_ai.services.evaluation.stability import measurements as stability_measurements

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
    model: str | None = None
    """The model the row's responses are attributed to (DEC-136): the recorded usage's model for
    a replayed capture, the execution ledger's for a live run, joined with ` + ` when an overlay
    routed more than one. None for an authored recording — no call was made, and the dash keeps
    an authored row from wearing a model's name (DEC-092's absent-is-a-dash rule)."""

    workflow_version: str | None = None
    """The workflow shape the row's recording pins (DEC-134), read from the feed. The
    stratification section (DEC-143) refuses to pool rows across shapes without a label, and the
    shape is half of the stratum key. None where a feed predates the field — rendered as a dash,
    and pooled only under the labelled mixed stratum."""

    evidence_coverage: float | None = None
    """`evidence_assessment_coverage` (DEC-116): the fraction of supplied evidence subjects the
    validation phase actually assessed. None where the run reported none — baselines make one
    call and assess nothing, and pre-metric recordings carry no reading."""

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
    annotation_agreement: float | None = None
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
            model=" + ".join(str(m) for m in feed.get("models") or []) or None,
            workflow_version=(
                str(feed["workflow_version"]) if feed.get("workflow_version") is not None else None
            ),
            evidence_coverage=_metric(feed, "evidence_assessment_coverage"),
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
            annotation_agreement=_metric(feed, "annotation_agreement"),
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


def _ratio(numerator: int, denominator: int) -> str:
    """A pooled percentage that carries its denominator (DEC-143): a 100% over 2 must read
    differently from a 100% over 50, and the counts are the honest interval statement — the
    corpus states n rather than inventing confidence arithmetic (DEC-077's posture)."""
    if not denominator:
        return "—"
    return f"{numerator / denominator * 100:.0f}% ({numerator}/{denominator})"


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
table.main th:nth-child(3), table.main td:nth-child(3) { text-align: left; }
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
                row.evidence_coverage,
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
            f"<td>{_pct(row.evidence_coverage)}</td>"
            f"<td>{_count(row.token_usage)}</td></tr>"
        )
    return f"""
<h2>Truth-set coverage</h2>
<p class="meta">The reserved metrics (#329), each computed only where the scenario authors its
truth source. Context accuracy, threat coverage, and mapping accuracy are recall against the
expected-context, expected-threats, and expected-control-mappings files; question usefulness
covers the expected questions not paired to a documentation gap; the unsupported-claim rate is
over the report's prose sentences. A dash is unmeasured, never zero — tokens are unreported by
offline replays and populate from live runs, and a dash under Dup miss means the scenario's
duplicate pairs produced no evaluable population (DEC-110): no data is not a zero rate.
Coverage is `evidence_assessment_coverage` (DEC-116) — under the batched shape (DEC-134) an
unassessed subject fails the attempt, so a batched row reading below 100% is a defect, not a
budget note. Context and threat matching are exact-name
structural checks: forgeflow's context and threat rows reflect naming divergence between the
live run and the independently authored truth set (its components and flows match fully;
actors, assets, and claims differ by name), not extraction omission — the per-type breakdown
is recorded in each metric's notes.</p>
<div class="scroll">
<table>
<thead><tr>
<th>Scenario</th><th>Condition</th>
<th>Context</th><th>Threats</th><th>Mappings</th><th>Questions</th>
<th>Unsupported</th><th>Severity</th><th>Dup miss</th><th>Coverage</th><th>Tokens</th>
</tr></thead>
<tbody>
{chr(10).join(lines)}
</tbody>
</table>
</div>"""


_STABILITY_METRICS = (
    ("estimated_cost", "Cost (USD)"),
    ("execution_duration", "Runtime (s)"),
    ("model_call_count", "Model calls"),
    ("token_usage", "Tokens"),
    ("evidence_assessment_coverage", "Evidence-assessment coverage"),
    ("finding_evidence_coverage", "Evidence coverage"),
    ("false_positive_rate", "False-positive rate"),
    ("false_negative_rate", "False-negative rate"),
)


def _stability_run_row(live: dict[str, Any]) -> str:
    """One measurement's headline figures: the counts DEC-077 requires be visible.

    Failed attempts and defaulted decisions are figures here rather than prose because they
    qualify the agreement beside them — an agreement count over runs whose decisions were
    substituted means something different from one over runs that matched the recorded human.
    """
    n = int(live.get("n", 0))
    failed = int(live.get("failed_runs", 0))
    return (
        f"<tr><td>{html.escape(str(live.get('scenario', '')))}</td>"
        f"<td>{html.escape(str(live.get('profile', '')))}</td>"
        f"<td>{n}</td><td>{failed}</td>"
        f"<td>{int(live.get('defaulted_decisions', 0))}</td>"
        f"<td>{html.escape(stability_agreement(live))}</td></tr>"
    )


def _stability_metric_table(live: dict[str, Any]) -> str:
    """The per-metric variance for one measured scenario."""
    means = live.get("metric_mean", {})
    stdevs = live.get("metric_stdev", {})
    rows = [
        f"<tr><td>{label}</td><td>{means[name]:.4g}</td><td>{stdevs.get(name, 0.0):.4g}</td></tr>"
        for name, label in _STABILITY_METRICS
        if name in means
    ]
    if not rows:
        return ""
    return f"""<h3>{html.escape(str(live.get("scenario", "")))}</h3>
<div class="scroll">
<table>
<thead><tr><th>Metric</th><th>Mean</th><th>Std dev</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</div>"""


def _live_stability_section(live: dict[str, Any] | list[Any] | None) -> str:
    """The DEC-077 measurement, rendered from the committed summary artifact.

    Read, never regenerated: live runs are manual and priced (DEC-077), so the drift checks
    cannot re-run them — the committed `docs/eval/live-stability.json` is the record, the way
    the history file is. Absent artifact, absent section. Cost and runtime are the two cells
    the offline table cannot carry (its replays cost nothing by construction), which is why
    they render here with the profile named.

    The artifact carries one measurement per scenario measured, so the section leads with the
    run counts across scenarios and then gives each its variance table. Scenarios are rendered
    beside each other, never differenced: a measurement on one scenario is not a baseline for
    another, and the page states counts rather than implying a trend.
    """
    entries = stability_measurements(live)
    if not entries:
        return ""
    metric_tables = "\n".join(
        table for entry in entries if (table := _stability_metric_table(entry))
    )
    return f"""<h2>Live stability</h2>
<p class="note">DEC-077's protocol: n live runs per scenario, identical input, checkpoint
decisions replayed by content fingerprint with the unmatched falling back to the named default
policy — so the defaulted count qualifies the agreement beside it. Reported, never gated. Rows
are listed, never differenced: each measures one scenario on one profile and workflow shape, so
a row is not a baseline for another and the page states no trend across them.</p>
<div class="scroll">
<table>
<thead><tr><th>Scenario</th><th>Profile</th><th>Completed runs</th><th>Failed attempts</th>
<th>Defaulted decisions</th><th>Item agreement</th></tr></thead>
<tbody>
{chr(10).join(_stability_run_row(entry) for entry in entries)}
</tbody>
</table>
</div>
{metric_tables}"""


def _history_section(history: Sequence[ScorecardSnapshot]) -> str:
    """The retained snapshots (DEC-081), newest first: version keys and pooled numbers only.

    Pooling is over authoritative rows — the history tracks the pipeline, so baselines and
    ablations stay out of it. The per-row detail every snapshot retains lives in the committed
    history file this section is rendered from.
    """
    if not history:
        return ""
    lines = []
    for snapshot in reversed(list(history)):
        authoritative = [row for row in snapshot.rows if row.authoritative]
        matched = sum(row.matched for row in authoritative)
        missed = sum(row.missed for row in authoritative)
        spurious = sum(row.spurious for row in authoritative)
        lines.append(
            f"<tr><td>{html.escape(snapshot.recorded_at)}</td>"
            f"<td>{html.escape(snapshot.git_ref)}</td>"
            f"<td>{html.escape(_short_digest(snapshot.prompt_digest))}</td>"
            f"<td>{html.escape(snapshot.catalog_version)}</td>"
            f"<td>{_ratio(matched, matched + spurious)}</td>"
            f"<td>{_ratio(matched, matched + missed)}</td>"
            f"<td>{_pct(snapshot.f1)}</td><td>{_cost(snapshot.cost)}</td></tr>"
        )
    return f"""
<h2>History</h2>
<p class="meta">Retained snapshots (DEC-081), newest first. Precision, recall, and F1 are pooled
over the authoritative rows of each snapshot and carry their counts (DEC-143); a snapshot's pool
can mix models and shapes, and the stratified table above is the labelled reading of the current
corpus. Per-row detail is retained in <code>docs/eval/history.jsonl</code>.</p>
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


def _stratified_section(rows: Sequence[ScorecardRow]) -> str:
    """Pooled accuracy split by (model, workflow shape) — DEC-143's refusal to pool unlabelled.

    A single pooled number over rows measured on different models and workflow shapes misleads
    in a measured way: the #332 record shows decision-replay fidelity differing per model, and
    the pre-batching rows carry a diagnosed failure mode the batched rows do not. Each stratum
    pools only rows one model produced under one shape; the final row is the mixed pool, kept —
    pooled-with-labels beats separate-and-unfindable — and labelled so it can never read as a
    single population's number. Percentages carry their denominators.
    """
    authoritative = [row for row in rows if row.authoritative and row.condition == "clean"]
    if not authoritative:
        return ""
    strata: dict[tuple[str, str], list[ScorecardRow]] = {}
    for row in authoritative:
        key = (row.model or "—", row.workflow_version or "—")
        strata.setdefault(key, []).append(row)
    lines = []
    for (model, shape), grouped in sorted(strata.items()):
        matched = sum(row.matched for row in grouped)
        missed = sum(row.missed for row in grouped)
        spurious = sum(row.spurious for row in grouped)
        lines.append(
            f"<tr><td>{html.escape(model)}</td><td>{html.escape(shape)}</td>"
            f"<td>{len(grouped)}</td>"
            f"<td>{matched}</td><td>{missed}</td><td>{spurious}</td>"
            f"<td>{_ratio(matched, matched + spurious)}</td>"
            f"<td>{_ratio(matched, matched + missed)}</td></tr>"
        )
    if len(strata) > 1:
        matched = sum(row.matched for row in authoritative)
        missed = sum(row.missed for row in authoritative)
        spurious = sum(row.spurious for row in authoritative)
        lines.append(
            f"<tr><td colspan=2>all strata — pooled across models and shapes</td>"
            f"<td>{len(authoritative)}</td>"
            f"<td>{matched}</td><td>{missed}</td><td>{spurious}</td>"
            f"<td>{_ratio(matched, matched + spurious)}</td>"
            f"<td>{_ratio(matched, matched + missed)}</td></tr>"
        )
    return f"""
<h2>Pooled accuracy by stratum</h2>
<p class="meta">Authoritative clean rows pooled per (model, workflow shape) stratum (DEC-143).
Rows measured on different models or shapes are different populations — the two pre-batching
`claude-opus-5` rows carry the diagnosed evidence-validation funnel failure the batched rows do
not, and cross-model rows differ in decision-replay fidelity (the #332 record's measured
confound) — so the mixed pool renders only under its explicit label. Every percentage carries
its counts.</p>
<div class="scroll">
<table>
<thead><tr>
<th>Model</th><th>Workflow</th><th>Rows</th>
<th>Matched</th><th>Missed</th><th>Spurious</th>
<th>Precision</th><th>Recall</th>
</tr></thead>
<tbody>
{chr(10).join(lines)}
</tbody>
</table>
</div>"""


def _baseline_section(rows: Sequence[ScorecardRow]) -> str:
    """The live head-to-head (DEC-143): the pipeline's clean row beside its three baselines.

    The comparison that carries the thesis, live-vs-live since the #484 sweep recorded a live
    control arm beside every capture. Cells are matched/missed/spurious counts — the denominators
    are the cells. The delta column is the single-pass comparison the DEC-126 baseline exists
    for: the whole assessment in one call against the decomposed pipeline, as a difference in
    spurious findings (invented weaknesses, the DEC-009 failure class).
    """
    by_scenario: dict[str, dict[str, ScorecardRow]] = {}
    for row in rows:
        by_scenario.setdefault(row.scenario, {})[row.condition] = row
    ordered = [
        (scenario, conditions)
        for scenario, conditions in sorted(by_scenario.items())
        if "clean" in conditions
        and conditions["clean"].authoritative
        and any(condition.startswith("baseline-") for condition in conditions)
    ]
    if not ordered:
        return ""

    def cell(row: ScorecardRow | None) -> str:
        if row is None:
            return "<td>—</td>"
        return f"<td>{row.matched}/{row.missed}/{row.spurious}</td>"

    lines = []
    for scenario, conditions in ordered:
        trace = conditions["clean"]
        single = conditions.get("baseline-single-pass")
        delta = "—" if single is None else f"{single.spurious - trace.spurious:+d}"
        lines.append(
            f"<tr><td>{html.escape(scenario)}</td>"
            f"{cell(trace)}"
            f"{cell(conditions.get('baseline-generic'))}"
            f"{cell(conditions.get('baseline-structured'))}"
            f"{cell(single)}"
            f"<td>{delta}</td></tr>"
        )
    return f"""
<h2>Live baselines beside the pipeline</h2>
<p class="meta">Per scenario: the authoritative clean row beside the three one-call baselines
(DEC-074, DEC-126), as matched/missed/spurious counts. Baselines are non-authoritative and
excluded from every pooled number; this section is where they are read, against the pipeline
on the same inputs. Δ spurious is the single-pass baseline's spurious count minus the
pipeline's — the decomposition question as a difference in invented weaknesses, positive when
the one-call form invents more.</p>
<div class="scroll">
<table>
<thead><tr>
<th>Scenario</th><th>Trace m/x/s</th><th>Generic m/x/s</th>
<th>Structured m/x/s</th><th>Single-pass m/x/s</th><th>Δ spurious</th>
</tr></thead>
<tbody>
{chr(10).join(lines)}
</tbody>
</table>
</div>"""


def _comparison_section(
    title: str,
    intro: str,
    feeds: Sequence[dict[str, Any]],
    *,
    record: str,
) -> str:
    """One committed comparison read out (DEC-143): rows from the priced feeds, read like the
    live-stability artifact — the drift checks cannot re-run a priced live arm, so the committed
    feed files are the record and the page renders whatever they carry. Absent files, absent
    section. The `defaulted decisions` column is the #332 confound made visible: a checkpoint
    the replay could not answer was defaulted, and a row's accuracy is conditioned on how many."""
    if not feeds:
        return ""
    rows = rows_from_feeds(feeds)
    labels = {
        (str(feed["scenario"]), str(feed["condition"])): (
            str(feed.get("label") or "—"),
            int(feed.get("defaulted_decisions") or 0),
        )
        for feed in feeds
    }
    lines = []
    previous_scenario: str | None = None
    for row in sorted(
        rows, key=lambda entry: (entry.scenario, labels[(entry.scenario, entry.condition)][0])
    ):
        label, defaulted = labels[(row.scenario, row.condition)]
        attr = ' class="scenario-start"' if row.scenario != previous_scenario else ""
        previous_scenario = row.scenario
        lines.append(
            f"<tr{attr}><td>{html.escape(row.scenario)}</td><td>{html.escape(label)}</td>"
            f"<td>{html.escape(row.model) if row.model else '—'}</td>"
            f"<td>{html.escape(row.workflow_version) if row.workflow_version else '—'}</td>"
            f"<td>{row.matched}</td><td>{row.missed}</td><td>{row.spurious}</td>"
            f"<td>{_pct(row.evidence_coverage)}</td>"
            f"<td>{defaulted}</td>"
            f"<td>{_cost(row.cost)}</td></tr>"
        )
    return f"""
<h2>{html.escape(title)}</h2>
<p class="meta">{intro} Rendered from the committed feeds — priced live arms the drift checks
cannot re-run, read like the live-stability artifact. The written record with its caveats is
<code>{html.escape(record)}</code>; this table restates none of them loosely.</p>
<div class="scroll">
<table>
<thead><tr>
<th>Scenario</th><th>Arm</th><th>Model</th><th>Workflow</th>
<th>Matched</th><th>Missed</th><th>Spurious</th>
<th>Coverage</th><th>Defaulted decisions</th><th>Cost</th>
</tr></thead>
<tbody>
{chr(10).join(lines)}
</tbody>
</table>
</div>"""


def _review_time_section(rows: Sequence[ScorecardRow], feeds: Sequence[dict[str, Any]]) -> str:
    """Checkpoint review time (DEC-117), where any feed carries it — and the structural reason
    it is absent when it is absent, stated rather than omitted (DEC-143). A harness-decided
    checkpoint records no session, so replayed feeds carry no timing by design; the instrument
    populates only from a run a person reviewed through the review commands."""
    carrying = [
        (
            str(feed["scenario"]),
            str(feed["condition"]),
            _metric(feed, "context_review_seconds"),
            _metric(feed, "finding_review_seconds"),
        )
        for feed in feeds
        if _metric(feed, "context_review_seconds") is not None
        or _metric(feed, "finding_review_seconds") is not None
    ]
    if not carrying:
        return """
<h2>Checkpoint review time</h2>
<p class="meta">DEC-117's instrument: wall clock from the first review-command session at a
checkpoint to that checkpoint's conclusion, emitted as <code>context_review_seconds</code> and
<code>finding_review_seconds</code>, gating nothing. Every row on this page replays a recording,
and a harness-decided checkpoint records no session — so the column is structurally empty here,
not unmeasured by neglect: the numbers populate from live human-reviewed runs, and none is part
of the recorded corpus yet.</p>"""
    lines = [
        f"<tr><td>{html.escape(scenario)}</td><td>{html.escape(condition)}</td>"
        f"<td>{_count(context_seconds)}</td><td>{_count(finding_seconds)}</td></tr>"
        for scenario, condition, context_seconds, finding_seconds in sorted(carrying)
    ]
    return f"""
<h2>Checkpoint review time</h2>
<p class="meta">DEC-117's instrument: wall clock from the first review-command session at a
checkpoint to that checkpoint's conclusion, stated as wall clock — attention is not observable
from a command line. Gates nothing.</p>
<div class="scroll">
<table>
<thead><tr><th>Scenario</th><th>Condition</th><th>Context review (s)</th>
<th>Finding review (s)</th></tr></thead>
<tbody>
{chr(10).join(lines)}
</tbody>
</table>
</div>"""


def _agreement_section(rows: Sequence[ScorecardRow]) -> str:
    """Annotator agreement (#530, DEC-112): a statement about the truth sets, kept apart from
    the run metrics so the two are never read as one claim. With no second annotation set the
    section states the absence and what fills it (DEC-143) — an instrument that silently
    disappears reads as never having existed."""
    carrying = [row for row in rows if row.annotation_agreement is not None and row.authoritative]
    if not carrying:
        return """
<h2>Annotator agreement</h2>
<p class="meta">Jaccard agreement between the authoritative truth set and a second annotation
set, pooled over the DEC-056 identity forms (DEC-112). The instrument and its adjudication rule
(DEC-119) exist; no second annotation set has been authored, so there is no number here — a
statement about the record, not a zero. Every truth-set-relative metric on this page rests on a
single annotator until one is (#565).</p>"""
    lines = [
        f"<tr><td>{html.escape(row.scenario)}</td><td>{_pct(row.annotation_agreement)}</td></tr>"
        for row in carrying
    ]
    return f"""
<h2>Annotator agreement</h2>
<p class="meta">Jaccard agreement between the authoritative truth set and a second annotation
set, pooled over the DEC-056 identity forms (DEC-112). A statement about the truth set, not
the run: the first set stays authoritative, and the statistic gates nothing. Scenarios with no
second set measure nothing here.</p>
<div class="scroll">
<table>
<thead><tr><th>Scenario</th><th>Agreement</th></tr></thead>
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
    live_stability: dict[str, Any] | list[Any] | None = None,
    model_comparison: Sequence[dict[str, Any]] = (),
    prompt_comparison: Sequence[dict[str, Any]] = (),
) -> str:
    """Render the scorecard HTML deterministically from the feeds. Metrics and identifiers only.

    `model_comparison` and `prompt_comparison` are the committed comparison feeds (#332, #331) —
    priced live arms read like the live-stability artifact, never regenerated by the drift
    checks. Empty sequences render no section (DEC-143).
    """
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
            f"<td>{html.escape(row.model) if row.model else '—'}</td>"
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
<table class="main">
<thead><tr>
<th>Scenario</th><th>Condition</th><th>Model</th>
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
(DEC-056 matching). Model is the row's attribution (DEC-136): the model the recorded usage or
the execution ledger says produced the responses — rows measured on different models must never
be read as one population, and a dash marks an authored recording no model produced. A dash
elsewhere is an undefined ratio — recall where the scenario expects no findings,
precision where a run produced none. Compliance is the injected-instruction compliance rate under
attack (DEC-075) — zero is the target — shown only for adversarial conditions. Rows marked * are
non-authoritative (baselines and ablations, DEC-012). Run-to-run variance is recorded per
DEC-077 where a live protocol ran; deterministic replays show none.
Per-item diffs stay local (DEC-073). The forgeflow and husky-ai rows are the two pre-batching
`claude-opus-5` captures (workflow 0.1): each approved defensible findings that matched none of
the reachable expectations, and the diagnosis is recorded — the single evidence-validation call
silently under-assessed (25 of 185 mappings on forgeflow; coverage 0.275 on husky-ai), so an
unassessed mapping resolved to no output (DEC-013, DEC-116,
<code>docs/eval/live-diagnosis.md</code>). The DEC-134 batched shape closed that funnel and
every workflow-0.2 capture reads coverage 100%; re-capturing the two 0.1 scenarios under it is
the named follow-up (#588's residual). Two of forgeflow's three finding expectations are
conditional on a reviewer-resolved contradiction its protocol did not supply — they report as
conditional-unreached, not missed, with the paired questions carrying their grade (DEC-133).
Cost shows a dash where the run was an offline replay that measured nothing.</p>
{_stratified_section(rows)}
{_baseline_section(rows)}
{_adversarial_section(rows)}
{_truth_section(rows)}
{
        _comparison_section(
            "Model comparison",
            "The #332 arms: three profiles over shared scenarios, cost beside quality, one run per "
            "arm — n=1, stated rather than smoothed. Accuracy across models is confounded by "
            "decision-replay fidelity; the defaulted-decisions column is that confound, visible.",
            model_comparison,
            record="docs/eval/model-comparison.md",
        )
    }
{
        _comparison_section(
            "Prompt comparison",
            "The #331 pair: pre- and post-batching evidence validation as one unit — prompt text "
            "and call shape travel together on the workflow version (DEC-134), so this comparison "
            "isolates the pair, not the prose.",
            prompt_comparison,
            record="docs/eval/prompt-comparison-331.md",
        )
    }
{_review_time_section(rows, feeds)}
{_agreement_section(rows)}
{_live_stability_section(live_stability)}
{_history_section(history)}
{_trend_section(history)}
</body>
</html>
"""
