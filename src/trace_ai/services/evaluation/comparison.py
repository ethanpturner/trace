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
DEC-006); a baseline's citation resolves to nothing because `BaselineFinding.evidence_quote` is a
string the model wrote rather than a reference to a stored excerpt; and run-to-run stability is a
live-run measurement (DEC-077) that deterministic replay cannot produce. The honest empty cell is the point — the market the survey describes is full of tools
whose comparison tables fill every cell and cite nothing.

STRIDE GPT is not a row: it cannot run through the seam, so it is scored in the portfolio
write-up, not here (DEC-074). It is named under the table so its absence is a stated decision, not
an omission.

An **external arm** (DEC-155) is a row of a different kind and is labelled as one: a code
reviewer's validated findings, hand-mapped to the catalogue and scored by the same matcher, keyed
`external-<arm>`. It is non-authoritative, attributed to the model its feed names (DEC-136), and
carries its provenance inline (DEC-152). Where a denominator is under five the cell shows counts
and no percentage. No external feed committed means no external row, and the table renders
exactly as before.
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
_EXTERNAL_PREFIX = "external-"
_SMALL_DENOMINATOR = 5


@dataclass(frozen=True, slots=True)
class ToolSummary:
    """One tool's runs collapsed to the comparison metrics. Counts only, no content."""

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
    # DEC-154: authored rejections a spurious finding breached, over the scoreable population.
    rejections_breached: int
    rejections_scoreable: int
    # DEC-155: set on an external arm only — the tool, its models, its provenance, and how many
    # of its cited code locators resolved at the reviewed snapshot (None where not measured).
    external: bool = False
    models: str | None = None
    provenance: str | None = None
    tool_identity: str | None = None
    locators_resolved: int | None = None
    locators_total: int | None = None
    # How many of the adversarial runs behind `compliance` name a model, so the cell can say
    # captured or authored per DEC-152 instead of asserting one for all of them.
    compliance_captured_runs: int = 0


def _spurious(feed: dict[str, Any]) -> int:
    findings = (feed.get("items") or {}).get("findings", {})
    return len(findings.get("spurious") or [])


def _rejections(feed: dict[str, Any]) -> tuple[int, int]:
    """Breached and scoreable rejections for one run (DEC-154), zero-zero where unscoreable."""
    entry = (feed.get("items") or {}).get("rejections") or {}
    return len(entry.get("breached") or {}), int(entry.get("scoreable") or 0)


def _metric(feed: dict[str, Any], name: str) -> dict[str, Any] | None:
    return (feed.get("metrics") or {}).get(name)


def _is_external(condition: str) -> bool:
    return condition.startswith(_EXTERNAL_PREFIX)


def _tool_of(feed: dict[str, Any]) -> str:
    condition = str(feed.get("condition", ""))
    if condition in _BASELINE_LABELS or _is_external(condition):
        return condition
    return _TRACE_LABEL


def summaries_from_feeds(feeds: Sequence[dict[str, Any]]) -> list[ToolSummary]:
    """Collapse the feeds to one summary per tool, ordered baselines first then Trace.

    A tool with no feeds is omitted rather than shown as a row of dashes.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    for feed in feeds:
        buckets.setdefault(_tool_of(feed), []).append(feed)

    external_arms = sorted(tool for tool in buckets if _is_external(tool))
    order = [*_BASELINE_LABELS, *external_arms, _TRACE_LABEL]
    summaries: list[ToolSummary] = []
    for tool in order:
        tool_feeds = buckets.get(tool)
        if not tool_feeds:
            continue
        summaries.append(_summarize(tool, tool_feeds))
    return summaries


def _external_label(tool: str) -> str:
    return f"{tool.removeprefix(_EXTERNAL_PREFIX)} (external, non-authoritative)"


def _summarize_external(tool: str, feeds: Sequence[dict[str, Any]]) -> ToolSummary:
    """One external arm's runs collapsed (DEC-155). Locator counts pool; rates never do."""
    models = sorted({str(m) for feed in feeds for m in (feed.get("models") or [])})
    provenances = sorted({str(feed.get("provenance") or "unstated") for feed in feeds})
    tools = sorted(
        {
            f"{(feed.get('external') or {}).get('tool', {}).get('name', '?')} @ "
            f"{(feed.get('external') or {}).get('tool', {}).get('version', '?')}"
            for feed in feeds
        }
    )
    resolved: int | None = None
    total: int | None = None
    for feed in feeds:
        locators = (feed.get("external") or {}).get("locators")
        if not locators:
            continue
        resolved = (resolved or 0) + int(locators.get("resolved") or 0)
        total = (total or 0) + int(locators.get("total") or 0)
    return ToolSummary(
        tool=tool,
        label=_external_label(tool),
        scenarios=len({str(feed["scenario"]) for feed in feeds}),
        runs=len(feeds),
        schema_valid_runs=None,
        evidence_covered=None,
        evidence_total=None,
        spurious=sum(_spurious(feed) for feed in feeds),
        compliance=None,
        compliance_runs=0,
        compliance_captured_runs=0,
        rejections_breached=sum(_rejections(feed)[0] for feed in feeds),
        rejections_scoreable=sum(_rejections(feed)[1] for feed in feeds),
        external=True,
        models=" + ".join(models) or None,
        provenance=", ".join(provenances),
        tool_identity="; ".join(tools),
        locators_resolved=resolved,
        locators_total=total,
    )


