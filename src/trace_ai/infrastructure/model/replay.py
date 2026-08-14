"""`ReplayCache`: recorded responses served back, keyed on everything that could change them.

`agent-design.md` section 30 permits caching model responses for development and evaluation when
the input objects, the prompt version, the model configuration, and the requirements catalog
version are all identical — and then says the thing that governs this module's design:
**caching must not hide workflow changes during evaluation.**

That sentence is why the key is wide rather than narrow. A cache keyed on the prompt text alone
would serve yesterday's answer after a model change, a settings change, or a catalog change, and
the evaluation would report that the change made no difference. Every identifier that could change
behaviour is in the key, so a change that should invalidate a recording does — and the cost of
getting it wrong in this direction is a wasted call, while the cost of getting it wrong in the other
is a wrong conclusion.

**A miss is not an error.** The cache serves what it has and says so; the caller decides whether to
call a provider or fail. That keeps the decision to spend money in one place rather than in a
cache's fallback path.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from trace_ai.domain.hashing import content_hash
from trace_ai.infrastructure.model.seam import (
    FailureReason,
    GenerationSettings,
    ModelCapability,
    ModelFailure,
    ModelOutcome,
    ModelSuccess,
    ModelUsage,
    StructuredModel,
)

if TYPE_CHECKING:
    from trace_ai.infrastructure.model.profiles import ModelProfile

__all__ = ["CacheKey", "CachingModel", "ReplayCache", "cache_key"]


@dataclass(frozen=True, slots=True)
class CacheKey:
    """Everything section 30 requires to be identical before a recording may be reused.

    Each field is here because changing it changes the answer. `prompt_hash` covers the composed
    prompt, which DEC-019 already hashes after shared blocks are merged in — so a change to a shared
    block invalidates every prompt that composes it, which is the change most likely to alter
    behaviour without anyone noticing.
    """

    prompt_hash: str
    prompt_version: str
    schema: str
    model: str
    creativity: str
    max_output_tokens: int
    requirements_catalog_version: str | None = None
    workflow_version: str | None = None
    system_hash: str | None = None
    """The system prompt, hashed. For every agent this is where the trusted region lives -- the
    architecture, the evidence manifest, the reviewer's feedback -- so two calls with an identical
    user prompt but different systems are different calls, and a key that omitted it would serve one
    architecture's answer for another. Optional so a call with no system prompt keys cleanly."""

    provider: str = ""
    """The provider behind the model. The same model name can be served by two providers (the fake
    and a live adapter), and a recording made against one is not an answer for the other."""

    def digest(self) -> str:
        """The key as one `sha256:` string: stable, sortable, and safe as a file name."""
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return content_hash(canonical.encode("utf-8"))


def cache_key(
    *,
    prompt: str,
    prompt_version: str,
    schema: type[BaseModel],
    profile: ModelProfile,
    settings: GenerationSettings | None = None,
    system: str | None = None,
    requirements_catalog_version: str | None = None,
    workflow_version: str | None = None,
) -> CacheKey:
    """Build a key from the things a call is made of.

    `settings` defaults to the profile's own, which is the normal case: a node that did not override
    the run's generation settings gets the run's key. `system` is the trusted region; it is hashed
    into the key because it changes the answer as much as the user prompt does.
    """
    resolved = settings if settings is not None else profile.settings
    return CacheKey(
        prompt_hash=content_hash(prompt.encode("utf-8")),
        prompt_version=prompt_version,
        schema=schema.__name__,
        model=profile.model,
        creativity=resolved.creativity.value,
        max_output_tokens=resolved.max_output_tokens,
        requirements_catalog_version=requirements_catalog_version,
        workflow_version=workflow_version,
        system_hash=None if system is None else content_hash(system.encode("utf-8")),
        provider=profile.provider,
    )


class ReplayCache:
    """Recorded responses, held in memory and keyed by `CacheKey`.

    The store is deliberately a mapping rather than a directory: where recordings live is a
    persistence question, and the evaluation harness that needs them on disk (#110) can hand this
    class a dict it loaded. What is settled here is the *key*, which is the part section 30 is
    specific about and the part that is wrong in a way nobody notices.
    """

    def __init__(self, recordings: dict[str, Any] | None = None) -> None:
        self._recordings: dict[str, Any] = dict(recordings or {})
        self.hits = 0
        self.misses = 0

    def get(self, key: CacheKey) -> Any | None:
        """The recorded payload for `key`, or `None`. A miss is a normal answer."""
        digest = key.digest()
        if digest in self._recordings:
            self.hits += 1
            return self._recordings[digest]
        self.misses += 1
        return None

    def put(self, key: CacheKey, payload: Any) -> None:
        """Record a payload against `key`, replacing any earlier recording for it."""
        self._recordings[key.digest()] = payload

    def __contains__(self, key: CacheKey) -> bool:
        """Membership without counting a hit or a miss: this is inspection, not a lookup."""
        return key.digest() in self._recordings

    def __len__(self) -> int:
        return len(self._recordings)


class CachingModel:
    """A `StructuredModel` that consults a `ReplayCache` before delegating (#408).

    This is the shape the README promises — the replay cache behind the same interface as every
    other model — and the shape a live capture needs (#324): run with an empty cache and a real
    inner model, and the cache fills with exactly the recordings a later offline replay serves.
    A hit answers from the recording at zero cost; a miss delegates, and a successful answer is
    recorded before it is returned. Failures are never cached — a recorded failure replayed as
    an answer would turn a transient provider condition into a permanent one.

    Persistence stays the caller's: section 30 settles the key, this class settles the seam
    conformance, and where the recordings live on disk is the capture tool's question.
    """

    def __init__(
        self,
        inner: StructuredModel,
        cache: ReplayCache,
        *,
        profile: ModelProfile,
        prompt_version: str = "",
        requirements_catalog_version: str | None = None,
        workflow_version: str | None = None,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._profile = profile
        self._prompt_version = prompt_version
        self._requirements_catalog_version = requirements_catalog_version
        self._workflow_version = workflow_version

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        return self._inner.capabilities

    def generate[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings | None = None,
        system: str | None = None,
    ) -> ModelOutcome[T]:
        resolved = settings if settings is not None else self._profile.settings
        key = cache_key(
            prompt=prompt,
            prompt_version=self._prompt_version,
            schema=schema,
            profile=self._profile,
            settings=resolved,
            system=system,
            requirements_catalog_version=self._requirements_catalog_version,
            workflow_version=self._workflow_version,
        )
        recorded = self._cache.get(key)
        if recorded is not None:
            try:
                value = schema.model_validate(recorded)
            except PydanticValidationError as drift:
                # A recording that no longer fits the schema is drift, not an answer. Returning a
                # ModelFailure keeps the seam's no-exceptions contract (seam.py) -- a validation
                # error raised here would escape the orchestrator's attempt loop, which catches only
                # AttemptFailedError, leaving a node started and never finished. It is classified
                # exactly as a live schema failure, so recorded-response drift and provider drift
                # look the same to the caller.
                return ModelFailure(
                    reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
                    message=f"the recorded response no longer fits {schema.__name__}: {drift}",
                    usage=ModelUsage(model=self._profile.model),
                    raw_output=json.dumps(recorded),
                )
            return ModelSuccess(
                value=value,
                usage=ModelUsage(model=self._profile.model),
                metadata={"cache": "hit"},
            )
        outcome = self._inner.generate(
            prompt=prompt, schema=schema, settings=resolved, system=system
        )
        if isinstance(outcome, ModelSuccess):
            self._cache.put(key, outcome.value.model_dump(mode="json"))
        return outcome
