"""DEC-069: per-agent model profile overlays — resolve at load, attribute per call.

Issue #344's acceptance criterion is attribution: a run with one overlaid agent records that
agent's model on its execution records and the base model everywhere else. The chain is asserted
end to end here with stub adapters — the router picks the adapter by response schema (the same
mutual-exclusivity `recorded.py` already relies on), the usage carries the answering model, and
`record_usage` stamps it onto the record.

Fail-at-load is the half DEC-069 says is worth writing down: an overlay naming anything but the
six agents is refused when the profile is constructed, never mid-run.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.domain.proposals.threat_analysis import ThreatAnalysisProposal
from trace_ai.infrastructure.model.factory import (
    AGENT_BY_SCHEMA,
    OverlayRoutingModel,
    build_model,
)
from trace_ai.infrastructure.model.profiles import (
    AGENT_NAMES,
    AgentOverlay,
    ModelProfile,
    resolve_profile,
)
from trace_ai.infrastructure.model.seam import (
    GenerationSettings,
    ModelSuccess,
    ModelUsage,
)

BASE = resolve_profile("primary-development")

ECONOMY_OVERLAY = AgentOverlay(
    model="claude-sonnet-5",
    input_cost_per_million=Decimal("3.00"),
    output_cost_per_million=Decimal("15.00"),
    cache_read_cost_per_million=Decimal("0.30"),
    cache_creation_cost_per_million=Decimal("3.75"),
)


def overlaid(**overlays: AgentOverlay) -> ModelProfile:
    return replace(BASE, agent_overlays=dict(overlays))


# ------------------------------------------------------------------------------------------
# Resolution (profiles.py)
# ------------------------------------------------------------------------------------------


def test_a_profile_without_an_overlay_resolves_to_itself() -> None:
    assert BASE.for_agent("threat-analysis") is BASE


def test_an_overlay_replaces_model_and_rates_and_clears_itself() -> None:
    profile = overlaid(**{"threat-analysis": ECONOMY_OVERLAY})
    resolved = profile.for_agent("threat-analysis")

    assert resolved.model == "claude-sonnet-5"
    assert resolved.input_cost_per_million == Decimal("3.00")
    assert resolved.cache_creation_cost_per_million == Decimal("3.75")
    assert resolved.name == BASE.name  # the profile name is the run's; the model is the call's
    assert resolved.agent_overlays == {}  # the adapter sees one resolved bundle
    # Every other agent resolves to the base bundle.
    assert profile.for_agent("critical-review").model == BASE.model


def test_an_overlay_never_touches_generation_settings() -> None:
    """DEC-094: an overlay names a model and its rates, nothing else. Settings stay the base
    profile's, and creativity stays the AGENTS table's, applied by the node (DEC-085)."""
    profile = overlaid(**{"threat-analysis": ECONOMY_OVERLAY})
    assert profile.for_agent("threat-analysis").settings == BASE.settings
    assert not hasattr(ECONOMY_OVERLAY, "settings")


def test_an_unknown_overlay_key_fails_at_load() -> None:
    """A misspelling, a deterministic node, or a seventh agent is refused at construction."""
    for bad in ("threat-analysys", "finding-consolidation", "severity-support"):
        with pytest.raises(ValueError, match="not model-assisted agents"):
            overlaid(**{bad: ECONOMY_OVERLAY})


def test_the_agent_names_are_the_caps_inventory_by_node_name() -> None:
    assert frozenset(AGENT_BY_SCHEMA.values()) == AGENT_NAMES
    assert len(AGENT_BY_SCHEMA) == 6  # six agents, capped (DEC-030)


# ------------------------------------------------------------------------------------------
# Routing and attribution (factory + ledger)
# ------------------------------------------------------------------------------------------


class _StubAdapter:
    """Answers as the model its profile names, so attribution is observable."""

    capabilities: frozenset[Any] = frozenset()

    def __init__(self, model: str) -> None:
        self.name = f"stub:{model}"
        self._model = model
        self.calls = 0

    def generate(self, **kwargs: Any) -> Any:
        self.calls += 1
        return ModelSuccess(
            value=kwargs["schema"].model_construct(),
            usage=ModelUsage(model=self._model, input_tokens=10, output_tokens=5),
        )


def router() -> tuple[OverlayRoutingModel, _StubAdapter, _StubAdapter]:
    base = _StubAdapter("claude-opus-5")
    economy = _StubAdapter("claude-sonnet-5")
    return (
        OverlayRoutingModel(base=base, by_agent={"threat-analysis": economy}),
        base,
        economy,
    )


def test_the_overlaid_agents_schema_routes_to_its_adapter() -> None:
    routing, base, economy = router()
    settings = GenerationSettings()

    threat = routing.generate(prompt="p", schema=ThreatAnalysisProposal, settings=settings)
    context = routing.generate(prompt="p", schema=ContextExtractionProposal, settings=settings)

    assert isinstance(threat, ModelSuccess)
    assert threat.usage.model == "claude-sonnet-5"
    assert context.usage.model == "claude-opus-5"
    assert economy.calls == 1
    assert base.calls == 1


def test_attribution_lands_on_the_execution_records(tmp_path: Any) -> None:
    """Issue #344's acceptance criterion, end to end through the ledger."""
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.execution_ledger import ExecutionLedger, start_run

    routing, _, _ = router()
    settings = GenerationSettings()

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Overlay", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        ledger = ExecutionLedger(handle, run)

        with ledger.record(
            "threat-analysis", node_version="0.1", execution_type=ExecutionType.MODEL
        ) as execution:
            outcome = routing.generate(prompt="p", schema=ThreatAnalysisProposal, settings=settings)
            execution.record_usage(outcome.usage)
        with ledger.record(
            "context-extraction", node_version="0.1", execution_type=ExecutionType.MODEL
        ) as execution:
            context_outcome = routing.generate(
                prompt="p", schema=ContextExtractionProposal, settings=settings
            )
            execution.record_usage(context_outcome.usage)

        by_node = {record.node_name: record for record in ledger.records()}
        assert by_node["threat-analysis"].model_name == "claude-sonnet-5"
        assert by_node["context-extraction"].model_name == "claude-opus-5"


def test_build_model_routes_only_when_an_overlay_exists() -> None:
    from trace_ai.infrastructure.model.anthropic_adapter import AnthropicModel

    plain = build_model(BASE)
    assert isinstance(plain, AnthropicModel)

    routed = build_model(overlaid(**{"threat-analysis": ECONOMY_OVERLAY}))
    assert isinstance(routed, OverlayRoutingModel)
    assert routed.name == plain.name if hasattr(plain, "name") else True


def test_the_fake_provider_ignores_overlays_and_stays_recorded() -> None:
    from trace_ai.infrastructure.model.fake import DeterministicModel

    fake = replace(
        resolve_profile("offline-fake"),
        agent_overlays={"threat-analysis": ECONOMY_OVERLAY},
    )
    assert isinstance(build_model(fake), DeterministicModel)
