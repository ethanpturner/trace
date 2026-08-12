"""The ForgeFlow truth files, held to their own shape and to the catalog.

`tests/unit/test_requirements_catalog.py` established the reasoning and it applies unchanged:
hand-maintained data with no reader drifts silently. These four files are graded against, so a
typo in a requirement identifier is a case that quietly stops testing anything.

Three properties matter more than the shape checks:

**Every requirement reference resolves against the catalog version the files declare.** No
requirement text is restated anywhere — restating would fork the catalog, and DEC-010's first open
question asks exactly this. A reference that no longer resolves is a case grading against a
requirement nobody has.

**Every suppression names an entry that is actually in the catalog.** A negative expectation whose
`common_false_positives` entry does not exist is a test that passes because nothing suppresses
anything, which is indistinguishable from a system that finds nothing at all.

**Nothing under `expected/` reaches an agent.** `tests/unit/test_forgeflow_fixture.py` already
asserts that no module under `src/` reads the directory; this file adds the narrower claim the
issue asks for, that no payload assembler does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.control_mapping import SatisfactionStatus
from trace_ai.services.requirements.loader import load_catalog

EXPECTED = PROJECT_ROOT / "demo" / "forgeflow" / "expected"

THREATS = EXPECTED / "expected-threats.yaml"
MAPPINGS = EXPECTED / "expected-control-mappings.yaml"
QUESTIONS = EXPECTED / "expected-questions.yaml"
REJECTIONS = EXPECTED / "expected-rejections.yaml"

TRUTH_FILES = (THREATS, MAPPINGS, QUESTIONS, REJECTIONS)

# Mechanisms a negative expectation may name. Closed, because "no_evidence" is the one that
# would otherwise absorb every case somebody could not be bothered to trace.
MECHANISMS = frozenset(
    {"common_false_positives", "non_applicable_conditions", "no_evidence", "documentation_gap"}
)


def load(path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), f"{path.name} is not a mapping"
    return parsed


@pytest.fixture(scope="module")
def catalog_requirements() -> dict[str, Any]:
    return load_catalog("0.1").by_id()


# The files exist, where DEC-027 puts them


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.name)
def test_the_truth_file_exists(path: Path) -> None:
    assert path.is_file()


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.name)
def test_every_truth_file_names_the_scenario_and_version(path: Path) -> None:
    parsed = load(path)

    assert parsed["scenario"] == "forgeflow"
    assert parsed["benchmark_version"] == "1.0"


@pytest.mark.parametrize("path", [MAPPINGS, REJECTIONS], ids=lambda p: p.name)
def test_the_files_that_cite_requirements_pin_the_catalog_version(path: Path) -> None:
    """A reference without a version is a reference to whatever is on disk today."""
    assert load(path)["catalog_version"] == "0.1"


# Threats (scenario section 18)


def test_all_ten_expected_threats_are_recorded() -> None:
    threats = load(THREATS)["threats"]

    assert len(threats) == 10
    assert [entry["key"] for entry in threats] == [f"THR-{n:03d}" for n in range(1, 11)]


@pytest.mark.parametrize("field", ["title", "summary", "preconditions", "impact_elements"])
def test_every_threat_records_the_elements_a_match_needs(field: str) -> None:
    for entry in load(THREATS)["threats"]:
        assert entry.get(field), f"{entry['key']} has no {field}"


def test_every_threat_records_at_least_one_precondition_and_impact() -> None:
    """Section 18's own shape: a scenario missing either is not yet a scenario."""
    for entry in load(THREATS)["threats"]:
        assert len(entry["preconditions"]) >= 1
        assert len(entry["impact_elements"]) >= 1


def test_the_conditional_threat_is_marked_optional() -> None:
    """Section 18 conditions THR-010 itself; neither raising nor omitting it is a miss."""
    threats = {entry["key"]: entry for entry in load(THREATS)["threats"]}

    assert threats["THR-010"]["optional"] is True
    assert sum(1 for entry in threats.values() if entry.get("optional")) == 1


