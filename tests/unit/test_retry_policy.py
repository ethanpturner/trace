"""Tests for the error taxonomy and the retry policy.

`agent-design.md` section 26 draws one line and everything here is about keeping it: an output that
failed to parse is worth another attempt, and an analysis that genuinely cannot be concluded is an
answer. Retrying the second spends money to no purpose and invites an agent to fabricate something
on the third attempt, because producing an answer is the only way to stop being retried.

Three properties carry the weight.

**A non-retryable class is refused whatever the budget says.** Insufficient evidence with two
retries remaining is still not retried.

**Feedback is what makes a retry differ from a repetition.** A second identical call to a model that
just produced an invalid object is a second roll of the same dice.

**The failed output goes to a file and never into an error message.** `ExecutionRecord.error_message`
must be safe (section 27), and model output can contain a quoted source excerpt, an echoed prompt,
or a credential the document under review happened to include.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import FailureReason
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.workflow.errors import (
    NON_RETRYABLE,
    RETRYABLE,
    SECTION_11_FAILURE_CLASSES,
    ErrorClass,
    WorkflowError,
    classify_model_failure,
)
from trace_ai.workflow.retry import (
    DEFAULT_MAXIMUM_DELAY_SECONDS,
    AttemptContext,
    AttemptFailedError,
    RetryPolicy,
    preserve_failed_output,
    run_with_retries,
)


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


# ------------------------------------------------------------------------------------------
# The taxonomy
# ------------------------------------------------------------------------------------------


def test_the_taxonomy_contains_section_26_s_six_classes() -> None:
    """Closed, because a free-text error class in a log is one nobody decided on — and the first
    thing anyone does with one is decide whether to retry it."""
    documented = {
        "schema_validation_failure",
        "transient_provider_failure",
        "missing_required_relationship",
        "insufficient_evidence",
        "unresolved_contradiction",
        "reviewer_input_required",
    }
    assert documented <= {member.value for member in ErrorClass}


def test_the_retryable_set_is_section_26_s_retry_on_list() -> None:
    assert {member.value for member in RETRYABLE} == {
        "schema_validation_failure",
        "transient_provider_failure",
        "missing_required_relationship",
    }


def test_every_class_is_retryable_or_not_and_never_both() -> None:
    assert set(ErrorClass) == RETRYABLE | NON_RETRYABLE
    assert not RETRYABLE & NON_RETRYABLE


def test_an_application_fault_is_named_and_not_retryable() -> None:
    """Section 11 names a failure class section 26's retry policy does not. Folding a bug into a
    provider condition would make it retryable; folding it into an analysis condition would make it
    read as a judgment about the material."""
    assert ErrorClass.UNEXPECTED_APPLICATION_FAILURE in NON_RETRYABLE


def test_every_section_11_failure_class_maps_to_exactly_one_member() -> None:
    """A documented condition with no member is one the code cannot name."""
    assert len(SECTION_11_FAILURE_CLASSES) == 5
    assert all(isinstance(member, ErrorClass) for member in SECTION_11_FAILURE_CLASSES.values())


def test_awaiting_a_reviewer_decision_is_not_a_failure() -> None:
    """DEC-017 replaced section 11's human-review timeout: a paused run holds nothing in memory,
    waiting costs nothing, and there is no timeout. The member is the reason a run stopped."""
    assert SECTION_11_FAILURE_CLASSES["awaiting a reviewer decision"] is (
        ErrorClass.REVIEWER_INPUT_REQUIRED
    )
    assert ErrorClass.REVIEWER_INPUT_REQUIRED in NON_RETRYABLE


@pytest.mark.parametrize("reason", list(FailureReason))
def test_every_model_failure_reason_classifies(reason: FailureReason) -> None:
    """The seam classifies what happened to one call; this classifies what it means for the
    workflow. A reason with no mapping would reach the orchestrator as a KeyError."""
    assert isinstance(classify_model_failure(reason), ErrorClass)


def test_a_refusal_is_an_application_fault_rather_than_a_provider_condition() -> None:
    """Nothing the workflow can retry changes a refusal, and the request came from us."""
    assert classify_model_failure(FailureReason.REFUSED) is (
        ErrorClass.UNEXPECTED_APPLICATION_FAILURE
    )


# ------------------------------------------------------------------------------------------
# The policy
# ------------------------------------------------------------------------------------------


def test_a_schema_failure_retries_up_to_the_configured_limit() -> None:
    policy = RetryPolicy(maximum_retries_per_node=2)
    assert policy.should_retry(ErrorClass.SCHEMA_VALIDATION_FAILURE, attempt_number=0)
    assert policy.should_retry(ErrorClass.SCHEMA_VALIDATION_FAILURE, attempt_number=1)
    assert not policy.should_retry(ErrorClass.SCHEMA_VALIDATION_FAILURE, attempt_number=2)


@pytest.mark.parametrize(
    "error_class",
    [
        ErrorClass.INSUFFICIENT_EVIDENCE,
        ErrorClass.UNRESOLVED_CONTRADICTION,
        ErrorClass.REVIEWER_INPUT_REQUIRED,
    ],
)
def test_a_non_retryable_class_is_refused_whatever_the_budget_says(
    error_class: ErrorClass,
) -> None:
    """`agent-design.md` section 26, Non-retryable analysis conditions: these produce questions or
    human review, not repeated model calls. The answer would not change and the pressure to produce
    one would."""
    policy = RetryPolicy(maximum_retries_per_node=5)
    assert not policy.should_retry(error_class, attempt_number=0)


def test_backoff_is_exponential_and_capped() -> None:
    """The cap is load-bearing: the workflow duration ceiling is wall-clock, so unbounded backoff
    would let a provider outage consume the run's budget and stop it for the wrong reason."""
    policy = RetryPolicy(base_delay_seconds=1.0, maximum_delay_seconds=4.0)
    assert [policy.delay_for(n) for n in range(0, 6)] == [0.0, 1.0, 2.0, 4.0, 4.0, 4.0]
    assert all(policy.delay_for(n) <= DEFAULT_MAXIMUM_DELAY_SECONDS for n in range(20))


