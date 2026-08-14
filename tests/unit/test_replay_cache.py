"""Tests for the replay cache key, one component at a time.

`agent-design.md` section 30 permits caching when the input objects, the prompt version, the model
configuration, and the requirements catalog version are all identical — and then states the
constraint this file exists to enforce: **caching must not hide workflow changes during
evaluation.**

That is why each component gets its own test. A cache keyed too narrowly serves yesterday's answer
after a change and the evaluation reports that the change made no difference, which is a wrong
conclusion rather than a wasted call. Every test below is one way that could happen.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from trace_ai.domain.hashing import is_content_hash
from trace_ai.infrastructure.model import (
    CacheKey,
    Creativity,
    GenerationSettings,
    ReplayCache,
    cache_key,
    resolve_profile,
)


class Proposal(BaseModel):
    summary: str


class OtherShape(BaseModel):
    value: int


PROFILE = resolve_profile("primary-development")


def key(**changes: Any) -> CacheKey:
    fields: dict[str, Any] = {
        "prompt": "Extract the context from the following documents.",
        "prompt_version": "extract-context-v1",
        "schema": Proposal,
        "profile": PROFILE,
        "requirements_catalog_version": "0.1",
        "workflow_version": "1",
        **changes,
    }
    return cache_key(**fields)


def test_the_same_call_produces_the_same_key() -> None:
    """Without this the cache never hits and the rest of the file is about nothing."""
    assert key().digest() == key().digest()


def test_the_digest_is_a_content_hash() -> None:
    """One hash format across the system (DEC-019), so a key is safe as a file name and sorts."""
    assert is_content_hash(key().digest())


@pytest.mark.parametrize(
    ("label", "change"),
    [
        ("the composed prompt", {"prompt": "Extract the context. Be thorough."}),
        ("the prompt version", {"prompt_version": "extract-context-v2"}),
        ("the target schema", {"schema": OtherShape}),
        ("the model", {"profile": resolve_profile("economy")}),
        (
            "the generation settings",
            {"settings": GenerationSettings(creativity=Creativity.MODERATE)},
        ),
        ("the output ceiling", {"settings": GenerationSettings(max_output_tokens=32_000)}),
        ("the requirements catalog version", {"requirements_catalog_version": "0.2"}),
        ("the workflow version", {"workflow_version": "2"}),
    ],
)
def test_a_change_that_could_change_the_answer_changes_the_key(
    label: str, change: dict[str, Any]
) -> None:
    """One test per component, because a cache that misses one of them is wrong in exactly one
    direction — it reports that a change made no difference."""
    assert key().digest() != key(**change).digest(), f"{label} did not change the key"


def test_the_prompt_hash_covers_the_composed_prompt() -> None:
    """DEC-019 hashes a prompt after shared blocks are merged in, which is what makes a change to a
    shared block invalidate every prompt that composes it — the change most likely to alter
    behaviour without anyone noticing."""
    assert key(prompt="a").digest() != key(prompt="a ").digest()


def test_two_systems_with_one_prompt_get_distinct_keys() -> None:
    """The system prompt carries the whole trusted region for every agent — the architecture, the
    evidence manifest, the reviewer's feedback. Two calls with an identical user prompt but a
    different system are different calls, and a key that omitted it would serve one architecture's
    answer for another."""
    assert key(system="architecture A").digest() != key(system="architecture B").digest()
    assert key(system="architecture A").digest() != key().digest()


def test_the_provider_is_in_the_key() -> None:
    """The same model name can be served by two providers (the fake and a live adapter); a recording
    made against one is not an answer for the other."""
    from dataclasses import replace

    assert key().digest() != key(profile=replace(PROFILE, provider="fake")).digest()


# --------------------------------------------------------------------------------------------
# The cache itself
# --------------------------------------------------------------------------------------------


def test_a_miss_is_a_normal_answer_rather_than_an_error() -> None:
    """The cache serves what it has; whether to spend money is the caller's decision, and keeping it
    there means it is made in one place rather than in a cache's fallback path."""
    cache = ReplayCache()
    assert cache.get(key()) is None
    assert (cache.hits, cache.misses) == (0, 1)


def test_a_recorded_response_is_served_back() -> None:
    cache = ReplayCache()
    cache.put(key(), {"summary": "recorded"})
    assert cache.get(key()) == {"summary": "recorded"}
    assert (cache.hits, cache.misses) == (1, 0)


def test_a_recording_is_not_served_after_the_prompt_version_moves() -> None:
    """The section 30 rule, exercised end to end rather than only on the key."""
    cache = ReplayCache()
    cache.put(key(), {"summary": "recorded"})
    assert cache.get(key(prompt_version="extract-context-v2")) is None


def test_membership_does_not_count_as_a_lookup() -> None:
    """`in` is inspection — a test or a report asking what is recorded should not move the counters
    an evaluation reads."""
    cache = ReplayCache()
    cache.put(key(), {"summary": "recorded"})
    assert key() in cache
    assert (cache.hits, cache.misses) == (0, 0)


def test_re_recording_replaces_rather_than_accumulates() -> None:
    cache = ReplayCache()
    cache.put(key(), {"summary": "first"})
    cache.put(key(), {"summary": "second"})
    assert len(cache) == 1
    assert cache.get(key()) == {"summary": "second"}


# ------------------------------------------------------------------------------------------
# The cache behind the seam (#408)
# ------------------------------------------------------------------------------------------


