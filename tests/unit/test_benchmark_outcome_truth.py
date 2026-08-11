"""The M4 outcome-side truth files: findings, gaps, observations, and the reviewer notes.

Issue #109. These tests hold structure and convention, not judgement — the style
`test_requirements_catalog.py` and `test_benchmark_truth.py` established for hand-maintained
fixture data. The judgement calls live in `reviewer-notes.md`, which is itself held to exist.

The test that matters most is the DEC-009 one: no expected finding rests on the absence of
documentation. The scenario's centre of gravity is that webhook replay protection — genuinely
missing in the complete scenario — is a documentation gap and a rejection here, never a finding,
because the supplied documents state only that the topic is undocumented (DEC-029).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT

EXPECTED = PROJECT_ROOT / "demo" / "forgeflow" / "expected"
INPUT = PROJECT_ROOT / "demo" / "forgeflow" / "input"

FINDINGS = EXPECTED / "expected-findings.yaml"
GAPS = EXPECTED / "expected-documentation-gaps.yaml"
OBSERVATIONS = EXPECTED / "expected-observations.yaml"
NOTES = EXPECTED / "reviewer-notes.md"


def loaded(path: Path) -> dict[str, Any]:
    parsed: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), f"{path.name} did not parse to a mapping"
    return parsed


def findings() -> list[dict[str, Any]]:
    return list(loaded(FINDINGS)["findings"])


def gaps() -> list[dict[str, Any]]:
    return list(loaded(GAPS)["documentation_gaps"])


def observations() -> list[dict[str, Any]]:
    return list(loaded(OBSERVATIONS)["observations"])


# ------------------------------------------------------------------------------------------
# The files exist and carry the truth-file header
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", [FINDINGS, GAPS, OBSERVATIONS], ids=lambda p: p.name)
def test_the_truth_file_exists_and_names_the_scenario(path: Path) -> None:
    data = loaded(path)
    assert data["benchmark_version"] == "1.0", path.name
    assert data["scenario"] == "forgeflow", path.name
    assert "source" in data, path.name


def test_the_reviewer_notes_exist_and_record_the_judgement_calls() -> None:
    assert NOTES.is_file()
    text = NOTES.read_text(encoding="utf-8")
    for call in ("DEC-029", "FND-003", "GAP-004", "severity", "borderline"):
        assert call.casefold() in text.casefold(), f"the notes do not cover {call}"


# ------------------------------------------------------------------------------------------
# Findings: three, affirmatively evidenced, sourced from real documents
# ------------------------------------------------------------------------------------------


def test_the_expected_findings_are_the_dec_029_three() -> None:
    """DEC-029 resolved the count: FND-002, FND-003, FND-004, and never FND-001."""
    keys = [entry["key"] for entry in findings()]
    assert keys == ["FND-002", "FND-003", "FND-004"]


def test_every_expected_finding_names_the_evidence_it_must_rest_on() -> None:
    for entry in findings():
        assert entry.get("evidence_establishes"), f"{entry['key']} names no required evidence"
        assert entry.get("supported_by"), f"{entry['key']} names no supplying document"


def test_every_supplying_document_exists_in_the_input_directory() -> None:
    for entry in [*findings(), *gaps()]:
        for name in entry.get("supported_by", []):
            assert (INPUT / name).is_file(), f"{entry['key']} cites {name}, which is not supplied"


def test_every_finding_requirement_resolves_against_catalog_zero_one() -> None:
    catalog_ids: set[str] = set()
    for path in (PROJECT_ROOT / "requirements" / "0.1").glob("*.yaml"):
        parsed: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        for requirement in parsed.get("requirements", []):
            catalog_ids.add(str(requirement["id"]))
    for entry in findings():
        assert entry["requirement_id"] in catalog_ids, (
            f"{entry['key']} cites {entry['requirement_id']}, which catalog 0.1 does not have"
        )


def test_severity_is_guidance_and_never_a_graded_value() -> None:
    """DEC-030: the pipeline emits nothing to score severity against."""
    for entry in findings():
        assert "severity_guidance" in entry, f"{entry['key']} has no reviewer guidance"
        assert "severity" not in entry, (
            f"{entry['key']} declares a graded severity; DEC-030 makes severity the "
            f"reviewer's, so the truth set records guidance only"
        )


def test_dec_009_no_expected_finding_rests_on_the_absence_of_documentation() -> None:
    """The DEC-009 line, held over the fixture data itself.

    FND-001 is absent from the findings; the webhook replay subject appears as GAP-004 and as
    the rejection REJ-11 instead; and no finding's required evidence is phrased as an absence —
    every `evidence_establishes` entry states something a document affirmatively says.
    """
    keys = {entry["key"] for entry in findings()}
    assert "FND-001" not in keys

    all_text = " ".join(
        f"{entry['subject']} {' '.join(entry['evidence_establishes'])}" for entry in findings()
    ).casefold()
    assert "replay" not in all_text, "the replay subject belongs to GAP-004, never a finding"

    gap_keys = {entry["key"] for entry in gaps()}
    assert "GAP-004" in gap_keys

    rejections = loaded(EXPECTED / "expected-rejections.yaml")["rejections"]
    replay_rejections = [
        entry for entry in rejections if "replay" in str(entry["claim"]).casefold()
    ]
    assert replay_rejections, "the wrong conclusion GAP-004 prevents must be a rejection"

    absence_phrases = ("is not documented", "is undocumented", "no documentation", "is absent")
    for entry in findings():
        for required in entry["evidence_establishes"]:
            lowered = str(required).casefold()
            assert not any(phrase in lowered for phrase in absence_phrases), (
                f"{entry['key']} requires evidence phrased as an absence: {required!r}. "
                f"Evidence establishes what a document says, never what it does not (DEC-009)."
            )


# ------------------------------------------------------------------------------------------
# Gaps and observations
# ------------------------------------------------------------------------------------------


def test_the_four_expected_gaps_are_recorded_with_what_is_missing() -> None:
    entries = gaps()
    assert [entry["key"] for entry in entries] == ["GAP-001", "GAP-002", "GAP-003", "GAP-004"]
    for entry in entries:
        assert entry.get("missing"), f"{entry['key']} does not say what is missing"


def test_gap_004_pairs_the_load_bearing_question() -> None:
    """Scenario section 21: Q-02 is load-bearing rather than optional."""
    gap_004 = next(entry for entry in gaps() if entry["key"] == "GAP-004")
    assert gap_004["paired_question"] == "Q-02"

    questions = loaded(EXPECTED / "expected-questions.yaml")["questions"]
    assert any(question["key"] == "Q-02" for question in questions)


def test_the_observations_are_the_two_contradictions_and_the_injection() -> None:
    """DEC-021: one object type, two kinds; scenario sections 16 and 17 supply exactly three."""
    entries = observations()
    kinds = [entry["kind"] for entry in entries]
    assert kinds.count("contradiction") == 2
    assert kinds.count("injection_attempt") == 1
    for entry in entries:
        if entry["kind"] == "contradiction":
            assert len(entry["between"]) == 2, f"{entry['key']} needs both sides"
            for side in entry["between"]:
                assert (INPUT / side["document"]).is_file()
        else:
            assert (INPUT / entry["document"]).is_file()


# ------------------------------------------------------------------------------------------
# No counts, and nothing supplied to Trace
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", [FINDINGS, GAPS, OBSERVATIONS], ids=lambda p: p.name)
def test_no_truth_file_declares_a_count(path: Path) -> None:
    """DEC-028: the expected set is what a file enumerates, at any nesting depth."""

    def scan(value: Any, trail: str) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                assert "count" not in str(key).casefold(), f"{path.name}: {trail}.{key}"
                assert "expected_outputs" not in str(key), f"{path.name}: {trail}.{key}"
                scan(nested, f"{trail}.{key}")
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                scan(nested, f"{trail}[{index}]")

    scan(loaded(path), "$")


def test_nothing_under_expected_is_read_by_an_assessment_run() -> None:
    """The truth set is never supplied to Trace (scenario section 25).

    The same rule `test_forgeflow_fixture.py` enforces, re-asserted beside the files it
    protects: no module under `src/` references this directory.
    """
    offenders = []
    evaluation = PROJECT_ROOT / "src" / "trace_ai" / "services" / "evaluation"
    for path in (PROJECT_ROOT / "src").rglob("*.py"):
        if path.is_relative_to(evaluation):
            # The one sanctioned consumer: the evaluation harness compares a *finished* run
            # against the truth set, which is grading, not assessing. Nothing on the pipeline
            # path may read it.
            continue
        source = path.read_text(encoding="utf-8")
        if "forgeflow/expected" in source or "expected-findings" in source:
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert not offenders, f"{offenders} reference the ForgeFlow truth set"
