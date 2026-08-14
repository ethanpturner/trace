"""Offline tests for the Anthropic adapter, driven through a stub client.

The adapter's contract is that every provider condition comes back as a `ModelFailure` — an
exception escaping `generate` would leave the execution ledger with a node that started and never
finished. The SDK's `messages.parse` breaks that contract from inside: it validates each text
block client-side and raises `pydantic.ValidationError` on text that does not fit the schema,
which is exactly the shape of a truncated or malformed response — the responses the adapter's
failure branches were written for. #395 records the gap; the adapter now owns the validation
step, and this file drives it with the non-conforming responses a live provider would need to be
coaxed into producing.

Nothing here reaches a provider. The stub client stands where `anthropic.Anthropic` would, which
is also what lets these tests assert the request shape — the effort mapping, the transformed
schema, adaptive thinking — that `agent-design.md` section 29 says the adapter's own tests cover.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import anthropic
import pytest
from pydantic import BaseModel

from trace_ai.infrastructure.model.anthropic_adapter import EFFORT_BY_CREATIVITY, AnthropicModel
from trace_ai.infrastructure.model.seam import (
    Creativity,
    FailureReason,
    GenerationSettings,
    ModelCapability,
    ModelFailure,
    ModelSuccess,
)


class Proposal(BaseModel):
    """A schema small enough that a test's non-conforming text is obviously non-conforming."""

    name: str


class _StubMessages:
    def __init__(self, outcome: object) -> None:
        self._outcome = outcome
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


class _StubClient:
    """Stands where `anthropic.Anthropic` would, and remembers what the adapter asked of it."""

    def __init__(self, outcome: object) -> None:
        self.messages = _StubMessages(outcome)
        self.timeout: float | None = None

    def with_options(self, *, timeout: float) -> _StubClient:
        self.timeout = timeout
        return self


def _response(text: str | None, *, stop_reason: str = "end_turn") -> SimpleNamespace:
    content = [] if text is None else [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(
        model="claude-opus-5",
        stop_reason=stop_reason,
        content=content,
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


def _generate(outcome: object, **overrides: Any) -> tuple[Any, _StubClient]:
    client = _StubClient(outcome)
    adapter = AnthropicModel("primary-development", client=client)
    settings = GenerationSettings(**overrides) if overrides else GenerationSettings()
    result = adapter.generate(prompt="the prompt", schema=Proposal, settings=settings)
    return result, client


@pytest.mark.parametrize("creativity", list(Creativity))
def test_the_request_carries_the_effort_for_each_creativity(creativity: Creativity) -> None:
    """Section 29's mapping, asserted where a wrong mapping would otherwise be invisible: every
    creativity value lands as its declared effort, with adaptive thinking alongside it."""
    _, client = _generate(_response('{"name": "x"}'), creativity=creativity)

    (request,) = client.messages.requests
    assert request["output_config"]["effort"] == EFFORT_BY_CREATIVITY[creativity]
    assert request["thinking"] == {"type": "adaptive"}


def test_the_request_sends_the_transformed_schema_the_sdk_would_send() -> None:
    """The adapter builds the wire request `messages.parse` would have built — the schema through
    the SDK's own `transform_schema`, merged into `output_config` — so owning the validation step
    changes what is parsed, never what is asked for."""
    _, client = _generate(_response('{"name": "x"}'), timeout_seconds=30.0)

    (request,) = client.messages.requests
    assert request["model"] == "claude-opus-5"
    assert request["messages"] == [{"role": "user", "content": "the prompt"}]
    assert request["output_config"]["format"] == {
        "type": "json_schema",
        "schema": anthropic.transform_schema(Proposal),
    }
    assert client.timeout == 30.0


def test_a_truncated_response_is_a_truncation_failure_with_the_raw_output() -> None:
    """The case #395 exists for: a `max_tokens` stop leaves text no schema can parse. The stop
    reason is checked before validation, so it reports as what happened — truncation — and the
    partial output survives for the person debugging it (data-model.md section 33)."""
    partial = '{"name": "tr'
    outcome, _ = _generate(_response(partial, stop_reason="max_tokens"))

    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.OUTPUT_TRUNCATED
    assert outcome.raw_output == partial
    assert outcome.usage.output_tokens == 50


def test_a_refusal_is_a_refused_failure() -> None:
    outcome, _ = _generate(_response(None, stop_reason="refusal"))

    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.REFUSED


def test_non_conforming_text_is_a_schema_failure_not_an_exception() -> None:
    """Valid JSON of the wrong shape returns through the seam rather than raising past it. The
    message stays safe (section 27): the model's text is untrusted, so the detail rides in
    `raw_output` and never in the message."""
    wrong_shape = '{"colour": "blue"}'
    outcome, _ = _generate(_response(wrong_shape))

    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.SCHEMA_VALIDATION_FAILURE
    assert outcome.raw_output == wrong_shape
    assert "blue" not in outcome.message


def test_invalid_json_is_a_schema_failure_not_an_exception() -> None:
    """The exact text that made the SDK's client-side parse raise `pydantic.ValidationError`."""
    not_json = "Here is the object you asked for: {"
    outcome, _ = _generate(_response(not_json))

    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.SCHEMA_VALIDATION_FAILURE
    assert outcome.raw_output == not_json


def test_a_response_with_no_text_block_is_a_schema_failure() -> None:
    outcome, _ = _generate(_response(None))

    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.SCHEMA_VALIDATION_FAILURE
    assert outcome.raw_output is None


def test_an_untransformable_schema_is_a_failure_not_an_exception() -> None:
    """`transform_schema` refuses an unconstrained sub-schema — `pydantic.JsonValue` emits one —
    with a `ValueError` that would otherwise escape `generate`. It comes back classified instead,
    and the request is never sent: the stub records no call. The schema incompatibility itself is
    a separate defect (#412); this pins only that the adapter's contract holds around it."""
    from pydantic import JsonValue

    class Claim(BaseModel):
        value: JsonValue

    client = _StubClient(_response('{"value": 1}'))
    adapter = AnthropicModel("primary-development", client=client)
    outcome = adapter.generate(prompt="p", schema=Claim, settings=GenerationSettings())

    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.INVALID_REQUEST
    assert "Claim" in outcome.message
    assert client.messages.requests == []


def test_a_valid_response_returns_the_parsed_object_with_its_conditions() -> None:
    """Success carries the object, the priced usage, and the effort the call actually ran at —
    the recording section 29 requires so a wrong mapping is checkable after the fact."""
    outcome, _ = _generate(_response('{"name": "x"}'), creativity=Creativity.MODERATE)

    assert isinstance(outcome, ModelSuccess)
    assert outcome.value == Proposal(name="x")
    assert outcome.metadata["effort"] == EFFORT_BY_CREATIVITY[Creativity.MODERATE]
    assert outcome.metadata["creativity"] == Creativity.MODERATE.value
    assert ModelCapability.STRUCTURED_OUTPUT in outcome.capabilities_used
    assert outcome.usage.estimated_cost > 0
