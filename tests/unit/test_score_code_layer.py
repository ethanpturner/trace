"""The code-layer scorer reads a DEC-156 truth file and scores a reviewer's feed RealVuln-style.

A finding matches an entry by cited file and a CWE in the entry's acceptable set; two entries
sharing a file and a family are separated by the cited line against a declared function span; a
`non_scoring` entry leaves both numerator and denominator; a finding that cites no file is counted
as unmatchable rather than as either a hit or a miss; a trap hit is a false positive.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from trace_ai.config import PROJECT_ROOT

_SCRIPT = PROJECT_ROOT / "scripts" / "score_code_layer.py"
_TRUTH = PROJECT_ROOT / "benchmarks" / "unsigned-webhooks" / "expected" / "code-ground-truth.yaml"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("score_code_layer", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["score_code_layer"] = module  # dataclasses resolve deferred annotations here
    spec.loader.exec_module(module)
    return module


def _feed(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "feed.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_the_receiver_finding_matches_and_the_ledger_is_non_scoring(tmp_path: Path) -> None:
    mod = _module()
    spans = {
        "deploy_notifier/main.py:receive_event": (31, 59),
        "deploy_notifier/main.py:healthz": (25, 28),
    }
    entries = mod.load_truth(_TRUTH, spans)
    feed = _feed(
        tmp_path,
        [
            {"signature": "a", "cwe": "CWE-306", "code_paths": ["deploy_notifier/main.py:31"]},
            {"signature": "a", "cwe": "CWE-306", "code_paths": ["deploy_notifier/main.py:31"]},
            {"signature": "b", "cwe": "CWE-294", "code_paths": ["deploy_notifier/replay.py:15"]},
            {"signature": "c", "cwe": ["CWE-400"], "code_paths": ["deploy_notifier/main.py:38"]},
            {"signature": "d", "cwe": "CWE-306", "code_paths": ["target"]},
            {"signature": "e", "cwe": "CWE-798", "code_paths": ["deploy_notifier/notifier.py:20"]},
        ],
    )
    result = mod.score(feed, entries)
    summary = result.summary(sum(1 for e in entries if e.vulnerable and e.scoring))

    assert summary["duplicates_collapsed"] == 1
    assert summary["matched_entries"] == ["unsigned-webhooks-001"]
    assert summary["non_scoring"] == 1
    assert summary["unmatchable_no_file"] == 1
    assert summary["trap_hits"] == 1  # the hardcoded-credential trap on notifier.py
    assert summary["false_positives"] == 2  # the trap hit and the unmatched CWE-400
    assert summary["precision"] == {"numerator": 1, "denominator": 3}
    assert summary["recall"] == {"numerator": 1, "denominator": 1}


def test_a_healthz_finding_is_the_trap_not_the_receiver(tmp_path: Path) -> None:
    mod = _module()
    entries = mod.load_truth(
        _TRUTH,
        {
            "deploy_notifier/main.py:receive_event": (31, 59),
            "deploy_notifier/main.py:healthz": (25, 28),
        },
    )
    feed = _feed(
        tmp_path,
        [{"signature": "h", "cwe": "CWE-306", "code_paths": ["deploy_notifier/main.py:26"]}],
    )
    summary = mod.score(feed, entries).summary(1)
    assert summary["trap_hits"] == 1 and summary["matched_entries"] == []
