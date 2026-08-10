"""`Requirement`: one version-controlled security expectation from the catalog.

`data-model.md` section 17 is authoritative for the fields. Three things about this object decide
how it behaves everywhere downstream, and all three are easier to get wrong than to get right.

**A requirement is authored, not generated.** DEC-018 gives it the authored identifier form --
`req-AUTH-001`, prefix plus category plus number, written by a person and stable across catalog
versions. `RequirementId` accepts both DEC-018 classes, so the loader additionally refuses a
generated-looking `req-001`: a catalog entry numbered by a counter would be an identifier nobody
authored, and expected-output files reference these by hand.

**`status` is a closed vocabulary.** Section 17's description names the three values rather than
illustrating them, which is the `DataFlow.direction` case in DEC-036 and not the
`component_type` case. `CatalogStatus` is therefore an enum. It lives here rather than in
`domain/enums.py` because that module is section 4's seven shared types and a test counts them.

**`acceptable_implementations` is non-exhaustive by construction.** Nothing in this module or
downstream of it may treat the list as the set of controls that satisfy the requirement.
`requirements/README.md` and `agent-design.md` sections 12 and 13 make that an explicit failure
condition for the mapping step; the field is a `list[str]` here and carries no cardinality rule
precisely because completeness is not claimed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import Severity
from trace_ai.domain.identifiers import RequirementId

__all__ = ["CatalogStatus", "Requirement"]


class CatalogStatus(StrEnum):
    """Lifecycle of an authored catalog object: a requirement, or a catalog version.

    Section 17 and section 30 both type their `status` as a string and both name the same three
    values in the description. One enum, because two spellings of one vocabulary is how a catalog
    ends up `retired` in the manifest and `active` in the file.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class Requirement(DomainModel):
    """A reusable security expectation (section 17).

    Not scoped to an assessment: it carries `catalog_version` rather than `assessment_id`, and the
    same object is read by every assessment that pins that version.
    """

    id: RequirementId
    catalog_version: str = Field(min_length=1)

    title: str = Field(min_length=1)

    statement: str = Field(min_length=1)
    """The normative expectation, written so that absence of evidence resolves to `unverified`
    and never to `unmet` (DEC-009). A statement phrased so that silence in a document proves a
    control missing is a DEC-009 violation regardless of how the rest of the catalog is worded."""

    rationale: str = Field(min_length=1)
    category: list[str] = Field(min_length=1)

    applicable_technologies: list[str] = Field(default_factory=list)

    applicable_conditions: list[str] = Field(default_factory=list)
    """When the requirement applies. Free text by decision, not by omission: data-model open
    question 5 asks how applicability should be represented machine-readably and is open, so
    a controlled vocabulary here would answer it by accident (`requirements/README.md`)."""

    non_applicable_conditions: list[str] = Field(default_factory=list)
    """When the requirement does not apply at all. Distinct from `common_false_positives`
    (DEC-011)."""

    acceptable_implementations: list[str] = Field(default_factory=list)
    """Example mechanism classes. **Non-exhaustive**; see the module docstring."""

    evidence_expectations: list[str] = Field(default_factory=list)

    common_false_positives: list[str] = Field(default_factory=list)
    """What must not be concluded when the requirement applies and the documentation is silent.
    Not `non_applicable_conditions` (DEC-011): that one says the requirement does not apply."""

    default_severity: Severity | None = None
    """Severity if the requirement is unmet. A default carried by the catalog, not an assignment:
    DEC-030 gives severity to the reviewer at checkpoint 2 and no node proposes one."""

    source_frameworks: list[str] = Field(default_factory=list)
    """Provenance, not compliance mapping. `'<framework> <version>: <control id>'`, checked for
    shape and against the adopted-framework list by `tests/unit/test_requirements_catalog.py` --
    which is an authoring convention rather than a schema rule, and where the adopted list
    belongs, because adopting a framework is a provenance decision. Nothing anywhere checks that
    a cited control exists: the frameworks are not vendored, and a plausible but wrong identifier
    passes."""

    status: CatalogStatus
    supersedes_id: RequirementId | None = None
