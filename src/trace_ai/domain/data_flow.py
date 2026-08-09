"""`DataFlow`: movement of data or commands between two components.

`data-model.md` section 14 is authoritative for the fields, and it is the only one of the five
context objects that states validation rules of its own. All three are enforced here or explicitly
placed elsewhere.

**Source and destination must differ.** A flow from a component to itself is not a flow between
components, and the rule is on the model because it needs no other object to check.

**Unknown encryption and authentication are the string `unknown`, never `False` and never absent.**
This is DEC-009 at field level, and it is why both fields default to `unknown` rather than to
`None`: a flow whose transport encryption nobody documented must say so, because silence read as
`False` is an asserted weakness nobody evidenced, and silence read as `True` is a control nobody
verified. The model refuses a boolean outright.

**`direction` is a closed vocabulary**, unlike the `*_type` fields around it. Section 14 describes
it as "One-way or bidirectional", which enumerates rather than illustrates, and DEC-036 uses that
distinction as its rule. `unknown` is the third member for the same reason the two fields above have
one: an extractor that cannot tell must be able to say so rather than guess, and a guessed direction
silently removes a threat.

**Referenced trust boundaries must exist** is not checked here. It is a claim about other objects,
which the Context Validation node owns; a model that could check it would need the whole context.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.identifiers import (
    AssessmentId,
    ComponentId,
    DataFlowId,
    EvidenceReferenceId,
    TrustBoundaryId,
)
from trace_ai.domain.vocabulary import UNKNOWN, VocabularyTerm

__all__ = ["DataFlow", "FlowDirection"]


class FlowDirection(StrEnum):
    """Which way data moves (section 14).

    Closed, because section 14 names the values rather than illustrating them. `UNKNOWN` is added
    by DEC-036: `direction` is required, and a required field with no honest value is a field that
    gets guessed.
    """

    ONE_WAY = "one_way"
    BIDIRECTIONAL = "bidirectional"
    UNKNOWN = "unknown"


class DataFlow(DomainModel):
    """Movement of data or commands between components (section 14)."""

    id: DataFlowId
    assessment_id: AssessmentId

    name: str = Field(min_length=1)
    source_component_id: ComponentId
    destination_component_id: ComponentId
    direction: FlowDirection

    protocol: str | None = None
    data_types: list[str] = Field(default_factory=list)

    authentication: VocabularyTerm = UNKNOWN
    """How the flow is authenticated. `unknown` when undocumented -- never `False`, never absent."""

    encryption_in_transit: VocabularyTerm = UNKNOWN
    """Documented transport encryption. `unknown` when undocumented (section 14, DEC-009)."""

    crosses_trust_boundary_ids: list[TrustBoundaryId] = Field(default_factory=list)

    internet_exposed: bool | None = None
    """`None` means the documentation does not say, which is not `False`."""

    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    status: ObjectStatus

    @model_validator(mode="after")
    def _endpoints_differ(self) -> Self:
        """Section 14: source and destination must be different components."""
        if self.source_component_id == self.destination_component_id:
            raise ValueError(
                f"source_component_id and destination_component_id are both "
                f"{self.source_component_id!r}; a data flow moves data between two components"
            )
        return self
