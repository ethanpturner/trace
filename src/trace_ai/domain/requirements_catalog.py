"""`RequirementsCatalog`: a versioned collection of requirements, identified by `(id, version)`.

`data-model.md` section 30 is authoritative. Two properties of this object are decided elsewhere
and are worth having in front of you when reading it.

**`id` is a name, not an identifier** (DEC-034). `core` is a lowercase slug outside the section 2.1
scheme: a catalog is not scoped to an assessment, is not minted by the persistence layer, and is
referenced by version. Nothing joins on `id` alone -- `Assessment.requirements_catalog_version`,
each requirement's own `catalog_version`, and a benchmark scenario's pinned version all name the
edition. `cat-core` was the mistake DEC-034 corrected, and `_check_catalog_name` refuses a value
shaped like an identifier so it cannot come back.

**`content_hash` covers meaning, not formatting** (DEC-019). It is computed over a canonical
re-serialization of the *parsed* catalog rather than over file bytes, so reformatting, reordering
keys, and editing comments do not change it. `services/requirements/loader.py` is the only thing
that computes or verifies it, and its docstring states exactly what goes in.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Final

from pydantic import Field, field_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.hashing import ContentHash
from trace_ai.domain.identifiers import PREFIXES, RequirementId
from trace_ai.domain.requirement import CatalogStatus

__all__ = ["RequirementsCatalog"]

# A lowercase slug: letters, digits, and internal hyphens. Deliberately permissive about hyphens
# and deliberately strict about the one thing DEC-034 cares about, which is checked separately.
_NAME: Final = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _check_catalog_name(value: str) -> str:
    """A lowercase slug that is not a section 2.1 prefix wearing a hyphen (DEC-034)."""
    if not _NAME.match(value):
        raise ValueError(
            f"{value!r} is not a catalog name. Expected a lowercase slug such as 'core' "
            f"(DEC-034; data-model.md section 30)."
        )
    head = value.split("-", 1)[0]
    if head in PREFIXES:
        raise ValueError(
            f"{value!r} reads as an identifier: {head!r} is the section 2.1 prefix for "
            f"{PREFIXES[head]}. A catalog carries a name, not an identifier, and is identified "
            f"by (id, version) (DEC-034). 'cat-core' was this mistake."
        )
    return value


class RequirementsCatalog(DomainModel):
    """A versioned collection of reusable requirements (section 30)."""

    id: str = Field(min_length=1)
    """The catalog's *name*: a lowercase slug, outside the identifier scheme (DEC-034)."""

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str | None = None

    requirement_ids: list[RequirementId] = Field(min_length=1)
    """Every requirement the version contains. The loader asserts this and the category files
    agree in both directions; a manifest that is merely a subset would hide a requirement from
    every consumer while the files looked complete."""

    created_at: datetime
    status: CatalogStatus

    content_hash: ContentHash
    """`sha256:<hex>` over a canonical re-serialization of the parsed catalog (DEC-019)."""

    @field_validator("id")
    @classmethod
    def _name_not_identifier(cls, value: str) -> str:
        return _check_catalog_name(value)

    @field_validator("created_at")
    @classmethod
    def _at_utc_when_undated(cls, value: datetime) -> datetime:
        """A catalog is authored, and what gets written in YAML is a date.

        `created_at: 2026-08-08` parses to a naive midnight. Every other timestamp in the system
        comes from `domain.base.now()` and is timezone-aware; a naive one here would compare and
        serialize as though it were UTC without saying so. The assumption is made explicit rather
        than left to whatever reads it next.
        """
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
