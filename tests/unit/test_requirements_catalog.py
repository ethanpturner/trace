"""Tests for the requirements catalog in `requirements/` and the loader that reads it.

The catalog was hand-maintained YAML that no code read, and these tests were the only thing
holding it to `docs/architecture/data-model.md` section 17. `services/requirements/loader.py`
now reads it, so most of what was asserted here by convention is enforced at load for every
caller, and this file tests through the loader rather than around it.

Two halves, deliberately kept apart:

- **Loader behaviour.** Each refusal gets a test that constructs the broken catalog it refuses,
  in a copy of the real tree under `tmp_path`. A validator with no test for the invalid case is
  a validator nobody has run.
- **Catalog authoring conventions.** Identifier prefix, and `source_frameworks` citation format
  against the list of frameworks the catalog has adopted. These stay in the test because they
  are conventions rather than schema: adopting a framework is a provenance decision recorded in
  `requirements/README.md`, and putting the adopted list in product code would make citing a new
  one a code change.

Neither half checks judgment. Whether a requirement is *correct* is a review question; whether
it is *well-formed* is this file's. ASVS citation identifiers are now resolved against a cached
v5.0.0 export (issue #221, survey item A1); NIST and OWASP Top 10 for LLM citations remain
unresolved because those frameworks are not vendored, and a plausible but wrong identifier
there still passes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.enums import Severity
from trace_ai.domain.requirement import CatalogStatus, Requirement
from trace_ai.services.requirements.loader import (
    CATALOG_ROOT,
    CatalogHashError,
    CatalogManifestError,
    CatalogNotFoundError,
    CatalogSchemaError,
    CatalogVersionError,
    canonical_bytes,
    compute_hash,
    current_version,
    load_catalog,
)

if TYPE_CHECKING:
    from trace_ai.services.requirements.loader import LoadedCatalog

VERSION = current_version()
CATALOG = load_catalog(VERSION)
ALL_REQUIREMENTS = CATALOG.requirements

# Frameworks cited in catalog version 0.1. A new framework is a deliberate provenance decision
# (requirements/README.md), so it is added here too.
FRAMEWORKS = (
    "OWASP ASVS 5.0.0",
    "NIST SP 800-53 5.2.0",
    "OWASP Top 10 for LLM Applications 2025",
)


# --------------------------------------------------------------------------------------------
# A writable copy of the real tree, so a refusal is tested against a real catalog made wrong
# --------------------------------------------------------------------------------------------


@pytest.fixture
def catalog_tree(tmp_path: Path) -> Path:
    """A copy of `requirements/` that a test may break."""
    root = tmp_path / "requirements"
    shutil.copytree(CATALOG_ROOT, root)
    return root


def read_manifest(root: Path) -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load((root / "catalog.yaml").read_text(encoding="utf-8"))
    catalog: dict[str, Any] = document["catalog"]
    return catalog


def write_manifest(root: Path, catalog: dict[str, Any]) -> None:
    """Rewrite the manifest. Comments are lost, which is what the hash exists not to notice."""
    (root / "catalog.yaml").write_text(yaml.safe_dump({"catalog": catalog}), encoding="utf-8")


def a_requirement_file(root: Path) -> Path:
    return root / VERSION / "webhook-validation.yaml"


def edit_first_requirement(path: Path, changes: dict[str, Any]) -> None:
    """Apply `changes` to the first requirement in `path`; a `None` value removes the key."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    requirement = document["requirements"][0]
    for key, value in changes.items():
        if value is None:
            requirement.pop(key, None)
        else:
            requirement[key] = value
    path.write_text(yaml.safe_dump(document), encoding="utf-8")


# --------------------------------------------------------------------------------------------
# The catalog loads
# --------------------------------------------------------------------------------------------


def test_the_whole_catalog_loads() -> None:
    assert len(CATALOG) == 23
    assert CATALOG.version == VERSION
    assert all(isinstance(requirement, Requirement) for requirement in ALL_REQUIREMENTS)


def test_the_catalog_is_the_manifest_and_the_requirements_together() -> None:
    assert CATALOG.catalog.id == "core"
    assert CATALOG.catalog.status is CatalogStatus.DRAFT
    assert sorted(CATALOG.catalog.requirement_ids) == sorted(CATALOG.by_id())


