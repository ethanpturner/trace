"""The comparison table: one per-tool summary rendered from the same feeds as the scorecard.

The scorecard (DEC-076) is per scenario and condition; the comparison collapses those runs into
one row per tool — the generic-prompt baseline, the structured single-pass baseline, and Trace —
so a reader sees the pipeline's edge and its cost at a glance. It inherits the scorecard's
boundary exactly: metrics and identifiers only, never a finding title, a document fragment, or any
assessment content. It is Markdown rather than HTML because it is read in the README and the
portfolio, beside prose, where the scorecard's HTML page is not.

Every populated cell is a number that appears in a committed feed, and every empty cell says why
it is empty rather than leaving a blank a reader fills in optimistically. Three properties are
stated as structural facts rather than measured, because measuring them would measure nothing:
Trace's persisted objects are schema-valid by construction (an invalid proposal never persists,
DEC-006); a baseline links no claim to evidence because `BaselineFindings` has no evidence field;
and run-to-run stability is a live-run measurement (DEC-077) that deterministic replay cannot
produce. The honest empty cell is the point — the market the survey describes is full of tools
whose comparison tables fill every cell and cite nothing.

STRIDE GPT is not a row: it cannot run through the seam, so it is scored in the portfolio
write-up, not here (DEC-074). It is named under the table so its absence is a stated decision, not
an omission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from trace_ai.services.evaluation.stability import agreement_text as stability_agreement
from trace_ai.services.evaluation.stability import measurements as stability_measurements

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

__all__ = ["ToolSummary", "render_comparison", "summaries_from_feeds"]

# The baseline conditions (DEC-074), by the feed condition name, and how each is labelled in the
# table. Any condition not listed here is a Trace run — clean, adversarial, or otherwise.
_BASELINE_LABELS = {
    "baseline-generic": "Generic prompt (baseline)",
    "baseline-structured": "Structured single-pass (baseline)",
    "baseline-single-pass": "Whole assessment, one call (baseline)",
}
_TRACE_LABEL = "Trace"


@dataclass(frozen=True, slots=True)
class ToolSummary:
    """One tool's runs collapsed to the five comparison metrics. Counts only, no content."""

    tool: str
    label: str
    scenarios: int
    runs: int
    # schema validity: measured for baselines, structural for Trace.
    schema_valid_runs: int | None
    # evidence-linked claims: measured for Trace, structurally absent for baselines.
    evidence_covered: int | None
    evidence_total: int | None
    # spurious findings the tool produced, and over how many scenarios — lower is better.
    spurious: int
    # injected-instruction compliance under attack: measured for Trace's adversarial runs only.
    compliance: float | None
    compliance_runs: int


def _spurious(feed: dict[str, Any]) -> int:
    findings = (feed.get("items") or {}).get("findings", {})
    return len(findings.get("spurious") or [])


def _metric(feed: dict[str, Any], name: str) -> dict[str, Any] | None:
    return (feed.get("metrics") or {}).get(name)


def _tool_of(feed: dict[str, Any]) -> str:
    condition = str(feed.get("condition", ""))
    return condition if condition in _BASELINE_LABELS else _TRACE_LABEL


