"""The OpenAI adapter's one provider-reaching test, behind the same opt-in marker (DEC-095).

`pyproject.toml` deselects `integration` in `addopts`, so `uv run pytest` never runs this and CI
never needs a key. Run it deliberately:

    uv run pytest -m integration

What it proves is what the unit tests structurally cannot: that the request this adapter builds
is one the provider accepts, and that a real response carries the fields the execution ledger
reads. It is one call, at the smallest settings that still produce a schema-validated object.
No live OpenAI pipeline run has been measured; this round trip is the adapter's only live
evidence until one is.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from trace_ai.config import MissingSettingError, get_settings
from trace_ai.infrastructure.model.openai_adapter import OpenAIModel
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
        get_settings().require("openai_api_key")
    except MissingSettingError as error:
        pytest.skip(str(error))

    model = OpenAIModel("openai-experimental")
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
    assert usage.model.startswith("gpt-")
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0
    assert usage.estimated_cost > 0
    assert usage.duration_seconds > 0

    # DEC-014: what the call actually used, recorded so an evaluation result is interpretable
    # against the conditions that produced it.
    assert outcome.metadata["effort"] == "medium"
    assert outcome.capabilities_used <= model.capabilities
