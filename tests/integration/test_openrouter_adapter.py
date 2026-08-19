"""The OpenRouter path's one provider-reaching test, behind the same opt-in marker (DEC-135).

`pyproject.toml` deselects `integration` in `addopts`, so `uv run pytest` never runs this and CI
never needs a key. Run it deliberately:

    uv run pytest -m integration

What it proves is what the unit tests structurally cannot: that the gateway's beta Responses
endpoint accepts the request this adapter builds — including a reasoning effort the routed model
does not natively list, which the gateway normalizes rather than rejects — and that a real
response carries the fields the execution ledger reads. It is one call, at the smallest settings
that still produce a schema-validated object. No live OpenRouter pipeline run has been measured;
this round trip is the path's only live evidence until a capture or comparison run produces more.
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

    name: str = Field(description="The colour named in the instruction, exactly as written.")


def test_a_live_gateway_call_returns_a_validated_object() -> None:
    """One attempt, one validated object, and the usage the ledger needs.

    A skip rather than a failure when the key is unset: this file is opt-in, and a developer who
    opted in without a key wants to be told that, not to debug an assertion.
    """
    try:
        get_settings().require("openrouter_api_key")
    except MissingSettingError as error:
        pytest.skip(str(error))

    model = OpenAIModel("openrouter-economy")
    outcome = model.generate(
        # A copy task rather than a knowledge question: the profile names a floor-cost model,
        # and this test proves the wire round trip, not the model's general knowledge.
        prompt='The colour is "blue". Fill in the schema with that colour.',
        schema=Colour,
        settings=GenerationSettings(
            creativity=Creativity.LOW, max_output_tokens=2_000, timeout_seconds=120.0
        ),
    )

    assert isinstance(outcome, ModelSuccess), getattr(outcome, "message", outcome)
    assert outcome.value.name.strip().lower() == "blue"

    usage = outcome.usage
    assert usage.model == "openai/gpt-5.1", "the gateway must route the named model"
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0
    assert usage.estimated_cost > 0
    assert usage.duration_seconds > 0

    # DEC-014: what the call actually used, recorded so an evaluation result is interpretable
    # against the conditions that produced it. The effort is what was *requested*; the gateway
    # normalizes it to the nearest level the routed model supports (DEC-135). The schema format
    # must be honored, not silently degraded — a first live call that fell back to `json_object`
    # would mean every pipeline call pays the degradation.
    assert outcome.metadata["effort"] == "medium"
    assert outcome.metadata["schema_grammar"] == "requested"
    assert outcome.capabilities_used <= model.capabilities
