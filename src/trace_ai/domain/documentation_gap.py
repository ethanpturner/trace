"""`DocumentationGap`: what Trace records when it cannot determine whether a control exists.

`data-model.md` section 23 is authoritative for the fields, and its *Important distinction* is the
whole reason the object exists:

> A documentation gap means: Trace cannot determine whether a control exists or is effective.
> A finding means: Available evidence supports the conclusion that a meaningful security weakness
> exists.

DEC-009 states the same separation from the decision side, and DEC-013's outcome table routes every
`unverified` mapping here or to a `Question` and to nothing else. Collapsing the two is the exact
failure this project exists to avoid, so the schema is built so that a gap *cannot* be read as an
asserted weakness: there is no recommendation, no impact, no likelihood, and no validation status
on this object, and `extra="forbid"` makes adding one a validation error rather than a quiet
widening of what a gap claims.

**`severity` here rates the gap, not a weakness** (DEC-045). It reuses section 4.5's `Severity`
vocabulary for a different meaning — how much the inability to verify impedes the assessment — and
that is the easiest field on the object to misread. It is also the one place this object departs
from DEC-030: a `Finding` is created with `unassigned` because the reviewer assigns severity at
checkpoint 2, and **a gap may never carry `unassigned`**, because checkpoint 2 reviews findings and
no step anywhere would ever assign it. A field nothing can fill is not a field awaiting a value.

**`importance` is required and is not `severity`.** `severity` is a label; `importance` is the
sentence saying why the gap matters. A gap with neither is indistinguishable from noise, and a gap
with only the label tells a reviewer nothing they can act on.

A `DocumentationGap` is not a `Question` (section 22). A question asks a person for an answer the
documents do not contain; a gap records that the documentation itself is insufficient. Section 16
splits them by which problem is primary, and the two are often raised together.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import Field, field_validator, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.control_mapping import ApplicabilityStatus, SatisfactionStatus
from trace_ai.domain.enums import ObjectStatus, Severity
from trace_ai.domain.identifiers import (
    AssessmentId,
    DocumentationGapId,
    EvidenceReferenceId,
    parse_id,
)

if TYPE_CHECKING:
    from trace_ai.domain.control_mapping import ControlMapping

__all__ = ["DocumentationGap", "warrants_documentation_gap"]


class DocumentationGap(DomainModel):
    """Missing or inadequate documentation, asserting nothing about the implementation."""

    id: DocumentationGapId
    assessment_id: AssessmentId

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    """What documentation is missing. Required and non-empty."""

    importance: str = Field(min_length=1)
    """Why the gap matters, in prose. Required and non-empty: a gap with no stated reason it
    matters is noise, and a reviewer cannot decide whether to chase it."""

    related_object_ids: list[str] = Field(default_factory=list)
    """Components, threats, controls, or requirements the gap bears on. Each is a well-formed
    identifier; whether it resolves to an object *in this assessment* is checked where the
    assessment's objects are known, not here."""

    requested_evidence: list[str] = Field(default_factory=list)
    """What documentation would close the gap, phrased for a person to go and find."""

    severity: Severity
    """How much this gap impedes the assessment — not the severity of a weakness (DEC-045).
    `unassigned` is refused: nothing downstream assigns a gap's severity."""

    status: ObjectStatus
    generated_by: str = Field(min_length=1)

    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    """Evidence showing the ambiguity or contradiction. Optional, and deliberately so: the ordinary
    gap is documentation that says nothing, and silence cannot be quoted (DEC-013)."""

    @field_validator("related_object_ids")
    @classmethod
    def _related_ids_are_identifiers(cls, value: list[str]) -> list[str]:
        """Every entry parses as a section 2.1 identifier, and the bad one is named.

        This catches a descriptive slug — `cmp-webhook-receiver` — before it is stored. It does not
        catch an identifier for an object that does not exist; that needs the assessment's contents
        and is `MappingProposal.validate_references`'s check at the proposal boundary and the
        Mapping Validation node's afterwards.
        """
        for entry in value:
            parse_id(entry)
        return value

    @model_validator(mode="after")
    def _severity_is_assigned(self) -> Self:
        """A gap carries a real severity, because no later step supplies one (DEC-045).

        `Finding` is created with `unassigned` and DEC-030 has the reviewer resolve it at
        checkpoint 2. Checkpoint 2 reviews findings; `current-architecture.md` section 5.12 lists
        no gap action at all. An `unassigned` gap would therefore be rendered unassigned into
        report section 9, which is not a value awaiting a decision — it is a decision nobody was
        ever asked to make.
        """
        if self.severity is Severity.UNASSIGNED:
            raise ValueError(
                "a documentation gap may not carry severity 'unassigned' (DEC-045). Severity here "
                "rates how much the inability to verify impedes the assessment, and the node that "
                "raises the gap is the only step that ever assigns it."
            )
        return self


def warrants_documentation_gap(mapping: ControlMapping) -> bool:
    """Whether this mapping outcome is a gap candidate, per `agent-design.md` section 16.

    Section 16 gives two rules that this decides between, and the distinction is DEC-009's:

    - *Use a DocumentationGap when* the primary issue is inability to verify architecture or
      control design and no implementation weakness is yet supported. That is `unverified`, which
      DEC-013's outcome table sends here or to a `Question` and never to a finding.
    - *Use no output when* the requirement is not applicable. A requirement that does not apply is
      not documentation that is missing; ForgeFlow's absent local password policy is the worked
      example, and raising a gap for it would reintroduce the noise `not_applicable` removes.

    Everything else — `satisfied`, `partially_satisfied`, `unmet` — has cited evidence by schema,
    so the inability to verify is not the primary issue and section 16's precondition fails.

    **This decides gap-or-nothing, not gap-or-question.** Section 16 splits those on whether the
    answer is obtainable and could materially change the assessment, which is a judgment about the
    world rather than about the mapping, and Finding Consolidation makes it in M4.
    """
    if mapping.applicability_status is ApplicabilityStatus.NOT_APPLICABLE:
        return False
    return mapping.satisfaction_status is SatisfactionStatus.UNVERIFIED
