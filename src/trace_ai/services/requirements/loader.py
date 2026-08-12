"""The catalog loader: the first product code that reads `requirements/`.

DEC-010 stores the catalog as version-controlled YAML -- a `catalog.yaml` manifest and one file
per primary category under a directory named for the catalog version -- and left validation to a
test, on the grounds that nothing read it. This module is the reader. What the test enforced by
convention, this enforces at load, for every caller, including the mapping step.

What the loader refuses, and why each one is a refusal rather than a warning:

- **A requirement that does not conform to section 17.** Unknown fields included: `extra="forbid"`
  makes an invented key a validation error, and a catalog field nobody reads is a field the author
  believed was doing something.
- **A requirement identifier that is not authored.** DEC-018 gives requirements the authored form,
  `req-AUTH-001`. `req-001` parses as a valid generated identifier, which is the problem: a
  catalog entry numbered by a counter is an identifier no person assigned, and benchmark
  expected-output files reference these by hand.
- **A manifest and a set of files that disagree in either direction.** Both directions, because
  they fail differently and both silently: an identifier only in the manifest is a requirement
  that vanished, and one only in the files is a requirement no consumer was told about.
- **A declared version that is not the version in the tree.** See *Version pinning* below.
- **A `content_hash` that does not match what the catalog now contains.**

## What the hash covers

DEC-019 fixes `RequirementsCatalog.content_hash` as SHA-256 over "a canonical re-serialization of
the parsed catalog: keys sorted, comments and formatting discarded". A hash over an unstated input
is not verifiable -- two implementations can both be correct and disagree -- so the input is stated
exactly here and computed in exactly one place, `canonical_bytes`:

    {"catalog": <the manifest, validated and JSON-dumped, without content_hash>,
     "requirements": [<each requirement, validated and JSON-dumped, ordered by id>]}

serialized with `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)` and
encoded UTF-8. Four consequences follow, and they are the point rather than side effects:

- **It covers the parsed catalog, not the file.** Comments, indentation, YAML block style, key
  order, and which category file a requirement lives in are all invisible to it. A hash that
  churns on whitespace reports change where there is none, and one that reports change constantly
  is one nobody reads.
- **`content_hash` is excluded from its own input.** It has to be: the manifest carries the value
  being computed. Everything else in the manifest is covered.
- **Requirements are ordered by identifier and `requirement_ids` is sorted.** Order in the
  manifest is presentation -- version 0.1 groups it by category with blank lines -- so reordering
  it is not a change in what the catalog says.
- **It covers the validated view, so defaults are part of it.** An absent optional list hashes as
  `[]`. Adding an optional field to `Requirement` therefore changes every catalog hash, which is
  correct: the object changed.

Prose in a YAML comment is invisible to all of this, even where that prose is doing real work.
`requirements/README.md` says so where a catalog author will read it.

## Version pinning

`load_catalog` requires the caller to name a version, and the caller in an assessment passes
`Assessment.requirements_catalog_version`. Nothing here globs the version directories and takes
the last one: a directory listing sorts, and a `0.2/` added mid-assessment would silently change
what an in-flight run is assessed against.

Each version's manifest declares its own version, so a pin that disagrees with what the tree
holds is refused by name rather than served a different edition. The root `catalog.yaml` is
version 0.1's manifest; every later version carries its own `catalog-<version>.yaml` beside it
(DEC-057), so releasing a new version never edits a frozen one. `current_version()` is the
explicit way to ask what the root manifest declares, for tooling and tests that legitimately
want whatever is there.

## Lifecycle status (DEC-057)

`versions.yaml` is the governance registry: lifecycle status, maintainer, release and review
dates, all outside the hashed content. The loader verifies the hash against the manifest as
frozen, then overrides `status` from the registry where an entry exists — so 0.1 can move from
`draft` to `active` to `retired` without a byte of its frozen content changing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import yaml
from pydantic import ValidationError

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.hashing import ALGORITHM, content_hash
from trace_ai.domain.identifiers import IdentifierKind, parse_id
from trace_ai.domain.requirement import Requirement
from trace_ai.domain.requirements_catalog import RequirementsCatalog

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CATALOG_ROOT",
    "MANIFEST_FILE",
    "VERSIONS_REGISTRY",
    "CatalogError",
    "CatalogHashError",
    "CatalogManifestError",
    "CatalogNotFoundError",
    "CatalogSchemaError",
    "CatalogVersionError",
    "LoadedCatalog",
    "canonical_bytes",
    "compute_hash",
    "current_version",
    "load_catalog",
    "registry_status",
]

CATALOG_ROOT: Final = PROJECT_ROOT / "requirements"
MANIFEST_FILE: Final = CATALOG_ROOT / "catalog.yaml"
VERSIONS_REGISTRY: Final = CATALOG_ROOT / "versions.yaml"

# Stands in for `content_hash` while the manifest is validated, and is removed before anything is
# hashed. A real value cannot be supplied here -- it is what the validated object is needed to
# compute -- and section 30 makes the field required, so the model cannot be built without one.
_PLACEHOLDER_HASH: Final = f"{ALGORITHM}:{'0' * 64}"

_SECTION_17: Final = "docs/architecture/data-model.md section 17"
_SECTION_30: Final = "docs/architecture/data-model.md section 30"


class CatalogError(RuntimeError):
    """Anything that stopped the catalog from being read as written."""


class CatalogNotFoundError(CatalogError):
    """No manifest, or no directory for the version it declares."""


class CatalogSchemaError(CatalogError):
    """A requirement or the manifest does not conform to the data model."""


class CatalogManifestError(CatalogError):
    """The manifest and the category files disagree, or an identifier is malformed."""


class CatalogVersionError(CatalogError):
    """The caller pinned a version the tree does not hold."""


class CatalogHashError(CatalogError):
    """The declared `content_hash` is not the hash of what the catalog now contains."""


@dataclass(frozen=True, slots=True)
class LoadedCatalog:
    """A catalog version, parsed and validated: the manifest and every requirement in it."""

    catalog: RequirementsCatalog
    requirements: tuple[Requirement, ...]

    @property
    def version(self) -> str:
        return self.catalog.version

    def by_id(self) -> dict[str, Requirement]:
        """Every requirement keyed by identifier, in catalog order."""
        return {requirement.id: requirement for requirement in self.requirements}

    def __len__(self) -> int:
        return len(self.requirements)


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise CatalogNotFoundError(f"{path} does not exist")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise CatalogSchemaError(f"{path} is not valid YAML: {error}") from error


def _manifest_file(root: Path, version: str | None = None) -> Path:
    """The manifest for `version`: its own file where one exists, the root manifest otherwise.

    DEC-010 gave the repository one manifest when it held one version. DEC-057 gives every later
    version its own — `catalog-0.2.yaml` beside `catalog.yaml` — so releasing 0.2 never edits the
    frozen 0.1 manifest whose hash recorded runs verify. The per-version file lives at the root
    rather than inside the version directory, because the loader treats every `*.yaml` under a
    version directory as a category file.
    """
    if version is not None:
        versioned = root / f"catalog-{version}.yaml"
        if versioned.is_file():
            return versioned
    return root / "catalog.yaml"


def registry_status(version: str, root: Path = CATALOG_ROOT) -> str | None:
    """The lifecycle status `versions.yaml` records for `version`, if the registry exists.

    DEC-057 puts governance metadata outside the frozen, hashed content: retiring a version must
    not alter content whose hash a recorded assessment verifies. The registry is therefore the
    authority on lifecycle where both it and the manifest speak, and absent entirely for a tree
    that predates it.
    """
    if not (root / "versions.yaml").is_file():
        return None
    document = _read_yaml(root / "versions.yaml")
    if not isinstance(document, dict) or not isinstance(document.get("versions"), dict):
        raise CatalogSchemaError(
            f"{root / 'versions.yaml'} has no top-level 'versions' mapping (DEC-057)"
        )
    entry = document["versions"].get(version)
    if entry is None:
        return None
    if not isinstance(entry, dict) or not isinstance(entry.get("status"), str):
        raise CatalogSchemaError(
            f"{root / 'versions.yaml'} entry for {version!r} declares no status (DEC-057)"
        )
    return str(entry["status"])


def _manifest_mapping(root: Path, version: str | None = None) -> dict[str, Any]:
    manifest_file = _manifest_file(root, version)
    document = _read_yaml(manifest_file)
    if not isinstance(document, dict) or not isinstance(document.get("catalog"), dict):
        raise CatalogSchemaError(
            f"{manifest_file} has no top-level 'catalog' mapping ({_SECTION_30})"
        )
    catalog: dict[str, Any] = document["catalog"]
    return catalog


def current_version(root: Path = CATALOG_ROOT) -> str:
    """The version the manifest in `root` declares.

    For tooling and tests that want whatever is in the tree. An assessment does not call this:
    it pins a version and passes it to `load_catalog`, so that adding a catalog version cannot
    change what an in-flight run is assessed against.
    """
    catalog = _manifest_mapping(root)
    version = catalog.get("version")
    if not isinstance(version, str) or not version:
        raise CatalogSchemaError(f"{root / 'catalog.yaml'} declares no version ({_SECTION_30})")
    return version


def _requirement_files(version_directory: Path) -> list[Path]:
    return sorted(version_directory.glob("*.yaml"))


def _parse_requirements(version_directory: Path) -> tuple[Requirement, ...]:
    """Every requirement in every category file, validated, in file-then-document order."""
    parsed: list[Requirement] = []
    for path in _requirement_files(version_directory):
        document = _read_yaml(path)
        if not isinstance(document, dict) or not isinstance(document.get("requirements"), list):
            raise CatalogSchemaError(
                f"{path.name} has no top-level 'requirements' list (DEC-010 gives each category "
                f"file a single such list)"
            )
        for index, entry in enumerate(document["requirements"]):
            parsed.append(_parse_requirement(path, index, entry))
    return tuple(parsed)


def _parse_requirement(path: Path, index: int, entry: Any) -> Requirement:
    if not isinstance(entry, dict):
        raise CatalogSchemaError(f"{path.name}: requirement {index} is not a mapping")

    where = entry.get("id") if isinstance(entry.get("id"), str) else f"entry {index}"
    try:
        requirement = Requirement.model_validate(entry)
    except ValidationError as error:
        raise CatalogSchemaError(
            f"{path.name}: {where} does not conform to {_SECTION_17}. Adding a field to the "
            f"Requirement object is a design change and belongs in the decision log.\n{error}"
        ) from error

    kind = parse_id(requirement.id).kind
    if kind is not IdentifierKind.AUTHORED:
        raise CatalogManifestError(
            f"{path.name}: {requirement.id} is a {kind} identifier. Catalog requirements are "
            f"authored (DEC-018): '<prefix>-<CATEGORY>-<number>', as in 'req-AUTH-001'. A "
            f"counter-numbered identifier is one no person assigned."
        )
    return requirement


def canonical_bytes(catalog: RequirementsCatalog, requirements: tuple[Requirement, ...]) -> bytes:
    """The exact input DEC-019 hashes for a catalog. See the module docstring.

    `content_hash` is excluded, so this accepts a catalog carrying any value in that field --
    including the placeholder the loader uses before the real one exists.
    """
    manifest = catalog.model_dump(mode="json")
    manifest.pop("content_hash")
    manifest["requirement_ids"] = sorted(manifest["requirement_ids"])

    payload = {
        "catalog": manifest,
        "requirements": [
            requirement.model_dump(mode="json")
            for requirement in sorted(requirements, key=lambda r: r.id)
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _check_manifest_agrees(
    declared: list[str], requirements: tuple[Requirement, ...], version: str
) -> None:
    found = [requirement.id for requirement in requirements]

    duplicates = sorted({rid for rid in found if found.count(rid) > 1})
    if duplicates:
        raise CatalogManifestError(f"duplicate requirement ids in {version}: {duplicates}")

    only_manifest = sorted(set(declared) - set(found))
    only_files = sorted(set(found) - set(declared))
    if only_manifest or only_files:
        raise CatalogManifestError(
            f"catalog.yaml and the {version} requirement files disagree. "
            f"Only in the manifest: {only_manifest or 'none'}; "
            f"only in the files: {only_files or 'none'}. Both directions are errors: an "
            f"identifier only in the manifest is a requirement that vanished, and one only in "
            f"the files is a requirement no consumer was told about."
        )

    mismatched = sorted(r.id for r in requirements if r.catalog_version != version)
    if mismatched:
        raise CatalogManifestError(
            f"these requirements declare a catalog_version other than {version!r}: {mismatched}"
        )


def _build(
    version: str, root: Path
) -> tuple[dict[str, Any], RequirementsCatalog, tuple[Requirement, ...]]:
    """Parse and validate: the raw manifest, the validated catalog, the requirements.

    The catalog returned carries `_PLACEHOLDER_HASH`, because computing the real one needs a
    validated object and the field is required. It is the input to `canonical_bytes`, which
    excludes `content_hash` for exactly this reason. Nothing outside this module sees it: both
    callers replace it, one with the computed hash and one with a comparison.

    **Manifest agreement is checked by `load_catalog` and not here**, so that `compute_hash` can
    produce the right value for a catalog that is structurally wrong. Repairing a stale hash and
    reporting a vanished requirement are different jobs, and a repair tool that refuses to run
    until the catalog is already correct is not a repair tool.
    """
    catalog_mapping = _manifest_mapping(root, version)
    declared_version = catalog_mapping.get("version")
    if declared_version != version:
        raise CatalogVersionError(
            f"catalog version {version!r} was requested and the manifest at "
            f"{_manifest_file(root, version)} declares {declared_version!r}. A pinned version "
            f"that is not in the tree is refused rather than served a different edition."
        )

    version_directory = root / version
    if not version_directory.is_dir():
        raise CatalogNotFoundError(
            f"catalog version {version!r} has no directory at {version_directory} (DEC-010 gives "
            f"each version its own)"
        )

    requirements = _parse_requirements(version_directory)
    if not requirements:
        raise CatalogSchemaError(f"catalog version {version!r} contains no requirements")

    fields = {key: value for key, value in catalog_mapping.items() if key != "content_hash"}

    try:
        provisional = RequirementsCatalog.model_validate(
            {**fields, "content_hash": _PLACEHOLDER_HASH}
        )
    except ValidationError as error:
        raise CatalogSchemaError(
            f"{root / 'catalog.yaml'} does not conform to {_SECTION_30}.\n{error}"
        ) from error

    return catalog_mapping, provisional, requirements


def compute_hash(version: str, root: Path = CATALOG_ROOT) -> str:
    """What `content_hash` should be for the catalog on disk, ignoring what it declares.

    Separate from `load_catalog` because a stale or absent hash is the one state the loader
    refuses to read, and something has to be able to compute the correct value from that state --
    `scripts/catalog_hash.py --write` is that something.
    """
    _, provisional, requirements = _build(version, root)
    return content_hash(canonical_bytes(provisional, requirements))


def load_catalog(version: str, root: Path = CATALOG_ROOT) -> LoadedCatalog:
    """Load, validate, and hash-check the catalog at `version`.

    `version` is required and is not defaulted from the tree: an assessment passes
    `Assessment.requirements_catalog_version`, so that a catalog version added mid-run cannot
    change what the run is assessed against. Use `current_version()` when you genuinely want
    whatever is on disk.
    """
    catalog_mapping, provisional, requirements = _build(version, root)
    _check_manifest_agrees(list(provisional.requirement_ids), requirements, version)

    declared_hash = catalog_mapping.get("content_hash")
    computed = content_hash(canonical_bytes(provisional, requirements))

    if declared_hash is None:
        raise CatalogHashError(
            f"{root / 'catalog.yaml'} declares no content_hash, which {_SECTION_30} requires. "
            f"The catalog now hashes to {computed}. Run "
            f"`uv run python scripts/catalog_hash.py --write` to record it."
        )
    if declared_hash != computed:
        raise CatalogHashError(
            f"{root / 'catalog.yaml'} declares content_hash {declared_hash!r} and the catalog "
            f"hashes to {computed!r}. The catalog changed and the hash was not regenerated; run "
            f"`uv run python scripts/catalog_hash.py --write`. The hash covers the parsed "
            f"catalog, so this is a change in content and not in formatting (DEC-019)."
        )

    # DEC-057: lifecycle status is governance metadata, sourced from `versions.yaml` where both
    # it and the manifest speak. Applied *after* the hash check on purpose — the manifest's own
    # status is part of the hashed content and stays whatever it was when the version froze,
    # while the registry's answer can change (draft → active → retired) without moving a hash a
    # recorded assessment verifies.
    lifecycle = registry_status(version, root)
    catalog = RequirementsCatalog.model_validate(
        {
            **provisional.model_dump(),
            "content_hash": computed,
            **({"status": lifecycle} if lifecycle is not None else {}),
        }
    )
    return LoadedCatalog(catalog=catalog, requirements=requirements)
