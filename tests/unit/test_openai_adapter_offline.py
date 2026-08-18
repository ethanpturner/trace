"""The OpenAI adapter's provider-specific behaviour, behind a stub client (DEC-095, #539).

The cross-provider contract lives in `test_adapter_conformance.py`; this file holds what is
this provider's alone: the Responses API request shape, the creativity-to-`reasoning.effort`
mapping, the non-strict schema format and its `json_object` fallback, the refusal part, and
the disjointing of an `input_tokens` figure that includes the cached span (DEC-067).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest
from pydantic import BaseModel, ConfigDict

from trace_ai.infrastructure.model.openai_adapter import (
    REASONING_EFFORT_BY_CREATIVITY,
    OpenAIModel,
)
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.seam import (
    Creativity,
    FailureReason,
    GenerationSettings,
    ModelCapability,
    ModelFailure,
    ModelSuccess,
)


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class _Responses:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _Client:
    def __init__(self, *outcomes: object) -> None:
        self.responses = _Responses(list(outcomes))

    def with_options(self, *, timeout: float) -> _Client:
        return self


def _response(
    text: str | None,
    *,
    status: str = "completed",
    incomplete_reason: str | None = None,
    refusal: str | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cached_tokens: int = 0,
) -> SimpleNamespace:
    content: list[SimpleNamespace] = []
    if refusal is not None:
        content.append(SimpleNamespace(type="refusal", refusal=refusal))
    if text is not None:
        content.append(SimpleNamespace(type="output_text", text=text))
    return SimpleNamespace(
        model="gpt-5.1",
        status=status,
        incomplete_details=(
            SimpleNamespace(reason=incomplete_reason) if incomplete_reason is not None else None
        ),
        output=[SimpleNamespace(type="message", content=content)],
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
        ),
    )


def _adapter(*outcomes: object) -> tuple[OpenAIModel, _Client]:
    client = _Client(*outcomes)
    return OpenAIModel("openai-experimental", client=client), client


@pytest.mark.parametrize("creativity", list(REASONING_EFFORT_BY_CREATIVITY))
def test_the_request_carries_the_reasoning_effort_for_each_creativity(
    creativity: Creativity,
) -> None:
    adapter, client = _adapter(_response('{"name": "ok"}'))
    outcome = adapter.generate(
        prompt="p", schema=_Schema, settings=GenerationSettings(creativity=creativity)
    )
    assert isinstance(outcome, ModelSuccess)
    request = client.responses.requests[0]
    assert request["reasoning"] == {"effort": REASONING_EFFORT_BY_CREATIVITY[creativity]}
    assert outcome.metadata["effort"] == REASONING_EFFORT_BY_CREATIVITY[creativity]


def test_the_schema_is_requested_non_strict() -> None:
    """Strict mode requires every key required and rewrites optionals as explicit nulls — a
    shape the proposals' defaulted fields would then fail to validate. Guidance, not grammar;
    the adapter validates the text itself either way."""
    adapter, client = _adapter(_response('{"name": "ok"}'))
    adapter.generate(prompt="p", schema=_Schema, settings=GenerationSettings())
    fmt = client.responses.requests[0]["text"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["strict"] is False
    assert fmt["schema"] == _Schema.model_json_schema()


def test_a_schema_format_rejection_resends_as_json_object() -> None:
    """The rejection precedes the model — no tokens billed — so the resend is not a second
    attempt, and the degradation is recorded on the metadata rather than silent."""
    rejection = openai.BadRequestError(
        message="Invalid schema for response_format",
        response=httpx2.Response(
            400, request=httpx2.Request("POST", "https://api.openai.example/v1")
        ),
        body={"error": {"message": "Invalid schema for response_format"}},
    )
    adapter, client = _adapter(rejection, _response('{"name": "ok"}'))
    outcome = adapter.generate(prompt="p", schema=_Schema, settings=GenerationSettings())

    assert isinstance(outcome, ModelSuccess)
    assert outcome.metadata["schema_grammar"] == "unsupported_omitted"
    assert client.responses.requests[1]["text"] == {"format": {"type": "json_object"}}


def test_any_other_bad_request_stays_a_single_attempt() -> None:
    error = openai.BadRequestError(
        message="max_completion_tokens is too large",
        response=httpx2.Response(
            400, request=httpx2.Request("POST", "https://api.openai.example/v1")
        ),
        body=None,
    )
    adapter, client = _adapter(error)
    outcome = adapter.generate(prompt="p", schema=_Schema, settings=GenerationSettings())
    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.INVALID_REQUEST
    assert len(client.responses.requests) == 1


def test_a_refusal_is_a_refused_failure_carrying_the_refusal_text() -> None:
    adapter, _ = _adapter(_response(None, refusal="I cannot help with that."))
    outcome = adapter.generate(prompt="p", schema=_Schema, settings=GenerationSettings())
    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.REFUSED
    assert outcome.raw_output == "I cannot help with that."
    assert "I cannot help" not in outcome.message, "refusal text is untrusted model output"


def test_usage_subtracts_the_cached_span_to_stay_disjoint() -> None:
    """The provider's `prompt_tokens` includes the cached span; DEC-067 keeps the input spans
    disjoint, so the adapter subtracts and prices each span at its own rate."""
    adapter, _ = _adapter(
        _response('{"name": "ok"}', input_tokens=1000, output_tokens=10, cached_tokens=800)
    )
    outcome = adapter.generate(prompt="p", schema=_Schema, settings=GenerationSettings())
    assert isinstance(outcome, ModelSuccess)
    assert outcome.usage.input_tokens == 200
    assert outcome.usage.cache_read_tokens == 800
    assert outcome.usage.cache_creation_tokens == 0
    profile = resolve_profile("openai-experimental")
    assert outcome.usage.estimated_cost == profile.cost_of(
        input_tokens=200, output_tokens=10, cache_read_tokens=800, cache_creation_tokens=0
    )
    assert ModelCapability.PROMPT_CACHING in outcome.capabilities_used


def test_prompt_caching_is_not_reported_when_nothing_was_cached() -> None:
    adapter, _ = _adapter(_response('{"name": "ok"}'))
    outcome = adapter.generate(prompt="p", schema=_Schema, settings=GenerationSettings())
    assert isinstance(outcome, ModelSuccess)
    assert ModelCapability.PROMPT_CACHING not in outcome.capabilities_used


def test_a_cache_prefix_is_accepted_and_the_message_stays_plain() -> None:
    """The provider caches prefixes automatically; there is no marker to place, and a hint must
    not change the request."""
    adapter, client = _adapter(_response('{"name": "ok"}'))
    adapter.generate(
        prompt="stable prefix. variable tail",
        schema=_Schema,
        settings=GenerationSettings(),
        cache_prefix="stable prefix. ",
    )
    request = client.responses.requests[0]
    assert request["input"] == [{"role": "user", "content": "stable prefix. variable tail"}]


def test_a_system_cache_prefix_is_accepted_and_the_system_message_stays_plain() -> None:
    """DEC-105's hint has no marker on this provider either; the request is unchanged."""
    adapter, client = _adapter(_response('{"name": "ok"}'))
    adapter.generate(
        prompt="the prompt",
        schema=_Schema,
        settings=GenerationSettings(),
        system="catalog span. per-threat tail",
        system_cache_prefix="catalog span. ",
    )
    request = client.responses.requests[0]
    assert request["instructions"] == "catalog span. per-threat tail"


def test_the_system_region_is_its_own_message() -> None:
    adapter, client = _adapter(_response('{"name": "ok"}'))
    adapter.generate(
        prompt="p", schema=_Schema, settings=GenerationSettings(), system="the system region"
    )
    request = client.responses.requests[0]
    assert request["instructions"] == "the system region"


def test_a_profile_naming_another_provider_is_refused() -> None:
    with pytest.raises(ValueError, match="this adapter serves 'openai'"):
        OpenAIModel(resolve_profile("primary-development"))
