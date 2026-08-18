"""`OrganizationalControl`: one control the organization provides, authored and versioned.

`data-model.md` section 30a is authoritative for the fields. An organizational control is
authored configuration, not an assessment product: it carries a *name* — a lowercase slug,
outside the DEC-018 identifier scheme, exactly as DEC-034 rules for authored artifacts — and
it is identified by `(name, catalog_version)`. The org-controls catalog under `org-controls/`
is its only source, and `services/org_controls/loader.py` is that catalog's only reader.

**What the object asserts is bounded on purpose** (#528, DEC-115). An organizational control
says a mechanism exists *organizationally* — central logging exists, secrets come from the
enterprise vault — and nothing more. Whether *this system* actually inherits it is the
pipeline's ordinary work: the parser seeds a documented claim with catalog provenance, the
claim is decided at checkpoint 1, and evidence validation still judges what the mapping
concludes from it. An org control is never authority; it is a statement with a source.
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import Field, field_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.identifiers import PREFIXES

__all__ = ["OrganizationalControl"]

_NAME: Final = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _check_control_name(value: str) -> str:
    """A lowercase slug that is not a section 2.1 prefix wearing a hyphen (DEC-034)."""
    if not _NAME.match(value):
        raise ValueError(
            f"{value!r} is not an organizational-control name. Expected a lowercase slug such "
            f"as 'central-logging' (DEC-034; data-model.md section 30a)."
        )
    head = value.split("-", 1)[0]
    if head in PREFIXES:
        raise ValueError(
            f"{value!r} reads as an identifier: {head!r} is the section 2.1 prefix for "
            f"{PREFIXES[head]}. An organizational control carries a name, not an identifier, "
            f"and is identified by (name, catalog_version) (DEC-034)."
        )
    return value


class OrganizationalControl(DomainModel):
    """One control the organization provides (section 30a)."""

    name: str = Field(min_length=1)
    """The control's *name*: a lowercase slug, outside the identifier scheme (DEC-034)."""

    title: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    mechanism: str = Field(min_length=1)
    applies_when: list[str] = Field(default_factory=list)
    catalog_version: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _name_is_a_slug(cls, value: str) -> str:
        return _check_control_name(value)
