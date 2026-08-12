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

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Final

from trace_ai.infrastructure.model.seam import Creativity, GenerationSettings

__all__ = [
    "AGENT_NAMES",
    "DEFAULT_PROFILE",
    "PROFILES",
    "AgentOverlay",
    "ModelProfile",
    "UnknownModelProfileError",
    "resolve_profile",
]

# Tokens per unit of the published price. Rates are quoted per million tokens.
_PER_MILLION: Final = Decimal(1_000_000)

# The six model-assisted agents, by node name — the cap's inventory (DEC-030,
# `tests/unit/test_agent_cap.py`) in the spelling the workflow nodes use. Overlay keys are
# validated against this set when a profile is constructed (DEC-069): a misspelling, a
# deterministic node, or a seventh agent is a configuration error refused at load, not mid-run.
AGENT_NAMES: Final[frozenset[str]] = frozenset(
    {
        "context-extraction",
        "threat-analysis",
        "requirement-and-control-mapping",
        "evidence-validation",
        "critical-review",
        "report-generation",
    }
)


@dataclass(frozen=True, slots=True)
class AgentOverlay:
    """One agent's model-and-rates override inside a profile (DEC-069).

    The four rates are required alongside the model, never inherited: a substituted model priced
    at the base model's rates would make `estimated_cost` describe a call that never happened.
    `settings` overrides the profile's generation settings when given; `Creativity` stays the
    agent's own declared intent either way and is applied on top by the node.
    """

    model: str
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    cache_read_cost_per_million: Decimal
    cache_creation_cost_per_million: Decimal
    settings: GenerationSettings | None = None


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
    cache_read_cost_per_million: Decimal
    """Cache reads are priced at a fraction of input. Separate because prompt caching is the
    capability DEC-014 kept the seam capability-aware for."""

    cache_creation_cost_per_million: Decimal
    """Cache writes are priced at a premium over input (DEC-067). The profile owns the weight so
    `estimated_cost` stays a billed-equivalent number, not a raw token count."""

    max_input_characters: int = 400_000
    """A conservative ceiling on assembled input, in characters rather than tokens.

    Characters because the application cannot count a provider's tokens without asking it, and a
    budget that needs a network call to evaluate is one that cannot be enforced while assembling.
    Conservative because the consequence of being wrong is asymmetric: too low drops evidence and
    says which, too high produces a request the provider refuses after the assembly work is done.
    """

    agent_overlays: dict[str, AgentOverlay] = field(default_factory=dict)
    """Per-agent model-and-settings overrides (DEC-069). Optional; a profile without one behaves
    exactly as before. Keys are validated against `AGENT_NAMES` at construction — fail at load,
    never mid-run — and deterministic nodes make no model calls and can carry no override. No
    shipped profile routes agents to different models until the evaluation harness has measured
    what a cheaper model costs in quality; the mechanism lands so that measurement is a config
    edit rather than a design change."""

    def __post_init__(self) -> None:
        unknown = sorted(set(self.agent_overlays) - AGENT_NAMES)
        if unknown:
            known = ", ".join(sorted(AGENT_NAMES))
            raise ValueError(
                f"profile {self.name!r} carries overlays for {unknown}, which are not "
                f"model-assisted agents. The six agents are: {known} (DEC-069, DEC-030's cap). "
                f"A deterministic node makes no model calls and can carry no override."
            )

    def for_agent(self, agent_name: str) -> ModelProfile:
        """The bundle one agent's calls resolve to (DEC-069).

        Without an overlay for `agent_name` this is the profile itself. With one, the model, its
        rates, and optionally its settings are replaced, and the returned bundle carries no
        overlays of its own — the adapter sees one resolved bundle, exactly as before. The
        profile `name` is kept: attribution of *which model answered* rides
        `ExecutionRecord.model_name`, which snapshots the resolved model per call.
        """
        overlay = self.agent_overlays.get(agent_name)
        if overlay is None:
            return self
        return replace(
            self,
            model=overlay.model,
            input_cost_per_million=overlay.input_cost_per_million,
            output_cost_per_million=overlay.output_cost_per_million,
            cache_read_cost_per_million=overlay.cache_read_cost_per_million,
            cache_creation_cost_per_million=overlay.cache_creation_cost_per_million,
            settings=overlay.settings if overlay.settings is not None else self.settings,
            agent_overlays={},
        )

    def cost_of(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> Decimal:
        """The estimated cost of one call: DEC-067's weighted sum at this profile's rates.

        The cache spans are counted separately rather than folded into `input_tokens`, because
        the provider reports them as separate figures and adding them together would make a
        working cache indistinguishable from a broken one in the ledger. `input_tokens` here
        means uncached input at the full rate — the three input spans are disjoint.
        """
        return (
            Decimal(input_tokens) * self.input_cost_per_million
            + Decimal(output_tokens) * self.output_cost_per_million
            + Decimal(cache_read_tokens) * self.cache_read_cost_per_million
            + Decimal(cache_creation_tokens) * self.cache_creation_cost_per_million
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
        cache_read_cost_per_million=Decimal("0.50"),
        cache_creation_cost_per_million=Decimal("6.25"),
    ),
    "economy": ModelProfile(
        name="economy",
        provider="anthropic",
        model="claude-sonnet-5",
        settings=GenerationSettings(creativity=Creativity.LOW),
        input_cost_per_million=Decimal("3.00"),
        output_cost_per_million=Decimal("15.00"),
        cache_read_cost_per_million=Decimal("0.30"),
        cache_creation_cost_per_million=Decimal("3.75"),
    ),
    "offline-fake": ModelProfile(
        name="offline-fake",
        provider="fake",
        model="deterministic-fake",
        settings=GenerationSettings(creativity=Creativity.LOW),
        input_cost_per_million=Decimal(0),
        output_cost_per_million=Decimal(0),
        cache_read_cost_per_million=Decimal(0),
        cache_creation_cost_per_million=Decimal(0),
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
