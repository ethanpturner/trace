"""The per-tool comparison table (#277, DEC-074/DEC-076): metrics-only, honest empty cells.

The table collapses the scorecard's feeds to one row per tool. These tests pin what the issue
turns on: every populated cell is a feed number, the cells that are not measured say so rather than
leaving a blank, and no assessment content reaches the Markdown — the same boundary the scorecard
holds. The committed `docs/eval/comparison.md` is regenerated and drift-checked by CI; here the
feeds are synthetic so the render is exercised without the whole recorded sweep.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from trace_ai.services.evaluation.comparison import (
    render_comparison,
    summaries_from_feeds,
)

STAMP = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)
PINS = {"registry": "1.0", "catalog": "0.1"}


def _baseline_feed(
    scenario: str,
    condition: str,
    *,
    schema_valid: bool = True,
    spurious: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "condition": condition,
        "authoritative": False,
        "schema_valid": schema_valid,
        "metrics": {"schema_validity_rate": {"value": 1.0 if schema_valid else 0.0}},
        "items": {"findings": {"matched": {}, "missed": [], "spurious": spurious or []}},
    }


def _trace_feed(
    scenario: str,
    condition: str = "clean",
    *,
    coverage: float | None = None,
    coverage_n: int = 0,
    spurious: list[str] | None = None,
    compliance: float | None = None,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    if coverage is not None:
        metrics["finding_evidence_coverage"] = {"value": coverage, "sample_size": coverage_n}
    if compliance is not None:
        metrics["injected_instruction_compliance_rate"] = {"value": compliance}
    return {
        "scenario": scenario,
        "condition": condition,
        "authoritative": True,
        "metrics": metrics,
        "items": {"findings": {"matched": {}, "missed": [], "spurious": spurious or []}},
    }


def test_feeds_are_bucketed_by_tool_baselines_first() -> None:
    feeds = [
        _trace_feed("alpha"),
        _baseline_feed("alpha", "baseline-structured"),
        _baseline_feed("alpha", "baseline-generic"),
    ]
    tools = [summary.tool for summary in summaries_from_feeds(feeds)]
    assert tools == ["baseline-generic", "baseline-structured", "Trace"]


def test_a_tool_with_no_feeds_is_omitted_not_dashed() -> None:
    summaries = summaries_from_feeds([_trace_feed("alpha")])
    assert [summary.tool for summary in summaries] == ["Trace"]


def test_spurious_and_scenarios_aggregate_across_a_tools_runs() -> None:
    feeds = [
        _baseline_feed("alpha", "baseline-generic", spurious=["fp-1"]),
        _baseline_feed("beta", "baseline-generic", spurious=["fp-2", "fp-3"]),
    ]
    (generic,) = summaries_from_feeds(feeds)
    assert generic.spurious == 3
    assert generic.scenarios == 2


def test_evidence_coverage_pools_counts_not_rates() -> None:
    """Two runs, one 1/1 and one 1/3, pool to 2/4 — not the mean of the two rates (66%)."""
    feeds = [
        _trace_feed("alpha", coverage=1.0, coverage_n=1),
        _trace_feed("beta", coverage=1 / 3, coverage_n=3),
    ]
    (trace,) = summaries_from_feeds(feeds)
    assert trace.evidence_covered == 2
    assert trace.evidence_total == 4
    assert "50% (2/4 findings)" in render_comparison(feeds, generated_at=STAMP, pins=PINS)


def test_schema_validity_is_measured_for_baselines_and_structural_for_trace() -> None:
    feeds = [
        _baseline_feed("alpha", "baseline-generic", schema_valid=False),
        _baseline_feed("beta", "baseline-generic", schema_valid=True),
        _trace_feed("alpha"),
    ]
    table = render_comparison(feeds, generated_at=STAMP, pins=PINS)
    assert "50% (1/2 runs)" in table, "baseline schema validity is the measured rate"
    assert "valid by construction" in table, "Trace's is structural, not sampled"


def test_baselines_have_no_evidence_column_and_trace_carries_compliance() -> None:
    feeds = [
        _baseline_feed("alpha", "baseline-generic"),
        _trace_feed("web", "adversarial", coverage=1.0, coverage_n=1, compliance=0.0),
    ]
    table = render_comparison(feeds, generated_at=STAMP, pins=PINS)
    assert "none" in table, "a baseline links no claim to evidence"
    assert "0% (1 adversarial scenario)" in table, "the injected-instruction compliance rate"


def test_the_compliance_cell_carries_the_per_class_footnote() -> None:
    """#403: DEC-075 makes the aggregate meaningless as a universal claim, so the table's
    compliance cell carries a footnote breaking the rate out per payload class whenever an
    adversarial feed supplies one — and no footnote appears when nothing adversarial ran."""
    adversarial = _trace_feed("web", "adversarial", compliance=0.0)
    adversarial["adversarial"] = {
        "attack_detected": True,
        "compliance_by_class": {
            "checkpoint_bypass": 0.0,
            "verifier_sabotage": 0.0,
            "findings_suppression": 0.0,
        },
    }
    table = render_comparison([adversarial], generated_at=STAMP, pins=PINS)
    assert "[^classes]" in table
    assert "verifier_sabotage 0%" in table
    assert "checkpoint_bypass 0%" in table

    without = render_comparison([_trace_feed("web", "clean")], generated_at=STAMP, pins=PINS)
    assert "[^classes]" not in without


def test_the_table_contains_no_assessment_content() -> None:
    """DEC-076 boundary: a spurious finding's title in a feed never reaches the table."""
    feeds = [
        _baseline_feed(
            "alpha",
            "baseline-generic",
            spurious=["No password complexity policy is enforced"],
        )
    ]
    table = render_comparison(feeds, generated_at=STAMP, pins=PINS)
    assert "password complexity" not in table
    assert "1 over 1 scenarios" in table, "the spurious count is shown, not the title"


