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
KIND_REPORT = "doctored-kind-report"
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


FIRST_STOP = {
    "clean": {"findings": 0, "gaps": 7, "cite": 3, "sole": 0, "questions": 3},
    "doctored": {"findings": 0, "gaps": 11, "cite": 8, "sole": 1, "questions": 4},
}


def _final(run: str) -> dict[str, object]:
    return _load(EXCHANGE / run / "checkpoint-2-summary.json")


def _cells(label: str, after: str) -> list[int]:
    row = _table_row(label, after=after)
    if row and not re.match(r"^\d", row[0]):
        row = row[1:]
    return [int(re.match(r"\d+", cell).group()) for cell in row]  # type: ignore[union-attr]


def test_page_states_the_counts_at_the_first_stop() -> None:
    after = "### After checkpoint 1"
    assert _cells("Provisional findings proposed", after)[1:] == [
        FIRST_STOP[run]["findings"] for run in RUNS
    ]
    assert _cells("Documentation gaps", after)[1:] == [FIRST_STOP[run]["gaps"] for run in RUNS]
    assert _cells("… citing the packet among their evidence", after) == [
        FIRST_STOP[run]["cite"] for run in RUNS
    ]
    assert _cells("… with the packet as sole evidence", after) == [
        FIRST_STOP[run]["sole"] for run in RUNS
    ]
    assert _cells("Open questions", after)[1:] == [FIRST_STOP[run]["questions"] for run in RUNS]


def test_page_states_the_checkpoint_two_counts_the_summaries_hold() -> None:
    after = "### Checkpoint 2, and the reports"
    finals = {run: _final(run) for run in RUNS}

    def cp2(run: str, *path: str) -> int:
        node: object = finals[run]["checkpoint_2"]
        for key in path:
            assert isinstance(node, dict)
            node = node[key]
        assert isinstance(node, int)
        return node

    def rep(run: str, key: str) -> int:
        node = finals[run]["report"]
        assert isinstance(node, dict)
        return int(node[key])

    assert _cells("Provisional findings at checkpoint 2", after) == [
        cp2(r, "provisional_findings", "count") for r in RUNS
    ]
    assert _cells("… approved / rejected", after) == [cp2(r, "approved") for r in RUNS]
    assert _cells("Documentation gaps in the package (candidate)", after) == [
        cp2(r, "documentation_gaps", "count") for r in RUNS
    ]
    assert _cells("Gaps citing the packet", after) == [
        cp2(r, "documentation_gaps", "cite_packet") for r in RUNS
    ]
    assert _cells("Open questions", after) == [cp2(r, "open_questions") for r in RUNS]
    assert _cells("Report: approved findings", after) == [rep(r, "approved_findings") for r in RUNS]
    assert _cells("Report: assumption rows", after) == [rep(r, "assumption_rows") for r in RUNS]
    assert _cells("Report: open questions", after) == [
        rep(r, "open_questions_rendered") for r in RUNS
    ]
    for run in RUNS:
        assert rep(run, "documentation_gaps_rendered") == 0
        assert cp2(run, "documentation_gaps", "count") > 0


def test_no_provisional_finding_cited_the_packet_and_the_page_says_so() -> None:
    for run in RUNS:
        rows = _final(run)["checkpoint_2"]
        assert isinstance(rows, dict)
        findings = rows["provisional_findings"]
        assert isinstance(findings, dict)
        for row in findings["rows"]:
            assert row["cites_packet"] is False, row
    assert "No provisional finding in either run cited the packet" in PAGE.read_text()


def test_each_run_commits_its_report_decisions_and_recordings() -> None:
    for run in RUNS:
        for name in (
            "report.md",
            "ledger.txt",
            "decisions-findings.yaml",
            "decisions-context.yaml",
        ):
            assert (EXCHANGE / run / name).is_file(), (run, name)
        assert (EXCHANGE / run / "journal").is_dir()
        final = _final(run)
        assert isinstance(final["ledger_total_usd"], float)
        calls = final["model_calls"]
        assert isinstance(calls, int) and calls > 0


def test_the_kind_report_run_states_what_the_gate_refused_and_excluded() -> None:
    """The DEC-158 proof run's own summary, against the section that quotes it.

    The claim the section makes is narrow and checkable: the package carried no blocking question
    and no validation error, so it was approvable before the gate; six subjects carried the reason;
    the blanket pass was refused; and four identifiers that existed at extraction are absent from
    the approved revision.
    """
    summary = _load(EXCHANGE / KIND_REPORT / "checkpoint-1-summary.json")

    questions = summary["questions"]
    assert isinstance(questions, dict)
    assert questions["blocking"] == 0, (
        "the section's claim that the package was otherwise approvable rests on this: no blocking "
        "question stood in the way"
    )

    assert len(summary["report_derived_subjects"]) == 6  # type: ignore[arg-type]

    approval = summary["approval"]
    assert isinstance(approval, dict)
    assert approval["blanket_pass_refused"] is True
    assert approval["blockers_named"] == 6

    extracted = approval["extracted_membership"]
    approved = approval["approved_membership"]
    assert isinstance(extracted, dict) and isinstance(approved, dict)
    assert (extracted["components"], approved["components"]) == (9, 8)
    assert (extracted["assets"], approved["assets"]) == (5, 4)
    assert (extracted["claims"], approved["claims"]) == (25, 23)
    assert set(approval["excluded_by_the_gate"]) == {
        "cmp-009",
        "ast-005",
        "ctx-023",
        "ctx-024",
    }, "the fabricated component and asset and the two fabrication claims are the ones excluded"

    page = PAGE.read_text()
    assert "## What `--kind report` changes" in page
    for identifier in ("cmp-009", "ast-005", "ctx-023", "ctx-024"):
        assert identifier in page, f"the section names {identifier}"


def test_the_kind_report_summary_carries_no_source_text() -> None:
    keys = _walk_keys(_load(EXCHANGE / KIND_REPORT / "checkpoint-1-summary.json"))
    assert not (keys & FORBIDDEN_KEYS), keys & FORBIDDEN_KEYS
