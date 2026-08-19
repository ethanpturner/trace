"""Building the model a profile names, which is the one place a provider is chosen.

DEC-014 makes the application talk to a seam and puts provider code in an adapter behind it. That
leaves one question the seam does not answer: who decides which adapter. A caller that constructed
`AnthropicModel` directly would be a second place the provider is named, and the seam would be
agnostic everywhere except at the point where it matters.

**`provider` on the profile is the switch, and there is nothing else.** Adding a provider means
adding an adapter and a branch here, and nothing else in the application changes — which is the
property "provider-agnostic" is supposed to mean and the only way to check it.

**The fake is a first-class provider, not a test hook.** `offline-fake` names `provider="fake"`,
and `current-architecture.md` section 5.1 wants the command line usable for repeatable evaluation
and for demo recovery. Both need a run that reaches no provider, so replaying recorded responses is
a supported way to run the pipeline rather than something only tests do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.infrastructure.model.agents import AGENTS
from trace_ai.infrastructure.model.fake import DeterministicModel

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from pydantic import BaseModel

    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.infrastructure.model.recorded import RecordedResponse
    from trace_ai.infrastructure.model.seam import (
        GenerationSettings,
        ModelCapability,
        ModelOutcome,
        StructuredModel,
    )

__all__ = ["AGENT_BY_SCHEMA", "OverlayRoutingModel", "UnknownProviderError", "build_model"]

# Which agent a response schema belongs to. The schemas are mutually exclusive by construction —
# `infrastructure/model/recorded.py` already relies on exactly that to infer a recording's agent —
# so the schema a call asks for identifies the agent making it, and DEC-069's per-agent routing
# needs no new parameter on the seam. Derived from the one `AGENTS` table (WS11) rather than
# restated, so it cannot disagree with the recorded-response schemas or the node prompts.
AGENT_BY_SCHEMA: Final[Mapping[str, str]] = {spec.schema.__name__: spec.name for spec in AGENTS}


class UnknownProviderError(ValueError):
    """A profile naming a provider no adapter implements."""

    def __init__(self, provider: str, known: Sequence[str]) -> None:
        super().__init__(
            f"no adapter implements provider {provider!r}. Known providers: {', '.join(known)}. "
            f"Adding one means adding an adapter behind the seam and a branch in build_model "
            f"(DEC-014)."
        )
        self.provider = provider


@dataclass(frozen=True, slots=True)
class OverlayRoutingModel:
    """DEC-069's routing, behind the seam: one resolved adapter per overlaid agent.

    Resolution happened in `profiles.py` (`for_agent`) before anything here was built, so every
    adapter this holds sees one resolved bundle. A schema no overlay's agent asks for goes to the
    base adapter, and a schema outside `AGENT_BY_SCHEMA` — nothing in the pipeline produces one —
    goes there too rather than failing a call configuration already accepted.
    """

    base: StructuredModel
    by_agent: Mapping[str, StructuredModel]

    @property
    def name(self) -> str:
        return self.base.name

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        return self.base.capabilities

    def generate[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings | None = None,
        system: str | None = None,
        cache_prefix: str | None = None,
        system_cache_prefix: str | None = None,
    ) -> ModelOutcome[T]:
        agent = AGENT_BY_SCHEMA.get(schema.__name__)
        model = self.by_agent.get(agent, self.base) if agent is not None else self.base
        return model.generate(
            prompt=prompt,
            schema=schema,
            settings=settings,
            system=system,
            cache_prefix=cache_prefix,
            system_cache_prefix=system_cache_prefix,
        )


def build_model(
    profile: ModelProfile, *, responses: Sequence[BaseModel | RecordedResponse] = ()
) -> StructuredModel:
    """The model this profile names.

    `responses` are the queued outcomes for the fake provider and are ignored by a real one — a
    recorded run is a property of the profile, not of the call site, and a caller that could feed
    responses to a live provider would be a caller that could silently stop calling it.

    A profile carrying agent overlays (DEC-069) builds one adapter per distinct resolved bundle,
    wrapped in `OverlayRoutingModel`; a profile without one builds exactly what it always did.
    The fake provider replays recorded responses in order and reaches no provider, so an overlay
    changes nothing it does — recorded runs stay recorded runs.
    """
    if profile.provider == "fake":
        return DeterministicModel(responses, name=profile.model)
    if profile.provider == "anthropic":
        from trace_ai.infrastructure.model.anthropic_adapter import AnthropicModel

        if profile.agent_overlays:
            return OverlayRoutingModel(
                base=AnthropicModel(profile),
                by_agent={
                    agent: AnthropicModel(profile.for_agent(agent))
                    for agent in profile.agent_overlays
                },
            )
        # The profile object, not its name: passing the name re-resolves it from the global
        # registry, which reverts an ad-hoc profile (one built with `replace(...)` or
        # `with_creativity(...)`) to whatever the registry holds under that name -- or raises
        # `UnknownModelProfileError` if the name is not registered at all.
        return AnthropicModel(profile)
    if profile.provider in ("openai", "openrouter"):
        # One branch, two provider names (DEC-135): OpenRouter is OpenAI-compatible and the
        # adapter resolves the base URL and key from the provider itself.
        from trace_ai.infrastructure.model.openai_adapter import OpenAIModel

        if profile.agent_overlays:
            return OverlayRoutingModel(
                base=OpenAIModel(profile),
                by_agent={
                    agent: OpenAIModel(profile.for_agent(agent)) for agent in profile.agent_overlays
                },
            )
        return OpenAIModel(profile)
    raise UnknownProviderError(profile.provider, ("anthropic", "openai", "openrouter", "fake"))