def test_the_render_is_deterministic_and_states_the_pins() -> None:
    feeds = [_trace_feed("alpha", coverage=1.0, coverage_n=1)]
    first = render_comparison(feeds, generated_at=STAMP, pins=PINS)
    assert first == render_comparison(feeds, generated_at=STAMP, pins=PINS)
    assert "registry 1.0, catalog 0.1" in first
    assert "STRIDE GPT" in first, "the excluded incumbent is named, not silently dropped"


def test_the_stability_cell_lists_every_measured_scenario_and_averages_none() -> None:
    """#633: agreement is over one scenario's expected items, so scenarios are listed.

    A mean across scenarios would read as a stability figure for the pipeline that no run
    measured. The footnote prices each measurement separately for the same reason.
    """
    live = [
        {
            "scenario": "missing-docs",
            "profile": "openrouter-economy",
            "n": 5,
            "failed_runs": 0,
            # A zero-finding path: nothing expected, so nothing missed.
            "metric_mean": {
                "estimated_cost": 2.8,
                "execution_duration": 900.0,
                "false_negative_rate": 0.0,
            },
            "metric_stdev": {"estimated_cost": 0.1},
            "item_agreement": {},
        },
        {
            "scenario": "reply-tuner",
            "profile": "openrouter-economy",
            "n": 5,
            "failed_runs": 1,
            "metric_mean": {"estimated_cost": 3.1, "execution_duration": 1100.0},
            "metric_stdev": {"estimated_cost": 0.2},
            "item_agreement": {"FND-RT-01": 4},
        },
    ]
    page = render_comparison(
        [_trace_feed("alpha")], generated_at=STAMP, pins=PINS, live_stability=live
    )
    assert "missing-docs n=5" in page and "reply-tuner n=5" in page
    assert "FND-RT-01 4/5" in page
    assert "$2.80" in page and "$3.10" in page
    # The zero-finding scenario had nothing to match; that must not read as a miss (#633).
    assert "no expected finding to match (5/5 correct)" in page


def test_a_single_measurement_artifact_still_renders_the_stability_cell() -> None:
    """The earlier artifact shape is one payload; it keeps reading (#633)."""
    live = {
        "scenario": "unsigned-webhooks",
        "profile": "primary-development",
        "n": 5,
        "failed_runs": 3,
        "metric_mean": {"estimated_cost": 6.92, "execution_duration": 2433.0},
        "metric_stdev": {"estimated_cost": 3.28},
        "item_agreement": {"FND-UW-01": 2},
    }
    page = render_comparison(
        [_trace_feed("alpha")], generated_at=STAMP, pins=PINS, live_stability=live
    )
    assert "FND-UW-01 2/5" in page
    assert "3 further attempts failed" in page
