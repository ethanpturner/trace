"""The retry policy: bounded, reason-specific, and carrying feedback forward.

`agent-design.md` section 26 makes retries bounded and reason-specific, and `data-model.md` section
33 lists four things the workflow does with an invalid output: preserve it for debugging, return
validation feedback to the generating node where appropriate, retry within configured limits, and
stop or request human review when valid output cannot be produced. This module does all four.

**Feedback is the reason a retry is worth anything.** A second identical call to a model that just
produced an invalid object is a second roll of the same dice. What makes the attempt different is
telling the node what was wrong with the last one, so `AttemptContext` carries the previous
failure's feedback and the attempt number, and a test asserts the second attempt's input differs
from the first.

**The failed output goes to a file, not into an error message.** `ExecutionRecord.error_message`
must be safe (section 27), and the output of a failed attempt is model text that may contain a
quoted source excerpt, an echoed prompt, or a credential the document under review happened to
include. It is written to the assessment's `traces/` area and the record names the file.

**Backoff is bounded.** `current-architecture.md` section 11 asks for bounded exponential backoff on
a provider failure, and the bound matters for a reason beyond politeness: the workflow duration
ceiling is enforced against wall-clock time, so unbounded backoff would let a provider outage
consume the run's remaining budget silently and stop it for the wrong reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from trace_ai.domain.base import now
from trace_ai.infrastructure.filesystem.atomic import write_text_atomic
from trace_ai.workflow.errors import RETRYABLE, ErrorClass, WorkflowError

if TYPE_CHECKING:
    from collections.abc import Callable

    from trace_ai.infrastructure.filesystem.artifact_store import ArtifactStore

__all__ = [
    "DEFAULT_BASE_DELAY_SECONDS",
    "DEFAULT_MAXIMUM_DELAY_SECONDS",
    "AttemptContext",
    "AttemptFailedError",
    "RetryPolicy",
    "preserve_failed_output",
    "run_with_retries",
]

# The first backoff, and the ceiling no delay exceeds. The ceiling is the load-bearing one: the
# workflow duration limit is wall-clock, so an unbounded delay would spend it on waiting.
DEFAULT_BASE_DELAY_SECONDS: Final = 1.0
DEFAULT_MAXIMUM_DELAY_SECONDS: Final = 30.0


@dataclass(frozen=True, slots=True)
class AttemptContext:
    """What one attempt knows about the attempts before it."""

    attempt_number: int
    """Zero for the first attempt. The final attempt's number is what the node's execution record
    carries as `retry_number` — the retries the execution consumed (#398)."""

    feedback: str | None = None
    """What was wrong with the previous attempt, in terms the node can act on.

    `None` on the first attempt. It is the whole reason a retry differs from a repetition, and it
    is *validation* feedback — what the schema rejected — never the model's own words back at it.
    """

    @property
    def is_retry(self) -> bool:
        return self.attempt_number > 0


@dataclass(frozen=True, slots=True)
class AttemptFailedError(Exception):
    """What a node raises when an attempt fails, classified.

    A node raises this rather than returning it, because a failed attempt is not a result the
    orchestrator should be able to mistake for one — and because the retry loop needs to see it
    before the ledger writes the execution.
    """

    error_class: ErrorClass
    message: str
    raw_output: str | None = None
    """The invalid output, preserved per section 33. It goes to a file, never into a message."""

    feedback: str | None = None
    """What to tell the next attempt. Distinct from `message`, which is for a person."""


@dataclass(slots=True)
class RetryPolicy:
    """Section 26's default policy, parameterized by the configuration's per-node limit."""

    maximum_retries_per_node: int = 2
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS
    maximum_delay_seconds: float = DEFAULT_MAXIMUM_DELAY_SECONDS
    sleep: Callable[[float], None] = field(default=lambda _seconds: None)
    """How the loop waits. Injected so a test asserts the delays rather than serving them."""

    def should_retry(self, error_class: ErrorClass, *, attempt_number: int) -> bool:
        """Whether another attempt is permitted after a failure of this class.

        Two conditions, and the order is the point: a non-retryable class is refused whatever the
        budget says. An insufficient-evidence condition with retries remaining is still not
        retried, because the answer would not change and the pressure to produce one would.
        """
        if error_class not in RETRYABLE:
            return False
        return attempt_number < self.maximum_retries_per_node

    def delay_for(self, attempt_number: int) -> float:
        """The backoff before attempt `attempt_number`, exponential and capped."""
        if attempt_number <= 0:
            return 0.0
        exponential = self.base_delay_seconds * float(2 ** (attempt_number - 1))
        return min(exponential, self.maximum_delay_seconds)


def preserve_failed_output(
    artifacts: ArtifactStore, *, node_name: str, attempt_number: int, raw_output: str
) -> str:
    """Write an invalid output to the assessment's debug area and return its relative path.

    `traces/` is where `current-architecture.md` section 5.16 puts debug artifacts. The file name
    carries the node and the attempt so a reader of an `ExecutionRecord` can find the one that
    matches the row they are looking at, and a timestamp so two runs of the same node do not
    collide — the artifact store refuses to overwrite stored content with different content, and a
    failed attempt is exactly the case where the content differs every time.
    """
    stamp = now().strftime("%Y%m%dT%H%M%S%f")
    filename = f"{node_name}-attempt-{attempt_number}-{stamp}.txt"
    path = artifacts.area("traces") / filename
    write_text_atomic(path, raw_output)
    return str(path.relative_to(artifacts.assessment_root))


def run_with_retries[T](
    attempt: Callable[[AttemptContext], T],
    *,
    policy: RetryPolicy,
    node_name: str,
    artifacts: ArtifactStore | None = None,
    on_attempt_failed: Callable[[int, AttemptFailedError, str | None], None] | None = None,
) -> T:
    """Run `attempt` until it succeeds or the policy stops permitting another one.

    Raises `WorkflowError` when it stops, carrying the class, the attempt count, and the path to
    the last preserved output. The exception is what the orchestrator records on
    `WorkflowRun.error_summary`; the last valid checkpoint is untouched, because nothing here
    writes state.
    """
    attempt_number = 0
    feedback: str | None = None
    artifact_path: str | None = None

    while True:
        try:
            return attempt(AttemptContext(attempt_number=attempt_number, feedback=feedback))
        except AttemptFailedError as failure:
            artifact_path = None
            if artifacts is not None and failure.raw_output is not None:
                artifact_path = preserve_failed_output(
                    artifacts,
                    node_name=node_name,
                    attempt_number=attempt_number,
                    raw_output=failure.raw_output,
                )
            if on_attempt_failed is not None:
                on_attempt_failed(attempt_number, failure, artifact_path)

            if not policy.should_retry(failure.error_class, attempt_number=attempt_number):
                raise WorkflowError(
                    failure.error_class,
                    failure.message,
                    artifact_path=artifact_path,
                    attempts=attempt_number + 1,
                ) from None

            attempt_number += 1
            feedback = failure.feedback
            policy.sleep(policy.delay_for(attempt_number))
