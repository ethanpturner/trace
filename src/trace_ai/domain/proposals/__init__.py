"""What an agent returns: proposed objects, and the metadata naming what produced them.

`agent-design.md` section 22 and DEC-006 both say the same thing from different sides — agents
propose, the application validates and persists. These schemas are that boundary: they carry no
identifier, no status, no approval, and no severity, so the rule is a property of the shape rather
than something a reviewer of the code has to remember.
"""

from trace_ai.domain.proposals.context_extraction import (
    ContextExtractionProposal,
    LocalKey,
    ProposalError,
    ProposedActor,
    ProposedAsset,
    ProposedComponent,
    ProposedContextClaim,
    ProposedDataFlow,
    ProposedObservation,
    ProposedQuestion,
    ProposedSystemContext,
    ProposedTrustBoundary,
)
from trace_ai.domain.proposals.conversion import ConvertedContext, convert_proposal
from trace_ai.domain.proposals.generation import CONTEXT_EXTRACTION_AGENT, GenerationMetadata
from trace_ai.domain.proposals.mapping import (
    MAPPING_AGENT,
    ControlProposal,
    DocumentationGapProposal,
    MappingProposal,
    RequirementMappingProposal,
    promote_control,
    promote_documentation_gap,
    promote_mapping,
)
from trace_ai.domain.proposals.threat_analysis import (
    THREAT_ANALYSIS_AGENT,
    ThreatProposal,
    promote_threat,
)

__all__ = [
    "CONTEXT_EXTRACTION_AGENT",
    "MAPPING_AGENT",
    "THREAT_ANALYSIS_AGENT",
    "ContextExtractionProposal",
    "ControlProposal",
    "ConvertedContext",
    "DocumentationGapProposal",
    "GenerationMetadata",
    "LocalKey",
    "MappingProposal",
    "ProposalError",
    "ProposedActor",
    "ProposedAsset",
    "ProposedComponent",
    "ProposedContextClaim",
    "ProposedDataFlow",
    "ProposedObservation",
    "ProposedQuestion",
    "ProposedSystemContext",
    "ProposedTrustBoundary",
    "RequirementMappingProposal",
    "ThreatProposal",
    "convert_proposal",
    "promote_control",
    "promote_documentation_gap",
    "promote_mapping",
    "promote_threat",
]
