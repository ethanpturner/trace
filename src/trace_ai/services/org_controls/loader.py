"""The org-controls catalog loader: one reader, validated, hash-verified (#528, DEC-115).

The requirements loader's rules, applied to the smaller sibling. `org-controls/<version>.yaml`
is version-controlled authored configuration; this module is the only thing that reads it. A
caller names the version it wants — a new version added mid-assessment cannot change what an
in-flight run consults — every control validates as an `OrganizationalControl`, and the
`content_hash` is recomputed over the *parsed* catalog on every load (DEC-019: comments,
indentation, and key order do not move it) and compared to the declared one. A drifted file is
refused, because the claims a parser seeds cite this catalog by version and a version whose
content can move is provenance that means nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.org_control import OrganizationalControl

__all__ = ["OrgCatalogError", "OrgControlCatalog", "compute_org_hash", "load_org_controls"]

ORG_CONTROLS_ROOT = PROJECT_ROOT / "org-controls"

_HASH_FIELD = "content_hash"


class OrgCatalogError(ValueError):
    """The catalog cannot be read as what it claims to be, with the reason stated."""


@dataclass(frozen=True, slots=True)
class OrgControlCatalog:
    """One loaded version: the controls, keyed access, and the verified hash."""

    version: str
    content_hash: str
    controls: tuple[OrganizationalControl, ...]

    def by_name(self) -> dict[str, OrganizationalControl]:
        return {control.name: control for control in self.controls}

    def __len__(self) -> int:
        return len(self.controls)


def _parsed(version: str) -> dict[str, Any]:
    path = ORG_CONTROLS_ROOT / f"{version}.yaml"
    if not path.is_file():
        known = sorted(entry.stem for entry in ORG_CONTROLS_ROOT.glob("*.yaml"))
        raise OrgCatalogError(
            f"no org-controls catalog version {version!r}; known versions: {known or 'none'}"
        )
    document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    body = (document or {}).get("org_controls_catalog")
    if not isinstance(body, dict):
        raise OrgCatalogError(f"{path.name} has no `org_controls_catalog` mapping")
    return body


def compute_org_hash(version: str) -> str:
    """The DEC-019 hash: over the parsed catalog with the hash field excluded from its input."""
    body = dict(_parsed(version))
    body.pop(_HASH_FIELD, None)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return content_hash(canonical.encode("utf-8"))


def load_org_controls(version: str) -> OrgControlCatalog:
    """Load one version, validated in both directions and hash-verified."""
    body = _parsed(version)
    declared_version = str(body.get("version", ""))
    if declared_version != version:
        raise OrgCatalogError(
            f"org-controls {version}.yaml declares version {declared_version!r}; the file and "
            f"its own declaration disagree"
        )
    declared_hash = str(body.get(_HASH_FIELD, ""))
    recomputed = compute_org_hash(version)
    if declared_hash != recomputed:
        raise OrgCatalogError(
            f"org-controls {version} content hash does not verify: declared {declared_hash}, "
            f"recomputed {recomputed}. Regenerate with "
            f"`uv run python scripts/org_controls_hash.py --version {version} --write` if the "
            f"edit was intended."
        )
    raw_controls = body.get("controls")
    if not isinstance(raw_controls, list) or not raw_controls:
        raise OrgCatalogError(f"org-controls {version} declares no controls")
    controls = tuple(OrganizationalControl.model_validate(entry) for entry in raw_controls)
    for control in controls:
        if control.catalog_version != version:
            raise OrgCatalogError(
                f"{control.name} declares catalog_version {control.catalog_version!r} inside "
                f"the {version} catalog; every entry names the version that defines it"
            )
    names = [control.name for control in controls]
    if len(set(names)) != len(names):
        raise OrgCatalogError(f"org-controls {version} repeats a control name")
    return OrgControlCatalog(version=version, content_hash=recomputed, controls=controls)
