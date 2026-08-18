"""The decision log's structural invariants: every entry has a body, and no number is missing.

Born of two real failures. In #528's session a conflict-resolution script truncated DEC-113 to a
bare heading, the file merged, and nothing noticed until a later merge read the tail. In #534's
session the inverse happened: the DEC-091 amendment paragraph replaced the `## DEC-092` heading
line, DEC-092's whole body survived headingless inside DEC-091, and two merges passed before
#564's session noticed the corpus citing an entry the log no longer held. The invariants a
script can hold are small and load-bearing: every `## DEC-` heading is followed by its `Date:`
line within a few lines — a heading with no body cannot satisfy it — and the heading numbers run
contiguously from the first to the last, so a deleted heading is a visible gap. Number
uniqueness is deliberately not asserted: the log records one real historical collision
(DEC-083 appears twice, noted in place), and the record keeps its history.
"""

from __future__ import annotations

import re

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


def test_entry_numbers_run_contiguously() -> None:
    numbers = sorted(
        {
            int(match)
            for match in re.findall(r"^## DEC-(\d+)", LOG.read_text(encoding="utf-8"), re.MULTILINE)
        }
    )
    missing = [n for n in range(numbers[0], numbers[-1] + 1) if n not in numbers]
    assert not missing, (
        f"decision-log numbers missing between DEC-{numbers[0]:03d} and DEC-{numbers[-1]:03d}: "
        f"{[f'DEC-{n:03d}' for n in missing]}. A gap is a heading an edit deleted; the body may "
        f"still be in the file, headingless inside the previous entry."
    )
