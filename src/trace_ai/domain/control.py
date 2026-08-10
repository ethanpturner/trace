"""`Control`: an implemented, inherited, claimed, or proposed safeguard.

`data-model.md` section 18 is authoritative. Three things about this object are decided elsewhere
and worth stating where they will be read.

**Inheritance scope is the structured fields, not a sentence** (DEC-026). An earlier
`inheritance_scope` string described in prose what `provider_component_id`,
`protected_component_ids`, `protected_asset_ids`, and `limitations` say structurally, which meant
the two could disagree with nothing to say which was right -- and prose cannot be compared against
the architecture, while inherited-control recognition is a named evaluation metric.

**Two inherited states are distinguished by field combination**, and the distinction is what the
ForgeFlow intentional non-findings turn on. A platform control the documentation states is
`inherited` + `implemented` with evidence present. A platform control nothing states is `inherited`
+ `claimed` with evidence absent, and it resolves to a `Question` -- never to `absent`, and by
DEC-013 never to `unmet`. `is_documented_inheritance` reads the difference so that no caller has to
reconstruct it.

**An `implemented` control cites evidence** (DEC-044). Section 12 makes "unverified controls are
marked implemented" a failure condition of the mapping step, and a schema that accepted an
implemented control with no evidence would leave that entirely to instruction.

**`generated_by` is required** (DEC-044). Section 18 as written had no provenance field, which made
a `Control` the one object in the pipeline whose origin could not be recovered -- and this object
has three possible origins.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final, Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ObjectStatus, ValidationStatus
from trace_ai.domain.identifiers import (
    AssessmentId,
    AssetId,
    ComponentId,
    ControlId,
    EvidenceReferenceId,
)

__all__ = [
    "EVIDENCED_IMPLEMENTATION_STATUSES",
    "Control",
    "ControlType",
    "ImplementationStatus",
]


class ControlType(StrEnum):
    """What kind of safeguard this is (section 18's control-type values).

    Closed, unlike the `component_type` family: section 18 heads the list "Control-type values"
    rather than "examples", which is DEC-036's stated test for a named vocabulary.
    """

    IMPLEMENTED = "implemented"
    INHERITED = "inherited"
    """Provided by a platform or another party. The provider is `provider_component_id`."""

    COMPENSATING = "compensating"
    PLANNED = "planned"
    RECOMMENDED = "recommended"
    """Proposed by the assessment rather than found in the system. Never evidence of a control."""


class ImplementationStatus(StrEnum):
    """How far the control actually exists (section 18's implementation-status values)."""

    IMPLEMENTED = "implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    CLAIMED = "claimed"
    """Someone says it exists and nothing evidences it. Not `absent`: DEC-009's whole point."""

    UNKNOWN = "unknown"
    ABSENT = "absent"
    """Evidence describes the control as missing. Requires evidence, like `unmet` does."""

    NOT_APPLICABLE = "not_applicable"


# The statuses that assert the control exists in the system, and therefore need a passage behind
# them. `claimed` and `unknown` are deliberately absent: they are what a control *without* evidence
# is called, and requiring evidence of them would leave nothing to record an undocumented control
# as (DEC-009).
EVIDENCED_IMPLEMENTATION_STATUSES: Final[frozenset[ImplementationStatus]] = frozenset(
    {
        ImplementationStatus.IMPLEMENTED,
        ImplementationStatus.PARTIALLY_IMPLEMENTED,
        ImplementationStatus.ABSENT,
    }
)


class Control(DomainModel):
    """An implemented, inherited, claimed, or proposed security safeguard (section 18)."""

    id: ControlId
    assessment_id: AssessmentId

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    control_type: ControlType

    provider_component_id: ComponentId | None = None
    """Who provides the control. For an `inherited` control this is the scope's subject
    (DEC-026)."""

    protected_component_ids: list[ComponentId] = Field(default_factory=list)
    protected_asset_ids: list[AssetId] = Field(default_factory=list)
    """What the control covers. Together with `limitations`, this *is* the inheritance scope."""

    implementation_status: ImplementationStatus
    validation_status: ValidationStatus
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    owner: str | None = None

    limitations: list[str] = Field(default_factory=list)
    """Where the coverage stops. The third structured field DEC-026 uses in place of prose."""

    generated_by: str = Field(min_length=1)
    """Which node or reviewer created this control (DEC-044). `context-extraction-v1` for one the
    extractor found described, `mapping-v1` for one the mapper proposed, `reviewer_edit` for one a
    person added. Required rather than defaulted: a default would make one origin the answer given
    when nobody supplied one, which is the reasoning DEC-039 used for `source_origin`."""

    created_at: datetime
    status: ObjectStatus

    @property
    def is_documented_inheritance(self) -> bool:
        """Whether this is a platform control the documentation actually establishes.

        The DEC-026 distinction, read once here rather than reconstructed by every caller. The
        `False` case for an inherited control is the one that becomes a `Question`, never an
        assertion that the control is absent.
        """
        return (
            self.control_type is ControlType.INHERITED
            and self.implementation_status is ImplementationStatus.IMPLEMENTED
            and bool(self.evidence_ids)
        )

    @model_validator(mode="after")
    def _asserted_implementation_cites_evidence(self) -> Self:
        """A control asserted to exist, or to be missing, cites a passage (DEC-044).

        `implemented`, `partially_implemented`, and `absent` are all claims about the system that
        a reader could check. `claimed` and `unknown` are what an unevidenced control is called,
        and they are exempt — that exemption is DEC-009, and removing it would leave an
        undocumented control with nowhere to be recorded except as absent.

        `recommended` and `planned` controls are exempt whatever their status: they are the
        assessment's own proposals and there is no source passage describing something nobody has
        built.
        """
        if self.control_type in {ControlType.PLANNED, ControlType.RECOMMENDED}:
            return self
        if (
            self.implementation_status in EVIDENCED_IMPLEMENTATION_STATUSES
            and not self.evidence_ids
        ):
            raise ValueError(
                f"a control with implementation_status "
                f"{self.implementation_status.value!r} must cite at least one evidence "
                f"reference. A control nobody documented is 'claimed' or 'unknown', never "
                f"'implemented' and never 'absent' (DEC-009, DEC-044)."
            )
        return self
