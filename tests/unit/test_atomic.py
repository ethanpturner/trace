"""Tests for atomic file writes.

The property that matters is that a reader never sees a half-written file: an interrupted write
leaves the previous contents (or nothing), never a truncation. The workflow state file leans on
this every phase, and a stored artifact leans on it to keep matching its content hash.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from trace_ai.infrastructure.filesystem import atomic


def test_write_text_atomic_creates_the_file(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    atomic.write_text_atomic(target, '{"ok": true}')
    assert target.read_text(encoding="utf-8") == '{"ok": true}'


def test_write_text_atomic_overwrites_in_place(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    atomic.write_text_atomic(target, "first")
    atomic.write_text_atomic(target, "second")
    assert target.read_text(encoding="utf-8") == "second"
    assert list(tmp_path.iterdir()) == [target], "a temporary was left behind"


def test_a_failed_write_preserves_the_previous_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash during the replace must leave the old file intact, not a truncation."""
    import os

    target = tmp_path / "state.json"
    atomic.write_text_atomic(target, "the good, whole, previous value")

    def failing_replace(src: object, dst: object) -> None:
        raise OSError("simulated crash during rename")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated crash"):
        atomic.write_bytes_atomic(target, b"a new value that never lands")

    assert target.read_text(encoding="utf-8") == "the good, whole, previous value"
    assert list(tmp_path.iterdir()) == [target], "the temporary was not cleaned up"