# ------------------------------------------------------------------------------------------
# The loop
# ------------------------------------------------------------------------------------------


def test_a_successful_first_attempt_runs_once() -> None:
    seen: list[AttemptContext] = []

    def attempt(context: AttemptContext) -> str:
        seen.append(context)
        return "ok"

    assert run_with_retries(attempt, policy=RetryPolicy(), node_name="context-extraction") == "ok"
    assert len(seen) == 1
    assert seen[0].feedback is None
    assert not seen[0].is_retry


def test_validation_feedback_reaches_the_next_attempt() -> None:
    """The whole reason a retry is worth anything: a second identical call to a model that just
    produced an invalid object is a second roll of the same dice."""
    seen: list[AttemptContext] = []

    def attempt(context: AttemptContext) -> str:
        seen.append(context)
        if context.attempt_number == 0:
            raise AttemptFailedError(
                error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
                message="the proposal did not validate",
                feedback="`claims[0].status` must be one of the seven documented values",
            )
        return "ok"

    assert run_with_retries(attempt, policy=RetryPolicy(), node_name="context-extraction") == "ok"
    assert [context.feedback for context in seen] == [
        None,
        "`claims[0].status` must be one of the seven documented values",
    ]


def test_an_insufficient_evidence_condition_produces_no_retry() -> None:
    """`agent-design.md` section 26, Non-retryable analysis conditions. This is the failure the
    whole taxonomy exists to keep out of the retry path."""
    attempts = 0

    def attempt(_context: AttemptContext) -> str:
        nonlocal attempts
        attempts += 1
        raise AttemptFailedError(
            error_class=ErrorClass.INSUFFICIENT_EVIDENCE,
            message="the documentation does not establish whether signatures are validated",
        )

    with pytest.raises(WorkflowError) as caught:
        run_with_retries(attempt, policy=RetryPolicy(maximum_retries_per_node=3), node_name="n")

    assert attempts == 1
    assert caught.value.error_class is ErrorClass.INSUFFICIENT_EVIDENCE
    assert not caught.value.retryable


def test_an_unresolved_contradiction_produces_no_retry() -> None:
    attempts = 0

    def attempt(_context: AttemptContext) -> str:
        nonlocal attempts
        attempts += 1
        raise AttemptFailedError(
            error_class=ErrorClass.UNRESOLVED_CONTRADICTION,
            message="retention is stated two ways and the answer changes the assessment",
        )

    with pytest.raises(WorkflowError):
        run_with_retries(attempt, policy=RetryPolicy(maximum_retries_per_node=3), node_name="n")
    assert attempts == 1


