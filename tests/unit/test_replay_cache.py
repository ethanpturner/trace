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
