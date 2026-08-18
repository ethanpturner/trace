"""The decision log's structural invariant: every entry has a body.

Born of a real failure (#528's session): a conflict-resolution script truncated DEC-113 to a
bare heading, the file merged, and nothing noticed until a later merge read the tail. The
invariant a script can hold is small and load-bearing: every `## DEC-` heading is followed by
its `Date:` line within a few lines — a heading with no body cannot satisfy it. Number
uniqueness is deliberately not asserted: the log records one real historical collision
(DEC-083 appears twice, noted in place), and the record keeps its history.
"""

from __future__ import annotations

from trace_ai.config import PROJECT_ROOT

LOG = PROJECT_ROOT / "docs" / "architecture" / "decision-log.md"


def test_every_entry_heading_is_followed_by_its_date_line() -> None:
    lines = LOG.read_text(encoding="utf-8").splitlines()
    dangling = []
    for index, line in enumerate(lines):
        if not line.startswith("## DEC-"):
            continue
        body: list[str] = []
        for candidate in lines[index + 1 :]:
            if candidate.startswith("## DEC-"):
                break
            body.append(candidate)
        if not any(candidate.startswith("Date:") for candidate in body[:4]):
            dangling.append(line.strip())
    assert not dangling, (
        f"decision-log entries with no body (a heading not followed by its Date line): "
        f"{dangling}. A truncated entry is a decision the record no longer holds."
    )
