"""What the Requirement and Control Mapping agent returns, and the promotions that own it.

The same boundary as `threat_analysis.py`, applied to two objects: `id`, `assessment_id`,
`generated_by`, `reviewer_status`, `status`, `validation_status`, and `created_at` have no field
here, and `extra="forbid"` makes a payload carrying one a validation error rather than a dropped
key.

**Controls are proposed by local key; everything else is an identifier.** This is the one place the
mapping step needs both. Threats, requirements, evidence, components, and assets already exist and
are supplied in the input package, so they are referenced by identifier. A control the mapper
*finds described* does not exist yet, so it is proposed with a local key that the mapping
referencing it uses — the same arrangement `ContextExtractionProposal` uses, and for the same
reason DEC-018 gives: an agent-chosen `ctl-001` could collide with a record that already exists.

**The schema keeps the rules the domain objects keep.** A proposed mapping is validated by
`ControlMapping`'s own validators at promotion, so an unevidenced `satisfied` fails there. It is
also checked here, before promotion, so the agent gets feedback naming the mapping rather than a
promotion traceback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import Field

from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.control import Control, ControlType, ImplementationStatus
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, Severity, ValidationStatus
from trace_ai.domain.identifiers import (
    AssetId,
    ComponentId,
    EvidenceReferenceId,
    RequirementId,
    ThreatId,
)
from trace_ai.domain.proposals.context_extraction import LocalKey, ProposalError

if TYPE_CHECKING:
    from collections.abc import Mapping, Set
    from datetime import datetime

    from trace_ai.domain.identifiers import (
        AssessmentId,
        ControlId,
        ControlMappingId,
        DocumentationGapId,
    )

__all__ = [
    "MAPPING_AGENT",
    "ControlProposal",
    "DocumentationGapProposal",
    "MappingProposal",
    "RequirementMappingProposal",
    "promote_control",
    "promote_documentation_gap",
    "promote_mapping",
]

# The agent version `agent-design.md` section 33 names for the mapping step.
MAPPING_AGENT: Final = "mapping-v1"


class ControlProposal(DomainModel):
    """A control the mapper found described (section 18, minus what the application owns).

    Carries a `key` rather than an identifier, because this control does not exist yet. Carries no
    `validation_status`: whether the evidence supports the control is the Evidence Validation
    step's answer, not this agent's.
    """

    key: LocalKey
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    control_type: ControlType

    provider_component_id: ComponentId | None = None
    protected_component_ids: list[ComponentId] = Field(default_factory=list)
    protected_asset_ids: list[AssetId] = Field(default_factory=list)

    implementation_status: ImplementationStatus
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    owner: str | None = None
    limitations: list[str] = Field(default_factory=list)


class RequirementMappingProposal(DomainModel):
    """One threat-requirement mapping (section 19, minus what the application owns)."""

    threat_id: ThreatId
    requirement_id: RequirementId

    control_keys: list[LocalKey] = Field(default_factory=list)
    """Controls proposed in the same response. Resolved to identifiers at promotion."""

    existing_control_ids: list[str] = Field(default_factory=list)
    """Controls that already exist, referenced by identifier. Separate from `control_keys` so a
    key and an identifier cannot be confused for one another in a single list."""

    applicability_status: ApplicabilityStatus
    applicability_reason: str = Field(min_length=1)

    suppressed_conclusion: str | None = None
    suppressed_by: str | None = None

    satisfaction_status: SatisfactionStatus
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel


class DocumentationGapProposal(DomainModel):
    """A gap candidate the mapper raised (section 23, minus what the application owns).

    `agent-design.md` section 12 lists "DocumentationGap candidates" among this agent's outputs, so
    the object is produced here rather than at finding consolidation. What the schema *omits* is
    the point: no recommendation, no impact, no validation status, and no way to say a control is
    absent. A gap records that Trace could not determine whether a control exists (section 23), and
    a proposal shape that could express more than that would let the DEC-009 collapse happen at the
    boundary rather than downstream of it.

    `severity` is present and rates the gap, not a weakness (DEC-045). Unlike `Finding.severity` it
    is the agent's to propose, because no checkpoint ever asks a reviewer for a gap's severity.
    """

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    importance: str = Field(min_length=1)

    related_object_ids: list[str] = Field(default_factory=list)
    requested_evidence: list[str] = Field(default_factory=list)
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)

    severity: Severity


class MappingProposal(DomainModel):
    """One model response: the controls found, the mappings drawn, and the gaps raised.

    An empty `mappings` list is valid for the same reason an empty threat list is: a requirement
    that does not apply to any threat in scope produces nothing, and a schema demanding output
    would be asking for mappings to exist.
    """

    controls: list[ControlProposal] = Field(default_factory=list)
    mappings: list[RequirementMappingProposal] = Field(default_factory=list)
    documentation_gaps: list[DocumentationGapProposal] = Field(default_factory=list)

    def validate_references(self, available: Set[str]) -> None:
        """Every identifier a mapping names must be one the input package supplied.

        Local keys are excluded: they are resolved against `controls` by `validate_keys`, which is
        a different failure with a different correction.
        """
        unknown: dict[int, list[str]] = {}
        for position, mapping in enumerate(self.mappings):
            referenced = [
                mapping.threat_id,
                mapping.requirement_id,
                *mapping.existing_control_ids,
                *mapping.evidence_ids,
            ]
            missing = sorted({value for value in referenced if value not in available})
            if missing:
                unknown[position] = missing

        for position, control in enumerate(self.controls):
            referenced = [
                *([control.provider_component_id] if control.provider_component_id else []),
                *control.protected_component_ids,
                *control.protected_asset_ids,
                *control.evidence_ids,
            ]
            missing = sorted({value for value in referenced if value not in available})
            if missing:
                unknown[-1 - position] = missing

        # A gap's `related_object_ids` is checked here rather than on `DocumentationGap`, because
        # only the caller knows what the assessment contains. The model checks the identifiers are
        # well formed; this checks they name something that was supplied.
        offset = -1 - len(self.controls)
        for position, gap in enumerate(self.documentation_gaps):
            referenced = [*gap.related_object_ids, *gap.evidence_ids]
            missing = sorted({value for value in referenced if value not in available})
            if missing:
                unknown[offset - position] = missing

        if unknown:
            raise ProposalError(
                f"these identifiers were not in the input package: "
                f"{sorted({value for values in unknown.values() for value in values})}. A mapping "
                f"may only reference threats, requirements, controls, and evidence it was given."
            )

    def validate_keys(self) -> None:
        """Every `control_keys` entry names a control proposed in the same response."""
        proposed = {control.key for control in self.controls}
        duplicates = sorted(
            {key for key in proposed if [c.key for c in self.controls].count(key) > 1}
        )
        if duplicates:
            raise ProposalError(f"these control keys are used twice in one response: {duplicates}")

        unresolved = sorted(
            {
                key
                for mapping in self.mappings
                for key in mapping.control_keys
                if key not in proposed
            }
        )
        if unresolved:
            raise ProposalError(
                f"these control keys are referenced by a mapping and proposed by nothing: "
                f"{unresolved}. A key names a control in the same response; a control that "
                f"already exists is referenced by identifier in existing_control_ids."
            )


def promote_control(
    proposal: ControlProposal,
    *,
    control_id: ControlId,
    assessment_id: AssessmentId,
    generated_by: str = MAPPING_AGENT,
    created_at: datetime | None = None,
) -> Control:
    """Turn a proposed control into one the application owns.

    `validation_status` is `not_evaluated` and is not a parameter. Whether the cited evidence
    actually supports the control is the Evidence Validation step's answer, and a promotion that
    could set it would be answering that question before it was asked.
    """
    payload = proposal.model_dump()
    payload.pop("key")
    return Control.model_validate(
        {
            **payload,
            "id": control_id,
            "assessment_id": assessment_id,
            "validation_status": ValidationStatus.NOT_EVALUATED,
            "generated_by": generated_by,
            "created_at": created_at if created_at is not None else now(),
            "status": ObjectStatus.CANDIDATE,
        }
    )


def promote_documentation_gap(
    proposal: DocumentationGapProposal,
    *,
    gap_id: DocumentationGapId,
    assessment_id: AssessmentId,
    generated_by: str = MAPPING_AGENT,
) -> DocumentationGap:
    """Turn a proposed gap into one the application owns.

    `status` is `candidate` and is not a parameter, for the same reason `promote_threat` fixes it:
    an agent that could propose `approved` would be approving its own work (DEC-005).
    """
    return DocumentationGap.model_validate(
        {
            **proposal.model_dump(),
            "id": gap_id,
            "assessment_id": assessment_id,
            "generated_by": generated_by,
            "status": ObjectStatus.CANDIDATE,
        }
    )


def promote_mapping(
    proposal: RequirementMappingProposal,
    *,
    mapping_id: ControlMappingId,
    assessment_id: AssessmentId,
    control_ids: Mapping[str, str],
    generated_by: str = MAPPING_AGENT,
) -> ControlMapping:
    """Turn a proposed mapping into one the application owns.

    `control_ids` maps each local key to the identifier its control was allocated. A key with no
    entry stops the promotion by name rather than producing a mapping pointing at nothing.
    """
    payload = proposal.model_dump()
    keys = payload.pop("control_keys")
    existing = payload.pop("existing_control_ids")

    resolved: list[str] = []
    for key in keys:
        if key not in control_ids:
            raise ProposalError(
                f"control key {key!r} was not allocated an identifier. Conversion refuses before "
                f"allocating anything when a key is unresolved (DEC-018)."
            )
        resolved.append(control_ids[key])

    return ControlMapping.model_validate(
        {
            **payload,
            "id": mapping_id,
            "assessment_id": assessment_id,
            "control_ids": [*resolved, *existing],
            "generated_by": generated_by,
            "reviewer_status": ObjectStatus.CANDIDATE,
        }
    )
