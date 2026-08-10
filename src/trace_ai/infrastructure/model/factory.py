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

from typing import TYPE_CHECKING

from trace_ai.infrastructure.model.fake import DeterministicModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic import BaseModel

    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.infrastructure.model.seam import StructuredModel

__all__ = ["UnknownProviderError", "build_model"]


class UnknownProviderError(ValueError):
    """A profile naming a provider no adapter implements."""

    def __init__(self, provider: str, known: Sequence[str]) -> None:
        super().__init__(
            f"no adapter implements provider {provider!r}. Known providers: {', '.join(known)}. "
            f"Adding one means adding an adapter behind the seam and a branch in build_model "
            f"(DEC-014)."
        )
        self.provider = provider


def build_model(profile: ModelProfile, *, responses: Sequence[BaseModel] = ()) -> StructuredModel:
    """The model this profile names.

    `responses` are the queued outcomes for the fake provider and are ignored by a real one — a
    recorded run is a property of the profile, not of the call site, and a caller that could feed
    responses to a live provider would be a caller that could silently stop calling it.
    """
    if profile.provider == "fake":
        return DeterministicModel(responses, name=profile.model)
    if profile.provider == "anthropic":
        from trace_ai.infrastructure.model.anthropic_adapter import AnthropicModel

        return AnthropicModel(profile.name)
    raise UnknownProviderError(profile.provider, ("anthropic", "fake"))
