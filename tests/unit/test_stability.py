"""Ablation sets and stability (#270, evaluation-plan section 14, DEC-077).

The ablation set runs offline and answers the DEC-012 decision gate per scenario: removing a
stage that earns its place moves a metric. Stability is a live measurement; its aggregation is a
pure function tested on synthetic feeds, and the live path refuses the offline profile because
deterministic replay measures nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from trace_ai.services.evaluation.stability import (
    ABLATION_SET,
    StabilityError,
    run_ablation_set,
    run_stability,
    summarize_runs,
)

if TYPE_CHECKING:
    from pathlib import Path


# ------------------------------------------------------------------------------------------
# The ablation set
# ------------------------------------------------------------------------------------------


def test_removing_evidence_validation_loses_the_finding(
    tmp_path: Path, authored_scenario_registry: Path
) -> None:
    """The DEC-012 decision gate, measured: without evidence validation the finding is not
    produced, so the truth-set finding is missed and the false-negative rate goes to 1.

    Probed against the frozen authored fixture rather than a registered scenario: live
    recordings' scores move on re-capture, and this test pins harness behaviour, not one
    recording's outcome."""
    comparison = run_ablation_set(
        "authored-fixture",
        data_root=tmp_path / "work",
        label="test",
        registry_path=authored_scenario_registry,
        results_root=tmp_path / "results",
    )
    assert comparison.authoritative["false_negative_rate"] == 0.0
    assert set(comparison.ablations) == set(ABLATION_SET)
    assert comparison.ablations["no-evidence-validation"]["false_negative_rate"] == 1.0
    assert comparison.delta("no-evidence-validation", "false_negative_rate") == 1.0


def test_the_ablation_set_stops_before_the_report(
    tmp_path: Path, authored_scenario_registry: Path
) -> None:
    """An ablation that changes the finding set is measured on the findings, not the report whose
    recorded sections were authored for the authoritative findings."""
    comparison = run_ablation_set(
        "authored-fixture",
        data_root=tmp_path / "work",
        label="test",
        registry_path=authored_scenario_registry,
        results_root=tmp_path / "results",
    )
    # model_call_count is a finding-level run measure and drops when a model stage is removed.
    assert (
        comparison.ablations["no-evidence-validation"]["model_call_count"]
        < comparison.authoritative["model_call_count"]
    )


# ------------------------------------------------------------------------------------------
# Stability aggregation (pure function)
# ------------------------------------------------------------------------------------------


def _feed(fnr: float, matched: list[str], *, defaulted: int = 0) -> dict[str, object]:
    return {
        "metrics": {"false_negative_rate": {"value": fnr}},
        "items": {"findings": {"matched": {key: ["x"] for key in matched}}},
        "defaulted_decisions": defaulted,
    }


def test_summarize_reports_variance_and_per_item_agreement() -> None:
    feeds = [
        _feed(0.0, ["FND-A", "FND-B"]),
        _feed(0.5, ["FND-A"]),
        _feed(0.0, ["FND-A", "FND-B"]),
        _feed(0.0, ["FND-A", "FND-B"]),
        _feed(0.5, ["FND-A"], defaulted=1),
    ]
    summary = summarize_runs("scenario", feeds)

    assert summary.n == 5
    assert summary.metric_mean["false_negative_rate"] == pytest.approx(0.2)
    assert summary.metric_stdev["false_negative_rate"] > 0.0
    assert summary.item_agreement == {"FND-A": 5, "FND-B": 3}
    assert summary.unanimous == ["FND-A"]
    assert summary.flickering == ["FND-B"]
    assert summary.defaulted_decisions == 1


def test_a_single_run_has_zero_variance() -> None:
    summary = summarize_runs("scenario", [_feed(0.0, ["FND-A"])])
    assert summary.metric_stdev["false_negative_rate"] == 0.0
    assert summary.unanimous == ["FND-A"]


def test_summarize_refuses_no_runs() -> None:
    with pytest.raises(StabilityError, match="no runs"):
        summarize_runs("scenario", [])


# ------------------------------------------------------------------------------------------
# The live stability path refuses the offline profile
# ------------------------------------------------------------------------------------------


def test_stability_refuses_the_offline_profile(tmp_path: Path) -> None:
    """DEC-077: deterministic replay reports zero variance and measures nothing, so the live
    protocol refuses it rather than presenting a meaningless zero as a result."""
    with pytest.raises(StabilityError, match="deterministic"):
        run_stability(
            "unsigned-webhooks",
            n=5,
            data_root=tmp_path,
            label="test",
            profile_name="offline-fake",
        )