def test_the_catalog_name_is_a_name_and_not_an_identifier() -> None:
    """DEC-034. `cat-core` was the mistake; `cat` is not a prefix in section 2.1."""
    assert "-" not in CATALOG.catalog.id


def test_the_version_directory_exists() -> None:
    assert (CATALOG_ROOT / VERSION).is_dir()


def test_every_requirement_is_reachable_by_identifier() -> None:
    by_id = CATALOG.by_id()

    assert len(by_id) == len(ALL_REQUIREMENTS), "two requirements share an identifier"


# --------------------------------------------------------------------------------------------
# Version pinning: a version added to the tree cannot change an in-flight assessment
# --------------------------------------------------------------------------------------------


def test_loading_requires_a_version_the_tree_holds(catalog_tree: Path) -> None:
    with pytest.raises(CatalogVersionError) as raised:
        load_catalog("0.2", root=catalog_tree)

    assert "0.2" in str(raised.value)
    assert VERSION in str(raised.value)


def test_a_version_directory_that_is_missing_is_named(catalog_tree: Path) -> None:
    shutil.rmtree(catalog_tree / VERSION)

    with pytest.raises(CatalogNotFoundError, match=VERSION):
        load_catalog(VERSION, root=catalog_tree)


def test_an_absent_manifest_is_not_a_silent_empty_catalog(catalog_tree: Path) -> None:
    (catalog_tree / "catalog.yaml").unlink()

    with pytest.raises(CatalogNotFoundError):
        load_catalog(VERSION, root=catalog_tree)


# --------------------------------------------------------------------------------------------
# Schema conformance, enforced at load rather than asserted per field
# --------------------------------------------------------------------------------------------


def test_a_field_outside_section_seventeen_fails_and_names_it(catalog_tree: Path) -> None:
    edit_first_requirement(a_requirement_file(catalog_tree), {"severity_if_unmet": "high"})
    with pytest.raises(CatalogSchemaError) as raised:
        load_catalog(VERSION, root=catalog_tree)

    message = str(raised.value)
    assert "severity_if_unmet" in message
    assert "data-model.md section 17" in message
    assert "req-WEBHOOK-001" in message


def test_a_missing_required_field_fails(catalog_tree: Path) -> None:
    edit_first_requirement(a_requirement_file(catalog_tree), {"rationale": None})
    with pytest.raises(CatalogSchemaError, match="rationale"):
        load_catalog(VERSION, root=catalog_tree)


def test_default_severity_takes_only_the_section_four_five_vocabulary(catalog_tree: Path) -> None:
    edit_first_requirement(a_requirement_file(catalog_tree), {"default_severity": "severe"})
    with pytest.raises(CatalogSchemaError, match="default_severity"):
        load_catalog(VERSION, root=catalog_tree)


def test_status_takes_only_draft_active_retired(catalog_tree: Path) -> None:
    edit_first_requirement(a_requirement_file(catalog_tree), {"status": "published"})
    with pytest.raises(CatalogSchemaError, match="status"):
        load_catalog(VERSION, root=catalog_tree)


def test_category_must_be_a_non_empty_list(catalog_tree: Path) -> None:
    edit_first_requirement(a_requirement_file(catalog_tree), {"category": []})
    with pytest.raises(CatalogSchemaError, match="category"):
        load_catalog(VERSION, root=catalog_tree)


def test_a_category_file_without_a_requirements_list_fails(catalog_tree: Path) -> None:
    a_requirement_file(catalog_tree).write_text("webhooks: []\n", encoding="utf-8")

    with pytest.raises(CatalogSchemaError, match="requirements"):
        load_catalog(VERSION, root=catalog_tree)


# --------------------------------------------------------------------------------------------
# Identifiers
# --------------------------------------------------------------------------------------------


