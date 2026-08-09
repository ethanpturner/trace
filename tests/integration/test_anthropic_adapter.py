"""The one test that reaches a provider, and the marker that keeps it from running by accident.

`pyproject.toml` deselects `integration` in `addopts`, so `uv run pytest` never runs this and CI
never needs a key. Run it deliberately:

    uv run pytest -m integration

What it proves is the part unit tests structurally cannot: that the request this adapter builds is
one the provider accepts, and that a real response carries the fields the execution ledger reads.
Everything else about the seam — routing, failure classification, cost arithmetic, cache keys — is
exercised offline against `DeterministicModel`.

It is one call, at the smallest settings that still produce a schema-validated object, because the
value here is the round trip rather than the content.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from trace_ai.config import MissingSettingError, get_settings
from trace_ai.infrastructure.model.anthropic_adapter import AnthropicModel
from trace_ai.infrastructure.model.seam import (
    Creativity,
    GenerationSettings,
    ModelSuccess,
)

pytestmark = pytest.mark.integration


class Colour(BaseModel):
    """A schema small enough that the response is about the round trip and nothing else."""

    name: str = Field(description="The colour named in the question, lowercased.")


def test_a_live_call_returns_a_validated_object() -> None:
    """One attempt, one validated object, and the usage the ledger needs.

    A skip rather than a failure when the key is unset: this file is opt-in, and a developer who
    opted in without a key wants to be told that, not to debug an assertion.
    """
    try:
        get_settings().require("anthropic_api_key")
    except MissingSettingError as error:
        pytest.skip(str(error))

    model = AnthropicModel("primary-development")
    outcome = model.generate(
        prompt="What colour is a clear midday sky? Answer with the colour only.",
        schema=Colour,
        settings=GenerationSettings(
            creativity=Creativity.LOW, max_output_tokens=2_000, timeout_seconds=120.0
        ),
    )

    assert isinstance(outcome, ModelSuccess), getattr(outcome, "message", outcome)
    assert outcome.value.name.strip().lower() == "blue"

    usage = outcome.usage
    assert usage.model.startswith("claude-")
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0
    assert usage.estimated_cost > 0
    assert usage.duration_seconds > 0

    # DEC-014: what the call actually used, recorded so an evaluation result is interpretable
    # against the conditions that produced it.
    assert outcome.metadata["effort"] == "high"
    assert outcome.capabilities_used <= model.capabilities