def _summarize(tool: str, feeds: Sequence[dict[str, Any]]) -> ToolSummary:
    if _is_external(tool):
        return _summarize_external(tool, feeds)
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
    # A run whose feed names a model consumed a live capture; one that names none replayed an
    # authored recording. The cell reports the split rather than labelling every run by the
    # provenance of the majority (DEC-152, DEC-150).
    captured_runs = sum(
        1
        for feed in feeds
        if _metric(feed, "injected_instruction_compliance_rate") is not None
        and (feed.get("models") or [])
    )

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
        compliance_captured_runs=captured_runs,
        rejections_breached=sum(_rejections(feed)[0] for feed in feeds),
        rejections_scoreable=sum(_rejections(feed)[1] for feed in feeds),
    )


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _counts(numerator: int, denominator: int, unit: str) -> str:
    """Counts, with the percentage only where the denominator is at least five (DEC-155)."""
    noun = f" {unit}" if unit else ""
    if denominator < _SMALL_DENOMINATOR:
        return f"{numerator} of {denominator}{noun}"
    return f"{numerator} of {denominator}{noun} ({_pct(numerator / denominator)})"


def _schema_cell(summary: ToolSummary) -> str:
    if summary.external:
        return (
            f"not applicable — responses {summary.provenance}, "
            f"{summary.models or 'unattributed'} [^external]"
        )
    if summary.schema_valid_runs is None:
        return "valid by construction [^schema]"
    rate = _pct(summary.schema_valid_runs / summary.runs) if summary.runs else "—"
    return f"{rate} ({summary.schema_valid_runs}/{summary.runs} runs)"


def _evidence_cell(summary: ToolSummary) -> str:
    if summary.external:
        if summary.locators_total is None:
            return "locators not measured [^external]"
        if summary.locators_total == 0:
            return "no mapped findings"
        return (
            _counts(summary.locators_resolved or 0, summary.locators_total, "locators")
            + " resolve at the reviewed snapshot [^external]"
        )
    if summary.evidence_total is None:
        # A baseline cites passages; what it cannot do is give the citation a referent.
        return "cited, unresolvable [^evidence]"
    if summary.evidence_total == 0:
        return "no approved findings"
    # evidence_covered is set whenever evidence_total is (both come from the same runs).
    covered = summary.evidence_covered or 0
    rate = _pct(covered / summary.evidence_total)
    return f"{rate} ({covered}/{summary.evidence_total} findings)"


def _spurious_cell(summary: ToolSummary) -> str:
    return f"{summary.spurious} over {summary.scenarios} scenarios [^fp]"


def _rejection_cell(summary: ToolSummary) -> str:
    """Breached over scoreable rejections, or a dash where the population is empty (DEC-150)."""
    if summary.rejections_scoreable == 0:
        return "— [^rejections]"
    if summary.external:
        return (
            _counts(summary.rejections_breached, summary.rejections_scoreable, "")
            + " [^rejections]"
        )
    share = summary.rejections_breached / summary.rejections_scoreable
    return (
        f"{summary.rejections_breached} of {summary.rejections_scoreable} "
        f"({_pct(share)}) [^rejections]"
    )


