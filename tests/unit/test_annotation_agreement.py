"""Inter-annotator agreement (#530, DEC-112): machinery only; the labor is a person's.

The properties that matter: agreement is over the DEC-056 identity forms and never wording; an
absent second set measures nothing (unmeasured, never zero); an artifact the second pass has
not covered is skipped, not read as an empty annotation; and the pooled number is the identity
sets' Jaccard, with the counts recoverable per artifact.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_ai.services.evaluation.agreement import compute_agreement, second_annotation_dir

if TYPE_CHECKING:
    from pathlib import Path

FINDINGS_FIRST = """findings:
  - key: FND-01
    requirement_id: req-AUTH-002
    affected_component: Jupyter Notebook
  - key: FND-02
    requirement_id: req-SECRET-001
    affected_component: Gather Images Application
"""

FINDINGS_SECOND_AGREEING_WORDED_DIFFERENTLY = """findings:
  - key: SECOND-A
    requirement_id: req-AUTH-002
    affected_component: "jupyter   notebook"
  - key: SECOND-B
    requirement_id: req-NET-001
    affected_component: Jupyter Notebook
"""

GAPS = """documentation_gaps:
  - key: GAP-01
    requirement_id: req-LOG-001
"""

QUESTIONS_FIRST = """questions:
  - key: Q-01
    subject: replay handling
    asks: Does a delivery carry a nonce or timestamp?
    requirement_id: req-WEBHOOK-002
"""

QUESTIONS_SECOND = """questions:
  - key: SECOND-Q1
    asks: "does a delivery   carry a nonce or timestamp?"
  - key: SECOND-Q2
    asks: Is the queue depth bounded?
"""


def _write(directory: Path, name: str, text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text, encoding="utf-8")


def test_agreement_is_over_identity_forms_never_wording(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    second = second_annotation_dir(tmp_path)
    _write(expected, "expected-findings.yaml", FINDINGS_FIRST)
    _write(second, "expected-findings.yaml", FINDINGS_SECOND_AGREEING_WORDED_DIFFERENTLY)

    outcome = compute_agreement(expected, second)
    assert outcome is not None
    (findings,) = outcome.artifacts
    # AUTH-002/jupyter notebook is shared despite the whitespace and case differences;
    # SECRET-001 is first-only and NET-001 second-only.
    assert (findings.in_both, findings.only_first, findings.only_second) == (1, 1, 1)
    assert outcome.pooled == 1 / 3


def test_question_identity_is_the_corpus_asks_field(tmp_path: Path) -> None:
    """Every committed `expected-questions.yaml` carries the question text as `asks`; the
    instrument shipped reading `question` and no test noticed (#565). Identity remains the
    normalized text, matched whitespace- and case-insensitively."""
    expected = tmp_path / "expected"
    second = second_annotation_dir(tmp_path)
    _write(expected, "expected-questions.yaml", QUESTIONS_FIRST)
    _write(second, "expected-questions.yaml", QUESTIONS_SECOND)

    outcome = compute_agreement(expected, second)
    assert outcome is not None
    (questions,) = outcome.artifacts
    assert questions.artifact == "questions"
    assert (questions.in_both, questions.only_first, questions.only_second) == (1, 0, 1)


def test_every_committed_truth_set_parses_under_the_identity_reader() -> None:
    """The field names this instrument reads are pinned against the corpus itself: a truth-set
    shape change that would crash a real second-set comparison fails here first."""
    from trace_ai.config import PROJECT_ROOT
    from trace_ai.services.evaluation import agreement

    scenario_dirs = [
        PROJECT_ROOT / "demo" / "forgeflow",
        *sorted(path.parent for path in (PROJECT_ROOT / "benchmarks").glob("*/expected")),
    ]
    assert len(scenario_dirs) >= 14
    for scenario in scenario_dirs:
        expected = scenario / "expected"
        outcome = agreement.compute_agreement(expected, expected)
        assert outcome is not None, f"{scenario.name}: no artifact parsed"
        for entry in outcome.artifacts:
            assert entry.only_first == 0 and entry.only_second == 0, scenario.name


def test_the_protocol_document_names_what_the_instrument_reads() -> None:
    """`docs/eval/annotation-protocol.md` is what a second annotator follows; the file names,
    the `annotations/second/` location, and the `asks` field it teaches must be the ones this
    module reads, or the pass produces files the instrument cannot see."""
    from trace_ai.config import PROJECT_ROOT

    protocol = (PROJECT_ROOT / "docs" / "eval" / "annotation-protocol.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "annotations/second/",
        "expected-findings.yaml",
        "expected-documentation-gaps.yaml",
        "expected-questions.yaml",
        "asks:",
        "requirement_id:",
        "affected_component:",
    ):
        assert required in protocol, f"the protocol no longer mentions {required!r}"


def test_an_absent_second_set_measures_nothing(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    _write(expected, "expected-findings.yaml", FINDINGS_FIRST)
    assert compute_agreement(expected, second_annotation_dir(tmp_path)) is None


def test_an_uncovered_artifact_is_skipped_not_read_as_empty(tmp_path: Path) -> None:
    """The second pass annotated findings and said nothing about gaps: gaps contribute no
    disagreement, because silence is not an empty set."""
    expected = tmp_path / "expected"
    second = second_annotation_dir(tmp_path)
    _write(expected, "expected-findings.yaml", FINDINGS_FIRST)
    _write(expected, "expected-documentation-gaps.yaml", GAPS)
    _write(second, "expected-findings.yaml", FINDINGS_FIRST)

    outcome = compute_agreement(expected, second)
    assert outcome is not None
    assert [entry.artifact for entry in outcome.artifacts] == ["findings"]
    assert outcome.pooled == 1.0


def test_two_empty_files_are_vacuous_not_perfect(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    second = second_annotation_dir(tmp_path)
    _write(expected, "expected-findings.yaml", "findings: []\n")
    _write(second, "expected-findings.yaml", "findings: []\n")

    outcome = compute_agreement(expected, second)
    assert outcome is not None
    (findings,) = outcome.artifacts
    assert findings.jaccard is None
    assert outcome.pooled is None
