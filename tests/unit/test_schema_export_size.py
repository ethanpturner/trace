"""A ceiling on each agent schema's wire export, so growth is a visible CI failure (WS11).

When the provider refuses a schema as too large for its output grammar, the adapter degrades to no
server-side enforcement and records `schema_grammar: too_large_omitted` — a real, silent loss of a
safety net. That degradation is only visible after the fact; this makes the cause visible before it:
a schema that grows materially trips a red check here, so the growth is a decision someone makes
rather than a threshold something crosses unnoticed. The ceilings sit above today's sizes with
headroom for SDK jitter; raise one deliberately when a schema legitimately grows, and re-check that
the grammar still compiles.
"""

from __future__ import annotations

import json

import anthropic
import pytest

from trace_ai.infrastructure.model.agents import AGENTS

# Current transform_schema sizes are roughly: context 16.2k, mapping 8.8k, evidence 5.5k,
# threat 4.7k, critical 3.1k, report 1.1k. Ceilings carry ~25% headroom over those.
_CEILINGS = {
    "ContextExtractionProposal": 20_000,
    "ThreatAnalysisProposal": 6_000,
    "MappingProposal": 11_000,
    "EvidenceValidationProposal": 7_000,
    "CriticalReviewProposal": 4_000,
    "ReportSections": 2_000,
}


@pytest.mark.parametrize("spec", AGENTS, ids=lambda spec: spec.schema.__name__)
def test_the_wire_schema_stays_under_its_ceiling(spec: object) -> None:
    schema = spec.schema  # type: ignore[attr-defined]
    size = len(json.dumps(anthropic.transform_schema(schema)))
    ceiling = _CEILINGS[schema.__name__]
    assert size <= ceiling, (
        f"{schema.__name__}'s wire schema is {size} characters, over its {ceiling} ceiling. "
        f"A larger schema risks the provider rejecting its output grammar (schema_grammar: "
        f"too_large_omitted); raise the ceiling deliberately if the growth is intended."
    )


def test_every_agent_schema_has_a_ceiling() -> None:
    assert {spec.schema.__name__ for spec in AGENTS} == set(_CEILINGS)
