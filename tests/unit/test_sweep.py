"""The shared evaluation sweep (DEC-076).

`collect_feeds` is the one sweep the scorecard and the comparison read; the point of extracting it
here — out of scripts/build_scorecard.py, where the comparison script reached it by a sibling
import that only resolved from the scripts/ directory — is that both scripts import it from the
package and CI can sweep once and render both pages. These pin the dump/load contract that makes
the sweep-once path possible. The full sweep itself is exercised by the scorecard `--check` in CI,
which is where the recorded runs already replay.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from trace_ai.services.evaluation.sweep import dump_feeds, load_feeds


def test_dump_then_load_round_trips(tmp_path: Path) -> None:
    feeds: list[dict[str, object]] = [
        {"scenario": "forgeflow", "condition": "clean", "precision": 1.0},
        {"scenario": "forgeflow", "condition": "injection", "precision": 0.5},
    ]
    path = tmp_path / "feeds.json"

    dump_feeds(feeds, path)

    assert load_feeds(path) == feeds


def test_dump_creates_missing_parents(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "feeds.json"

    dump_feeds([], path)

    assert load_feeds(path) == []


def test_load_rejects_a_non_list_document(tmp_path: Path) -> None:
    path = tmp_path / "feeds.json"
    path.write_text('{"scenario": "forgeflow"}', encoding="utf-8")

    with pytest.raises(ValueError, match="feed list"):
        load_feeds(path)


def test_an_external_feed_is_scored_against_the_scenarios_committed_code(tmp_path: Path) -> None:
    """DEC-155 feeds cite `path:line`; the sweep resolves them in the scenario's `code/` (DEC-156)."""
    from trace_ai.services.evaluation.sweep import _reviewed_code

    def _write(slug: str) -> Path:
        path = tmp_path / f"{slug}-run-1.yaml"
        path.write_text(
            "\n".join(
                [
                    'feed_version: "1"',
                    "arm: mantis",
                    f"scenario: {slug}",
                    "run: 1",
                    "tool: {name: google/mantis, version: deadbeef}",
                    "models: []",
                    "snapshot_sha: 0123456789abcdef0123456789abcdef01234567",
                    "provenance: captured",
                    "mapped_by: test",
                    "findings: []",
                ]
            ),
            encoding="utf-8",
        )
        return path

    with_code = _reviewed_code(_write("unsigned-webhooks"))
    assert with_code is not None and with_code.name == "code" and with_code.is_dir()
    assert _reviewed_code(_write("forgeflow")) is None
