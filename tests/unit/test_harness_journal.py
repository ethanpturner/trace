"""The harness live path journals (#638, DEC-139): written live, re-driven explicitly, never
on a recording replay.

The #332 attempt measured the gap this closes: $14.35 of live responses lost to process kills
because `run_scenario` built its model bare while the CLI run commands journaled. These tests
drive the real harness path with the provider stubbed behind `build_model` — a live profile,
recorded responses standing in for the provider, no key and no spend — and pin the journal's
whole contract on that path: every consumed response lands in the work root's own
`traces/journal/` area, a named journal re-drives the pre-checkpoint prefix without touching
the provider, a spent entry answers exactly once, and the offline replay path mounts nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import trace_ai.services.evaluation.harness as harness_mod
from trace_ai.cli import run as cli_run
from trace_ai.config import PROJECT_ROOT
from trace_ai.infrastructure.model.factory import build_model
from trace_ai.infrastructure.model.journal import (
    SpentJournalEntryError,
    read_journal_entry,
    spent_marker,
)
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.recorded import load_recorded_responses
from trace_ai.services.evaluation.harness import HarnessError, run_scenario
from trace_ai.services.evaluation.registry import scenario

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# The smallest registered scenario: a full fourteen-phase run at unit-test cost.
SLUG = "missing-docs"

# A preserved #332 journal entry: a real live response with its request hash, committed as the
# attempt record's raw material and stable enough to fixture on.
PRESERVED_ENTRY = (
    PROJECT_ROOT
    / "docs"
    / "eval"
    / "model-comparison"
    / "journals"
    / "opus-missing-docs-attempt1"
    / "01-context-extraction.json"
)

# A live profile by provider, answered by recorded responses: the journal mounts on the
# `live` branch, and no key is read because `build_model` never reaches an adapter.
LIVE_PROFILE = "openrouter-economy"


def _recorded_backed_builder(skip: int = 0) -> Callable[..., object]:
    """A `build_model` stand-in: whatever profile is asked for, answer from the scenario's own
    recording. `skip` drops the leading responses a journal replay will serve instead — a
    re-driven provider is only asked the calls the journal cannot answer."""
    entry = scenario(SLUG)
    recordings = sorted(entry.recorded_dir_for("clean").rglob("[0-9]*.json"))[skip:]

    def _build(profile: object, responses: object = None) -> object:
        return build_model(
            resolve_profile("offline-fake"), responses=load_recorded_responses(recordings)
        )

    return _build


def _journal_dir(work_root: Path) -> Path:
    dirs = [path for path in work_root.rglob("journal") if path.is_dir()]
    assert len(dirs) == 1, f"expected one journal directory, found {dirs}"
    return dirs[0]


def test_a_live_harness_run_journals_and_a_named_journal_re_drives_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole #638 contract on the real path: journaled live, re-driven from the named
    entries, spent exactly once."""
    entry = scenario(SLUG)
    recording_count = len(sorted(entry.recorded_dir_for("clean").rglob("[0-9]*.json")))

    # First run: live branch, provider stubbed. Every consumed response must be journaled.
    monkeypatch.setattr(harness_mod, "build_model", _recorded_backed_builder())
    first = run_scenario(
        SLUG,
        data_root=tmp_path / "work",
        label="journal-test",
        profile_name=LIVE_PROFILE,
        results_root=tmp_path / "results",
    )
    assert first.completed
    journal = _journal_dir(tmp_path / "work")
    entries = sorted(journal.glob("[0-9]*.json"))
    assert len(entries) == recording_count, "every consumed response is journaled"
    parsed = [read_journal_entry(path) for path in entries]
    assert all(item.call_sha256 for item in parsed), "the journal hashes every request"

    # Second run on a fresh root: the first entry is named for replay, so the provider must
    # only be asked the remaining calls. Pre-checkpoint composition is deterministic across
    # fresh roots, which is exactly what makes the prefix servable (#639 owns the rest).
    monkeypatch.setattr(harness_mod, "build_model", _recorded_backed_builder(skip=1))
    second = run_scenario(
        SLUG,
        data_root=tmp_path / "work2",
        label="journal-redrive",
        profile_name=LIVE_PROFILE,
        results_root=tmp_path / "results2",
        replay_journal=parsed[:1],
    )
    assert second.completed
    assert spent_marker(entries[0]).exists(), "the replayed entry is marked spent at its source"

    # Spent means once: naming the same entry again is a loud refusal, not a silent re-serve.
    with pytest.raises(SpentJournalEntryError):
        read_journal_entry(entries[0])


def test_a_recording_replay_mounts_no_journal(tmp_path: Path) -> None:
    """The offline path is unchanged: journaling a replay would record responses no provider
    gave, so no journal directory may appear anywhere under the work root."""
    outcome = run_scenario(
        SLUG,
        data_root=tmp_path / "work",
        label="offline",
        results_root=tmp_path / "results",
    )
    assert outcome.completed
    assert not [path for path in (tmp_path / "work").rglob("journal") if path.is_dir()]


def test_replay_journal_is_refused_on_a_recording_replay(tmp_path: Path) -> None:
    """A recording replay serves its own responses; offering it a journal is refused before
    anything loads or runs."""
    preserved = read_journal_entry(PRESERVED_ENTRY)
    with pytest.raises(HarnessError, match=r"replay_journal.*live"):
        run_scenario(
            SLUG,
            data_root=tmp_path / "work",
            label="refused",
            replay_journal=[preserved],
        )


def test_the_evaluate_command_refuses_a_journal_on_the_offline_profile(tmp_path: Path) -> None:
    """The CLI mirror of the same refusal: `--replay-journal` under the offline default exits 1
    without touching the harness."""
    code = cli_run(
        [
            "evaluate",
            SLUG,
            "--replay-journal",
            str(PRESERVED_ENTRY),
            "--work-root",
            str(tmp_path / "work"),
        ]
    )
    assert code == 1


def test_a_preserved_journal_entry_answers_only_its_own_call() -> None:
    """The #332 journals are real fixture material: hashed, schema-typed, and refusing any
    request but the one that paid for them."""
    entry = read_journal_entry(PRESERVED_ENTRY)
    assert entry.call_sha256 is not None
    assert entry.answers(schema=type(entry.response), request_hash=entry.call_sha256)
    assert not entry.answers(schema=type(entry.response), request_hash="0" * 64)