def test_a_generated_identifier_is_refused(catalog_tree: Path) -> None:
    """DEC-018 gives catalog requirements the authored form.

    `req-001` is a perfectly valid *generated* identifier, which is the problem: it is a number
    from a counter rather than one a person assigned, and benchmark expected-output files
    reference requirement identifiers by hand.
    """
    path = a_requirement_file(catalog_tree)
    edit_first_requirement(path, {"id": "req-001"})
    catalog = read_manifest(catalog_tree)
    catalog["requirement_ids"] = [
        "req-001" if rid == "req-WEBHOOK-001" else rid for rid in catalog["requirement_ids"]
    ]
    write_manifest(catalog_tree, catalog)

    with pytest.raises(CatalogManifestError) as raised:
        load_catalog(VERSION, root=catalog_tree)

    assert "req-001" in str(raised.value)
    assert "authored" in str(raised.value)


def test_an_identifier_without_the_req_prefix_is_refused(catalog_tree: Path) -> None:
    edit_first_requirement(a_requirement_file(catalog_tree), {"id": "thr-WEBHOOK-001"})
    with pytest.raises(CatalogSchemaError, match="Requirement identifier"):
        load_catalog(VERSION, root=catalog_tree)


# --------------------------------------------------------------------------------------------
# Manifest agreement, in both directions
# --------------------------------------------------------------------------------------------


def test_an_identifier_only_in_the_manifest_is_an_error_naming_it(catalog_tree: Path) -> None:
    catalog = read_manifest(catalog_tree)
    catalog["requirement_ids"] = [*catalog["requirement_ids"], "req-GHOST-001"]
    write_manifest(catalog_tree, catalog)

    with pytest.raises(CatalogManifestError) as raised:
        load_catalog(VERSION, root=catalog_tree)

    assert "req-GHOST-001" in str(raised.value)
    assert "Only in the manifest" in str(raised.value)


def test_an_identifier_only_in_the_files_is_an_error_naming_it(catalog_tree: Path) -> None:
    catalog = read_manifest(catalog_tree)
    catalog["requirement_ids"] = [
        rid for rid in catalog["requirement_ids"] if rid != "req-WEBHOOK-002"
    ]
    write_manifest(catalog_tree, catalog)

    with pytest.raises(CatalogManifestError) as raised:
        load_catalog(VERSION, root=catalog_tree)

    assert "req-WEBHOOK-002" in str(raised.value)
    assert "only in the files" in str(raised.value)


def test_a_duplicate_identifier_is_an_error(catalog_tree: Path) -> None:
    path = catalog_tree / VERSION / "logging.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    duplicate = dict(document["requirements"][0])
    duplicate["id"] = "req-WEBHOOK-001"
    document["requirements"].append(duplicate)
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(CatalogManifestError, match="duplicate"):
        load_catalog(VERSION, root=catalog_tree)


def test_a_requirement_declaring_another_catalog_version_is_an_error(catalog_tree: Path) -> None:
    edit_first_requirement(a_requirement_file(catalog_tree), {"catalog_version": "0.9"})
    with pytest.raises(CatalogManifestError) as raised:
        load_catalog(VERSION, root=catalog_tree)

    assert "req-WEBHOOK-001" in str(raised.value)


# --------------------------------------------------------------------------------------------
# content_hash (DEC-019)
# --------------------------------------------------------------------------------------------


def test_the_declared_hash_matches_the_catalog() -> None:
    assert CATALOG.catalog.content_hash == compute_hash(VERSION)


def test_the_hash_is_stable_across_runs() -> None:
    assert compute_hash(VERSION) == compute_hash(VERSION)


def test_the_hash_changes_when_a_requirement_changes(catalog_tree: Path) -> None:
    before = compute_hash(VERSION, catalog_tree)
    edit_first_requirement(a_requirement_file(catalog_tree), {"title": "Something else"})

    assert compute_hash(VERSION, catalog_tree) != before


def test_the_hash_ignores_comments_and_key_order(catalog_tree: Path) -> None:
    """It covers the parsed catalog, not the file (DEC-019).

    `write_manifest` round-trips through `yaml.safe_dump`, which discards every comment in the
    manifest and re-orders its keys alphabetically. That is the largest formatting change the
    file can undergo, and the hash does not move.
    """
    before = compute_hash(VERSION, catalog_tree)
    write_manifest(catalog_tree, read_manifest(catalog_tree))

    assert compute_hash(VERSION, catalog_tree) == before


