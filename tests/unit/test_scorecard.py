"""The evaluation scorecard (#271, DEC-076): static, deterministic, metrics-only.

The tests pin the three properties the decision turns on: the page is a pure function of the
feeds (deterministic), it computes precision/recall/F1 correctly per the finding field class, and
it never contains assessment content — no finding title, no document text, only counts and
identifiers.
"""

from __future__ import annotations

from datetime import UTC, datetime

from trace_ai.services.evaluation.scorecard import (
    ScorecardRow,
    render_scorecard,
    rows_from_feeds,
)

STAMP = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)


def _feed(
    scenario: str,
    condition: str,
    *,
    matched: dict[str, list[str]] | None = None,
    missed: list[str] | None = None,
    spurious: list[str] | None = None,
    authoritative: bool = True,
    schema_valid: bool | None = None,
) -> dict[str, object]:
    return {
        "scenario": scenario,
        "condition": condition,
        "authoritative": authoritative,
        "schema_valid": schema_valid,
        "metrics": {"estimated_cost": {"value": 0.0}},
        "items": {
            "findings": {
                "matched": matched or {},
                "missed": missed or [],
                "spurious": spurious or [],
            }
        },
    }


def test_the_adversarial_rows_render_the_per_class_breakdown() -> None:
    """#403: DEC-075's tradeoff says the scorecard must label compliance per class — the
    aggregate is meaningless as a universal claim. An adversarial feed's per-class rates and its
    detection axis appear in their own section; a page with no adversarial feed omits it."""
    by_class = {
        "checkpoint_bypass": 0.0,
        "direct_instruction_injection": 0.0,
        "fence_delimiter_escape": 0.0,
        "findings_suppression": 0.0,
        "verifier_sabotage": 0.0,
    }
    adversarial_feed: dict[str, object] = {
        "scenario": "unsigned-webhooks",
        "condition": "adversarial",
        "authoritative": True,
        "items": {
            "findings": {"matched": {"FND-UW-01": ["fnd-001"]}, "missed": [], "spurious": []}
        },
        "metrics": {"injected_instruction_compliance_rate": {"value": 0.0}},
        "adversarial": {"attack_detected": True, "compliance_by_class": by_class},
    }
    generated = datetime(2026, 8, 13, tzinfo=UTC)

    page = render_scorecard([adversarial_feed], generated_at=generated)
    assert "Adversarial payload classes" in page
    for name in by_class:
        assert name in page
    assert "Attack detected" in page

    clean_feed = {key: value for key, value in adversarial_feed.items() if key != "adversarial"}
    clean_feed["condition"] = "clean"
    without = render_scorecard([clean_feed], generated_at=generated)
    assert "Adversarial payload classes" not in without


def test_precision_recall_f1_are_computed_over_the_finding_class() -> None:
    row = ScorecardRow(
        scenario="s",
        condition="clean",
        authoritative=True,
        matched=2,
        missed=1,
        spurious=1,
        schema_valid=None,
        cost=None,
    )
    assert row.precision == 2 / 3  # 2 matched of 3 produced
    assert row.recall == 2 / 3  # 2 matched of 3 expected
    assert row.f1 is not None and abs(row.f1 - 2 / 3) < 1e-9


def test_undefined_ratios_are_none_not_zero() -> None:
    """A zero-finding scenario has no recall denominator; a run that produced nothing has no
    precision denominator. Both are undefined, not zero."""
    no_expected = ScorecardRow("s", "clean", True, 0, 0, 1, None, None)
    assert no_expected.recall is None
    assert no_expected.precision == 0.0  # produced one, matched none

    produced_nothing = ScorecardRow("s", "clean", True, 0, 2, 0, None, None)
    assert produced_nothing.precision is None
    assert produced_nothing.recall == 0.0


def test_rows_are_sorted_so_the_page_is_deterministic() -> None:
    feeds = [
        _feed("zebra", "clean"),
        _feed("alpha", "baseline-generic"),
        _feed("alpha", "clean"),
    ]
    rows = rows_from_feeds(feeds)
    assert [(row.scenario, row.condition) for row in rows] == [
        ("alpha", "baseline-generic"),
        ("alpha", "clean"),
        ("zebra", "clean"),
    ]


def test_the_render_is_deterministic() -> None:
    feeds = [_feed("s", "clean", matched={"FND-1": ["fnd-001"]})]
    assert render_scorecard(feeds, generated_at=STAMP) == render_scorecard(
        feeds, generated_at=STAMP
    )


def test_the_scorecard_contains_no_assessment_content() -> None:
    """DEC-076: metrics and identifiers only. Finding titles in a feed never reach the page."""
    feeds = [
        _feed(
            "s",
            "baseline-generic",
            spurious=["No password complexity policy is enforced"],
            authoritative=False,
            schema_valid=True,
        )
    ]
    html = render_scorecard(feeds, generated_at=STAMP)
    assert "password complexity" not in html, "a finding title reached the page"
    assert ">1<" in html, "the spurious count is shown"


def test_the_thesis_contrast_is_visible() -> None:
    """Trace produces no spurious finding where a generic baseline invents one."""
    feeds = [
        _feed("oidc-portal", "clean", authoritative=True),
        _feed(
            "oidc-portal",
            "baseline-generic",
            spurious=["fp-1", "fp-2"],
            authoritative=False,
            schema_valid=True,
        ),
    ]
    rows = {row.condition: row for row in rows_from_feeds(feeds)}
    assert rows["clean"].spurious == 0
    assert rows["baseline-generic"].spurious == 2


def test_the_live_stability_section_renders_from_the_committed_artifact() -> None:
    """DEC-077's measurement reaches the page from the committed summary — read, never
    regenerated, because the drift checks cannot re-run a live protocol. Cost and runtime are
    the cells the offline table cannot carry, so they render here with the profile named; an
    absent artifact renders no section."""
    live = {
        "scenario": "unsigned-webhooks",
        "profile": "primary-development",
        "n": 5,
        "failed_runs": 1,
        "defaulted_decisions": 40,
        "metric_mean": {
            "estimated_cost": 2.31,
            "execution_duration": 412.0,
            "model_call_count": 9.2,
        },
        "metric_stdev": {
            "estimated_cost": 0.4,
            "execution_duration": 60.2,
            "model_call_count": 1.3,
        },
        "item_agreement": {"FND-UW-01": 4},
    }
    page = render_scorecard([], generated_at=STAMP, live_stability=live)
    assert "Live stability" in page
    assert "primary-development" in page
    assert "FND-UW-01 4/5" in page
    assert "1 of 6 attempts failed" in page
    assert "Cost (USD)" in page and "2.31" in page

    without = render_scorecard([], generated_at=STAMP)
    assert "Live stability" not in without
