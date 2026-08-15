"""The six model-assisted agents, in one table (DEC-030, WS11).

Adding a proposal type used to touch five places that state the same facts with nothing asserting
they agree: `AGENT_BY_SCHEMA` (`factory.py`) and `RESPONSE_SCHEMAS` (`recorded.py`) both encode
which agent owns which schema, in two packages; `AGENT_NAMES` (`profiles.py`) is a third; and each
node declares its own prompt identifier and `Creativity` inline, which is exactly how context
extraction's creativity came to disagree with the other five before it was corrected. This table is
the single source those all derive from, so a rename or a seventh agent is one edit and a test
failure rather than a silent divergence.

The order is the pipeline order, which is the order `RESPONSE_SCHEMAS` presents. `tests/unit/
test_agents.py` pins the derivations against the node constants and the six-agent cap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.domain.proposals.critical_review import CriticalReviewProposal
from trace_ai.domain.proposals.evidence_validation import EvidenceValidationProposal
from trace_ai.domain.proposals.mapping import MappingProposal
from trace_ai.domain.proposals.report_sections import ReportSections
from trace_ai.domain.proposals.threat_analysis import ThreatAnalysisProposal
from trace_ai.infrastructure.model.seam import Creativity

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = ["AGENTS", "AgentSpec", "agent_for_schema", "spec_for"]


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """One model-assisted agent: the facts that used to be spread across five places."""

    name: str
    """The node-name spelling the workflow uses, e.g. `context-extraction`."""

    schema: type[BaseModel]
    """The proposal the agent returns. Mutually exclusive across agents by construction, which is
    how a call's schema identifies the agent making it (DEC-069) and how a recording's schema
    identifies which call it answers."""

    prompt_id: str
    prompt_version: str
    creativity: Creativity
    """`agent-design.md` section 29's intent, held here so a node cannot drift from it (DEC-085)."""


AGENTS: Final[tuple[AgentSpec, ...]] = (
    AgentSpec(
        name="context-extraction",
        schema=ContextExtractionProposal,
        prompt_id="extract-context",
        prompt_version="v1",
        creativity=Creativity.LOW,
    ),
    AgentSpec(
        name="threat-analysis",
        schema=ThreatAnalysisProposal,
        prompt_id="generate-scenario-threats",
        prompt_version="v1",
        creativity=Creativity.MODERATE,
    ),
    AgentSpec(
        name="requirement-and-control-mapping",
        schema=MappingProposal,
        prompt_id="map-requirements-controls",
        prompt_version="v1",
        creativity=Creativity.LOW,
    ),
    AgentSpec(
        name="evidence-validation",
        schema=EvidenceValidationProposal,
        prompt_id="validate-evidence",
        prompt_version="v1",
        creativity=Creativity.LOW,
    ),
    AgentSpec(
        name="critical-review",
        schema=CriticalReviewProposal,
        prompt_id="challenge-analysis",
        prompt_version="v1",
        creativity=Creativity.MODERATE,
    ),
    AgentSpec(
        name="report-generation",
        schema=ReportSections,
        prompt_id="generate-report-sections",
        prompt_version="v1",
        creativity=Creativity.LOW,
    ),
)

_BY_NAME: Final = {spec.name: spec for spec in AGENTS}
_BY_SCHEMA: Final = {spec.schema.__name__: spec for spec in AGENTS}


def spec_for(name: str) -> AgentSpec:
    """The spec for a node name, so a node reads its prompt and creativity from one place."""
    return _BY_NAME[name]


def agent_for_schema(schema_name: str) -> str | None:
    """The agent that owns a schema, or `None` for a schema no agent produces."""
    spec = _BY_SCHEMA.get(schema_name)
    return spec.name if spec is not None else None
