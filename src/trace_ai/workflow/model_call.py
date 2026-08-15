"""One attempt at a model call, shared by all six model-assisted nodes (WS11).

Every node ran the same ~30 lines around `model.generate`: project the cost against the budget,
make the one attempt, turn a `ModelFailure` into an `AttemptFailedError` the retry loop understands,
reject the impossible third arm of the outcome union, record the attempt's usage, and copy the
conditions the call ran at onto the execution record. Six copies meant every cross-cutting change —
truncation escalation, cost projection, the `capabilities_used` and `schema_grammar` recording — had
to be made six times and stay in step, and the agent cap means it is always exactly six. One of
them, the creativity setting, had already drifted before it was caught.

`call_model` is that body, once. What stays in the node is what genuinely differs: the prompt (with
its per-node retry instruction, `with_retry_feedback` below), the schema, the system region, and the
domain validation of the returned object, which each node runs and raises its own
`AttemptFailedError` from. This adds no agent and no orchestration — it removes duplication inside
the existing six (DEC-016, DEC-030).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_ai.infrastructure.model.seam import ModelFailure, ModelSuccess
from trace_ai.workflow.errors import ErrorClass, classify_model_failure
from trace_ai.workflow.retry import AttemptFailedError

if TYPE_CHECKING:
    from pydantic import BaseModel

    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.infrastructure.model.seam import ModelUsage, StructuredModel
    from trace_ai.services.execution_ledger import Execution
    from trace_ai.workflow.limits import Budget

__all__ = ["cache_prefix_of", "call_model", "with_retry_feedback"]

# The conditions a call actually ran at, copied from the outcome onto the execution record so a
# reader of an ExecutionRecord can find them (section 29). `schema_grammar` joins `effort` and
# `creativity` here (WS11): when the provider rejects a schema as too large the adapter degrades to
# no server-side grammar and records `too_large_omitted`, and a run where every agent lost schema
# enforcement was otherwise indistinguishable from one where none did.
_RECORDED_CONDITIONS = ("effort", "creativity", "schema_grammar")


def cache_prefix_of(prompt: str, variable_suffix: str) -> str | None:
    """The stable leading span of a composed prompt: everything before its per-call source content.

    Every agent prompt ends with its source content (the fenced excerpts, or the report input), so
    the shared blocks, the body template, and the schema — identical across a node's calls and its
    retries — are the span before it, and that is what an adapter can cache (WS10). Returns `None`
    when the suffix is empty or not found, so the caller passes no hint rather than a wrong one; the
    retry feedback appended after the source keeps the prefix stable across attempts.
    """
    if not variable_suffix:
        return None
    index = prompt.rfind(variable_suffix)
    return prompt[:index] if index > 0 else None


def with_retry_feedback(base: str, feedback: str | None, *, instruction: str) -> str:
    """The prompt for one attempt: the composed base, plus validation feedback on a retry.

    `feedback` is `None` on the first attempt and the base is returned unchanged. On a retry the
    loop's accumulated validation feedback is appended under a fixed heading, followed by the node's
    own `instruction` — the one sentence that differs per agent, telling it not to restate the
    previous object or inflate its answer to make the correction pass.
    """
    if feedback is None:
        return base
    return (
        f"{base}\n\n## Validation feedback on your previous attempt\n\n{feedback}\n\n{instruction}"
    )


def call_model[T: BaseModel](
    model: StructuredModel | None,
    *,
    prompt: str,
    schema: type[T],
    profile: ModelProfile,
    system: str | None,
    budget: Budget | None,
    execution: Execution,
    usages: list[ModelUsage],
    cache_prefix: str | None = None,
) -> T:
    """Make one model attempt and return the validated object, or raise `AttemptFailedError`.

    The cost is projected against the budget before the call and charged after it, on success and
    failure alike, so a failed attempt still counts against the ceiling (section 27). Every provider
    condition arrives as a `ModelFailure` and leaves as an `AttemptFailedError` carrying the
    validation feedback forward; the returned object is not yet domain-validated — that is the
    caller's, because what makes a proposal invalid is the node's to say.

    `model` is `None` only when a model node was wired without one, which is an application fault
    rather than a provider condition, so it raises the non-retryable `UNEXPECTED_APPLICATION_FAILURE`
    — the guard the six nodes previously expressed as a `# type: ignore[union-attr]`.
    """
    if model is None:  # pragma: no cover - a model node is always wired with a model
        raise AttemptFailedError(
            error_class=ErrorClass.UNEXPECTED_APPLICATION_FAILURE,
            message="a model-assisted node was run without a model",
        )
    if budget is not None:
        budget.check_model_call(
            estimated_cost=profile.cost_of(
                input_tokens=len(prompt) // 4,
                output_tokens=profile.settings.max_output_tokens,
            )
        )

    outcome = model.generate(
        prompt=prompt,
        schema=schema,
        settings=profile.settings,
        system=system,
        cache_prefix=cache_prefix,
    )

    if isinstance(outcome, ModelFailure):
        usages.append(outcome.usage)
        if budget is not None:
            budget.spend_model_call(outcome.usage.estimated_cost)
        raise AttemptFailedError(
            error_class=classify_model_failure(outcome.reason),
            message=outcome.message,
            raw_output=outcome.raw_output,
            feedback=outcome.message,
        )

    if not isinstance(outcome, ModelSuccess):  # pragma: no cover - the union has two arms
        raise AttemptFailedError(
            error_class=ErrorClass.UNEXPECTED_APPLICATION_FAILURE,
            message=f"the model seam returned {type(outcome).__name__}",
        )

    usages.append(outcome.usage)
    for condition_key in _RECORDED_CONDITIONS:
        if condition_key in outcome.metadata:
            execution.metadata[condition_key] = outcome.metadata[condition_key]
    if budget is not None:
        budget.spend_model_call(outcome.usage.estimated_cost)

    return outcome.value