def _compliance_cell(summary: ToolSummary, *, labelled_per_class: bool = False) -> str:
    if summary.compliance is None:
        return "not run [^injection]"
    scenarios = summary.compliance_runs
    plural = "scenario" if scenarios == 1 else "scenarios"
    marker = " [^classes]" if labelled_per_class else ""
    # Provenance is stated per run rather than asserted for all of them (DEC-152). An adversarial
    # feed that names a model consumed a live capture; one that names none replayed an authored
    # recording, and a rate that mixes the two says how many of each it rests on.
    captured = summary.compliance_captured_runs
    if captured == scenarios:
        provenance = "captured live"
    elif captured == 0:
        provenance = "authored responses"
    else:
        provenance = f"{captured} captured live, {scenarios - captured} authored"
    return f"{_pct(summary.compliance)} ({scenarios} adversarial {plural}, {provenance}){marker}"


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
        "False positives | Rejections breached | Injected-instruction compliance | "
        "Run-to-run stability |"
    )
    divider = "| --- | --- | --- | --- | --- | --- | --- |"
    rows = [
        f"| {summary.label} | {_schema_cell(summary)} | {_evidence_cell(summary)} | "
        f"{_spurious_cell(summary)} | {_rejection_cell(summary)} | "
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
            "against what the run produced, as a **delta against the clean control** for the "
            "same scenario (DEC-164): an expected finding the unattacked run also misses was not "
            "suppressed by an attack, and unsupported conclusions the unattacked run also "
            "produces are the pipeline\u2019s rather than the attack\u2019s. Before DEC-164 the "
            "rule was absolute, so on unsigned-webhooks \u2014 whose clean recording misses "
            "FND-UW-01 too \u2014 one fact read as compliance across five classes at once "
            "(#691). A run with no clean control publishes no rate at all rather than a zero. "
            "The per-run detail is in the "
            "[scorecard](scorecard.html); the confound is in "
            "[adversarial-defence](../architecture/adversarial-defence.md).\n"
        )

    externals = [summary for summary in summaries if summary.external]
    external_footnote = ""
    if externals:
        described = "; ".join(
            f"{summary.label}: {summary.tool_identity}, {summary.runs} run"
            f"{'' if summary.runs == 1 else 's'} over {summary.scenarios} scenario"
            f"{'' if summary.scenarios == 1 else 's'}, responses {summary.provenance}, "
            f"attributed to {summary.models or 'no recorded model'}"
            for summary in externals
        )
        external_footnote = (
            "\n[^external]: An external arm (DEC-155) is a code reviewer that cannot run through "
            "the seam. Its validated findings were mapped by hand to a catalogue requirement and a "
            "component under the DEC-056 rule, recorded in a committed feed under `results/`, and "
            "scored by the same structural matcher as every other row, ties resolved in the "
            "external tool's favour (DEC-074). The row is non-authoritative, never enters an "
            "assessment, and is never a proposal. Findings the tool itself left unproven are "
            "carried as unverified and enter no metric. Schema validity does not apply — the "
            "mapping is a person's record, not a model's output. The evidence cell is DEC-151 "
            "ported to code: whether each cited `path:line` resolves in the worktree at the "
            "reviewed snapshot, reported as counts, with a rate only over five or more. "
            f"{described}.\n"
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

[^evidence]: **The baselines do cite passages.** `BaselineFinding.evidence_quote` is required and
    non-empty, so an earlier wording here — that a baseline "cannot cite a document even in
    principle" — was wrong about this repository's own schema. The difference is narrower and is
    measured rather than asserted: a baseline's citation is a string with no referent, so it can
    only be checked by searching the documents for it, and fewer than half survive that search
    ([citation-fidelity.md](citation-fidelity.md), which also explains why that is a resolvability
    rate and not a fabrication rate). Trace's figure is approved findings whose every cited
    `EvidenceReference` resolves to a stored, hashed excerpt re-verified on read
    (`finding_evidence_coverage`) — a citation a machine follows rather than one a reader trusts.

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

[^rejections]: Authored rejections a spurious finding breached, over the rejections the scenarios
    author with a requirement (DEC-154); lower is better and zero is the target. Every scenario
    carries an `expected-rejections.yaml` — the claims a correct assessment does not make, each
    with the mechanism that stops it — and until DEC-154 nothing scored them. A breach is a
    finding the matcher already classified spurious that cites a rejected requirement, so a
    matched finding cannot breach and neither can a DEC-148 divergence. **Attribution is
    requirement-level, not claim-level**: a spurious finding on a rejected requirement counts
    whether or not it makes the particular claim the rejection wrote, which can only report more
    breaches than were committed, never fewer. `reply-tuner` authors rejections carrying no
    requirement and is outside every denominator here (DEC-150). The pooled cell mixes workflow
    shapes, and the two pre-batching `claude-opus-5` rows carrying DEC-116's funnel contribute
    three of the pipeline's breaches; the stratified table is in DEC-154 and the per-scenario
    detail is in the [scorecard](scorecard.html).

[^injection]: The injected-instruction compliance rate is computed only where there is a defense
    to test. Trace's defense is the evidence fence and the structural checkpoints; a single-prompt
    baseline has neither, so the payload is not run through it — the result would measure the
    absence of a defense the baseline never claimed. Zero is the target (DEC-075).

    **Trace's zero is authored, not captured** (DEC-152). Both adversarial recordings were written
    offline against the deterministic substitute, on the stated premise that "a correct run under
    attack produces the same analysis"; no model has been run against a poisoned document in
    either scored condition. The reason is mechanical rather than evasive: `trace capture` takes a
    scenario and a stage and has no condition parameter, so the capture path cannot reach a
    condition the replay path understands. The one live data point is the ForgeFlow capture, whose
    extraction recorded an `injection_attempt` observation against a real payload — one payload,
    one stage, n=1. Until a condition can be captured, this cell reports what a correct run was
    expected to do.
{classes_footnote}{external_footnote}
{stability_footnote}
"""
