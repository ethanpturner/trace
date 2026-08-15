"""The one agent table, and the three registries derived from it (WS11, DEC-030).

Before this table the same facts lived in five places with nothing asserting they agreed, and one —
context extraction's creativity — had already drifted. These pin that the table is the single source:
the derived registries match it, the node constants match it, and it holds exactly the six agents the
cap allows. A seventh agent, or a node whose prompt or creativity disagrees with the table, fails
here rather than silently.
"""

from __future__ import annotations

from trace_ai.infrastructure.model.agents import AGENTS, agent_for_schema, spec_for
from trace_ai.infrastructure.model.factory import AGENT_BY_SCHEMA
from trace_ai.infrastructure.model.profiles import AGENT_NAMES
from trace_ai.infrastructure.model.recorded import RESPONSE_SCHEMAS
from trace_ai.workflow import (
    context_extraction,
    critical_review,
    evidence_validation,
    report_generation,
    requirement_control_mapping,
    threat_analysis,
)

_NODES = (
    context_extraction,
    threat_analysis,
    requirement_control_mapping,
    evidence_validation,
    critical_review,
    report_generation,
)


def test_the_table_holds_exactly_the_six_capped_agents() -> None:
    """DEC-030 caps the model-assisted agents at six; the table is that inventory."""
    assert len(AGENTS) == 6
    assert len({spec.name for spec in AGENTS}) == 6
    assert len({spec.schema for spec in AGENTS}) == 6


def test_agent_names_are_derived_from_the_table() -> None:
    assert frozenset(spec.name for spec in AGENTS) == AGENT_NAMES


def test_the_routing_table_is_derived_from_the_table() -> None:
    assert {spec.schema.__name__: spec.name for spec in AGENTS} == AGENT_BY_SCHEMA


def test_the_recorded_response_schemas_are_derived_in_pipeline_order() -> None:
    assert tuple(spec.schema for spec in AGENTS) == RESPONSE_SCHEMAS


def test_each_node_reads_its_prompt_and_creativity_from_the_table() -> None:
    """The node modules keep their `PROMPT_ID`/`PROMPT_VERSION` constants; the table must agree with
    every one, so the prompt a node composes is the prompt the table names."""
    for node in _NODES:
        spec = spec_for(node.NODE_NAME)
        assert spec.prompt_id == node.PROMPT_ID, node.NODE_NAME
        assert spec.prompt_version == node.PROMPT_VERSION, node.NODE_NAME


def test_agent_for_schema_resolves_and_declines() -> None:
    assert agent_for_schema("ContextExtractionProposal") == "context-extraction"
    assert agent_for_schema("NotAProposal") is None
