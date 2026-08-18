"""The one timestamp every deterministic render uses, so the committed pages change only on a number.

`agent-design.md` and the evaluation plan want the scorecard, the comparison, the ablation table,
and the replayed ForgeFlow report to be byte-stable: a diff shows a real change, not a clock tick.
That only holds if every renderer stamps the *same* instant. Five scripts and the harness each held
their own `GENERATED_AT`, and they had already drifted -- the harness stamped `2026-08-11` while
`report-hash.txt` was pinned against the replay script's `2026-08-14`, so the harness rendered the
same report to a different hash than the artifact it was supposed to reproduce.

One constant, imported everywhere, removes the drift by construction. `Date.now()` is deliberately
not used: a rendered artifact that moved with the wall clock could never be committed or diffed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

__all__ = ["DETERMINISTIC_STAMP"]

# The pinned generation instant. Changing it re-pins every committed page and the report hash in one
# place, on purpose -- which is the point of it being one place.
DETERMINISTIC_STAMP: Final = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)