def test_no_threat_records_prose_to_match_literally() -> None:
    """Section 18: exact wording does not need to match, so nothing here is a match string."""
    for entry in load(THREATS)["threats"]:
        assert "expected_title" not in entry
        assert "match_text" not in entry


def test_the_threat_file_sets_no_count_target() -> None:
    parsed = load(THREATS)

    assert "expected_count" not in parsed
    assert "minimum_threats" not in parsed


# Control mappings (scenario sections 13 and 14, DEC-013)


def test_every_expected_threat_has_mappings() -> None:
    threat_keys = {entry["key"] for entry in load(THREATS)["threats"]}
    mapped = {entry["threat_key"] for entry in load(MAPPINGS)["mappings"]}

    assert mapped == threat_keys


def test_every_requirement_reference_resolves(catalog_requirements: dict[str, Any]) -> None:
    """A reference that no longer resolves is a case grading against a requirement nobody has."""
    parsed = load(MAPPINGS)
    referenced = [
        applicable["requirement_id"]
        for entry in parsed["mappings"]
        for applicable in entry["applicable"]
    ]
    referenced += [entry["requirement_id"] for entry in parsed["must_not_conclude"]]
    referenced += [entry["requirement_id"] for entry in parsed["genuine_weaknesses"]]
    referenced += [entry["requirement_id"] for entry in load(REJECTIONS)["rejections"]]
    referenced += [
        entry["requirement_id"]
        for entry in load(QUESTIONS)["questions"]
        if "requirement_id" in entry
    ]

    assert referenced
    unknown = sorted({value for value in referenced if value not in catalog_requirements})
    assert not unknown, f"these requirement identifiers are not in catalog 0.1: {unknown}"


def test_no_requirement_text_is_restated(catalog_requirements: dict[str, Any]) -> None:
    """DEC-010's first open question, answered: reference the catalog, never copy it."""
    text = " ".join(path.read_text(encoding="utf-8") for path in TRUTH_FILES)

    for requirement in catalog_requirements.values():
        statement = " ".join(requirement.statement.split())
        assert statement not in text, f"{requirement.id}'s statement is copied into a truth file"


def test_every_expected_satisfaction_is_a_permitted_status() -> None:
    permitted = {member.value for member in SatisfactionStatus}

    for entry in load(MAPPINGS)["mappings"]:
        for applicable in entry["applicable"]:
            assert applicable["expected_satisfaction"] in permitted


def test_no_mapping_expects_unmet() -> None:
    """DEC-013: `unmet` needs a passage describing the shortfall, and none of the inputs has one."""
    for entry in load(MAPPINGS)["mappings"]:
        for applicable in entry["applicable"]:
            assert applicable["expected_satisfaction"] != SatisfactionStatus.UNMET.value


def test_every_applicable_mapping_states_a_reason() -> None:
    for entry in load(MAPPINGS)["mappings"]:
        for applicable in entry["applicable"]:
            assert applicable["reason"].strip()


# The five intentional non-findings (scenario section 14)


def test_all_five_intentional_non_findings_are_recorded() -> None:
    negatives = load(MAPPINGS)["must_not_conclude"]

    assert len(negatives) == 5
    assert [entry["scenario_section"] for entry in negatives] == [
        "14.1",
        "14.2",
        "14.3",
        "14.4",
        "14.5",
    ]


def test_every_negative_names_a_known_mechanism() -> None:
    for entry in load(MAPPINGS)["must_not_conclude"]:
        assert entry["mechanism"] in MECHANISMS, entry["key"]
        assert entry["entry"].strip()
        assert entry["expected_instead"].strip()


