"""The one place a provider is chosen.

DEC-014 puts provider code behind an adapter and has the application talk to a seam. That leaves a
question the seam does not answer — who decides which adapter — and `build_model` is the answer. It
is worth its own tests because it is the point at which "provider-agnostic" stops being an
aspiration: a caller that constructed `AnthropicModel` directly would be a second place the
provider is named, and the property would hold everywhere except where it matters.

`tests/unit/test_model_boundary.py` asserts the complementary half: no module but the adapter
imports `anthropic`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from trace_ai.infrastructure.model.factory import UnknownProviderError, build_model
from trace_ai.infrastructure.model.fake import DeterministicModel
from trace_ai.infrastructure.model.profiles import PROFILES, ModelProfile, resolve_profile
from trace_ai.infrastructure.model.seam import GenerationSettings, StructuredModel


def test_the_offline_profile_reaches_no_provider() -> None:
    """`current-architecture.md` section 5.1 wants the command line usable for repeatable
    evaluation and for demo recovery. Both need a run that reaches no provider, which is why the
    fake is a profile rather than a test hook."""
    model = build_model(resolve_profile("offline-fake"))

    assert isinstance(model, DeterministicModel)
    assert model.name == "deterministic-fake"


def test_the_anthropic_profiles_build_the_adapter() -> None:
    """Constructed without a key: the adapter holds the profile and builds its client lazily, so
    naming a provider is not the same as reaching one."""
    from trace_ai.infrastructure.model.anthropic_adapter import AnthropicModel

    for name in ("primary-development", "economy"):
        model = build_model(resolve_profile(name))
        assert isinstance(model, AnthropicModel)


def test_every_declared_profile_builds() -> None:
    """A profile naming a provider nothing implements would fail at the first model call, in a run
    that has already spent time on ingestion."""
    for name in PROFILES:
        assert isinstance(build_model(resolve_profile(name)), StructuredModel)


def test_an_unimplemented_provider_says_what_is_missing() -> None:
    invented = ModelProfile(
        name="invented",
        provider="a-provider-nobody-wrote",
        model="something",
        settings=GenerationSettings(),
        input_cost_per_million=Decimal(0),
        output_cost_per_million=Decimal(0),
        cached_input_cost_per_million=Decimal(0),
    )

    with pytest.raises(UnknownProviderError, match="a-provider-nobody-wrote"):
        build_model(invented)


def test_recorded_responses_reach_the_fake_and_nothing_else() -> None:
    """A caller that could feed responses to a live provider would be a caller that could silently
    stop calling it. The parameter is accepted for every profile and consumed by one."""
    from trace_ai.domain.proposals import ContextExtractionProposal

    proposal = ContextExtractionProposal.model_validate({"system": {"system_name": "ForgeFlow"}})
    fake = build_model(resolve_profile("offline-fake"), responses=[proposal])

    outcome = fake.generate(
        prompt="anything", schema=ContextExtractionProposal, settings=GenerationSettings()
    )
    assert getattr(outcome, "value", None) is proposal

    live = build_model(resolve_profile("primary-development"), responses=[proposal])
    assert not isinstance(live, DeterministicModel)
