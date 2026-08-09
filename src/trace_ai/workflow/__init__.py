"""Orchestration: phases, the transition table, execution limits, and the node protocol.

DEC-016 rejects an orchestration framework. What is here is what it names instead — a node
protocol, an explicit table of permitted transitions, and the ceilings `agent-design.md` section 27
requires the orchestrator to enforce.
"""

from trace_ai.workflow.limits import Budget, LimitExceededError, LimitKind
from trace_ai.workflow.nodes import Node, NodeContext, NodeResult
from trace_ai.workflow.orchestrator import Orchestrator, RunOutcome
from trace_ai.workflow.phases import (
    NODES_BY_PHASE,
    PAUSE_PHASES,
    TRANSITIONS,
    Phase,
    TransitionError,
    check_transition,
    successor,
)
from trace_ai.workflow.state import (
    AssessmentState,
    NextAction,
    PendingHumanReview,
    RemainingLimits,
)

__all__ = [
    "NODES_BY_PHASE",
    "PAUSE_PHASES",
    "TRANSITIONS",
    "AssessmentState",
    "Budget",
    "LimitExceededError",
    "LimitKind",
    "NextAction",
    "Node",
    "NodeContext",
    "NodeResult",
    "Orchestrator",
    "PendingHumanReview",
    "Phase",
    "RemainingLimits",
    "RunOutcome",
    "TransitionError",
    "check_transition",
    "successor",
]
