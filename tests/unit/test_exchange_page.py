"""`docs/eval/exchange.md` quotes counts from the two live runs under `docs/eval/exchange/`.

The runs are not replayable in CI (DEC-139 journals are provider recordings of a live run, and
the page says so), so the guard here is the same one the sibling pages use: every number the
page states is recomputed from the committed summaries, and the summaries carry identifiers and
statuses only -- no field may hold source-document text (the rule `observability.py` enforces for
logs, applied to what a page may commit).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "eval" / "exchange.md"
EXCHANGE = ROOT / "docs" / "eval" / "exchange" / "rag-support-bot"

RUNS = ("clean", "doctored")
FORBIDDEN_KEYS = {"value", "text", "excerpt", "description", "summary", "content", "rationale"}


def _load(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text())
    assert isinstance(loaded, dict)
    return {str(key): value for key, value in loaded.items()}


def _summary(run: str) -> dict[str, object]:
    return _load(EXCHANGE / run / "checkpoint-1-summary.json")


def _table_row(label: str, after: str = "") -> list[str]:
    """The cells of the first table row labelled `label` at or after the heading `after`."""
    started = not after
    for line in PAGE.read_text().splitlines():
        if not started:
            started = line.startswith(after)
            continue
        if line.startswith(f"| {label}"):
            return [cell.strip() for cell in line.strip("|").split("|")][1:]
    raise AssertionError(f"no table row labelled {label!r} after {after!r} in {PAGE.name}")


def _walk_keys(node: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            keys.add(str(key))
            keys |= _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            keys |= _walk_keys(item)
    return keys


@pytest.mark.parametrize("run", RUNS)
def test_summaries_carry_no_source_text(run: str) -> None:
    keys = _walk_keys(_summary(run))
    assert not (keys & FORBIDDEN_KEYS), keys & FORBIDDEN_KEYS


def test_page_states_the_checkpoint_one_counts_the_summaries_hold() -> None:
    summaries = {run: _summary(run) for run in RUNS}

    def claims(run: str, kind: str, field: str) -> int:
        block = summaries[run]["claims"]
        assert isinstance(block, dict)
        entry = block[kind]
        assert isinstance(entry, dict)
        return int(entry[field])

    def objects(run: str, field: str) -> int:
        block = summaries[run]["objects"]
        assert isinstance(block, dict)
        return sum(int(entry[field]) for entry in block.values() if isinstance(entry, dict))

    expectations = {
        "Claims classified `documented`": [claims(r, "documented_claims", "count") for r in RUNS],
        "Claims classified `inferred`": [claims(r, "interpreted_claims", "count") for r in RUNS],
        "Objects (components, actors, assets, flows, boundaries)": [
            objects(r, "count") for r in RUNS
        ],
    }
    for label, values in expectations.items():
        cells = _table_row(label, after="### Checkpoint 1")
        assert [int(re.match(r"\d+", cell).group()) for cell in cells] == values, label  # type: ignore[union-attr]

    sole = [claims(r, "documented_claims", "packet_sole_evidence") for r in RUNS]
    assert sole == [1, 7]
    inferred_sole = [claims(r, "interpreted_claims", "packet_sole_evidence") for r in RUNS]
    assert inferred_sole == [4, 0]
    assert [objects(r, "packet_sole_evidence") for r in RUNS] == [0, 4]


def test_both_runs_commit_their_decision_files_and_packets() -> None:
    for run in RUNS:
        assert (EXCHANGE / run / "decisions-context.yaml").is_file()
        assert (EXCHANGE / run / "mantis-review-packet.md").is_file()
    clean = (EXCHANGE / "clean" / "mantis-review-packet.md").read_text()
    doctored = (EXCHANGE / "doctored" / "mantis-review-packet.md").read_text()
    assert doctored.startswith(clean.rstrip("\n"))
    assert doctored.count("\n### B.") - clean.count("\n### B.") == 3


def test_page_states_the_persisted_counts_at_each_stop() -> None:
    def cp2(run: str) -> dict[str, object]:
        return _load(EXCHANGE / run / "checkpoint-2-summary.json")

    summaries = {run: cp2(run) for run in RUNS}

    def count(run: str, section: str, field: str = "count") -> int:
        block = summaries[run][section]
        assert isinstance(block, dict)
        return int(block[field])

    findings = [count(r, "provisional_findings") for r in RUNS]
    gaps = [count(r, "documentation_gaps") for r in RUNS]
    citing = [count(r, "documentation_gaps", "cite_packet") for r in RUNS]
    sole = [count(r, "documentation_gaps", "packet_sole_evidence") for r in RUNS]
    questions = [count(r, "open_questions") for r in RUNS]

    def cells(label: str) -> list[int]:
        row = _table_row(label, after="### After checkpoint 1")[1:]
        return [int(re.match(r"\d+", c).group()) for c in row]  # type: ignore[union-attr]

    assert cells("Provisional findings proposed") == findings == [0, 0]
    assert cells("Documentation gaps") == gaps
    assert cells("… citing the packet among their evidence") == citing
    assert cells("… with the packet as sole evidence") == sole
    assert cells("Open questions") == questions
    for run in RUNS:
        assert (EXCHANGE / run / "ledger.txt").is_file()
        assert (EXCHANGE / run / "journal").is_dir()
        stopped = summaries[run]["stopped_at"]
        assert isinstance(stopped, str) and stopped
