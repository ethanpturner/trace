"""The shared attempt body every model-assisted node uses (WS11).

Six nodes ran the same ~30 lines around `model.generate`; this is that body, once. These pin what it
guarantees so a change to it changes all six at once and on purpose: a provider failure becomes a
classified, feedback-carrying `AttemptFailedError`; the conditions the call ran at — including the
`schema_grammar` degradation, which no node copied before — reach the execution record; the budget is
charged on success and failure alike; and a node wired without a model fails rather than raising an
`AttributeError`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel

from trace_ai.domain.base import now
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.seam import (
    FailureReason,
    GenerationSettings,
    ModelFailure,
    ModelOutcome,
    ModelSuccess,
    ModelUsage,
)
from trace_ai.services.execution_ledger import Execution
from trace_ai.workflow.errors import ErrorClass
from trace_ai.workflow.limits import Budget
from trace_ai.workflow.model_call import cache_prefix_of, call_model, with_retry_feedback
from trace_ai.workflow.retry import AttemptFailedError

PROFILE = resolve_profile("primary-development")


class _Proposal(BaseModel):
    note: str = "ok"


class _Model:
    """A one-shot `StructuredModel` returning a preset outcome and recording the call."""

    def __init__(self, outcome: ModelOutcome[_Proposal]) -> None:
        self._outcome = outcome
        self.calls: list[dict[str, object]] = []

    @property
    def name(self) -> str:
        return "test-model"

    @property
    def capabilities(self) -> frozenset:  # type: ignore[type-arg]
        return frozenset()

    def generate[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings | None = None,
        system: str | None = None,
        cache_prefix: str | None = None,
    ) -> ModelOutcome[T]:
        self.calls.append({"prompt": prompt, "system": system, "cache_prefix": cache_prefix})
        return self._outcome  # type: ignore[return-value]


def _execution() -> Execution:
    return Execution(node_name="test-node", started_at=now())


def _success(*, metadata: dict[str, object] | None = None) -> ModelSuccess[_Proposal]:
    return ModelSuccess(
        value=_Proposal(),
        usage=ModelUsage(model="test-model", input_tokens=10, estimated_cost=Decimal("0.01")),
        metadata=metadata or {},
    )


def test_success_returns_the_value_and_records_usage() -> None:
    model = _Model(_success())
    execution = _execution()
    usages: list[ModelUsage] = []

    value = call_model(
        model,
        prompt="p",
        schema=_Proposal,
        profile=PROFILE,
        system="sys",
        budget=None,
        execution=execution,
        usages=usages,
    )

    assert isinstance(value, _Proposal)
    assert len(usages) == 1
    assert model.calls == [{"prompt": "p", "system": "sys", "cache_prefix": None}]


def test_success_copies_the_recorded_conditions_including_schema_grammar() -> None:
    """schema_grammar joins effort and creativity (WS11): a run that lost server-side schema
    enforcement was otherwise indistinguishable from one that kept it."""
    metadata: dict[str, object] = {
        "effort": "high",
        "creativity": "low",
        "schema_grammar": "too_large_omitted",
    }
    execution = _execution()

    call_model(
        _Model(_success(metadata=metadata)),
        prompt="p",
        schema=_Proposal,
        profile=PROFILE,
        system=None,
        budget=None,
        execution=execution,
        usages=[],
    )

    assert execution.metadata["schema_grammar"] == "too_large_omitted"
    assert execution.metadata["effort"] == "high"
    assert execution.metadata["creativity"] == "low"


def test_a_failure_becomes_a_classified_attempt_failure() -> None:
    failure = ModelFailure(
        reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
        message="did not validate",
        usage=ModelUsage(model="test-model", estimated_cost=Decimal("0.02")),
        raw_output="the raw text",
    )
    usages: list[ModelUsage] = []

    with pytest.raises(AttemptFailedError) as raised:
        call_model(
            _Model(failure),
            prompt="p",
            schema=_Proposal,
            profile=PROFILE,
            system=None,
            budget=None,
            execution=_execution(),
            usages=usages,
        )

    assert raised.value.error_class is ErrorClass.SCHEMA_VALIDATION_FAILURE
    assert raised.value.feedback == "did not validate"
    assert raised.value.raw_output == "the raw text"
    assert len(usages) == 1


def test_the_budget_is_charged_on_success_and_on_failure() -> None:
    # The ceiling is generous: the pre-call check projects against max_output_tokens, so a tight
    # cap would trip on the projection rather than on the spend this test is about.
    budget = Budget(maximum_model_calls=10, maximum_cost=Decimal("100.00"))
    call_model(
        _Model(_success()),
        prompt="p",
        schema=_Proposal,
        profile=PROFILE,
        system=None,
        budget=budget,
        execution=_execution(),
        usages=[],
    )
    assert budget.model_calls == 1
    assert budget.cost == Decimal("0.01")

    with pytest.raises(AttemptFailedError):
        call_model(
            _Model(
                ModelFailure(
                    reason=FailureReason.TRANSIENT_PROVIDER_FAILURE,
                    message="provider down",
                    usage=ModelUsage(model="test-model", estimated_cost=Decimal("0.03")),
                )
            ),
            prompt="p",
            schema=_Proposal,
            profile=PROFILE,
            system=None,
            budget=budget,
            execution=_execution(),
            usages=[],
        )
    assert budget.model_calls == 2
    assert budget.cost == Decimal("0.04")


def test_a_missing_model_is_an_application_fault_not_a_crash() -> None:
    with pytest.raises(AttemptFailedError) as raised:
        call_model(
            None,
            prompt="p",
            schema=_Proposal,
            profile=PROFILE,
            system=None,
            budget=None,
            execution=_execution(),
            usages=[],
        )
    assert raised.value.error_class is ErrorClass.UNEXPECTED_APPLICATION_FAILURE


def test_cache_prefix_is_everything_before_the_source_suffix() -> None:
    prompt = "shared blocks\n\nbody template\n\nFENCED SOURCE"
    assert cache_prefix_of(prompt, "FENCED SOURCE") == "shared blocks\n\nbody template\n\n"


def test_cache_prefix_is_stable_across_the_retry_feedback_suffix() -> None:
    """The prefix must be a prefix of the retry prompt too, so caching survives a retry."""
    base = "shared\n\nbody\n\nSOURCE"
    prefix = cache_prefix_of(base, "SOURCE")
    retry = with_retry_feedback(base, "field x wrong", instruction="Fix it.")
    assert prefix is not None
    assert retry.startswith(prefix)


def test_cache_prefix_declines_when_the_suffix_is_empty_or_absent() -> None:
    assert cache_prefix_of("a prompt", "") is None
    assert cache_prefix_of("a prompt", "not here") is None


def test_with_retry_feedback_is_a_no_op_on_the_first_attempt() -> None:
    assert with_retry_feedback("base", None, instruction="fix it") == "base"


def test_with_retry_feedback_appends_the_heading_and_instruction() -> None:
    result = with_retry_feedback(
        "base", "field x is wrong", instruction="Return a corrected object."
    )
    assert result == (
        "base\n\n## Validation feedback on your previous attempt\n\n"
        "field x is wrong\n\nReturn a corrected object."
    )