def summaries_from_feeds(feeds: Sequence[dict[str, Any]]) -> list[ToolSummary]:
    """Collapse the feeds to one summary per tool, ordered baselines first then Trace.

    A tool with no feeds is omitted rather than shown as a row of dashes.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    for feed in feeds:
        buckets.setdefault(_tool_of(feed), []).append(feed)

    order = [*_BASELINE_LABELS, _TRACE_LABEL]
    summaries: list[ToolSummary] = []
    for tool in order:
        tool_feeds = buckets.get(tool)
        if not tool_feeds:
            continue
        summaries.append(_summarize(tool, tool_feeds))
    return summaries


def _summarize(tool: str, feeds: Sequence[dict[str, Any]]) -> ToolSummary:
    is_baseline = tool in _BASELINE_LABELS

    schema_valid_runs: int | None = None
    if is_baseline:
        schema_valid_runs = sum(1 for feed in feeds if feed.get("schema_valid"))

    evidence_covered: int | None = None
    evidence_total: int | None = None
    if not is_baseline:
        covered = 0
        total = 0
        for feed in feeds:
            entry = _metric(feed, "finding_evidence_coverage")
            if entry is None:
                continue
            sample = int(entry.get("sample_size") or 0)
            total += sample
            # value is covered/sample exactly, so the product recovers the integer count.
            covered += round(float(entry["value"]) * sample)
        evidence_covered, evidence_total = covered, total

    compliance_values = [
        float(entry["value"])
        for feed in feeds
        if (entry := _metric(feed, "injected_instruction_compliance_rate")) is not None
    ]
    compliance = sum(compliance_values) / len(compliance_values) if compliance_values else None

    return ToolSummary(
        tool=tool,
        label=_BASELINE_LABELS.get(tool, _TRACE_LABEL),
        scenarios=len({str(feed["scenario"]) for feed in feeds}),
        runs=len(feeds),
        schema_valid_runs=schema_valid_runs,
        evidence_covered=evidence_covered,
        evidence_total=evidence_total,
        spurious=sum(_spurious(feed) for feed in feeds),
        compliance=compliance,
        compliance_runs=len(compliance_values),
    )


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _schema_cell(summary: ToolSummary) -> str:
    if summary.schema_valid_runs is None:
        return "valid by construction [^schema]"
    rate = _pct(summary.schema_valid_runs / summary.runs) if summary.runs else "—"
    return f"{rate} ({summary.schema_valid_runs}/{summary.runs} runs)"


def _evidence_cell(summary: ToolSummary) -> str:
    if summary.evidence_total is None:
        return "none [^evidence]"
    if summary.evidence_total == 0:
        return "no approved findings"
    # evidence_covered is set whenever evidence_total is (both come from the same runs).
    covered = summary.evidence_covered or 0
    rate = _pct(covered / summary.evidence_total)
    return f"{rate} ({covered}/{summary.evidence_total} findings)"


def _spurious_cell(summary: ToolSummary) -> str:
    return f"{summary.spurious} over {summary.scenarios} scenarios [^fp]"


def _compliance_cell(summary: ToolSummary, *, labelled_per_class: bool = False) -> str:
    if summary.compliance is None:
        return "not run [^injection]"
    scenarios = summary.compliance_runs
    plural = "scenario" if scenarios == 1 else "scenarios"
    marker = " [^classes]" if labelled_per_class else ""
    return f"{_pct(summary.compliance)} ({scenarios} adversarial {plural}){marker}"


def _class_rates(feeds: Sequence[dict[str, Any]]) -> dict[str, float]:
    """The compliance rate per payload class, averaged over the adversarial feeds (#403).

    Only Trace runs carry an `adversarial` block — the baselines are never run against the
    payloads (the [^injection] footnote says why) — so no tool filter is needed here.
    """
    by_class: dict[str, list[float]] = {}
    for feed in feeds:
        adversarial = feed.get("adversarial") or {}
        for name, rate in adversarial.get("compliance_by_class", {}).items():
            by_class.setdefault(str(name), []).append(float(rate))
    return {name: sum(rates) / len(rates) for name, rates in sorted(by_class.items())}


def _stability_cell(summary: ToolSummary, live: Sequence[Mapping[str, Any]]) -> str:
    """Measured for Trace once the DEC-077 artifact exists; the baselines are never run live.

    Each measured scenario reports its own agreement. They are listed, never averaged: an
    agreement count is over one scenario's expected items, and a mean across scenarios would
    read as a stability figure for the pipeline that no run measured.
    """
    if summary.label != _TRACE_LABEL or not live:
        return "not measured [^stability]"
    parts = [
        f"{entry.get('scenario', '')} n={int(entry.get('n', 0))}: {stability_agreement(entry)}"
        for entry in live
    ]
    return f"measured — {'; '.join(parts)} [^stability]"


def render_comparison(
    feeds: Sequence[dict[str, Any]],
    *,
    generated_at: datetime,
    pins: Mapping[str, str],
    live_stability: Mapping[str, Any] | Sequence[Any] | None = None,
) -> str:
    """Render the per-tool comparison as Markdown from the feeds. Metrics and identifiers only."""
    live = stability_measurements(live_stability)
    summaries = summaries_from_feeds(feeds)
    per_class = _class_rates(feeds)
    header = (
        "| Tool | Schema-validity | Evidence-linked claims | "
        "False positives | Injected-instruction compliance | Run-to-run stability |"
    )
    divider = "| --- | --- | --- | --- | --- | --- |"
    rows = [
        f"| {summary.label} | {_schema_cell(summary)} | {_evidence_cell(summary)} | "
        f"{_spurious_cell(summary)} | "
        f"{_compliance_cell(summary, labelled_per_class=bool(per_class))} | "
        f"{_stability_cell(summary, live)} |"
        for summary in summaries
    ]
    if live:
        measured = []
        for entry in live:
            n = int(entry.get("n", 0))
            failed = int(entry.get("failed_runs", 0))
            means = entry.get("metric_mean", {})
            stdevs = entry.get("metric_stdev", {})
            cost = means.get("estimated_cost")
            cost_sd = stdevs.get("estimated_cost", 0.0)
            duration = means.get("execution_duration")
            priced = (
                f", ${cost:.2f} ± {cost_sd:.2f} per run and {duration:.0f}s mean"
                if cost is not None and duration is not None
                else ""
            )
            measured.append(
                f"{n} completed live runs of {entry.get('scenario', '')} on "
                f"{entry.get('profile', '')} ({failed} further attempts failed and are "
                f"counted){priced}"
            )
        stability_footnote = (
            "[^stability]: Measured per DEC-077 — "
            + "; ".join(measured)
            + ". Identical input, checkpoint decisions from the protocol's named default policy "
            "with the defaulted count disclosed. Each scenario reports its own agreement and "
            "they are not averaged. The per-metric variance tables are on the "
            "[scorecard](scorecard.html). The baselines are never run live, so their variance "
            "stays unmeasured. Reported, never gated."
        )
    else:
        stability_footnote = (
            "[^stability]: Run-to-run variance requires repeated live runs (DEC-077); these "
            "are deterministic offline replays, whose zero variance measures the recording, "
            "not the model. No live run has been measured."
        )
    classes_footnote = ""
    if per_class:
        breakdown = ", ".join(f"{name} {_pct(rate)}" for name, rate in per_class.items())
        classes_footnote = (
            "\n[^classes]: Per payload class, because DEC-075 makes the aggregate meaningless "
            f"as a universal claim: {breakdown}. Checkpoint bypass is structural — a checkpoint "
            "advances only on a recorded reviewer decision (DEC-005) — and its zero is shown "
            "with that basis rather than measured each run; every other class is measured "
            "against what the run produced. The per-run detail is in the "
            "[scorecard](scorecard.html).\n"
        )

    total_scenarios = len({str(feed["scenario"]) for feed in feeds})
    pin_text = ", ".join(f"{key} {value}" for key, value in pins.items())

    return f"""<!-- Generated by scripts/build_comparison.py — do not edit by hand. -->
# Trace versus the prompt baselines

Every cell below is a number from a committed evaluation feed, regenerated offline from the
recorded runs by `scripts/build_comparison.py`; the same runs render the per-scenario
[evaluation scorecard](scorecard.html). Metrics and identifiers only — no assessment content
(DEC-076). Generated {generated_at.date().isoformat()} over {total_scenarios} scenarios ({pin_text}).

{header}
{divider}
{chr(10).join(rows)}

The two baselines are a single model call over the same source documents and the same requirements
catalog Trace sees, scored by the same structural matcher (DEC-074); ties are resolved in the
baseline's favour. Trace runs are the clean and adversarial conditions of the scenarios that carry
a recording. The tools are scored on different scenario sets — the "False positives" cell states
each tool's scenario count — because not every scenario has a recording for every tool yet; the
head-to-head subset is the scenarios where a Trace clean run and both baselines all appear.

STRIDE GPT, the open-source incumbent, is not a row: it cannot run through the seam, and a wrapper
would measure the wrapper, so it is scored in the portfolio write-up rather than in the repository
(DEC-074).

[^schema]: Trace's persisted objects are schema-valid by construction — a proposal that fails
    validation never enters state (DEC-006) — so there is no rate to sample. The baselines' output
    can fail to validate, and that failure is counted, not excused.

[^evidence]: A baseline links no claim to evidence because its output schema (`BaselineFindings`)
    carries a title, requirement, component, and rationale and no evidence reference; it cannot
    cite a document even in principle. Trace's figure is approved findings whose every cited
    `EvidenceReference` resolves to a stored, hashed excerpt (`finding_evidence_coverage`).

[^fp]: Spurious findings — produced but standing on no expected requirement — over the scenarios
    the tool was scored on; lower is better. The scenarios plant specific false-positive classes
    for a generic reviewer to invent: a local password policy an inherited control already covers,
    an encryption detail the managed database supplies, and a contradiction between documents.
    A finding on an expected requirement under a component name the expectation does not carry is
    not counted here and does not match either (DEC-148): the expectation stays missed, and the
    finding is reported as divergent rather than asserted to be a false positive. The rule applies
    to the baselines and the pipeline alike. Trace's cell pools every recorded run, including the
    two pre-batching `claude-opus-5` captures whose funnel defect DEC-116 diagnosed and DEC-134
    fixed; the scorecard's *Pooled accuracy by stratum* separates them, and the per-scenario detail
    is in the [scorecard](scorecard.html).

[^injection]: The injected-instruction compliance rate is measured only where there is a defense to
    test. Trace's defense is the evidence fence and the structural checkpoints; a single-prompt
    baseline has neither, so the payload is not run through it — the result would measure the
    absence of a defense the baseline never claimed. Zero is the target (DEC-075).
{classes_footnote}
{stability_footnote}
"""
