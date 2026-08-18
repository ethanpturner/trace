"""The release record and its shape (evaluation-plan section 17, #524).

Section 17 names six things every release records. The record is authored, so the test holds
its structure rather than its judgment: every section carries the four authored parts (version
and date are the heading), every git tag has a section, and the generated evaluation-summary
block matches what the committed artifacts say — the assembled-not-authored rule, enforced.
"""

from __future__ import annotations

import subprocess

from trace_ai.config import PROJECT_ROOT
from trace_ai.services.evaluation.release_record import (
    RELEASES,
    inject_summary,
    parse_releases,
    render_evaluation_summary,
)


def _record_text() -> str:
    return RELEASES.read_text(encoding="utf-8")


def test_every_entry_carries_the_section_17_parts() -> None:
    entries = parse_releases(_record_text())
    assert entries, "the release record has no entries"
    for entry in entries:
        assert not entry.missing_parts(), (
            f"{entry.version} is missing {entry.missing_parts()} — section 17 names all six "
            f"parts, and an entry without one is a release the record cannot account for"
        )


def test_every_release_tag_has_an_entry() -> None:
    """The direction that erodes: a tag cut without a record entry. The converse — an entry
    authored before its tag — is the normal pre-release state and is allowed."""
    tags = subprocess.run(
        ["git", "tag", "--list", "v*"],  # noqa: S607
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    recorded = {entry.version for entry in parse_releases(_record_text())}
    untracked = sorted(set(tags) - recorded)
    assert not untracked, f"tags with no release-record entry: {untracked}"


def test_the_generated_summary_block_is_current() -> None:
    """`build_release_record.py --check`, as a test: the newest entry's numbers are the
    committed artifacts', not an author's."""
    text = _record_text()
    newest = parse_releases(text)[0]
    assert inject_summary(text, newest.version, render_evaluation_summary()) == text


def test_entries_are_newest_first() -> None:
    entries = parse_releases(_record_text())
    dates = [entry.date for entry in entries]
    assert dates == sorted(dates, reverse=True)
