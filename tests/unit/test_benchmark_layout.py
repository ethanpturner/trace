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


# --- The code layer (DEC-156) ---------------------------------------------------------------
#
# A scenario may carry `code/`: a running implementation of the system its documents describe,
# authored from the truth set so a code reviewer and a documentation reviewer can be measured on
# one system. Trace never reads it; a code reviewer receives it alone. Its truth lives under
# `expected/` beside the design-level truth, in RealVuln's ground-truth shape so the scores
# compare with that leaderboard's (github.com/kolega-ai/Real-Vuln-Benchmark, arXiv 2604.13764).

CODE_TRUTH = "code-ground-truth.yaml"
CODE_NOTES = "code-notes.md"

# RealVuln's `ground-truth/{repo}/ground-truth.json`, top level and per finding, read from its
# README on 2026-09-10. Mirrored exactly: a consumer scoring against RealVuln's leaderboard reads
# these field names and no others.
REALVULN_TOP_LEVEL = frozenset(
    {
        "schema_version",
        "benchmark_version",
        "ground_truth_version",
        "repo_id",
        "repo_url",
        "commit_sha",
        "type",
        "language",
        "framework",
        "authorship",
        "authorship_model",
        "authorship_confidence",
        "authorship_evidence",
        "findings",
    }
)
REALVULN_FINDING_REQUIRED = frozenset(
    {
        "id",
        "is_vulnerable",
        "vulnerability_class",
        "primary_cwe",
        "acceptable_cwes",
        "file",
        "location",
        "severity",
        "evidence",
    }
)
REALVULN_FINDING_OPTIONAL = frozenset({"scoring", "non_scoring_reason"})
# Tokens that would hand a reviewer the answer key. None may appear anywhere under `code/`.
ANSWER_KEY_TOKENS = ("FND-", "GAP-", "REJ-", "is_vulnerable", "ground-truth", "code-notes")
CODE_SCRATCH = {".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def coded_scenarios() -> list[dict[str, Any]]:
    return [s for s in scenarios() if (PROJECT_ROOT / str(s["path"]) / "code").is_dir()]


def coded_scenario_ids() -> list[str]:
    return [str(s["slug"]) for s in coded_scenarios()]


def _code_files(code: Path) -> list[Path]:
    return [
        path
        for path in sorted(code.rglob("*"))
        if path.is_file() and not (set(path.relative_to(code).parts) & CODE_SCRATCH)
    ]


def _code_truth(slug: str) -> dict[str, Any]:
    entry = next(s for s in scenarios() if s["slug"] == slug)
    loaded: Any = yaml.safe_load(
        (PROJECT_ROOT / str(entry["path"]) / "expected" / CODE_TRUTH).read_text()
    )
    assert isinstance(loaded, dict)
    return loaded


def test_at_least_one_scenario_carries_a_code_layer() -> None:
    assert coded_scenario_ids(), "DEC-156 shipped two coded scenarios; none is registered"


@pytest.mark.parametrize("slug", coded_scenario_ids())
def test_a_code_layer_is_a_sibling_of_input_never_inside_it(slug: str) -> None:
    """The harness supplies `input/` and nothing else. Code beside it is unreadable to Trace by
    construction; code under it would be ingested as material under review."""
    entry = next(s for s in scenarios() if s["slug"] == slug)
    path = PROJECT_ROOT / str(entry["path"])
    code = (path / "code").resolve()
    source = (path / "input").resolve()
    assert source not in code.parents
    assert code not in source.parents


@pytest.mark.parametrize("slug", coded_scenario_ids())
def test_a_code_layer_carries_its_truth_under_expected(slug: str) -> None:
    """The code-level truth and the author's intent note live under `expected/`, where the
    existing rule already withholds them from Trace, and outside `code/`, which a code reviewer
    receives whole."""
    entry = next(s for s in scenarios() if s["slug"] == slug)
    expected = PROJECT_ROOT / str(entry["path"]) / "expected"
    assert (expected / CODE_TRUTH).is_file(), f"{slug}/code exists without expected/{CODE_TRUTH}"
    assert (expected / CODE_NOTES).is_file(), f"{slug}/code exists without expected/{CODE_NOTES}"


@pytest.mark.parametrize("slug", scenario_ids())
def test_code_truth_never_appears_without_code(slug: str) -> None:
    entry = next(s for s in scenarios() if s["slug"] == slug)
    path = PROJECT_ROOT / str(entry["path"])
    if not (path / "code").is_dir():
        assert not (path / "expected" / CODE_TRUTH).exists(), (
            f"{slug} carries a code-level truth file and no code/ for it to describe"
        )


@pytest.mark.parametrize("slug", coded_scenario_ids())
def test_code_truth_mirrors_realvuln_fields_exactly(slug: str) -> None:
    truth = _code_truth(slug)
    assert set(truth) == REALVULN_TOP_LEVEL, (
        f"{slug}/{CODE_TRUTH} top-level keys diverge from RealVuln's: "
        f"{sorted(set(truth) ^ REALVULN_TOP_LEVEL)}"
    )
    findings = truth["findings"]
    assert isinstance(findings, list) and findings
    for finding in findings:
        keys = set(finding)
        missing = REALVULN_FINDING_REQUIRED - keys
        extra = keys - REALVULN_FINDING_REQUIRED - REALVULN_FINDING_OPTIONAL
        assert not missing, f"{slug} {finding.get('id')} lacks {sorted(missing)}"
        assert not extra, f"{slug} {finding.get('id')} carries fields RealVuln has none of: {extra}"
        assert isinstance(finding["is_vulnerable"], bool)
        assert finding["primary_cwe"] in finding["acceptable_cwes"]
        assert set(finding["location"]) <= {"start_line", "end_line", "function"}
        assert set(finding["evidence"]) == {"source", "cve_id", "description"}
        if finding.get("scoring") == "non_scoring":
            assert finding.get("non_scoring_reason"), (
                f"{finding['id']} is non-scoring with no reason"
            )


@pytest.mark.parametrize("slug", coded_scenario_ids())
def test_code_truth_carries_a_negative_set(slug: str) -> None:
    """At least one vulnerability and at least three false-positive traps, so the code layer can
    be scored on precision and not only on recall (DEC-154's reasoning, applied to code)."""
    findings = _code_truth(slug)["findings"]
    scored = [f for f in findings if f.get("scoring", "scored") == "scored"]
    assert any(f["is_vulnerable"] for f in scored), f"{slug} authors no code-level vulnerability"
    traps = [f for f in scored if not f["is_vulnerable"]]
    assert len(traps) >= 3, f"{slug} authors {len(traps)} trap(s); at least three are required"


@pytest.mark.parametrize("slug", coded_scenario_ids())
def test_every_code_truth_location_resolves(slug: str) -> None:
    """A truth entry names a file under `code/` and a function defined in it. A location that
    does not resolve cannot be matched, and it is also the class of error a reviewer is scored
    against (DEC-151's resolvability rule, applied to the truth itself)."""
    entry = next(s for s in scenarios() if s["slug"] == slug)
    code = PROJECT_ROOT / str(entry["path"]) / "code"
    for finding in _code_truth(slug)["findings"]:
        target = code / str(finding["file"])
        assert target.is_file(), f"{slug} {finding['id']} names {finding['file']}, which is absent"
        text = target.read_text()
        function = finding["location"].get("function")
        if function:
            *owners, name = str(function).split(".")
            assert f"def {name}(" in text, (
                f"{slug} {finding['id']}: no def {name} in {finding['file']}"
            )
            for owner in owners:
                assert f"class {owner}" in text, f"{slug} {finding['id']}: no class {owner}"


@pytest.mark.parametrize("slug", coded_scenario_ids())
def test_the_code_layer_carries_no_answer_key(slug: str) -> None:
    """A code reviewer receives `code/` whole. Nothing in it may name a truth-set key, the truth
    file, or the intent note; the code states what the system does and nothing about what a
    correct review of it concludes."""
    entry = next(s for s in scenarios() if s["slug"] == slug)
    code = PROJECT_ROOT / str(entry["path"]) / "code"
    offenders = [
        f"{path.relative_to(PROJECT_ROOT)}: {token}"
        for path in _code_files(code)
        if path.suffix in {".py", ".md", ".toml", ".yaml", ".txt"}
        for token in ANSWER_KEY_TOKENS
        if token in path.read_text(errors="replace")
    ]
    assert not offenders, offenders


@pytest.mark.parametrize("slug", coded_scenario_ids())
def test_the_code_layer_is_a_standalone_project(slug: str) -> None:
    """A reviewer runs the target from its own directory with its own dependencies; the code
    layer never joins Trace's dependency set."""
    entry = next(s for s in scenarios() if s["slug"] == slug)
    code = PROJECT_ROOT / str(entry["path"]) / "code"
    assert (code / "pyproject.toml").is_file()
    assert (code / "uv.lock").is_file(), f"{slug}/code pins no lock; the target is not reproducible"
    assert (code / "README.md").is_file()


def test_the_manifest_digests_the_code_group() -> None:
    """DEC-146's manifest covers the code layer as its own group, so the digest a reviewer's
    snapshot pins is the digest the manifest records."""
    loaded: Any = yaml.safe_load((BENCHMARKS / "manifest.yaml").read_text())
    by_slug = {entry["slug"]: entry for entry in loaded["scenarios"]}
    for slug in scenario_ids():
        assert "code" in by_slug[slug]["files"], f"{slug}'s manifest entry has no code group"
    for slug in coded_scenario_ids():
        assert by_slug[slug]["files"]["code"]["count"] > 0, f"{slug}'s code group is empty"
