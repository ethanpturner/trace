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
    # The failed-attempt and defaulted-decision counts are figures in the run table, not prose:
    # they qualify the agreement beside them, so they belong in the same row (#633).
    assert "<th>Failed attempts</th>" in page and "<th>Defaulted decisions</th>" in page
    assert "<td>1</td>" in page and "<td>40</td>" in page
    assert "Cost (USD)" in page and "2.31" in page

    without = render_scorecard([], generated_at=STAMP)
    assert "Live stability" not in without


def test_the_stability_section_renders_every_measured_scenario_without_averaging() -> None:
    """#633: the protocol measures per scenario, so the artifact holds one entry per scenario.

    They render beside each other with their own agreement and their own variance table. An
    average across scenarios would read as a stability figure for the pipeline, which no run
    measured — a scenario's agreement is over that scenario's expected items.
    """
    live = [
        {
            "scenario": "missing-docs",
            "profile": "openrouter-economy",
            "n": 5,
            "failed_runs": 0,
            "defaulted_decisions": 12,
            # A zero-finding path: nothing was expected, so nothing was missed.
            "metric_mean": {"estimated_cost": 2.8, "false_negative_rate": 0.0},
            "metric_stdev": {"estimated_cost": 0.1},
            "item_agreement": {},
        },
        {
            "scenario": "reply-tuner",
            "profile": "openrouter-economy",
            "n": 5,
            "failed_runs": 1,
            "defaulted_decisions": 7,
            "metric_mean": {"estimated_cost": 3.1},
            "metric_stdev": {"estimated_cost": 0.2},
            "item_agreement": {"FND-RT-01": 3},
        },
    ]
    page = render_scorecard([], generated_at=STAMP, live_stability=live)
    assert "<h3>missing-docs</h3>" in page and "<h3>reply-tuner</h3>" in page
    assert "FND-RT-01 3/5" in page
    assert "2.8" in page and "3.1" in page
    # A zero-finding path had nothing to match, which must not read as a miss (#633).
    assert "no expected finding to match (5/5 correct)" in page
    assert "no expected item matched" not in page


def test_an_empty_agreement_reads_as_a_miss_only_when_something_was_expected() -> None:
    """#633: an empty agreement map is two different results and must not render as one.

    Nothing expected and nothing matched is a correct zero-finding run; something expected and
    nothing matched is a total miss. The mean false-negative rate is what separates them, and
    conflating the two would report the DEC-009 thesis case as a failure.
    """
    missed_everything = [
        {
            "scenario": "somewhere",
            "profile": "openrouter-economy",
            "n": 5,
            "failed_runs": 0,
            "defaulted_decisions": 0,
            "metric_mean": {"estimated_cost": 1.0, "false_negative_rate": 1.0},
            "metric_stdev": {"estimated_cost": 0.0},
            "item_agreement": {},
        }
    ]
    page = render_scorecard([], generated_at=STAMP, live_stability=missed_everything)
    assert "no expected item matched in any of 5" in page
    assert "no expected finding to match" not in page


def test_a_row_is_attributed_to_the_model_its_feed_names() -> None:
    """DEC-136: rows measured on different models must never read as one population. A feed's
    `models` list becomes the row's attribution and the page's Model column; a feed without one
    — an authored recording no model produced — renders a dash, never an invented name."""
    captured = dict(_feed("husky-ai", "clean", matched={"FND-HA-01": ["fnd-001"]}))
    captured["models"] = ["claude-opus-5"]
    routed = dict(_feed("forgeflow", "clean"))
    routed["models"] = ["claude-opus-5", "claude-sonnet-5"]
    authored = _feed("crypto-wallet", "clean")

    rows = rows_from_feeds([captured, routed, authored])
    by_scenario = {row.scenario: row for row in rows}
    assert by_scenario["husky-ai"].model == "claude-opus-5"
    assert by_scenario["forgeflow"].model == "claude-opus-5 + claude-sonnet-5"
    assert by_scenario["crypto-wallet"].model is None

    page = render_scorecard([captured, routed, authored], generated_at=STAMP)
    assert "<th>Model</th>" in page
    assert "claude-opus-5 + claude-sonnet-5" in page


