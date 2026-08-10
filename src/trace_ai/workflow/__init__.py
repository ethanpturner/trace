"""Orchestration: phases, the transition table, execution limits, and the node protocol.

DEC-016 rejects an orchestration framework. What is here is what it names instead — a node
protocol, an explicit table of permitted transitions, and the ceilings `agent-design.md` section 27
requires the orchestrator to enforce.
"""

from trace_ai.workflow.checkpoint import (
    CheckpointNode,
    ReviewPackage,
    build_review_package,
    load_state,
    pending_object_ids,
    resume,
    save_state,
)
from trace_ai.workflow.context_review import (
    ApprovalRefusedError,
    ClaimPresentation,
    ContextReviewNode,
    ContextReviewPackage,
    QuotedExcerpt,
    approve_context,
    build_context_review_package,
    request_re_extraction,
    system_context_key,
)
from trace_ai.workflow.context_validation import (
    SECTION_7_TRIGGERS,
    ContextValidationOutcome,
    ReviewTrigger,
    ValidationError,
    validate_context,
)
from trace_ai.workflow.errors import (
    NON_RETRYABLE,
    RETRYABLE,
    SECTION_11_FAILURE_CLASSES,
    ErrorClass,
    WorkflowError,
    classify_model_failure,
)
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
from trace_ai.workflow.retry import (
    AttemptContext,
    AttemptFailedError,
    RetryPolicy,
    preserve_failed_output,
    run_with_retries,
)
from trace_ai.workflow.state import (
    AssessmentState,
    NextAction,
    PendingHumanReview,
    RemainingLimits,
)

__all__ = [
    "NODES_BY_PHASE",
    "NON_RETRYABLE",
    "PAUSE_PHASES",
    "RETRYABLE",
    "SECTION_7_TRIGGERS",
    "SECTION_11_FAILURE_CLASSES",
    "TRANSITIONS",
    "ApprovalRefusedError",
    "AssessmentState",
    "AttemptContext",
    "AttemptFailedError",
    "Budget",
    "CheckpointNode",
    "ClaimPresentation",
    "ContextReviewNode",
    "ContextReviewPackage",
    "ContextValidationOutcome",
    "ErrorClass",
    "LimitExceededError",
    "LimitKind",
    "NextAction",
    "Node",
    "NodeContext",
    "NodeResult",
    "Orchestrator",
    "PendingHumanReview",
    "Phase",
    "QuotedExcerpt",
    "RemainingLimits",
    "RetryPolicy",
    "ReviewPackage",
    "ReviewTrigger",
    "RunOutcome",
    "TransitionError",
    "ValidationError",
    "WorkflowError",
    "approve_context",
    "build_context_review_package",
    "build_review_package",
    "check_transition",
    "classify_model_failure",
    "load_state",
    "pending_object_ids",
    "preserve_failed_output",
    "request_re_extraction",
    "resume",
    "run_with_retries",
    "save_state",
    "successor",
    "system_context_key",
    "validate_context",
]