def test_the_hash_ignores_the_order_of_requirement_ids(catalog_tree: Path) -> None:
    before = compute_hash(VERSION, catalog_tree)
    catalog = read_manifest(catalog_tree)
    catalog["requirement_ids"] = list(reversed(catalog["requirement_ids"]))
    write_manifest(catalog_tree, catalog)

    assert compute_hash(VERSION, catalog_tree) == before


def test_a_stale_hash_stops_the_load_and_says_how_to_repair_it(catalog_tree: Path) -> None:
    edit_first_requirement(a_requirement_file(catalog_tree), {"title": "Something else"})

    with pytest.raises(CatalogHashError) as raised:
        load_catalog(VERSION, root=catalog_tree)

    assert "scripts/catalog_hash.py" in str(raised.value)


def test_an_absent_hash_is_an_error_carrying_the_value_to_record(catalog_tree: Path) -> None:
    catalog = read_manifest(catalog_tree)
    expected = catalog.pop("content_hash")
    write_manifest(catalog_tree, catalog)

    with pytest.raises(CatalogHashError) as raised:
        load_catalog(VERSION, root=catalog_tree)

    assert expected in str(raised.value)


def test_the_hash_excludes_itself_from_its_own_input() -> None:
    """Otherwise it could not be computed: the manifest carries the value being hashed."""
    payload = canonical_bytes(CATALOG.catalog, CATALOG.requirements)

    assert CATALOG.catalog.content_hash.encode("utf-8") not in payload
    assert b"content_hash" not in payload


def test_the_hash_covers_the_rest_of_the_manifest(catalog_tree: Path) -> None:
    before = compute_hash(VERSION, catalog_tree)
    catalog = read_manifest(catalog_tree)
    catalog["name"] = "Something Else"
    write_manifest(catalog_tree, catalog)

    assert compute_hash(VERSION, catalog_tree) != before


# --------------------------------------------------------------------------------------------
# Per-requirement authoring conventions
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "requirement",
    ALL_REQUIREMENTS,
    ids=[requirement.id for requirement in ALL_REQUIREMENTS],
)
class TestRequirement:
    """Per-requirement checks, so a failure names the offending requirement."""

    def test_id_follows_the_naming_convention(self, requirement: Requirement) -> None:
        assert requirement.id.startswith("req-")
        assert requirement.id == requirement.id.strip()

    def test_catalog_version_matches_the_manifest(self, requirement: Requirement) -> None:
        assert requirement.catalog_version == VERSION

    def test_status_is_a_known_value(self, requirement: Requirement) -> None:
        assert requirement.status in set(CatalogStatus)

    def test_severity_is_a_known_value(self, requirement: Requirement) -> None:
        assert requirement.default_severity is None or requirement.default_severity in set(Severity)

    def test_category_is_a_non_empty_list(self, requirement: Requirement) -> None:
        assert requirement.category

    def test_citations_name_a_known_framework_and_version(self, requirement: Requirement) -> None:
        """`source_frameworks` entries are '<framework> <version>: <control id>'.

        The version lives inside the string because section 17 types the field as a list of
        strings, and control identifiers are not stable across releases
        (`requirements/README.md`). A citation without one goes stale invisibly.

        This is an authoring convention rather than a schema rule, so it is checked here rather
        than in the loader: the adopted-framework list below is the thing being enforced, and
        adopting a framework is a provenance decision, not a code change.
        """
        for citation in requirement.source_frameworks:
            framework, separator, control = citation.partition(": ")

            assert separator, (
                f"{requirement.id} citation {citation!r} "
                "is not '<framework> <version>: <control id>'"
            )
            assert framework in FRAMEWORKS, (
                f"{requirement.id} cites unknown framework {framework!r}. "
                "Citing a new framework is a provenance decision; add it to FRAMEWORKS."
            )
            assert control.strip(), f"{requirement.id} citation {citation!r} has no control id"


# --------------------------------------------------------------------------------------------
# ASVS citation resolution (issue #221, survey item A1)
# --------------------------------------------------------------------------------------------
#
# ASVS publishes a stable flat JSON export at each release tag, keyed by `req_id` like `V6.1.3`.
# The catalog cites the same identifier without the `V` prefix (e.g. `6.1.3`), so resolution is a
# lookup after prefixing. The export is cached under `requirements/_external/asvs/` so CI needs no
# network. `scripts/asvs_resolver.py` is the CLI for the same check; it is run here as a subprocess
# so the test exercises the script's entry point and not just its logic.

