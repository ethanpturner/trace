"""The committed static demo report is the report the recording produces (#278).

`demo/forgeflow/assets/forgeflow-report.md` is the demo's recovery fallback for the report beat: a
reader who cannot render live opens the committed file. It is only a safe fallback while it is the
*same* report the pipeline generates, so this pins its content hash to `report-hash.txt` — the hash
`scripts/replay_forgeflow.py` checks the freshly rendered report against. If the report changes the
pin moves, this test fails, and the committed asset has to be regenerated rather than drifting into
a fallback that shows something the pipeline no longer produces.
"""

from __future__ import annotations

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.hashing import content_hash

REPORT = PROJECT_ROOT / "demo" / "forgeflow" / "assets" / "forgeflow-report.md"
PINNED = PROJECT_ROOT / "demo" / "forgeflow" / "recorded" / "report-hash.txt"


def test_the_static_demo_report_matches_the_pinned_hash() -> None:
    computed = content_hash(REPORT.read_bytes())
    pinned = PINNED.read_text(encoding="utf-8").strip()
    assert computed == pinned, (
        "the committed demo report has drifted from the recorded run; regenerate it with "
        "`uv run python scripts/replay_forgeflow.py --data-root <dir>` and copy the report from "
        "`<dir>/assessments/asm-001/outputs/`"
    )