def test_every_catalog_backed_negative_names_a_real_entry(
    catalog_requirements: dict[str, Any],
) -> None:
    """A suppression naming an entry the catalog does not have suppresses nothing."""
    for entry in load(MAPPINGS)["must_not_conclude"]:
        if entry["mechanism"] == "common_false_positives":
            entries = catalog_requirements[entry["requirement_id"]].common_false_positives
        elif entry["mechanism"] == "non_applicable_conditions":
            entries = catalog_requirements[entry["requirement_id"]].non_applicable_conditions
        else:
            continue

        assert " ".join(entry["entry"].split()) in {" ".join(value.split()) for value in entries}, (
            entry["key"]
        )

        # `also_covers` names the other entries that would independently stop the same wrong
        # conclusion, and they may sit in either field: NF-14.3's mechanism is a
        # non-applicability condition while the two conclusions it also covers are
        # `common_false_positives` entries on the same requirement.
        requirement = catalog_requirements[entry["requirement_id"]]
        either = {
            " ".join(value.split())
            for value in (
                *requirement.common_false_positives,
                *requirement.non_applicable_conditions,
            )
        }
        also = {" ".join(value.split()) for value in entry.get("also_covers", [])}
        missing = sorted(also - either)
        assert not missing, (
            f"{entry['key']} names entries {entry['requirement_id']} lacks: {missing}"
        )


# The five genuine weaknesses (scenario section 13)


def test_all_five_genuine_weaknesses_are_recorded() -> None:
    weaknesses = load(MAPPINGS)["genuine_weaknesses"]

    assert len(weaknesses) == 5
    assert [entry["scenario_section"] for entry in weaknesses] == [
        "13.1",
        "13.2",
        "13.3",
        "13.4",
        "13.5",
    ]


def test_every_genuine_weakness_states_what_would_make_it_reachable() -> None:
    """Section 13.1 states its condition explicitly; the others get the same treatment."""
    for entry in load(MAPPINGS)["genuine_weaknesses"]:
        assert entry["evidence_condition"].strip()
        assert entry["reachable_at"] in {member.value for member in SatisfactionStatus}


def test_the_webhook_replay_case_is_a_documentation_gap_and_not_a_finding() -> None:
    """DEC-029: FND-001 is GAP-004. The topic is undocumented, not the control absent."""
    weaknesses = {entry["key"]: entry for entry in load(MAPPINGS)["genuine_weaknesses"]}
    replay = weaknesses["GW-13.1"]

    assert replay["expected_outcome"] == "documentation_gap"
    assert replay["reachable_at"] == SatisfactionStatus.UNVERIFIED.value


# Questions (scenario section 20)


def test_all_ten_expected_questions_are_recorded() -> None:
    questions = load(QUESTIONS)["questions"]

    assert len(questions) == 10
    assert [entry["key"] for entry in questions] == [f"Q-{n:02d}" for n in range(1, 11)]


def test_every_question_says_what_its_answer_would_change() -> None:
    """Section 20: questions are prioritised by their ability to change findings."""
    for entry in load(QUESTIONS)["questions"]:
        assert entry["changes"].strip()
        assert entry["priority"] in {"low", "medium", "high"}
        assert isinstance(entry["blocking"], bool)


def test_the_webhook_authenticity_ambiguity_is_a_question_and_not_a_finding() -> None:
    """Scenario 15.1, recorded where the acceptance criterion asks for it."""
    questions = {entry["key"]: entry for entry in load(QUESTIONS)["questions"]}

    assert questions["Q-01"]["arises_from"] == "scenario 15.1"
    assert questions["Q-01"]["requirement_id"] == "req-WEBHOOK-001"


def test_both_intentional_contradictions_produce_questions() -> None:
    """Scenario 16.1 and 16.2: Trace must not silently choose the safer statement."""
    questions = {entry["key"]: entry for entry in load(QUESTIONS)["questions"]}

    assert questions["Q-08"]["arises_from"] == "scenario 16.1"
    assert questions["Q-07"]["arises_from"] == "scenario 16.2"


