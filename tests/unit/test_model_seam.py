"""Tests for the model seam: settings, results, profiles, and the deterministic substitute.

Nothing here reaches a provider, and that is the property the file exists to demonstrate rather
than to assert in passing: `current-architecture.md` section 9 lists test substitutes as a required
capability of the abstraction, and `pyproject.toml` deselects the `integration` marker so a bare
`uv run pytest` cannot spend money.

Two design decisions carry most of the weight.

**An adapter returns failures rather than raising** (DEC-014). A failure is a result with a cost and
a duration, and the caller needs both — an exception would leave the execution ledger with a node
that started and never finished.

**A schema failure keeps the raw output.** `data-model.md` section 33 requires it be preserved for
debugging, and it is the one place model text survives validation.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest
from pydantic import BaseModel

from trace_ai.infrastructure.model import (
    DEFAULT_PROFILE,
    PROFILES,
    Creativity,
    DeterministicModel,
    FailureReason,
    GenerationSettings,
    ModelCapability,
    ModelFailure,
    ModelSuccess,
    ModelUsage,
    ResponsesExhaustedError,
    StructuredModel,
    UnknownModelProfileError,
    resolve_profile,
)


class Proposal(BaseModel):
    """A stand-in for an agent's proposal object."""

    summary: str
    confidence: str = "low"


class OtherShape(BaseModel):
    value: int


# --------------------------------------------------------------------------------------------
# Generation settings
# --------------------------------------------------------------------------------------------


def test_the_default_creativity_is_the_conservative_one() -> None:
    """`agent-design.md` section 29 assigns Low to Context Extraction, Requirement Mapping, and
    Evidence Validation — three of the six agents, and the first one built."""
    assert GenerationSettings().creativity is Creativity.LOW


def test_the_creativity_vocabulary_is_section_twenty_nine_s() -> None:
    """Three values, because the section 29 table uses three."""
    assert [value.value for value in Creativity] == ["low", "moderate"]


def test_settings_name_no_sampling_parameter() -> None:
    """DEC-014: creativity is provider-neutral intent, not a knob. A seam carrying `temperature`
    would be one provider's interface wearing a neutral name — and `temperature` is rejected
    outright on the current Anthropic models."""
    fields = set(GenerationSettings.__dataclass_fields__)
    assert not fields & {"temperature", "top_p", "top_k", "effort", "thinking"}


