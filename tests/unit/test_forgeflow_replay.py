"""The committed ForgeFlow recording replays byte-for-byte in the default suite (#263).

This is the reviewer-verifiable claim: the whole pipeline re-runs from
`demo/forgeflow/recorded/` with no provider credential, and the rendered report's content hash
matches the pinned one. The test runs the same `replay()` the documented one-liner runs, against
a temporary data root, so `uv run pytest` proves what
`uv run python scripts/replay_forgeflow.py` prints.
"""

from __future__ import annotations

import importlib.util
import sys
from typing import TYPE_CHECKING, Any

from trace_ai.config import PROJECT_ROOT

if TYPE_CHECKING:
    from pathlib import Path


def _load() -> Any:
    path = PROJECT_ROOT / "scripts" / "replay_forgeflow.py"
    spec = importlib.util.spec_from_file_location("replay_forgeflow", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["replay_forgeflow"] = module
    spec.loader.exec_module(module)
    return module


replay_forgeflow = _load()


def test_the_recorded_run_replays_to_the_pinned_report_hash(
    tmp_path: Path, monkeypatch: Any
) -> None:
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    produced = replay_forgeflow.replay(tmp_path / "replay")

    assert produced == replay_forgeflow.pinned_hash(), (
        "the recorded ForgeFlow run no longer reproduces its report byte-for-byte; either a "
        "pipeline change altered rendering (re-pin deliberately, with the diff reviewed) or "
        "determinism broke (fix that instead)"
    )


def test_two_replays_produce_identical_reports(tmp_path: Path) -> None:
    """Stability is against the recording, not against luck: two fresh roots, one hash."""
    first = replay_forgeflow.replay(tmp_path / "one")
    second = replay_forgeflow.replay(tmp_path / "two")
    assert first == second
