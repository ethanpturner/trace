"""The five execution ceilings, checked before a step rather than after it.

`agent-design.md` section 27 requires the orchestrator to enforce maximum node executions, model
calls, retries, cost, and workflow duration, and DEC-016 assigns that enforcement to the
orchestrator rather than to any node. Three of the five come from `AssessmentConfiguration`
(`data-model.md` section 6); node executions and duration have no field there and are given
defaults here.

**Four ceilings are checks on this budget; the retries ceiling is a policy it issues** (DEC-084).
A retry decision is made inside a node's attempt loop, between a classified failure and the next
attempt — a place the orchestrator never stands, because an agent node records its own execution.
So the budget does not check retries; it *derives* the `RetryPolicy` the loop runs under, from the
same configuration field, through `retry_policy()`. The ceiling is enforced exactly once and the
configured value is the operative one either way.

**Before, not after.** A cost ceiling checked after a call has already been paid is a record of
overspending rather than a limit. The check therefore takes the *estimated* cost of the call about
to be made — which means the ceiling holds against an estimate, and the tradeoff is stated rather
than hidden: an estimate that is too low lets one call through that a perfect one would have
refused. One call is the worst case, and it is bounded by `max_output_tokens`.

**Exceeding a limit stops the run with a classified reason.** It does not truncate the work, skip a
node, or continue with a smaller request. `agent-design.md` section 27 exists because an
uncontrolled loop is the failure mode of an agent pipeline, and a limit that degrades gracefully is
one that never stops anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from trace_ai.workflow.retry import RetryPolicy
from trace_ai.workflow.state import RemainingLimits

if TYPE_CHECKING:
    from datetime import datetime

    from trace_ai.domain.assessment import AssessmentConfiguration

__all__ = [
    "DEFAULT_MAXIMUM_DURATION_SECONDS",
    "DEFAULT_MAXIMUM_NODE_EXECUTIONS",
    "Budget",
    "LimitExceededError",
    "LimitKind",
    "resolve_retry_policy",
]

# Section 27 requires both ceilings and section 6 carries neither, so they are set here. The node
# count is a multiple of the fourteen phases -- generous enough that only a loop reaches it, which
# is what it is for. The duration bounds a run that is stuck rather than slow; a paused run does
# not consume it, because DEC-017 pauses by exiting.
DEFAULT_MAXIMUM_NODE_EXECUTIONS: Final = 100
DEFAULT_MAXIMUM_DURATION_SECONDS: Final = 3_600.0


class LimitKind(StrEnum):
    """Which of the budget-checked ceilings stopped the run.

    Retries are absent deliberately (DEC-084): an exhausted retry budget stops the run under the
    *failing attempt's* error class with the attempt count, because section 26 classifies the stop
    by what kept failing, not by the ceiling that stopped the retrying.
    """

    MODEL_CALLS = "maximum_model_calls"
    COST = "maximum_cost"
    NODE_EXECUTIONS = "maximum_node_executions"
    DURATION = "maximum_workflow_duration"


class LimitExceededError(RuntimeError):
    """A step was refused because it would exceed a ceiling.

    Carries the kind so the run's error is classified rather than a string somebody parses, and
    names the limit and the value that would have crossed it — the two things a reader needs to
    decide whether the limit is wrong or the run is.
    """

    def __init__(self, kind: LimitKind, limit: object, attempted: object) -> None:
        super().__init__(
            f"{kind.value} is {limit}; this step would reach {attempted}. "
            f"Stopping (agent-design.md section 27)."
        )
        self.kind = kind
        self.limit = limit
        self.attempted = attempted


@dataclass(slots=True)
class Budget:
    """What a run may still spend, and the checks that refuse a step that would exceed it.

    Mutable, unlike almost everything else here, and deliberately: this is the one object that
    changes as the run proceeds and is not part of the persisted record. What *is* persisted is the
    remaining figures on `AssessmentState.execution_limits`, which `remaining()` produces.
    """

    maximum_model_calls: int | None = None
    maximum_cost: Decimal | None = None
    maximum_retries_per_node: int = 2
    maximum_node_executions: int = DEFAULT_MAXIMUM_NODE_EXECUTIONS
    maximum_duration_seconds: float = DEFAULT_MAXIMUM_DURATION_SECONDS

    model_calls: int = 0
    cost: Decimal = field(default_factory=lambda: Decimal(0))
    node_executions: int = 0

    @classmethod
    def from_configuration(
        cls,
        configuration: AssessmentConfiguration,
        *,
        maximum_node_executions: int = DEFAULT_MAXIMUM_NODE_EXECUTIONS,
        maximum_duration_seconds: float = DEFAULT_MAXIMUM_DURATION_SECONDS,
    ) -> Budget:
        """The three ceilings section 6 carries, plus the two it does not."""
        return cls(
            maximum_model_calls=configuration.maximum_model_calls,
            maximum_cost=configuration.maximum_cost,
            maximum_retries_per_node=configuration.maximum_retries_per_node,
            maximum_node_executions=maximum_node_executions,
            maximum_duration_seconds=maximum_duration_seconds,
        )

    # -- checks ----------------------------------------------------------------------------

    def check_node_execution(self) -> None:
        """Refuse a node execution that would exceed the count or the elapsed-time ceiling."""
        if self.node_executions + 1 > self.maximum_node_executions:
            raise LimitExceededError(
                LimitKind.NODE_EXECUTIONS, self.maximum_node_executions, self.node_executions + 1
            )

    def check_duration(self, *, started_at: datetime, at: datetime) -> None:
        """Refuse to continue a run that has been going longer than the ceiling allows."""
        elapsed = (at - started_at).total_seconds()
        if elapsed > self.maximum_duration_seconds:
            raise LimitExceededError(
                LimitKind.DURATION, self.maximum_duration_seconds, round(elapsed, 3)
            )

    def check_model_call(self, *, estimated_cost: Decimal = Decimal(0)) -> None:
        """Refuse a model call that would exceed the call count or the cost ceiling.

        A configuration of zero calls stops before the first one, which is the point: it is how a
        run is made to prove it needs a model rather than assumed to.
        """
        if self.maximum_model_calls is not None and self.model_calls + 1 > self.maximum_model_calls:
            raise LimitExceededError(
                LimitKind.MODEL_CALLS, self.maximum_model_calls, self.model_calls + 1
            )
        if self.maximum_cost is not None and self.cost + estimated_cost > self.maximum_cost:
            raise LimitExceededError(LimitKind.COST, self.maximum_cost, self.cost + estimated_cost)

    def retry_policy(self) -> RetryPolicy:
        """The policy an agent node's attempt loop runs under, carrying this budget's ceiling.

        This is how `maximum_retries_per_node` becomes operative (#397): a node given a budget and
        no explicit policy runs under this one, so configuring zero retries produces exactly one
        attempt rather than the policy default's three.
        """
        return RetryPolicy(maximum_retries_per_node=self.maximum_retries_per_node)

    # -- consumption -----------------------------------------------------------------------

    def spend_node_execution(self) -> None:
        self.node_executions += 1

    def spend_model_call(self, cost: Decimal = Decimal(0)) -> None:
        self.model_calls += 1
        self.cost += cost

    def remaining(self) -> RemainingLimits:
        """The figures section 31's `execution_limits` block records.

        `None` where no ceiling is configured, rather than a large number standing in for one: an
        absent limit and a generous limit are different statements about a run.
        """
        return RemainingLimits(
            model_calls_remaining=(
                None
                if self.maximum_model_calls is None
                else max(self.maximum_model_calls - self.model_calls, 0)
            ),
            cost_remaining=(
                None
                if self.maximum_cost is None
                else max(self.maximum_cost - self.cost, Decimal(0))
            ),
        )


def resolve_retry_policy(explicit: RetryPolicy | None, budget: Budget | None) -> RetryPolicy:
    """The policy a node's attempt loop runs under.

    Precedence is the point (#397): an explicitly supplied policy wins, because a test that says
    "no retries" means it; otherwise the budget's, because that is where the configuration's
    `maximum_retries_per_node` lives; the built-in default only when there is neither.
    """
    if explicit is not None:
        return explicit
    if budget is not None:
        return budget.retry_policy()
    return RetryPolicy()
