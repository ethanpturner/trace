"""Tests for the requirements catalog in `requirements/`.

The catalog is hand-maintained YAML that no code reads yet, which is exactly the
kind of data that drifts silently. These tests enforce what DEC-010 leaves to a
"separate step": that requirement files conform to the Requirement object in
`docs/architecture/data-model.md` section 17, that identifiers follow the
catalog's convention, that the manifest and the files agree, and that framework
citations carry a version.

They check structure and convention, not judgment. Whether a requirement is
*correct* is a review question; whether it is *well-formed* is this file's.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT

CATALOG_DIR = PROJECT_ROOT / "requirements"
CATALOG_FILE = CATALOG_DIR / "catalog.yaml"

# docs/architecture/data-model.md section 17.
REQUIRED_FIELDS = frozenset(
    {"id", "catalog_version", "title", "statement", "rationale", "category", "status"}
)
OPTIONAL_FIELDS = frozenset(
    {
        "applicable_technologies",
        "applicable_conditions",
        "non_applicable_conditions",
        "acceptable_implementations",
        "evidence_expectations",
        "common_false_positives",
        "default_severity",
        "source_frameworks",
        "supersedes_id",
    }
)
KNOWN_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS

# data-model.md sections 4.5 and 17.
SEVERITIES = frozenset({"informational", "low", "medium", "high", "critical", "unassigned"})
STATUSES = frozenset({"draft", "active", "retired"})

# Frameworks cited in catalog version 0.1. A new framework is a deliberate
# provenance decision (requirements/README.md), so it is added here too.
FRAMEWORKS = (
    "OWASP ASVS 5.0.0",
    "NIST SP 800-53 5.2.0",
    "OWASP Top 10 for LLM Applications 2025",
)


def _manifest() -> dict[str, Any]:
    loaded = yaml.safe_load(CATALOG_FILE.read_text(encoding="utf-8"))
    catalog: dict[str, Any] = loaded["catalog"]
    return catalog


def _version() -> str:
    version: str = _manifest()["version"]
    return version


def _requirements() -> list[tuple[str, dict[str, Any]]]:
    """Every requirement in the current catalog version, with its file name."""
    found: list[tuple[str, dict[str, Any]]] = []
    for path in sorted((CATALOG_DIR / _version()).glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for requirement in document["requirements"]:
            found.append((path.name, requirement))
    return found


ALL_REQUIREMENTS = _requirements()


def test_catalog_version_directory_exists() -> None:
    assert (CATALOG_DIR / _version()).is_dir()


def test_catalog_contains_requirements() -> None:
    # Guards the parametrized tests below: an empty glob would make them vacuous.
    assert ALL_REQUIREMENTS


def test_every_category_file_has_a_requirements_list() -> None:
    for path in sorted((CATALOG_DIR / _version()).glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(document, dict), f"{path.name} is not a mapping"
        assert isinstance(document.get("requirements"), list), (
            f"{path.name} has no top-level 'requirements' list"
        )


def test_manifest_and_files_agree() -> None:
    declared = _manifest()["requirement_ids"]
    found = [requirement["id"] for _, requirement in ALL_REQUIREMENTS]

    assert sorted(declared) == sorted(found), (
        "catalog.yaml and the requirement files disagree; "
        f"only in manifest: {sorted(set(declared) - set(found))}, "
        f"only in files: {sorted(set(found) - set(declared))}"
    )


def test_requirement_ids_are_unique() -> None:
    found = [requirement["id"] for _, requirement in ALL_REQUIREMENTS]

    duplicates = sorted({rid for rid in found if found.count(rid) > 1})

    assert not duplicates, f"duplicate requirement ids: {duplicates}"


@pytest.mark.parametrize(
    ("file_name", "requirement"),
    [(name, requirement) for name, requirement in ALL_REQUIREMENTS],
    ids=[requirement["id"] for _, requirement in ALL_REQUIREMENTS],
)
class TestRequirement:
    """Per-requirement conformance, so a failure names the offending requirement."""

    def test_has_required_fields(self, file_name: str, requirement: dict[str, Any]) -> None:
        missing = sorted(REQUIRED_FIELDS - set(requirement))

        assert not missing, f"{file_name}: missing required fields {missing}"

    def test_has_no_unknown_fields(self, file_name: str, requirement: dict[str, Any]) -> None:
        unknown = sorted(set(requirement) - KNOWN_FIELDS)

        assert not unknown, (
            f"{file_name}: fields not in data-model.md section 17: {unknown}. "
            "Adding a field to the Requirement object is a design change."
        )

    def test_id_follows_the_naming_convention(
        self, file_name: str, requirement: dict[str, Any]
    ) -> None:
        rid = requirement["id"]

        assert rid.startswith("req-"), f"{file_name}: {rid} does not start with 'req-'"
        assert rid == rid.strip(), f"{file_name}: {rid} has surrounding whitespace"

    def test_catalog_version_matches_the_manifest(
        self, file_name: str, requirement: dict[str, Any]
    ) -> None:
        assert requirement["catalog_version"] == _version(), (
            f"{file_name}: {requirement['id']} declares catalog_version "
            f"{requirement['catalog_version']!r}, manifest declares {_version()!r}"
        )

    def test_status_is_a_known_value(self, file_name: str, requirement: dict[str, Any]) -> None:
        assert requirement["status"] in STATUSES, (
            f"{file_name}: {requirement['id']} has status {requirement['status']!r}"
        )

    def test_severity_is_a_known_value(self, file_name: str, requirement: dict[str, Any]) -> None:
        severity = requirement.get("default_severity")

        assert severity is None or severity in SEVERITIES, (
            f"{file_name}: {requirement['id']} has default_severity {severity!r}"
        )

    def test_category_is_a_non_empty_list(
        self, file_name: str, requirement: dict[str, Any]
    ) -> None:
        category = requirement["category"]

        assert isinstance(category, list) and category, (
            f"{file_name}: {requirement['id']} has an empty or non-list category"
        )

    def test_citations_name_a_known_framework_and_version(
        self, file_name: str, requirement: dict[str, Any]
    ) -> None:
        """`source_frameworks` entries are '<framework> <version>: <control id>'.

        The version lives inside the string because section 17 types the field as
        a list of strings, and control identifiers are not stable across releases
        (requirements/README.md). A citation without one goes stale invisibly.
        """
        for citation in requirement.get("source_frameworks", []):
            framework, separator, control = citation.partition(": ")

            assert separator, (
                f"{file_name}: {requirement['id']} citation {citation!r} "
                "is not '<framework> <version>: <control id>'"
            )
            assert framework in FRAMEWORKS, (
                f"{file_name}: {requirement['id']} cites unknown framework {framework!r}. "
                "Citing a new framework is a provenance decision; add it to FRAMEWORKS."
            )
            assert control.strip(), (
                f"{file_name}: {requirement['id']} citation {citation!r} has no control id"
            )
