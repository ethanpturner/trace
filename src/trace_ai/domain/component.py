"""`Component`: a technical or logical part of the reviewed system.

`data-model.md` section 11 is authoritative for the fields. Two things about this object are worth
stating where they will be read.

**`component_type` is an open vocabulary** (DEC-036). Section 11 heads its list "Component-type
examples" and types the field `string`; `KNOWN_COMPONENT_TYPES` records what the corpus already
uses and validates nothing.

**Three-valued exposure is expressed by `None`, and `None` is not `False`.**
`internet_accessible` and `externally_managed` are optional booleans, so a component carries one of
three states: documented as true, documented as false, and not stated. Reading the third as the
second is the DEC-009 failure at field level -- a component nobody documented as internet-facing is
not thereby internal, and treating it as internal is how a real exposure disappears from an
assessment. Anything consuming these fields tests for `is None` before testing truth.
"""

from __future__ import annotations

from typing import Final

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.identifiers import AssessmentId, ComponentId, EvidenceReferenceId
from trace_ai.domain.vocabulary import VocabularyTerm

__all__ = ["KNOWN_COMPONENT_TYPES", "Component"]

# Section 11's thirteen examples, plus the six `demo/forgeflow/input/structured-system-input.yaml`
# uses that section 11 does not list. Documentation, not a validation rule (DEC-036): the fixture
# is the evidence that this list was never complete, so nothing here treats it as complete now.
KNOWN_COMPONENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "user_interface",
        "service",
        "api_gateway",
        "background_worker",
        "data_store",
        "message_queue",
        "identity_provider",
        "external_service",
        "repository_provider",
        "ci_cd_system",
        "secrets_manager",
        "object_storage",
        "administrative_interface",
        # Used by the ForgeFlow scenario and absent from section 11.
        "web_application",
        "managed_database",
        "managed_cache",
        "managed_storage",
        "managed_security_service",
        "internal_application",
    }
)


class Component(DomainModel):
    """A technical or logical part of the reviewed system (section 11)."""

    id: ComponentId
    assessment_id: AssessmentId

    name: str = Field(min_length=1)
    component_type: VocabularyTerm
    """What kind of thing this is. Open vocabulary; see `KNOWN_COMPONENT_TYPES`."""

    description: str | None = None
    technology: list[str] = Field(default_factory=list)
    ownership: str | None = None
    deployment_zone: str | None = None

    internet_accessible: bool | None = None
    """Documented exposure. `None` means the documentation does not say, which is not `False`."""

    externally_managed: bool | None = None
    """Whether another party runs it. `None` means the documentation does not say."""

    data_classifications: list[str] = Field(default_factory=list)
    authentication_mechanisms: list[str] = Field(default_factory=list)
    authorization_mechanisms: list[str] = Field(default_factory=list)
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    status: ObjectStatus