def test_the_contradictions_are_recorded_as_mapping_outcomes_too() -> None:
    outcomes = [
        applicable
        for entry in load(MAPPINGS)["mappings"]
        for applicable in entry["applicable"]
        if applicable.get("expected_outcome") == "question"
    ]

    assert {applicable["requirement_id"] for applicable in outcomes} >= {
        "req-DATA-002",
        "req-AI-002",
    }


# Rejections (scenario section 22)


def test_every_rejected_claim_is_recorded() -> None:
    rejections = load(REJECTIONS)["rejections"]

    assert len(rejections) == 11
    assert [entry["key"] for entry in rejections] == [f"REJ-{n:02d}" for n in range(1, 12)]


def test_every_rejection_names_a_mechanism_and_a_reason() -> None:
    """A claim that fails to appear is not evidence of anything on its own."""
    for entry in load(REJECTIONS)["rejections"]:
        assert entry["mechanism"] in MECHANISMS, entry["key"]
        assert entry["entry"].strip()
        assert entry["why"].strip()
        assert entry["claim"].strip()


def test_every_catalog_backed_rejection_names_a_real_entry(
    catalog_requirements: dict[str, Any],
) -> None:
    for entry in load(REJECTIONS)["rejections"]:
        if entry["mechanism"] == "common_false_positives":
            entries = catalog_requirements[entry["requirement_id"]].common_false_positives
        elif entry["mechanism"] == "non_applicable_conditions":
            entries = catalog_requirements[entry["requirement_id"]].non_applicable_conditions
        else:
            continue

        normalized = {" ".join(value.split()) for value in entries}
        assert " ".join(entry["entry"].split()) in normalized, entry["key"]


def test_the_three_named_regressions_are_all_present() -> None:
    """`evaluation-plan.md` section 11 names three by name."""
    claims = " ".join(entry["claim"] for entry in load(REJECTIONS)["rejections"]).lower()

    assert "password-complexity" in claims
    assert "unencrypted" in claims
    assert "multi-factor authentication is completely absent" in claims


def test_the_replay_claim_is_rejected_as_a_documentation_gap() -> None:
    """Section 22 names this as the one a generic review most expects to get wrong."""
    rejections = {entry["key"]: entry for entry in load(REJECTIONS)["rejections"]}

    assert rejections["REJ-11"]["mechanism"] == "documentation_gap"
    assert "undocumented" in rejections["REJ-11"]["entry"]


# The truth set is withheld


def test_no_payload_assembler_reads_the_expected_directory() -> None:
    """Scenario section 25: the whole directory is withheld during an assessment.

    `services/evaluation/` is exempt by name: the evaluation layer is the grader, and DEC-073
    has it read the truth set *after* a run to score it. What keeps the withholding real is the
    input side — the packages agents receive are asserted elsewhere to carry no expected
    content, and the harness supplies a scenario's `input/` directory and nothing else.
    """
    assemblers = sorted((PROJECT_ROOT / "src" / "trace_ai" / "services").rglob("*.py"))
    assemblers += sorted((PROJECT_ROOT / "src" / "trace_ai" / "workflow").rglob("*.py"))
    assert assemblers, "the assembler sweep found no modules"

    # Path references, not prose. `services/requirements/loader.py` mentions
    # "expected-output files" in a docstring, which is a sentence about the benchmark rather
    # than a read of it, and a test that fired on the word would be testing the prose.
    grader = PROJECT_ROOT / "src" / "trace_ai" / "services" / "evaluation"
    for path in assemblers:
        if path.is_relative_to(grader):
            continue
        text = path.read_text(encoding="utf-8")
        for forbidden in ("expected/", '"expected"', "'expected'", "forgeflow/expected"):
            assert forbidden not in text, f"{path} references the withheld truth set"


def test_the_truth_files_declare_no_expected_output_counts() -> None:
    """DEC-028: the expected set is the enumerated content, and a count is derived from it."""
    for path in TRUTH_FILES:
        parsed = load(path)
        for forbidden in ("expected_findings", "expected_threats", "expected_questions"):
            assert forbidden not in parsed, f"{path.name} declares a count"