def test_exhausted_retries_stop_with_a_classified_error() -> None:
    attempts = 0

    def attempt(_context: AttemptContext) -> str:
        nonlocal attempts
        attempts += 1
        raise AttemptFailedError(
            error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE, message="still invalid"
        )

    with pytest.raises(WorkflowError) as caught:
        run_with_retries(attempt, policy=RetryPolicy(maximum_retries_per_node=2), node_name="n")

    assert attempts == 3, "one attempt plus two retries"
    assert caught.value.attempts == 3
    assert caught.value.error_class is ErrorClass.SCHEMA_VALIDATION_FAILURE


def test_the_loop_waits_between_attempts_and_the_waits_are_bounded() -> None:
    waits: list[float] = []

    def attempt(context: AttemptContext) -> str:
        if context.attempt_number < 2:
            raise AttemptFailedError(
                error_class=ErrorClass.TRANSIENT_PROVIDER_FAILURE, message="rate limited"
            )
        return "ok"

    policy = RetryPolicy(
        maximum_retries_per_node=3,
        base_delay_seconds=1.0,
        maximum_delay_seconds=1.5,
        sleep=waits.append,
    )
    assert run_with_retries(attempt, policy=policy, node_name="n") == "ok"
    assert waits == [1.0, 1.5]


# ------------------------------------------------------------------------------------------
# Preserving the failed output, safely
# ------------------------------------------------------------------------------------------


def test_the_failed_output_is_written_to_the_debug_area(handle: AssessmentHandle) -> None:
    """Section 33 requires the invalid output be preserved for debugging; section 5.16 puts debug
    artifacts in `traces/`."""
    path = preserve_failed_output(
        handle.artifacts, node_name="context-extraction", attempt_number=0, raw_output='{"cl'
    )
    assert path.startswith("traces/")
    assert (handle.artifacts.assessment_root / path).read_text(encoding="utf-8") == '{"cl'


def test_the_error_message_carries_the_path_and_none_of_the_output(
    handle: AssessmentHandle,
) -> None:
    """`ExecutionRecord.error_message` must be safe (section 27). A failed attempt's output is model
    text that can contain an echoed prompt, a quoted source excerpt, or a credential the document
    under review happened to include — all three are in this one."""
    dangerous = (
        "You are the Context Extraction Agent. Follow these instructions.\n"
        "The operations guide says analysis artifacts are retained for 30 days.\n"
        "ANTHROPIC_API_KEY=sk-ant-not-a-real-key-000000\n"
    )

    def attempt(_context: AttemptContext) -> str:
        raise AttemptFailedError(
            error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
            message="the proposal did not validate",
            raw_output=dangerous,
        )

    with pytest.raises(WorkflowError) as caught:
        run_with_retries(
            attempt,
            policy=RetryPolicy(maximum_retries_per_node=0),
            node_name="context-extraction",
            artifacts=handle.artifacts,
        )

    message = str(caught.value)
    assert "traces/" in message
    for secret in ("Context Extraction Agent", "retained for 30 days", "sk-ant-"):
        assert secret not in message

    preserved = caught.value.artifact_path
    assert preserved is not None
    assert (handle.artifacts.assessment_root / preserved).read_text(encoding="utf-8") == dangerous


def test_each_attempt_preserves_its_own_output(handle: AssessmentHandle) -> None:
    """The artifact store refuses to overwrite stored content with different content, and a failed
    attempt is exactly the case where the content differs every time."""
    written: list[str | None] = []

    def attempt(context: AttemptContext) -> str:
        raise AttemptFailedError(
            error_class=ErrorClass.SCHEMA_VALIDATION_FAILURE,
            message="invalid",
            raw_output=f"attempt {context.attempt_number}",
        )

    with pytest.raises(WorkflowError):
        run_with_retries(
            attempt,
            policy=RetryPolicy(maximum_retries_per_node=1),
            node_name="context-extraction",
            artifacts=handle.artifacts,
            on_attempt_failed=lambda _n, _f, path: written.append(path),
        )

    assert len(written) == 2
    assert written[0] != written[1]
