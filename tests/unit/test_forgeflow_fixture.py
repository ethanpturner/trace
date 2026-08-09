"""Tests keeping the ForgeFlow benchmark contract out of the material under review.

`demo/forgeflow/input/structured-system-input.yaml` used to end with an `evaluation:`
block declaring the expected finding, question, documentation-gap, and contradiction
counts. That file is supplied to Trace as a source document, so the benchmark contract sat
inside the material under assessment. `demo/forgeflow/forgeflow-scenario.md` section 25
states that expected files must not be supplied to Trace during an assessment.

Two things were wrong with it. Every measurement taken against the scenario was
contaminated, because the system under test was given the answer key. And the pipeline was
handed a finding quota, which `docs/product/design-principles.md` section 9 rejects and
`CLAUDE.md` lists as a binding constraint -- a model that reads `findings: 3` has been told
how many to produce.

These tests exist so the leak cannot silently return. Issue #18.

They check structure and placement, not judgment. Whether the expected counts are *right*
is a review question, currently disputed and tracked by issue #39; whether they are in a
file Trace will read is this file's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow"
INPUT_DIR = FORGEFLOW / "input"
EXPECTED_DIR = FORGEFLOW / "expected"
CONTRACT = EXPECTED_DIR / "evaluation-contract.yaml"

# The documents the scenario supplies to Trace. forgeflow-scenario.md section 2.
INPUT_DOCUMENTS = (
    "product-overview.md",
    "architecture-overview.md",
    "security-overview.md",
    "operations-guide.md",
    "github-integration.md",
    "ai-analysis.md",
    "sample-repository-notes.md",
    "structured-system-input.yaml",
)

# Keys that describe what an assessment should conclude. None of these belongs in a
# document under review, whatever the file is called.
CONTRACT_KEYS = frozenset(
    {
        "evaluation",
        "expected_outputs",
        "expected_findings",
        "expected_questions",
        "expected_documentation_gaps",
        "expected_contradictions",
        "benchmark_version",
        "prompt_injection_fixture",
    }
)


def input_files() -> list[Path]:
    return sorted(p for p in INPUT_DIR.iterdir() if p.is_file() and not p.name.startswith("."))


def walk_keys(node: Any) -> list[str]:
    """Every mapping key anywhere in a parsed YAML document."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.append(str(key))
            found.extend(walk_keys(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(walk_keys(item))
    return found


def test_input_directory_holds_exactly_the_scenario_documents() -> None:
    assert {p.name for p in input_files()} == set(INPUT_DOCUMENTS)


@pytest.mark.parametrize("name", INPUT_DOCUMENTS)
def test_input_document_declares_no_expected_outputs(name: str) -> None:
    """No document under review may state what the assessment should conclude."""
    text = (INPUT_DIR / name).read_text()
    offenders = sorted(key for key in CONTRACT_KEYS if f"{key}:" in text)
    assert not offenders, (
        f"{name} contains benchmark contract key(s) {offenders}. Expected-output data "
        f"belongs in {EXPECTED_DIR.relative_to(PROJECT_ROOT)}, never in a document "
        f"supplied to Trace. See issue #18 and forgeflow-scenario.md section 25."
    )


def test_structured_input_parses_and_carries_no_contract_key() -> None:
    """The structural half of the same check: parse it and inspect the real keys."""
    loaded: Any = yaml.safe_load((INPUT_DIR / "structured-system-input.yaml").read_text())
    assert isinstance(loaded, dict)
    offenders = sorted(CONTRACT_KEYS.intersection(walk_keys(loaded)))
    assert not offenders, f"structured-system-input.yaml still declares {offenders}"


def test_structured_input_retains_its_scenario_content() -> None:
    """Removing the contract must not have taken the scenario data with it."""
    loaded: Any = yaml.safe_load((INPUT_DIR / "structured-system-input.yaml").read_text())
    for key in ("system", "components", "data_assets", "trust_boundaries", "notes"):
        assert key in loaded, f"structured-system-input.yaml lost its '{key}' section"


def test_injection_fixture_is_preserved_verbatim() -> None:
    """The planted payload is test data. Sanitizing it would destroy what it proves.

    agent-design.md section 25 and forgeflow-scenario.md section 17 both depend on this
    content being present and unaltered.
    """
    text = (INPUT_DIR / "sample-repository-notes.md").read_text()
    assert "AI ANALYSIS OVERRIDE" in text


def test_evaluation_contract_exists_outside_the_input_directory() -> None:
    assert CONTRACT.is_file(), (
        f"the relocated evaluation contract is missing from "
        f"{EXPECTED_DIR.relative_to(PROJECT_ROOT)}"
    )
    assert CONTRACT.parent != INPUT_DIR


def test_evaluation_contract_is_well_formed() -> None:
    loaded: Any = yaml.safe_load(CONTRACT.read_text())
    assert isinstance(loaded, dict)
    assert loaded["benchmark_version"] == "1.0"
    assert loaded["catalog_version"] == "0.1", (
        "the contract pins the requirements catalog version its expected outputs were "
        "authored against (DEC-027). There is no per-scenario requirements file."
    )


COUNT_KEYS = ("findings", "questions", "documentation_gaps", "contradictions")


def test_evaluation_contract_declares_no_counts() -> None:
    """DEC-028: the expected set is enumerated, never totalled.

    This test inverted when DEC-028 landed. It used to require an `expected_outputs` block
    carrying declared counts, because issue #18's concern was only *where* that block
    lived -- moving it out of the input directory stopped it contaminating measurements.

    DEC-028 went further. A declared count that can disagree with its own enumeration is a
    second source of truth, and it did disagree: the contract said three findings and five
    questions, the scenario document said four and ten. A count used as a grading target is
    also a finding quota by another name, which is the thing moving the file was meant to
    prevent and did not.

    So the count must not come back anywhere in the contract, at any nesting depth.
    """
    loaded: Any = yaml.safe_load(CONTRACT.read_text())
    assert "expected_outputs" not in loaded
    assert "disputed" not in loaded, (
        "the disputed-counts block records a conflict DEC-028 and DEC-029 resolved"
    )
    keys = set(walk_keys(loaded))
    offenders = sorted(keys & set(COUNT_KEYS))
    assert not offenders, (
        f"{offenders} reintroduce declared expected-output counts. The expected set is "
        f"the enumerated content of the expected-*.yaml files (DEC-028); a count is "
        f"derived from a file when a report needs one and is stored nowhere."
    )


def test_no_source_code_reads_the_expected_directory() -> None:
    """Nothing in the product may load expected outputs.

    There is no ingestion path yet, so today this asserts a property of an empty set. It is
    written now because the moment ingestion exists is the moment this can regress, and a
    test added afterwards is a test added after the bug.
    """
    needles = ("forgeflow/expected", 'forgeflow" / "expected', "forgeflow', 'expected")
    offenders = [
        str(path.relative_to(PROJECT_ROOT))
        for path in (PROJECT_ROOT / "src").rglob("*.py")
        if any(needle in path.read_text() for needle in needles)
    ]
    assert not offenders, (
        f"{offenders} reference the expected-output directory. Expected outputs are "
        f"benchmark truth and must never be read by the pipeline under test."
    )