def test_a_hit_answers_from_the_recording_and_never_reaches_the_inner_model() -> None:
    """The README's claim, made literal: the replay cache sits behind the same interface as
    every other model. A recorded answer is served as a zero-cost `ModelSuccess` that says it
    came from the cache, and the inner model is never consulted."""
    from trace_ai.infrastructure.model import DeterministicModel, ModelSuccess
    from trace_ai.infrastructure.model.profiles import resolve_profile
    from trace_ai.infrastructure.model.replay import CachingModel, ReplayCache, cache_key

    profile = resolve_profile("primary-development")
    key = cache_key(prompt="the prompt", prompt_version="v1", schema=Proposal, profile=profile)
    cache = ReplayCache({key.digest(): {"summary": "recorded"}})
    inner = DeterministicModel()  # empty queue: any call would raise ResponsesExhaustedError

    model = CachingModel(inner, cache, profile=profile, prompt_version="v1")
    outcome = model.generate(prompt="the prompt", schema=Proposal)

    assert isinstance(outcome, ModelSuccess)
    assert outcome.value == Proposal(summary="recorded")
    assert outcome.metadata["cache"] == "hit"
    assert outcome.usage.estimated_cost == 0
    assert cache.hits == 1


def test_a_miss_delegates_and_records_the_answer_for_the_next_run() -> None:
    """The capture shape (#324): run once against a real inner model and the cache fills with
    exactly the recordings a later replay serves. The second call is a hit; the inner model's
    queue proves it was consulted exactly once."""
    from trace_ai.infrastructure.model import DeterministicModel, ModelSuccess
    from trace_ai.infrastructure.model.profiles import resolve_profile
    from trace_ai.infrastructure.model.replay import CachingModel, ReplayCache

    profile = resolve_profile("primary-development")
    cache = ReplayCache()
    model = CachingModel(
        DeterministicModel([Proposal(summary="live")]), cache, profile=profile, prompt_version="v1"
    )

    first = model.generate(prompt="the prompt", schema=Proposal)
    assert isinstance(first, ModelSuccess)
    assert len(cache) == 1

    second = model.generate(prompt="the prompt", schema=Proposal)
    assert isinstance(second, ModelSuccess)
    assert second.value == Proposal(summary="live")
    assert second.metadata["cache"] == "hit", "the recording was not served on the second call"


def test_a_failure_is_never_recorded() -> None:
    """A cached failure replayed as an answer would make a transient provider condition
    permanent, so only a `ModelSuccess` is recorded."""
    from trace_ai.infrastructure.model import DeterministicModel, ModelFailure
    from trace_ai.infrastructure.model.profiles import resolve_profile
    from trace_ai.infrastructure.model.replay import CachingModel, ReplayCache

    class Other(BaseModel):
        value: int

    profile = resolve_profile("primary-development")
    cache = ReplayCache()
    model = CachingModel(
        DeterministicModel([Other(value=1)]), cache, profile=profile, prompt_version="v1"
    )

    outcome = model.generate(prompt="the prompt", schema=Proposal)
    assert isinstance(outcome, ModelFailure)
    assert len(cache) == 0


def test_a_drifted_recording_returns_a_failure_not_a_raise() -> None:
    """A recording that no longer fits the schema is drift, not an answer. It must come back as a
    ModelFailure — a ValidationError raised here would escape the orchestrator's attempt loop, which
    catches only AttemptFailedError, leaving a node started and never finished (seam contract)."""
    from trace_ai.infrastructure.model import DeterministicModel, ModelFailure
    from trace_ai.infrastructure.model.profiles import resolve_profile
    from trace_ai.infrastructure.model.replay import CachingModel, ReplayCache, cache_key
    from trace_ai.infrastructure.model.seam import FailureReason

    profile = resolve_profile("primary-development")
    key = cache_key(prompt="the prompt", prompt_version="v1", schema=Proposal, profile=profile)
    # A recording missing the required `summary` field: it was valid once and no longer is.
    cache = ReplayCache({key.digest(): {"not_summary": "drift"}})
    model = CachingModel(DeterministicModel(), cache, profile=profile, prompt_version="v1")

    outcome = model.generate(prompt="the prompt", schema=Proposal)
    assert isinstance(outcome, ModelFailure)
    assert outcome.reason is FailureReason.SCHEMA_VALIDATION_FAILURE
    assert outcome.raw_output is not None and "drift" in outcome.raw_output


def test_the_caching_model_keys_on_the_system_prompt() -> None:
    """A recording made under one system prompt must not be served for a call with a different one:
    the system is the trusted region, and a hit that ignored it would answer the wrong architecture."""
    from trace_ai.infrastructure.model import DeterministicModel, ModelSuccess
    from trace_ai.infrastructure.model.profiles import resolve_profile
    from trace_ai.infrastructure.model.replay import CachingModel, ReplayCache

    profile = resolve_profile("primary-development")
    cache = ReplayCache()
    # Record an answer for system A, then ask under system B: the inner model (empty queue) is
    # consulted and raises ResponsesExhaustedError, proving the recording was not reused.
    recorder = CachingModel(
        DeterministicModel([Proposal(summary="for A")]), cache, profile=profile, prompt_version="v1"
    )
    recorder.generate(prompt="the prompt", schema=Proposal, system="architecture A")
    assert len(cache) == 1

    from trace_ai.infrastructure.model.fake import ResponsesExhaustedError

    replayer = CachingModel(DeterministicModel(), cache, profile=profile, prompt_version="v1")
    hit = replayer.generate(prompt="the prompt", schema=Proposal, system="architecture A")
    assert isinstance(hit, ModelSuccess), "the identical system should hit"
    with pytest.raises(ResponsesExhaustedError):
        replayer.generate(prompt="the prompt", schema=Proposal, system="architecture B")
