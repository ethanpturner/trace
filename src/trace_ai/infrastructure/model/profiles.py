"""Model profiles: what `AssessmentConfiguration.model_profile` names.

`data-model.md` section 6 makes `model_profile` a required string and points it at nothing. DEC-014
says what it means: **a bundle of provider, model, and generation settings**, not a bare model
identifier. This module is that bundle.

`primary-development` is the default and resolves to the Anthropic adapter and `claude-opus-5`,
which DEC-014 names as the primary model. The other entries exist for the two things a profile is
actually used for — running the benchmark suite without a provider, and pinning a cheaper model for
a cost-sensitive pass — rather than to enumerate every model that exists.

**Prices are published rates held here, not returned by the provider.** They produce
`ModelUsage.estimated_cost`, which is why that field says estimated: it is a projection from a table
that can go stale between a rate change and someone editing this file. `evaluation-plan.md` section
3 requires the model and its configuration to be recorded with every run, and the profile name is
what records them.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Final

from trace_ai.infrastructure.model.seam import Creativity, GenerationSettings

__all__ = [
    "DEFAULT_PROFILE",
    "PROFILES",
    "ModelProfile",
    "UnknownModelProfileError",
    "resolve_profile",
]

# Tokens per unit of the published price. Rates are quoted per million tokens.
_PER_MILLION: Final = Decimal(1_000_000)


class UnknownModelProfileError(KeyError):
    """A configured `model_profile` names no profile.

    The message lists what is available, because the caller's next question is always "then what
    should it say", and an assessment configuration is hand-written.
    """

    def __init__(self, name: str) -> None:
        known = ", ".join(sorted(PROFILES))
        super().__init__(f"unknown model_profile {name!r}. Known profiles: {known}")
        self.name = name


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """A provider, a model, generation settings, and the limits that bound one call."""

    name: str
    provider: str
    """Which adapter serves it. `anthropic` is the only one implemented (DEC-014)."""

    model: str
    settings: GenerationSettings
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    cached_input_cost_per_million: Decimal
    """Cache reads are priced at a fraction of input. Separate because prompt caching is the
    capability DEC-014 kept the seam capability-aware for."""

    def cost_of(
        self, *, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0
    ) -> Decimal:
        """The estimated cost of one call, from this profile's published rates.

        `cached_input_tokens` is counted separately rather than as a discount on `input_tokens`,
        because the provider reports them as separate figures and adding them together would make a
        working cache indistinguishable from a broken one in the ledger.
        """
        return (
            Decimal(input_tokens) * self.input_cost_per_million
            + Decimal(output_tokens) * self.output_cost_per_million
            + Decimal(cached_input_tokens) * self.cached_input_cost_per_million
        ) / _PER_MILLION

    def with_creativity(self, creativity: Creativity) -> ModelProfile:
        """This profile with one agent's declared latitude (`agent-design.md` section 29).

        A profile carries the run's model and limits; creativity belongs to the agent. Returning a
        new profile rather than mutating keeps a node from changing the run's configuration for
        every node after it.
        """
        return replace(self, settings=replace(self.settings, creativity=creativity))


# The profiles that exist. Three, deliberately: the one every real run uses, one for a cheaper pass,
# and one that reaches no provider at all.
PROFILES: Final[dict[str, ModelProfile]] = {
    "primary-development": ModelProfile(
        name="primary-development",
        provider="anthropic",
        model="claude-opus-5",
        settings=GenerationSettings(creativity=Creativity.LOW),
        input_cost_per_million=Decimal("5.00"),
        output_cost_per_million=Decimal("25.00"),
        cached_input_cost_per_million=Decimal("0.50"),
    ),
    "economy": ModelProfile(
        name="economy",
        provider="anthropic",
        model="claude-sonnet-5",
        settings=GenerationSettings(creativity=Creativity.LOW),
        input_cost_per_million=Decimal("3.00"),
        output_cost_per_million=Decimal("15.00"),
        cached_input_cost_per_million=Decimal("0.30"),
    ),
    "offline-fake": ModelProfile(
        name="offline-fake",
        provider="fake",
        model="deterministic-fake",
        settings=GenerationSettings(creativity=Creativity.LOW),
        input_cost_per_million=Decimal(0),
        output_cost_per_million=Decimal(0),
        cached_input_cost_per_million=Decimal(0),
    ),
}

# What an `AssessmentConfiguration` means when nobody chose (DEC-014).
DEFAULT_PROFILE: Final = "primary-development"


def resolve_profile(name: str) -> ModelProfile:
    """The profile a configuration names, or an error saying what it could have named."""
    try:
        return PROFILES[name]
    except KeyError:
        raise UnknownModelProfileError(name) from None