def _stratum_feed(
    scenario: str,
    *,
    model: str,
    workflow: str,
    matched: dict[str, list[str]] | None = None,
    missed: list[str] | None = None,
    spurious: list[str] | None = None,
) -> dict[str, object]:
    feed = dict(_feed(scenario, "clean", matched=matched, missed=missed, spurious=spurious))
    feed["models"] = [model]
    feed["workflow_version"] = workflow
    return feed


def test_a_mixed_pool_renders_only_under_its_label() -> None:
    """DEC-143's stratification rule: rows measured on different models or workflow shapes pool
    per stratum, and the cross-stratum pool appears only under the explicit mixed label — never
    as a bare number a reader could take for one population's."""
    feeds = [
        _stratum_feed("a", model="claude-opus-5", workflow="0.1", matched={"F-1": ["fnd-001"]}),
        _stratum_feed("b", model="openai/gpt-5.1", workflow="0.2", missed=["F-2"]),
    ]
    page = render_scorecard(feeds, generated_at=STAMP)
    assert "Pooled accuracy by stratum" in page
    assert "all strata — pooled across models and shapes" in page

    single = render_scorecard(feeds[:1], generated_at=STAMP)
    assert "Pooled accuracy by stratum" in single
    assert "all strata" not in single, "one stratum needs no mixed pool"


def test_pooled_percentages_carry_their_denominators() -> None:
    """DEC-143's denominator rule: a pooled cell states its counts, so a 100% over one row
    cannot read like a 100% over fifty."""
    feeds = [
        _stratum_feed("a", model="m", workflow="0.2", matched={"F-1": ["fnd-001"]}),
    ]
    page = render_scorecard(feeds, generated_at=STAMP)
    assert "100% (1/1)" in page


def test_the_baseline_head_to_head_renders_beside_the_pipeline() -> None:
    """The live-vs-live section (DEC-143): the clean row beside its baselines, with the
    single-pass spurious delta signed."""
    feeds = [
        _feed("oidc-portal", "clean"),
        _feed(
            "oidc-portal",
            "baseline-generic",
            spurious=[f"fp-{i}" for i in range(17)],
            authoritative=False,
            schema_valid=True,
        ),
        _feed(
            "oidc-portal",
            "baseline-single-pass",
            spurious=["fp-a"],
            authoritative=False,
            schema_valid=True,
        ),
    ]
    page = render_scorecard(feeds, generated_at=STAMP)
    assert "Live baselines beside the pipeline" in page
    assert "0/0/17" in page, "the generic baseline's counts render"
    assert "+1" in page, "the single-pass delta is signed"

    without = render_scorecard([_feed("s", "clean")], generated_at=STAMP)
    assert "Live baselines beside the pipeline" not in without


def test_the_comparison_sections_render_from_committed_feeds() -> None:
    """DEC-143: the #331/#332 comparison feeds are read like the live-stability artifact.
    The defaulted-decisions column renders — the #332 confound made visible — and an empty
    sequence renders no section."""
    arm = _stratum_feed("missing-docs", model="claude-sonnet-5", workflow="0.2")
    arm["label"] = "sonnet"
    arm["defaulted_decisions"] = 11
    page = render_scorecard([], generated_at=STAMP, model_comparison=[arm])
    assert "Model comparison" in page
    assert "Defaulted decisions" in page
    assert ">11<" in page
    assert "Prompt comparison" not in page

    without = render_scorecard([], generated_at=STAMP)
    assert "Model comparison" not in without


def test_the_empty_human_instruments_state_their_absence() -> None:
    """DEC-143: an instrument with no data renders its section with the reason, not silence —
    review time is structurally absent from replays (DEC-117), and agreement waits on a second
    annotation set (#565). No data is a statement, never a zero."""
    page = render_scorecard([_feed("s", "clean")], generated_at=STAMP)
    assert "Checkpoint review time" in page
    assert "records no session" in page
    assert "Annotator agreement" in page
    assert "no second annotation set has been authored" in page.lower()
