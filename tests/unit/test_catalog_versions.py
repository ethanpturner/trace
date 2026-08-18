"""Catalog 0.2 and the DEC-057 governance machinery (issue #348).

The acceptance criteria are the spine: `load_catalog("0.2")` passes both-direction manifest
validation (the loader itself enforces that; loading is the assertion), every 0.1 requirement's
fate in 0.2 is recorded per DEC-057's vocabulary and held referentially complete in both
directions, and every new 0.2 requirement is phrased in the documentation register so silence
resolves to `unverified`, never `unmet` (DEC-009 — the register caveat DEC-058 calls the
decision's load-bearing half).
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from trace_ai.domain.requirement import CatalogStatus
from trace_ai.services.requirements.loader import (
    CATALOG_ROOT,
    VERSIONS_REGISTRY,
    load_catalog,
    registry_status,
)

FATE_MAP = CATALOG_ROOT / "mappings" / "0.1-to-0.2.yaml"

# DEC-057's minor-boundary vocabulary. The major-boundary fates (moved_to, merged_to, split_to,
# deleted) are not valid at 0.1 -> 0.2 because a minor version never renumbers.
MINOR_FATES = frozenset({"unchanged", "revised", "retired"})


def fates() -> dict[str, dict[str, Any]]:
    document = yaml.safe_load(FATE_MAP.read_text(encoding="utf-8"))
    return {
        identifier: (entry if isinstance(entry, dict) else {"fate": entry})
        for identifier, entry in document["fates"].items()
    }


def test_both_versions_load_and_agree_with_their_manifests() -> None:
    """Issue #348's first acceptance criterion: loading is the both-direction validation."""
    old = load_catalog("0.1")
    new = load_catalog("0.2")
    assert len(old) == 23
    assert len(new) == 37
    assert new.catalog.version == "0.2"


def test_the_third_version_loads_and_carries_everything_forward() -> None:
    """Catalog 0.3 (#537, DEC-111): 0.2 plus the delegated-authentication pack, fates complete
    in both directions, and the new requirements phrased in the documentation register."""
    third = load_catalog("0.3")
    assert len(third) == 41
    assert third.catalog.version == "0.3"

    fate_map = yaml.safe_load(
        (CATALOG_ROOT / "mappings" / "0.2-to-0.3.yaml").read_text(encoding="utf-8")
    )
    mapped = set(fate_map["fates"])
    assert mapped == set(load_catalog("0.2").by_id())
    assert all(
        (entry if isinstance(entry, dict) else {"fate": entry})["fate"] in MINOR_FATES
        for entry in fate_map["fates"].values()
    )

    register = re.compile(r"documentation must (describe|state|identify)")
    new_ids = set(third.by_id()) - set(load_catalog("0.2").by_id())
    assert {identifier.split("-")[1] for identifier in new_ids} == {"OIDC"}
    for requirement in third.requirements:
        if requirement.id not in new_ids:
            continue
        statement = " ".join(str(requirement.statement).split())
        assert register.search(statement), requirement.id
        assert "verify that" not in statement.lower(), requirement.id


def test_every_old_identifier_has_a_fate_and_every_fate_names_an_old_identifier() -> None:
    """Issue #348's second acceptance criterion: referential completeness, both directions."""
    old_ids = set(load_catalog("0.1").by_id())
    mapped = set(fates())

    assert mapped == old_ids, (
        f"the fate map and 0.1 disagree. Unmapped: {sorted(old_ids - mapped) or 'none'}; "
        f"mapped but not in 0.1: {sorted(mapped - old_ids) or 'none'}"
    )


def test_every_fate_is_minor_boundary_vocabulary_and_targets_resolve() -> None:
    new_ids = set(load_catalog("0.2").by_id())
    for identifier, entry in fates().items():
        assert entry["fate"] in MINOR_FATES, (
            f"{identifier}: fate {entry['fate']!r} is not minor-boundary vocabulary (DEC-057); "
            f"a minor version never renumbers, so the major fates do not apply"
        )
        if entry["fate"] in {"unchanged", "revised"}:
            assert identifier in new_ids, (
                f"{identifier} is {entry['fate']} but absent from 0.2; a carried requirement "
                f"ships under its identifier"
            )
        if entry["fate"] == "revised":
            assert str(entry.get("reason", "")).strip(), (
                f"{identifier} is revised with no stated reason; a fate map exists to be read"
            )


def test_a_retired_requirement_would_stay_in_its_file() -> None:
    """DEC-057: retirement is a status, never a deletion, within a major lineage.

    0.2 retires nothing, so the assertion is the vocabulary's presence: any 0.1 identifier
    whose fate is `retired` must still resolve in 0.2 with `status: retired`.
    """
    new = load_catalog("0.2").by_id()
    for identifier, entry in fates().items():
        if entry["fate"] == "retired":
            assert identifier in new
            assert new[identifier].status is CatalogStatus.RETIRED


def test_the_registry_governs_lifecycle_without_touching_frozen_content() -> None:
    """DEC-057: each frozen manifest says draft; the registry says active; the registry wins."""
    assert VERSIONS_REGISTRY.is_file()
    assert registry_status("0.1") == "active"
    assert registry_status("0.2") == "active"
    assert load_catalog("0.1").catalog.status is CatalogStatus.ACTIVE
    assert load_catalog("0.2").catalog.status is CatalogStatus.ACTIVE


def test_registry_entries_and_version_directories_agree_in_both_directions() -> None:
    """The DEC-057 tradeoff, answered the way catalog.yaml's was: a both-directions test."""
    document = yaml.safe_load(VERSIONS_REGISTRY.read_text(encoding="utf-8"))
    registered = set(document["versions"])
    directories = {
        path.name for path in CATALOG_ROOT.iterdir() if path.is_dir() and path.name[0].isdigit()
    }
    assert registered == directories


def test_new_requirements_resolve_silence_to_unverified_never_unmet() -> None:
    """Issue #348's third acceptance criterion, checked on phrasing.

    Two rules a phrasing check can hold: every new statement is about what documentation must
    describe or state — the documentation register, not AISVS's runtime "Verify that" — and no
    statement or rationale reads absence as proof (`proves absent`, `must be treated as
    missing`). The judgment half stays a review question, as the catalog README says.
    """
    old_ids = set(load_catalog("0.1").by_id())
    new = [r for r in load_catalog("0.2").requirements if r.id not in old_ids]
    assert {r.id.split("-")[1] for r in new} == {"AGENT", "CODEGEN", "OPS", "RAG"}

    register = re.compile(r"documentation must (describe|state|identify)")
    for requirement in new:
        statement = " ".join(str(requirement.statement).split())
        assert register.search(statement), (
            f"{requirement.id} is not phrased in the documentation register; silence must "
            f"resolve to unverified (DEC-009, DEC-058's binding caveat)"
        )
        assert "verify that" not in statement.lower(), (
            f"{requirement.id} imports AISVS's runtime register (DEC-058 forbids it unrewritten)"
        )


def test_the_frozen_version_is_untouched() -> None:
    """0.1's hash is the one recorded runs verify; authoring 0.2 must not have moved it."""
    assert (
        load_catalog("0.1").catalog.content_hash
        == "sha256:82feaf088d0d8a347dddca9fb4883931432c9411fc2cc6d6ec5f10c511cdf102"
    )
