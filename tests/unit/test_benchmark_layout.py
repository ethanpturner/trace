"""Tests pinning the benchmark scenario layout and the scenario registry.

DEC-027 fixed a layout that the corpus had specified twice, differently.
`evaluation-plan.md` section 5 and `forgeflow-scenario.md` section 25 disagreed about the
file list and about whether the reviewer-notes file was `review-notes.md` or
`reviewer-notes.md`. They turned out not to be competing specifications at all -- one
described a scenario's inputs and the other its expected outputs -- but the drift was real
and had already cost something: DEC-021 added `SourceObservation` and neither list gained a
file for it, so the contract counted contradictions that had nowhere to live.

Two properties are worth a test rather than a document.

**Scenarios are discovered from a registry, never by scanning directories.** DEC-027 allows
two locations -- ForgeFlow at `demo/forgeflow/` because it is the demo as well as benchmark
scenario one, and `benchmarks/<slug>/` for the rest. Two discoverable homes is exactly the
specified-twice failure DEC-027 removed from the layout, and the registry is the only thing
that makes it safe. DEC-027 listed the corresponding test as an open question; this file is
that test, and the entry records it as closed.

**Nothing under `expected/` is supplied to Trace.** That rule is enforced for ForgeFlow by
`test_forgeflow_fixture.py`; here it is enforced as a property of the layout itself, so a
second scenario cannot arrive with its truth set in the wrong place.

These tests check structure and placement, not content. The expected-output files are not
authored yet -- that is M3 and M4 work -- so a registered scenario is allowed to have an
`expected/` directory that holds only its contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT

BENCHMARKS = PROJECT_ROOT / "benchmarks"
REGISTRY = BENCHMARKS / "scenarios.yaml"

# One expected-*.yaml per domain object type the pipeline produces and the benchmark
# grades, plus the negative set. DEC-027 makes this list derived rather than enumerated:
# it is what the rule produces under the current object model, and it is pinned here so
# that adding an object type to data-model.md without adding a file is a failing test
# rather than a silent omission -- which is how expected-observations.yaml came to be
# missing in the first place.
EXPECTED_FILE_NAMES = (
    "expected-context.yaml",
    "expected-threats.yaml",
    "expected-control-mappings.yaml",
    "expected-findings.yaml",
    "expected-questions.yaml",
    "expected-documentation-gaps.yaml",
    "expected-observations.yaml",
    "expected-rejections.yaml",
)


def registry() -> dict[str, Any]:
    loaded: Any = yaml.safe_load(REGISTRY.read_text())
    assert isinstance(loaded, dict)
    return loaded


def scenarios() -> list[dict[str, Any]]:
    entries: Any = registry()["scenarios"]
    assert isinstance(entries, list)
    return entries


def scenario_ids() -> list[str]:
    return [str(entry["slug"]) for entry in scenarios()]


def test_registry_exists_and_parses() -> None:
    assert REGISTRY.is_file(), (
        "benchmarks/scenarios.yaml is the authoritative list of benchmark scenarios "
        "(DEC-027). Without it the harness would have to scan directories."
    )
    assert registry()["registry_version"] == "1.0"


def test_registry_is_not_empty() -> None:
    assert scenarios(), "a registry naming no scenarios means no benchmark runs"


def test_scenario_slugs_are_unique() -> None:
    slugs = scenario_ids()
    assert len(slugs) == len(set(slugs))


@pytest.mark.parametrize("slug", scenario_ids())
def test_registered_scenario_path_resolves(slug: str) -> None:
    entry = next(s for s in scenarios() if s["slug"] == slug)
    path = PROJECT_ROOT / str(entry["path"])
    assert path.is_dir(), f"{slug} is registered at {entry['path']}, which is not a directory"


@pytest.mark.parametrize("slug", scenario_ids())
def test_registered_scenario_has_input_and_expected(slug: str) -> None:
    entry = next(s for s in scenarios() if s["slug"] == slug)
    path = PROJECT_ROOT / str(entry["path"])
    for subdirectory in ("input", "expected"):
        assert (path / subdirectory).is_dir(), (
            f"{slug} is missing {subdirectory}/. Every scenario directory holds input/ "
            f"and expected/ (DEC-027, evaluation-plan.md section 5)."
        )


@pytest.mark.parametrize("slug", scenario_ids())
def test_expected_directory_is_not_inside_input(slug: str) -> None:
    """The truth set must not sit anywhere the pipeline reads as material under review.

    This is the structural half of the rule issue #18 established. Withholding the whole
    `expected/` directory is a simpler rule than a per-file one, and it only works if
    `expected/` is a sibling of `input/` rather than a descendant of it.
    """
    entry = next(s for s in scenarios() if s["slug"] == slug)
    path = PROJECT_ROOT / str(entry["path"])
    expected = (path / "expected").resolve()
    source = (path / "input").resolve()
    assert source not in expected.parents
    assert expected not in source.parents


@pytest.mark.parametrize("slug", scenario_ids())
def test_registered_scenario_declares_a_contract(slug: str) -> None:
    entry = next(s for s in scenarios() if s["slug"] == slug)
    contract = PROJECT_ROOT / str(entry["path"]) / "expected" / "evaluation-contract.yaml"
    assert contract.is_file(), f"{slug} has no evaluation-contract.yaml"
    loaded: Any = yaml.safe_load(contract.read_text())
    assert "catalog_version" in loaded, (
        f"{slug}'s contract must pin the catalog version its expected outputs were "
        f"authored against. There is no per-scenario requirements file (DEC-027)."
    )


@pytest.mark.parametrize("slug", scenario_ids())
def test_every_truth_file_pins_the_contract_catalog_version(slug: str) -> None:
    """A truth file's `catalog_version` agrees with the scenario's contract (#602).

    oidc-portal shipped three files still pinning "0.1" while its contract and the registry said
    0.3 — a reference to a catalog the scenario was never authored against, and nothing noticed
    until a docs-truth pass read it. The contract is the one place the version is decided; every
    expected file that states one restates it."""
    entry = next(s for s in scenarios() if s["slug"] == slug)
    expected_dir = PROJECT_ROOT / str(entry["path"]) / "expected"
    contract: Any = yaml.safe_load((expected_dir / "evaluation-contract.yaml").read_text())
    pinned = contract["catalog_version"]
    for path in sorted(expected_dir.glob("*.yaml")):
        loaded: Any = yaml.safe_load(path.read_text())
        if isinstance(loaded, dict) and "catalog_version" in loaded:
            assert loaded["catalog_version"] == pinned, (
                f"{slug}/{path.name} pins catalog {loaded['catalog_version']!r}; the contract "
                f"pins {pinned!r}"
            )


def test_every_benchmark_directory_is_registered() -> None:
    """A scenario directory the registry does not name would simply never run.

    That is a silent omission, which is the failure mode this project is least tolerant of.
    DEC-027 raised it as an open question and this test closes it.
    """
    # `regressions/` is not a scenario: it holds single-behaviour false-positive fixtures
    # consumed directly by unit tests (issue #112, evaluation-plan.md section 11), has no
    # input/expected split, and is never run by the harness — so the registry does not list
    # it and the silent-omission argument does not apply. `results/` is DEC-073's derived,
    # gitignored feed home: any local `trace evaluate` creates it, and it is output, not a
    # scenario that could be silently omitted.
    unregistered = sorted(
        path.name
        for path in BENCHMARKS.iterdir()
        if path.is_dir()
        and path.name not in {"regressions", "results"}
        and path.name not in {str(s["slug"]) for s in scenarios()}
    )
    assert not unregistered, (
        f"{unregistered} sit under benchmarks/ without a scenarios.yaml entry and would "
        f"never be evaluated. Register them or remove them."
    )


def test_expected_file_names_are_kebab_case_yaml() -> None:
    for name in EXPECTED_FILE_NAMES:
        assert name.startswith("expected-")
        assert name.endswith(".yaml")
        assert name == name.lower()
        assert "_" not in name


def test_reviewer_notes_spelling_is_settled() -> None:
    """DEC-027 chose `reviewer-notes.md`; `review-notes.md` must not reappear.

    The corpus uses "reviewer" as the actor noun throughout -- reviewer acceptance rate,
    reviewer edit rate -- and consistency with that is the only thing that distinguished
    the two spellings. It is pinned so it is only decided once.

    The decision log is exempt. Naming what it rejected is what it is for, and DEC-027 has
    to be able to say which spelling lost. Every other document should use the winner.
    """
    documents = [
        path
        for path in sorted(PROJECT_ROOT.glob("docs/**/*.md"))
        + sorted(PROJECT_ROOT.glob("demo/**/*.md"))
        if path.name != "decision-log.md"
    ]
    offenders = [
        f"{path.relative_to(PROJECT_ROOT)}:{number}"
        for path in documents
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if "review-notes.md" in line
    ]
    assert not offenders, f"{offenders} use the rejected spelling; DEC-027 chose reviewer-notes.md"


def test_forgeflow_is_registered_and_carries_its_narrative() -> None:
    """ForgeFlow's location is a role split, not an exception.

    It stays at demo/forgeflow/ because it is the demo as well as benchmark scenario one,
    and the demo half is forgeflow-scenario.md -- a narrative written to be read by a
    person. Scenarios that exist only to be measured have no equivalent and live under
    benchmarks/. If the narrative ever disappears, the reason for the split has gone with
    it and the scenario should move.
    """
    entry = next((s for s in scenarios() if s["slug"] == "forgeflow"), None)
    assert entry is not None, "ForgeFlow is benchmark scenario one and must be registered"
    assert Path(str(entry["path"])) == Path("demo/forgeflow")
    narrative = PROJECT_ROOT / str(entry["narrative"])
    assert narrative.is_file()