ASVS_EXPORT = CATALOG_ROOT / "_external" / "asvs" / "v5.0.0.flat.json"
ASVS_FRAMEWORK = "OWASP ASVS 5.0.0"
ASVS_ROW_COUNT = 345  # v5.0.0; the survey verified the row count by hand.


def _asvs_req_ids() -> frozenset[str]:
    document = json.loads(ASVS_EXPORT.read_text(encoding="utf-8"))
    return frozenset(str(row["req_id"]) for row in document["requirements"])


def _asvs_citations() -> list[tuple[str, str]]:
    """Every (requirement id, citation) pair that names ASVS, drawn from the loaded catalog."""
    pairs: list[tuple[str, str]] = []
    for requirement in ALL_REQUIREMENTS:
        for citation in requirement.source_frameworks:
            framework, separator, _control = citation.partition(": ")
            if separator and framework == ASVS_FRAMEWORK:
                pairs.append((requirement.id, citation))
    return pairs


def test_the_cached_asvs_export_is_the_expected_release() -> None:
    """A guard before the resolution check. A truncated or swapped export fails here, not below."""
    assert ASVS_EXPORT.is_file(), f"cached ASVS export missing at {ASVS_EXPORT}"
    ids = _asvs_req_ids()
    assert len(ids) == ASVS_ROW_COUNT, (
        f"ASVS v5.0.0 export has {len(ids)} rows, expected {ASVS_ROW_COUNT}. The cache at "
        f"{ASVS_EXPORT} may have been replaced with a different release."
    )
    # First and last `req_id` in the v5.0.0 export, checked by membership rather than min/max
    # because string ordering puts "V9.2.4" above "V17.3.2".
    assert "V1.1.1" in ids
    assert "V17.3.2" in ids


@pytest.mark.parametrize(
    "requirement_id, citation",
    _asvs_citations(),
    ids=[f"{rid}::{citation}" for rid, citation in _asvs_citations()],
)
def test_every_asvs_citation_resolves_against_the_pinned_export(
    requirement_id: str, citation: str
) -> None:
    """A typo'd or stale ASVS identifier is currently silent; this resolves it by lookup."""
    _framework, _separator, control = citation.partition(": ")
    assert f"V{control}" in _asvs_req_ids(), (
        f"{requirement_id} cites {citation!r}, and `V{control}` is not a `req_id` in the pinned "
        f"ASVS v5.0.0 export at {ASVS_EXPORT}. The identifier is typo'd or stale."
    )


def test_the_asvs_resolver_script_reports_no_unresolved_citations() -> None:
    """`scripts/asvs_resolver.py --check` exits zero when every ASVS citation resolves."""
    result = subprocess.run(
        [sys.executable, "scripts/asvs_resolver.py", "--check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"asvs_resolver.py --check exited {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# --------------------------------------------------------------------------------------------
# The loaded object
# --------------------------------------------------------------------------------------------


def test_absent_optional_lists_are_empty_rather_than_none() -> None:
    """So a consumer iterates rather than testing for `None` first."""
    for requirement in ALL_REQUIREMENTS:
        assert isinstance(requirement.applicable_technologies, list)
        assert isinstance(requirement.common_false_positives, list)


def test_applicable_technologies_is_populated_on_nothing() -> None:
    """The fact DEC-024 turns on, asserted so it cannot change without the decision being reread.

    It is the only structured filter field section 17 offers, and it carries no data. That is why
    there is no deterministic requirement pre-filter and why the whole catalog goes to every
    mapping call. If this starts failing, DEC-024's expiry trigger is worth re-reading.
    """
    populated = [r.id for r in ALL_REQUIREMENTS if r.applicable_technologies]

    assert not populated, (
        f"{populated} now carry applicable_technologies. DEC-024 rejected a deterministic "
        f"pre-filter partly because this field is empty on every requirement."
    )


def test_a_loaded_catalog_is_immutable() -> None:
    loaded: LoadedCatalog = CATALOG

    with pytest.raises(AttributeError):
        loaded.catalog = CATALOG.catalog  # type: ignore[misc]
