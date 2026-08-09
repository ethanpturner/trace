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

__all__ = ["DeterministicModel", "RecordedCall"]


@dataclass(frozen=True, slots=True)
class RecordedCall:
    """One request the fake was given, kept so a test can assert on what an agent asked for."""

    prompt: str
    schema: type
    settings: GenerationSettings
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
        outcomes: Iterable[BaseModel | ModelFailure] = (),
        *,
        name: str = "deterministic-fake",
        capabilities: frozenset[ModelCapability] = frozenset(),
    ) -> None:
        self._queued: deque[BaseModel | ModelFailure] = deque(outcomes)
        self._name = name
        self._capabilities = capabilities
        self.calls: list[RecordedCall] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        """Empty by default: a test that depends on a capability should say so."""
        return self._capabilities

    def queue(self, *outcomes: BaseModel | ModelFailure) -> None:
        """Add outcomes to the end of the queue."""
        self._queued.extend(outcomes)

    def generate[T: "BaseModel"](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings,
        system: str | None = None,
    ) -> ModelOutcome[T]:
        self.calls.append(RecordedCall(prompt, schema, settings, system))

        if not self._queued:
            raise AssertionError(
                f"{self._name} was called {len(self.calls)} time(s) with nothing queued for this "
                f"one. Queue an outcome per expected call; a fake that repeats its last answer "
                f"hides a node calling the model more often than the test describes."
            )

        outcome = self._queued.popleft()
        usage = ModelUsage(model=self._name)

        if isinstance(outcome, ModelFailure):
            return outcome

        if not isinstance(outcome, schema):
            return ModelFailure(
                reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
                message=(
                    f"queued a {type(outcome).__name__} where {schema.__name__} was asked for"
                ),
                usage=usage,
                raw_output=repr(outcome),
            )

        return ModelSuccess(value=outcome, usage=usage)
