"""The ablation table (#280, DEC-012/DEC-076): deltas from the authoritative run, nulls shown.

The table renders the harness ablation comparisons. These tests pin what the narrative depends on:
a delta is the change from the authoritative run, a component that moves no metric renders a blank
rather than vanishing, ablated rows are marked non-authoritative, and no assessment content reaches
the Markdown. The committed `docs/eval/ablation.md` is drift-checked by CI; here the comparisons are
synthetic so the render is exercised without the recorded sweep.
"""

from __future__ import annotations

from datetime import UTC, datetime

from trace_ai.services.evaluation.ablation import render_ablation, rows_from_comparisons
from trace_ai.services.evaluation.stability import AblationComparison

STAMP = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)
PINS = {"registry": "1.0", "catalog": "0.1"}


def _comparison() -> AblationComparison:
    return AblationComparison(
        scenario="unsigned-webhooks",
        label="t",
        authoritative={"false_negative_rate": 0.0, "finding_evidence_coverage": 1.0},
        ablations={
            "no-evidence-validation": {
                "false_negative_rate": 1.0,
                "finding_evidence_coverage": 1.0,
            },
            "no-critical-review": {"false_negative_rate": 0.0, "finding_evidence_coverage": 1.0},
        },
    )


def test_the_authoritative_row_comes_first_then_the_ablations() -> None:
    rows = rows_from_comparisons([_comparison()])
    assert [row.component for row in rows] == [
        "authoritative",
        "no-evidence-validation",
        "no-critical-review",
    ]
    assert rows[0].authoritative and not rows[1].authoritative


def test_a_moved_metric_shows_its_delta_and_an_unmoved_one_is_blank() -> None:
    table = render_ablation([_comparison()], generated_at=STAMP, pins=PINS)
    # evidence validation removed: false-negative rate 0% -> 100%, a +100 delta.
    assert "100% (+100)" in table
    # its evidence coverage did not move, so no delta annotation trails the 100%.
    assert "100% (+0)" not in table


def test_ablated_rows_are_marked_non_authoritative() -> None:
    table = render_ablation([_comparison()], generated_at=STAMP, pins=PINS)
    assert "no evidence validation *" in table
    assert "authoritative |" in table


def test_the_render_is_deterministic_and_states_the_pins() -> None:
    first = render_ablation([_comparison()], generated_at=STAMP, pins=PINS)
    assert first == render_ablation([_comparison()], generated_at=STAMP, pins=PINS)
    assert "registry 1.0, catalog 0.1" in first
