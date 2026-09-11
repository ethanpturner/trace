"""An external tool's findings are scored as a non-authoritative arm, by the same matcher (DEC-155).

The rules under test are the ones that keep the arm honest: the feed is validated and anything it
does not admit is refused; mapped rows go through the baseline scorer and nothing else, so a match
needs requirement *and* component (DEC-056) and a spurious row on a rejected requirement breaches
it (DEC-154); findings the tool left unproven enter no metric; a `path:line` locator is scored on
resolvability only when a worktree is supplied (DEC-150, DEC-151); the comparison renders the row
labelled, attributed, and with counts rather than a rate over a small denominator; and an empty
`results/` directory changes nothing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from trace_ai.services.evaluation.comparison import render_comparison, summaries_from_feeds
from trace_ai.services.evaluation.external_feed import (
    ExternalFeedError,
    discover_feeds,
    load_feed,
    resolve_locators,
    score_feed,
)

STAMP = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
PINS = {"registry": "1.0", "catalog": "0.1"}
SNAPSHOT = "0123456789abcdef0123456789abcdef01234567"


def _feed(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "feed_version": "1",
        "arm": "mantis",
        "scenario": "unsigned-webhooks",
        "run": 1,
        "tool": {"name": "google/mantis", "version": "deadbeef"},
        "models": ["openai/gpt-5.1"],
        "snapshot_sha": SNAPSHOT,
        "provenance": "captured",
        "mapped_by": "hand-mapped under the DEC-056 rule; reasoning per row",
        "findings": [
            {
                "raw_signature": "sig-uw-01",
                "requirement_id": "req-WEBHOOK-001",
                "component": "Event Receiver",
                "evidence_locator": "app/webhooks.py:42",
                "mapper_reasoning": "the receiver dispatches without an HMAC check",
            },
            {
                "raw_signature": "sig-data-fp",
                "requirement_id": "req-DATA-001",
                "component": "Event Receiver",
                "evidence_locator": "app/webhooks.py:7",
                "mapper_reasoning": "asserts confidentiality exposure on a public endpoint",
            },
        ],
        "unverified": [{"raw_signature": "sig-unproven", "reason": "failed_to_reproduce"}],
        "spurious": [{"raw_signature": "sig-no-req", "reason": "names no catalogue requirement"}],
    }
    payload.update(overrides)
    return payload


def _write(tmp_path: Path, payload: dict[str, Any], *, arm: str = "mantis", run: int = 1) -> Path:
    directory = tmp_path / "results" / arm
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{payload['scenario']}-run-{run}.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_a_valid_feed_loads_with_identifiers_and_no_prose_on_the_object(tmp_path: Path) -> None:
    feed = load_feed(_write(tmp_path, _feed()))
    assert feed.condition == "external-mantis"
    assert feed.label == "run-1"
    assert [row.raw_signature for row in feed.findings] == ["sig-uw-01", "sig-data-fp"]
    assert feed.unverified == (("sig-unproven", "failed_to_reproduce"),)
    assert feed.findings[0].title == "sig-uw-01", "the scorer's identifier is the signature"


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"provenance": "measured"}, "provenance"),
        ({"snapshot_sha": "not-hex"}, "snapshot_sha"),
        ({"arm": "Mantis"}, "arm"),
        ({"feed_version": "2"}, "feed_version"),
        ({"extra": True}, "does not admit"),
        ({"models": "openai/gpt-5.1"}, "models"),
    ],
)
def test_anything_the_schema_does_not_admit_is_refused(
    tmp_path: Path, overrides: dict[str, Any], fragment: str
) -> None:
    with pytest.raises(ExternalFeedError, match=fragment):
        load_feed(_write(tmp_path, _feed(**overrides)))


def test_a_row_carrying_finding_text_is_refused(tmp_path: Path) -> None:
    payload = _feed()
    payload["findings"][0]["title"] = "Webhook signature not verified"
    with pytest.raises(ExternalFeedError, match="does not admit"):
        load_feed(_write(tmp_path, payload))


def test_a_signature_appearing_twice_is_refused(tmp_path: Path) -> None:
    payload = _feed()
    payload["spurious"].append({"raw_signature": "sig-uw-01", "reason": "duplicate"})
    with pytest.raises(ExternalFeedError, match="appears twice"):
        load_feed(_write(tmp_path, payload))


def test_the_file_name_must_agree_with_the_body(tmp_path: Path) -> None:
    path = _write(tmp_path, _feed(run=2))
    with pytest.raises(ExternalFeedError, match="disagrees"):
        load_feed(path)


def test_rows_are_scored_by_the_baseline_matcher_and_breach_the_negative_set(
    tmp_path: Path,
) -> None:
    """unsigned-webhooks expects (req-WEBHOOK-001, Event Receiver) and rejects a confidentiality
    claim on req-DATA-001 (REJ-UW-02, mechanism common_false_positives)."""
    outcome = score_feed(_write(tmp_path, _feed()), results_root=tmp_path / "derived")
    assert outcome.matched == {"FND-UW-01": ["sig-uw-01"]}
    assert outcome.missed == []
    assert outcome.spurious == ["sig-data-fp", "sig-no-req"], (
        "the matcher's spurious row plus the one spurious by definition"
    )
    assert outcome.rejections["breached"] == {"REJ-UW-02": ["sig-data-fp"]}
    assert outcome.rejections["by_mechanism"]["common_false_positives"] == [1, 1]
    assert outcome.rejections["by_mechanism"]["documentation_gap"] == [0, 1]
    assert outcome.metrics["spurious_finding_count"] == 2.0
    assert outcome.metrics["false_negative_rate"] == 0.0
    assert "locator_resolvability" not in outcome.metrics, "unmeasured without a worktree"


def test_a_component_mismatch_is_divergent_not_matched(tmp_path: Path) -> None:
    payload = _feed()
    payload["findings"] = [dict(payload["findings"][0], component="Notifier")]
    payload["spurious"] = []
    payload["unverified"] = []
    outcome = score_feed(_write(tmp_path, payload), results_root=tmp_path / "derived")
    assert outcome.matched == {}
    assert outcome.missed == ["FND-UW-01"]
    assert outcome.divergent == {"FND-UW-01": ["sig-uw-01"]}
    assert outcome.spurious == [], "DEC-148 withholds a divergent row from spurious"


def test_the_derived_feed_is_non_authoritative_attributed_and_carries_identifiers_only(
    tmp_path: Path,
) -> None:
    outcome = score_feed(_write(tmp_path, _feed()), results_root=tmp_path / "derived")
    assert outcome.feed_path is not None
    derived = json.loads(outcome.feed_path.read_text(encoding="utf-8"))
    assert outcome.feed_path.parts[-3:] == ("unsigned-webhooks", "external-mantis", "run-1.json")
    assert derived["authoritative"] is False
    assert derived["condition"] == "external-mantis"
    assert derived["models"] == ["openai/gpt-5.1"]
    assert derived["provenance"] == "captured"
    assert derived["external"]["snapshot_sha"] == SNAPSHOT
    assert derived["external"]["unverified"] == 1
    assert derived["items"]["findings"]["unverified"] == ["sig-unproven"]
    assert "mapper_reasoning" not in json.dumps(derived), "prose stays in the feed file"
    assert "HMAC" not in json.dumps(derived)


def test_locators_resolve_only_inside_the_worktree_and_within_the_file(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    (worktree / "app").mkdir(parents=True)
    (worktree / "app" / "webhooks.py").write_text("\n".join(f"line {n}" for n in range(1, 11)))
    feed = load_feed(_write(tmp_path, _feed()))
    rows = list(feed.findings)
    outcome = resolve_locators(rows, worktree)
    assert (outcome.resolved, outcome.total) == (1, 2), "line 42 is past the file's ten lines"
    assert outcome.unresolved == ["sig-uw-01"]

    escaped = _feed()
    escaped["findings"] = [dict(escaped["findings"][1], evidence_locator="../outside.py:1")]
    (tmp_path / "outside.py").write_text("x\n")
    outside = load_feed(_write(tmp_path, escaped, arm="codex", run=1))
    assert resolve_locators(list(outside.findings), worktree).resolved == 0


def test_the_metric_is_emitted_with_a_worktree_and_carries_its_denominator(
    tmp_path: Path,
) -> None:
    worktree = tmp_path / "wt"
    (worktree / "app").mkdir(parents=True)
    (worktree / "app" / "webhooks.py").write_text("\n" * 50)
    outcome = score_feed(
        _write(tmp_path, _feed()), results_root=tmp_path / "derived", worktree=worktree
    )
    assert outcome.metrics["locator_resolvability"] == 1.0
    assert outcome.feed_path is not None
    derived = json.loads(outcome.feed_path.read_text(encoding="utf-8"))
    assert derived["metrics"]["locator_resolvability"]["sample_size"] == 2
    assert derived["external"]["locators"] == {"resolved": 2, "total": 2}


def test_the_comparison_renders_an_external_row_labelled_and_with_counts(
    tmp_path: Path,
) -> None:
    outcome = score_feed(_write(tmp_path, _feed()), results_root=tmp_path / "derived")
    assert outcome.feed_path is not None
    derived = json.loads(outcome.feed_path.read_text(encoding="utf-8"))
    trace = {
        "scenario": "unsigned-webhooks",
        "condition": "clean",
        "authoritative": True,
        "metrics": {},
        "items": {"findings": {"matched": {}, "missed": [], "spurious": []}},
    }
    summaries = summaries_from_feeds([trace, derived])
    assert [summary.tool for summary in summaries] == ["external-mantis", "Trace"]
    external = summaries[0]
    assert external.external and external.label == "mantis (external, non-authoritative)"
    assert external.models == "openai/gpt-5.1"
    table = render_comparison([trace, derived], generated_at=STAMP, pins=PINS)
    assert "| mantis (external, non-authoritative) |" in table
    assert "responses captured, openai/gpt-5.1" in table
    assert "1 of 2 [^rejections]" in table, "counts, no percentage, under five (DEC-155)"
    assert "%" not in table.split("| mantis (external")[1].split("|")[4], (
        "the rejection cell carries no rate over a denominator of two"
    )
    assert "locators not measured" in table
    assert "[^external]: An external arm (DEC-155)" in table
    assert "google/mantis @ deadbeef" in table


def test_no_external_feed_means_no_external_row_and_no_footnote() -> None:
    trace = {
        "scenario": "alpha",
        "condition": "clean",
        "authoritative": True,
        "metrics": {},
        "items": {"findings": {"matched": {}, "missed": [], "spurious": []}},
    }
    table = render_comparison([trace], generated_at=STAMP, pins=PINS)
    assert "[^external]" not in table
    assert "external" not in table.split("| Trace |")[0]


def test_discovery_over_an_absent_or_empty_root_yields_nothing(tmp_path: Path) -> None:
    assert discover_feeds(tmp_path / "missing") == []
    (tmp_path / "results" / "mantis").mkdir(parents=True)
    assert discover_feeds(tmp_path / "results") == []
    _write(tmp_path, _feed())
    _write(tmp_path, _feed(run=2), run=2)
    assert [path.name for path in discover_feeds(tmp_path / "results")] == [
        "unsigned-webhooks-run-1.yaml",
        "unsigned-webhooks-run-2.yaml",
    ]


def test_the_committed_results_root_is_outside_the_gitignored_harness_tree() -> None:
    from trace_ai.config import PROJECT_ROOT
    from trace_ai.services.evaluation.external_feed import EXTERNAL_FEEDS_ROOT
    from trace_ai.services.evaluation.harness import RESULTS_ROOT

    assert EXTERNAL_FEEDS_ROOT == PROJECT_ROOT / "results"
    assert not EXTERNAL_FEEDS_ROOT.is_relative_to(RESULTS_ROOT)
