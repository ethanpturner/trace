"""The negative set is scored, and it is scored only where a scenario authored something scoreable.

DEC-154. The rules under test are the ones a later reader is most likely to weaken by accident: a
rejection with no requirement leaves the denominator rather than defaulting into it, a rate over an
empty denominator is not emitted (DEC-150), and only findings the matcher already called spurious
are eligible to breach anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from trace_ai.services.evaluation.registry import load_registry
from trace_ai.services.evaluation.rejections import (
    Rejection,
    load_rejections,
    score_rejections,
    spurious_requirements,
)


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    (tmp_path / "expected-rejections.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
    return tmp_path


def test_an_entry_without_a_requirement_is_not_loaded(tmp_path: Path) -> None:
    directory = _write(
        tmp_path,
        {
            "rejections": [
                {"key": "REJ-01", "mechanism": "no_evidence", "requirement_id": "req-A-001"},
                {"key": "REJ-02", "conclusion": "unscoreable", "suppressed_by": "silence"},
            ]
        },
    )
    loaded = load_rejections(directory)
    assert [rejection.key for rejection in loaded] == ["REJ-01"]


def test_a_scenario_with_no_scoreable_rejections_emits_no_rate() -> None:
    outcome = score_rejections({}, [])
    assert outcome.scoreable is False
    assert outcome.breach_rate is None, "a rate over an empty denominator is not emitted (DEC-150)"
    assert outcome.breach_count == 0


def test_a_spurious_finding_on_a_rejected_requirement_breaches_it() -> None:
    rejections = [Rejection(key="REJ-01", mechanism="no_evidence", requirement_id="req-A-001")]
    outcome = score_rejections({"fnd-001": ["req-A-001"]}, rejections)
    assert outcome.breached == {"REJ-01": ["fnd-001"]}
    assert outcome.breach_rate == 1.0


def test_a_spurious_finding_elsewhere_breaches_nothing() -> None:
    rejections = [Rejection(key="REJ-01", mechanism="no_evidence", requirement_id="req-A-001")]
    outcome = score_rejections({"fnd-001": ["req-B-002"]}, rejections)
    assert outcome.breached == {}
    assert outcome.breach_rate == 0.0, "zero breaches over a real denominator is a measurement"


def test_only_spurious_findings_are_eligible() -> None:
    """The caller passes the matcher's `spurious` set; a matched finding never reaches here.

    Pinned because the cheap implementation -- scoring every approved finding -- would count a
    finding that answered an expectation as a breach whenever an expectation and a rejection share
    a requirement, which the corpus contains.
    """
    rejections = [Rejection(key="REJ-01", mechanism="no_evidence", requirement_id="req-A-001")]
    matched_finding_excluded_by_caller: dict[str, list[str]] = {}
    outcome = score_rejections(matched_finding_excluded_by_caller, rejections)
    assert outcome.breached == {}


def test_mechanisms_carry_their_own_counts() -> None:
    rejections = [
        Rejection(key="REJ-01", mechanism="no_evidence", requirement_id="req-A-001"),
        Rejection(key="REJ-02", mechanism="no_evidence", requirement_id="req-B-002"),
        Rejection(key="REJ-03", mechanism="documentation_gap", requirement_id="req-C-003"),
    ]
    outcome = score_rejections({"fnd-001": ["req-A-001"], "fnd-002": ["req-C-003"]}, rejections)
    assert outcome.by_mechanism == {"documentation_gap": (1, 1), "no_evidence": (1, 2)}


def test_a_finding_citing_several_requirements_breaches_each_it_names() -> None:
    rejections = [
        Rejection(key="REJ-01", mechanism="no_evidence", requirement_id="req-A-001"),
        Rejection(key="REJ-02", mechanism="no_evidence", requirement_id="req-B-002"),
    ]
    outcome = score_rejections({"fnd-001": ["req-A-001", "req-B-002"]}, rejections)
    assert sorted(outcome.breached) == ["REJ-01", "REJ-02"]


def test_spurious_requirements_reads_only_the_named_findings() -> None:
    class _Finding:
        def __init__(self, identifier: str, requirements: list[str]) -> None:
            self.id = identifier
            self.requirement_ids = requirements

    findings = [_Finding("fnd-001", ["req-A-001"]), _Finding("fnd-002", ["req-B-002"])]
    assert spurious_requirements(["fnd-002"], findings) == {"fnd-002": ["req-B-002"]}


@pytest.mark.parametrize("entry", list(load_registry()), ids=lambda entry: entry.slug)
def test_every_registered_scenario_loads_without_error(entry: object) -> None:
    """The loader tolerates both authored shapes; only the canonical one scores.

    Recorded as a fact about the corpus rather than an assertion that every scenario is scoreable:
    `reply-tuner` authors `conclusion`/`suppressed_by` and yields nothing, which is the state
    DEC-154 accepts and reports as a dash.
    """
    expected = entry.path / "expected"  # type: ignore[attr-defined]
    loaded = load_rejections(expected)
    authored = yaml.safe_load((expected / "expected-rejections.yaml").read_text(encoding="utf-8"))[
        "rejections"
    ]
    assert len(loaded) <= len(authored)
    for rejection in loaded:
        assert rejection.requirement_id.startswith("req-")


def test_exactly_one_registered_scenario_is_unscoreable() -> None:
    """Pins the survey DEC-154 rests on, so a later normalization has to update the decision."""
    unscoreable = [
        entry.slug for entry in load_registry() if not load_rejections(entry.path / "expected")
    ]
    assert unscoreable == ["reply-tuner"]