@pytest.mark.parametrize(
    "change", [{"max_output_tokens": 0}, {"max_output_tokens": -1}, {"timeout_seconds": 0}]
)
def test_settings_that_could_not_produce_a_call_are_rejected(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        GenerationSettings(**change)  # type: ignore[arg-type]


def test_settings_are_frozen() -> None:
    """A node that adjusted the run's settings in place would change them for every node after."""
    with pytest.raises(FrozenInstanceError):
        GenerationSettings().creativity = Creativity.MODERATE  # type: ignore[misc]


# --------------------------------------------------------------------------------------------
# Outcomes
# --------------------------------------------------------------------------------------------


def test_a_failure_carries_the_raw_output() -> None:
    """Section 33 requires an invalid output be preserved rather than discarded. This is the
    assertion that keeps it from being dropped as noise by someone tidying a failure path."""
    failure = ModelFailure(
        reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
        message="did not validate",
        usage=ModelUsage(model="m"),
        raw_output='{"summary": ',
    )
    assert failure.raw_output == '{"summary": '
    assert not failure.succeeded


@pytest.mark.parametrize(
    "reason",
    [
        FailureReason.SCHEMA_VALIDATION_FAILURE,
        FailureReason.TRANSIENT_PROVIDER_FAILURE,
        FailureReason.TIMEOUT,
        FailureReason.CONNECTION_FAILURE,
    ],
)
def test_a_condition_of_the_moment_is_retryable(reason: FailureReason) -> None:
    assert ModelFailure(reason=reason, message="", usage=ModelUsage(model="m")).retryable


@pytest.mark.parametrize(
    "reason",
    [
        FailureReason.REFUSED,
        FailureReason.INVALID_REQUEST,
        FailureReason.AUTHENTICATION_FAILURE,
        FailureReason.OUTPUT_TRUNCATED,
    ],
)
def test_a_statement_about_the_request_is_not_retryable(reason: FailureReason) -> None:
    """The same call refuses again, is malformed again, and is unauthorized again. Truncation is
    here too: retrying an identical request with the same ceiling truncates identically."""
    assert not ModelFailure(reason=reason, message="", usage=ModelUsage(model="m")).retryable


def test_a_result_reports_the_fields_the_ledger_needs() -> None:
    """`data-model.md` sections 26 and 27 want tokens, cost, and duration; collecting them here is
    what stops a caller reaching into a provider response."""
    usage = ModelUsage(
        model="claude-opus-5",
        input_tokens=1_000,
        output_tokens=500,
        estimated_cost=Decimal("0.0175"),
        duration_seconds=2.5,
    )
    success = ModelSuccess(value=Proposal(summary="ok"), usage=usage)
    assert success.succeeded
    assert (usage.model, usage.input_tokens, usage.output_tokens) == ("claude-opus-5", 1_000, 500)
    assert usage.estimated_cost == Decimal("0.0175")
    assert usage.duration_seconds == 2.5


# --------------------------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------------------------


def test_the_default_profile_is_the_one_dec_014_names() -> None:
    profile = resolve_profile(DEFAULT_PROFILE)
    assert profile.provider == "anthropic"
    assert profile.model == "claude-opus-5"
    assert profile.settings.creativity is Creativity.LOW


def test_an_unknown_profile_names_the_value_and_the_alternatives() -> None:
    """`model_profile` is hand-written in an assessment configuration, so the caller's next question
    is always "then what should it say"."""
    with pytest.raises(UnknownModelProfileError) as caught:
        resolve_profile("gpt-fastest")
    message = str(caught.value)
    assert "gpt-fastest" in message
    assert "primary-development" in message


def test_a_profile_prices_a_call_from_its_published_rates() -> None:
    """Estimated, and named so: these are rates held in a table, not figures the provider returns."""
    profile = resolve_profile("primary-development")
    assert profile.cost_of(input_tokens=1_000_000, output_tokens=0) == Decimal("5.00")
    assert profile.cost_of(input_tokens=0, output_tokens=1_000_000) == Decimal("25.00")
    assert profile.cost_of(input_tokens=0, output_tokens=0) == Decimal(0)


def test_cache_spans_are_priced_separately_rather_than_discounted() -> None:
    """Adding cache reads into `input_tokens` would make a working cache indistinguishable from a
    broken one in the ledger — and prompt caching is the capability DEC-014 kept the seam
    capability-aware for. DEC-067: reads at the discount, creation at the premium."""
    profile = resolve_profile("primary-development")
    read = profile.cost_of(input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000)
    assert read == Decimal("0.50")
    assert read < profile.cost_of(input_tokens=1_000_000, output_tokens=0)

    creation = profile.cost_of(input_tokens=0, output_tokens=0, cache_creation_tokens=1_000_000)
    assert creation == Decimal("6.25")
    assert creation > profile.cost_of(input_tokens=1_000_000, output_tokens=0)


def test_creativity_is_the_agent_s_and_the_profile_is_the_run_s() -> None:
    """`with_creativity` returns a new profile, so one node's declared latitude does not become the
    run's configuration for every node after it."""
    base = resolve_profile("primary-development")
    threat = base.with_creativity(Creativity.MODERATE)
    assert threat.settings.creativity is Creativity.MODERATE
    assert base.settings.creativity is Creativity.LOW
    assert threat.model == base.model


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_every_profile_names_itself_consistently(name: str) -> None:
    assert PROFILES[name].name == name


def test_a_profile_exists_that_reaches_no_provider() -> None:
    """What the benchmark suite runs against when no key is present."""
    assert resolve_profile("offline-fake").provider == "fake"


# --------------------------------------------------------------------------------------------
# The deterministic substitute
# --------------------------------------------------------------------------------------------


def test_the_fake_satisfies_the_protocol() -> None:
    assert isinstance(DeterministicModel(), StructuredModel)


def test_the_fake_returns_what_was_queued_in_order() -> None:
    model = DeterministicModel([Proposal(summary="first"), Proposal(summary="second")])
    settings = GenerationSettings()

    first = model.generate(prompt="p", schema=Proposal, settings=settings)
    second = model.generate(prompt="p", schema=Proposal, settings=settings)

    assert isinstance(first, ModelSuccess)
    assert isinstance(second, ModelSuccess)
    assert (first.value.summary, second.value.summary) == ("first", "second")


def test_the_fake_records_what_it_was_asked() -> None:
    """A test asserting that an agent fenced its input reads this, rather than a mocking library —
    which keeps the assertion about the application rather than about how it called a mock."""
    model = DeterministicModel([Proposal(summary="ok")])
    model.generate(
        prompt="<source>untrusted</source>",
        schema=Proposal,
        settings=GenerationSettings(creativity=Creativity.MODERATE),
        system="You extract context.",
    )

    (call,) = model.calls
    assert call.prompt == "<source>untrusted</source>"
    assert call.schema is Proposal
    assert call.system == "You extract context."
    assert call.settings.creativity is Creativity.MODERATE


def test_the_fake_can_queue_a_failure() -> None:
    """Retry routing has to be exercisable without a provider that can be made to fail."""
    failure = ModelFailure(
        reason=FailureReason.TRANSIENT_PROVIDER_FAILURE, message="429", usage=ModelUsage(model="f")
    )
    model = DeterministicModel([failure])
    outcome = model.generate(prompt="p", schema=Proposal, settings=GenerationSettings())
    assert outcome is failure
    assert outcome.retryable


def test_running_out_of_queued_outcomes_is_an_error() -> None:
    """A node that calls the model twice when the test queued one response is doing something the
    test never described. Repeating the last answer would hide it."""
    model = DeterministicModel([Proposal(summary="only")])
    model.generate(prompt="p", schema=Proposal, settings=GenerationSettings())
    with pytest.raises(ResponsesExhaustedError, match="no response left"):
        model.generate(prompt="p", schema=Proposal, settings=GenerationSettings())


def test_running_out_after_a_mismatch_blames_the_order_not_the_count() -> None:
    """Responses supplied out of order fail the schema, the retry consumes what was meant for the
    next call, and the queue runs dry — three effects of one mistake. The exhaustion message names
    the mismatch that started it, because 'supply more responses' is the wrong advice for a wrong
    order."""
    model = DeterministicModel([OtherShape(value=1)])
    mismatch = model.generate(prompt="p", schema=Proposal, settings=GenerationSettings())
    assert isinstance(mismatch, ModelFailure)
    with pytest.raises(ResponsesExhaustedError, match="check the order"):
        model.generate(prompt="p", schema=Proposal, settings=GenerationSettings())


def test_the_fake_refuses_an_object_of_the_wrong_shape() -> None:
    """A queued object that does not fit the schema is a test's mistake, and it surfaces the same
    way a real schema failure would rather than as a type error somewhere downstream."""
    model = DeterministicModel([OtherShape(value=1)])
    outcome = model.generate(prompt="p", schema=Proposal, settings=GenerationSettings())
    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.SCHEMA_VALIDATION_FAILURE
    assert outcome.raw_output is not None


def test_the_fake_declares_no_capabilities_by_default() -> None:
    """A test that depends on prompt caching should have to say so."""
    assert DeterministicModel().capabilities == frozenset()
    assert DeterministicModel(capabilities=frozenset({ModelCapability.PROMPT_CACHING})).capabilities


def test_the_adapter_maps_both_cache_spans_disjoint() -> None:
    """DEC-067's adapter wiring: the provider's cache figures land in their own fields, and the
    cost is the weighted sum — nothing folds a cache span into `input_tokens`."""
    from types import SimpleNamespace

    from trace_ai.infrastructure.model.anthropic_adapter import AnthropicModel

    adapter = AnthropicModel("primary-development", client=object())
    response = SimpleNamespace(
        model="claude-opus-5",
        usage=SimpleNamespace(
            input_tokens=1_000,
            output_tokens=500,
            cache_read_input_tokens=20_000,
            cache_creation_input_tokens=4_000,
        ),
    )

    usage = adapter._usage(response, duration=1.0)
    assert usage.input_tokens == 1_000
    assert usage.cache_read_tokens == 20_000
    assert usage.cache_creation_tokens == 4_000

    profile = resolve_profile("primary-development")
    assert usage.estimated_cost == profile.cost_of(
        input_tokens=1_000,
        output_tokens=500,
        cache_read_tokens=20_000,
        cache_creation_tokens=4_000,
    )
