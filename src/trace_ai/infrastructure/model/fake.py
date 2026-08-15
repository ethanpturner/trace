"""`DeterministicModel`: the substitute every unit test uses.

`current-architecture.md` section 9 lists test substitutes as a required capability of the model
abstraction, and DEC-014 names two. This is the first: it returns what the caller queued, in order,
and reaches nothing.

It exists so that prompt assembly, schema handling, validation, and retry routing can all be
exercised with no API key and no network — which is what makes `uv run pytest` free, and what
`pyproject.toml` deselects the `integration` marker to protect.

**It records what it was asked.** A test that wants to assert an agent fenced its input, or asked
for the right schema, reads `calls` rather than reaching for a mocking library. That keeps the
assertion about the application's behaviour rather than about how it invoked a mock.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from trace_ai.infrastructure.model.recorded import RecordedResponse
from trace_ai.infrastructure.model.seam import (
    FailureReason,
    GenerationSettings,
    ModelCapability,
    ModelFailure,
    ModelOutcome,
    ModelSuccess,
    ModelUsage,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic import BaseModel

__all__ = ["DeterministicModel", "RecordedCall", "ResponsesExhaustedError"]


class ResponsesExhaustedError(AssertionError):
    """The fake was asked for one more call than it had responses queued.

    An `AssertionError`, because in a test running out means the test described fewer calls than
    the node makes. It is typed because the same thing happens outside tests: `offline-fake` is a
    first-class provider, and an operator who supplies fewer `--response` files than the run makes
    model calls hits this too, so the CLI catches it by name and answers in one line.
    """

    def __init__(self, name: str, calls_made: int, last_mismatch: str | None) -> None:
        message = (
            f"{name} was asked for model call {calls_made} with no response left to serve. A "
            f"recorded run supplies one response per model call, in the order the run makes "
            f"them; repeating an earlier answer would hide a step calling the model more often "
            f"than the recording describes."
        )
        if last_mismatch is not None:
            message += (
                f" The previous call was served {last_mismatch}, so the run retried it and "
                f"consumed the response meant for the call after — check the order the "
                f"responses were supplied in."
            )
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class RecordedCall:
    """One request the fake was given, kept so a test can assert on what an agent asked for."""

    prompt: str
    schema: type
    settings: GenerationSettings | None
    system: str | None


class DeterministicModel:
    """A `StructuredModel` that returns queued outcomes and touches nothing.

    Queue objects or failures in the order they should be returned. Running out is an error rather
    than a repeat of the last value: a node that calls the model twice when the test queued one
    response is a node doing something the test did not describe, and silently serving the same
    answer again would hide it.
    """

    def __init__(
        self,
        outcomes: Iterable[BaseModel | ModelFailure | RecordedResponse] = (),
        *,
        name: str = "deterministic-fake",
        capabilities: frozenset[ModelCapability] = frozenset(),
    ) -> None:
        self._queued: deque[BaseModel | ModelFailure | RecordedResponse] = deque(outcomes)
        self._name = name
        self._capabilities = capabilities
        self._last_mismatch: str | None = None
        self.calls: list[RecordedCall] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        """Empty by default: a test that depends on a capability should say so."""
        return self._capabilities

    def queue(self, *outcomes: BaseModel | ModelFailure | RecordedResponse) -> None:
        """Add outcomes to the end of the queue."""
        self._queued.extend(outcomes)

    def generate[T: "BaseModel"](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings | None = None,
        system: str | None = None,
        cache_prefix: str | None = None,
    ) -> ModelOutcome[T]:
        # `cache_prefix` is a provider-side optimisation hint; the fake reaches no provider, so it
        # records nothing and replays the queue exactly as before (WS10).
        self.calls.append(RecordedCall(prompt, schema, settings, system))

        if not self._queued:
            raise ResponsesExhaustedError(self._name, len(self.calls), self._last_mismatch)

        queued = self._queued.popleft()

        if isinstance(queued, ModelFailure):
            self._last_mismatch = None
            return queued

        # A RecordedResponse carries the usage to replay (#461); a bare proposal carries none, so
        # the fake reports zeros exactly as it did before the envelope existed.
        if isinstance(queued, RecordedResponse):
            value: BaseModel = queued.response
            usage = queued.usage if queued.usage is not None else ModelUsage(model=self._name)
        else:
            value = queued
            usage = ModelUsage(model=self._name)

        if not isinstance(value, schema):
            # Remembered so that running out on the retry can say what actually went wrong: the
            # retry consumed the next call's response, and without this the exhaustion message
            # would blame the count when the cause was the order.
            self._last_mismatch = f"a {type(value).__name__} where {schema.__name__} was asked for"
            return ModelFailure(
                reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
                message=f"queued {self._last_mismatch}",
                usage=usage,
                raw_output=repr(value),
            )

        self._last_mismatch = None
        return ModelSuccess(value=value, usage=usage)
