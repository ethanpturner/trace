"""Scorecard history (DEC-081, issue #333).

Snapshots are retained, not regenerated: two successive snapshots stay distinguishable by their
version key, an identical key is refused rather than duplicated, and the rendered page shows the
history without ever containing assessment content — the DEC-076 boundary applies to the history
file the same as to the page.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from trace_ai.services.evaluation.history import (
    ScorecardSnapshot,
    SnapshotRefusedError,
    append_snapshot,
    load_history,
    prompt_tree_digest,
    snapshot_key,
)
from trace_ai.services.evaluation.scorecard import ScorecardRow, render_scorecard

GENERATED_AT = datetime(2026, 8, 12, 12, 0, 0, tzinfo=UTC)


def rows() -> tuple[ScorecardRow, ...]:
    return (
        ScorecardRow(
            scenario="forgeflow",
            condition="clean",
            authoritative=True,
            matched=3,
            missed=1,
            spurious=1,
            schema_valid=True,
            cost=0.0,
        ),
        ScorecardRow(
            scenario="forgeflow",
            condition="clean",
            authoritative=False,
            matched=9,
            missed=0,
            spurious=9,
            schema_valid=True,
            cost=0.0,
        ),
    )


def snapshot(git_ref: str = "abc1234", **changes: object) -> ScorecardSnapshot:
    fields: dict[str, object] = {
        "recorded_at": "2026-08-12",
        "git_ref": git_ref,
        "prompt_digest": "sha256:" + "a" * 64,
        "catalog_version": "0.2",
        "rows": rows(),
    }
    fields |= changes
    return ScorecardSnapshot(**fields)  # type: ignore[arg-type]


def test_two_snapshots_round_trip_and_stay_distinguishable(tmp_path: Path) -> None:
    history_file = tmp_path / "history.jsonl"
    append_snapshot(history_file, snapshot("abc1234"))
    append_snapshot(history_file, snapshot("def5678", recorded_at="2026-08-13"))

    retained = load_history(history_file)
    assert [entry.git_ref for entry in retained] == ["abc1234", "def5678"]
    assert retained[0].key != retained[1].key
    assert retained[0].rows == rows()


def test_a_snapshot_with_the_same_key_is_refused_not_duplicated(tmp_path: Path) -> None:
    history_file = tmp_path / "history.jsonl"
    append_snapshot(history_file, snapshot())
    with pytest.raises(SnapshotRefusedError, match="nothing new to retain"):
        append_snapshot(history_file, snapshot())
    assert len(load_history(history_file)) == 1


def test_pooling_covers_authoritative_rows_only() -> None:
    entry = snapshot()
    # 3 matched, 1 spurious, 1 missed from the authoritative row; the baseline row is excluded.
    assert entry.precision == 3 / 4
    assert entry.recall == 3 / 4
    assert entry.f1 == 3 / 4


def test_an_empty_history_is_an_empty_list_and_no_section(tmp_path: Path) -> None:
    assert load_history(tmp_path / "missing.jsonl") == []
    page = render_scorecard([], generated_at=GENERATED_AT, history=[])
    assert "History" not in page


def test_the_rendered_page_shows_the_history_newest_first() -> None:
    page = render_scorecard(
        [],
        generated_at=GENERATED_AT,
        history=[snapshot("abc1234"), snapshot("def5678", recorded_at="2026-08-13")],
    )
    assert "<h2>History</h2>" in page
    assert page.index("def5678") < page.index("abc1234")
    assert "history.jsonl" in page
    # The digest is shown shortened and without its algorithm prefix.
    assert "aaaaaaaaaaaa" in page
    assert "sha256:" not in page


def test_the_history_contains_metrics_and_identifiers_only(tmp_path: Path) -> None:
    """DEC-076's content boundary, applied to the committed history file."""
    history_file = tmp_path / "history.jsonl"
    append_snapshot(history_file, snapshot())
    import json

    payload = json.loads(history_file.read_text(encoding="utf-8"))
    assert set(payload) == {
        "recorded_at",
        "git_ref",
        "prompt_digest",
        "catalog_version",
        "rows",
    }
    assert set(payload["rows"][0]) == {
        "scenario",
        "condition",
        "authoritative",
        "matched",
        "missed",
        "spurious",
        "schema_valid",
        "cost",
        "compliance",
        "context_accuracy",
        "threat_coverage",
        "mapping_accuracy",
        "question_usefulness",
        "unsupported_claim_rate",
        "token_usage",
    }


def test_the_prompt_digest_moves_with_any_file_in_the_tree(tmp_path: Path) -> None:
    tree = tmp_path / "prompts"
    (tree / "shared").mkdir(parents=True)
    (tree / "agent.md").write_text("body", encoding="utf-8")
    (tree / "shared" / "block.md").write_text("shared", encoding="utf-8")
    before = prompt_tree_digest(tree)

    (tree / "shared" / "block.md").write_text("shared, edited", encoding="utf-8")
    assert prompt_tree_digest(tree) != before

    # A rename moves it too: the digest is path-keyed, not content-only.
    (tree / "shared" / "block.md").rename(tree / "shared" / "renamed.md")
    (tree / "shared" / "renamed.md").write_text("shared", encoding="utf-8")
    (tree / "agent.md").write_text("body", encoding="utf-8")
    assert prompt_tree_digest(tree) != before


def test_the_repository_key_is_computable_offline() -> None:
    digest, catalog_version = snapshot_key()
    assert digest.startswith("sha256:")
    assert catalog_version
