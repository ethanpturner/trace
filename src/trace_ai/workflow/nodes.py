"""The node protocol: what a workflow step is, and what it is not allowed to reach.

`current-architecture.md` section 5.3 says the orchestrator treats each analysis activity as a node
with defined inputs and outputs, and DEC-016 makes a node "a function taking typed input and
returning typed output, with a name and a version". All three execution types in `data-model.md`
section 27 use this one protocol — model, deterministic, and human checkpoint — so a checkpoint is a
node rather than a special case in the orchestrator's control flow. That is what DEC-005 means by
structural.

**Routing is not a node's to do.** `agent-design.md` section 27 says no agent may invoke itself or
another agent without workflow control, and the mechanism is `NodeContext`: it carries the
assessment handle, the state, and a model, and it carries no registry, no orchestrator, and no
other node. A node cannot enqueue itself because it has nothing to enqueue itself onto. A test
asserts the absence, because the absence is the safety property.

**A node reports what it did; it does not decide what happens next.** `NodeResult` names the objects
produced, the model calls made, and — for a checkpoint — the objects awaiting a decision. Which
phase follows is read from the transition table by the orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from trace_ai.domain.execution import ExecutionType
    from trace_ai.infrastructure.model.seam import ModelUsage, StructuredModel
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.workflow.phases import Phase
    from trace_ai.workflow.state import AssessmentState

__all__ = ["Node", "NodeContext", "NodeResult"]


@dataclass(frozen=True, slots=True)
class NodeContext:
    """Everything a node may reach, and nothing else.

    The absences are the design. There is no orchestrator here, no node registry, and no way to ask
    for another node — routing belongs to the orchestrator (`agent-design.md` section 27), and a
    node that could reach a peer could build the loop the section exists to prevent.

    `model` is `None` for a deterministic node and for a checkpoint. A node that finds it `None` and
    needs it is misconfigured, and should say so rather than proceed.
    """

    handle: AssessmentHandle
    """The scoped repository and artifact store. One assessment's code cannot reach another's."""

    state: AssessmentState
    model: StructuredModel | None = None


@dataclass(slots=True)
class NodeResult:
    """What one node execution produced, in the terms the ledger and the state record.

    Identifiers, counts, and costs — never objects and never text. A result carrying an object
    would be the second copy `data-model.md` section 31's state-design rule refuses.
    """

    produced_object_ids: list[str] = field(default_factory=list)
    consumed_object_ids: list[str] = field(default_factory=list)
    state_changes: dict[str, object] = field(default_factory=dict)
    """Fields to set on the state as the run advances — identifier lists, a context version."""

    model_usages: list[ModelUsage] = field(default_factory=list)
    """One per model call the node made. The orchestrator counts them and adds up the cost; a node
    reporting a count it did not make would make `WorkflowRun.total_model_calls` a claim rather
    than a measurement."""

    awaiting_review: list[str] = field(default_factory=list)
    """For a checkpoint node: the objects that need a `ReviewerDecision` before the run resumes."""

    prompt_version: str | None = None
    model_name: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def total_cost(self) -> Decimal:
        return sum((usage.estimated_cost for usage in self.model_usages), Decimal(0))


@runtime_checkable
class Node(Protocol):
    """One workflow step.

    `phase` is declared rather than inferred so the orchestrator can refuse a node registered
    against a phase that does not list it — a node in the wrong phase is a pipeline nobody decided
    on, and it would otherwise run correctly and in the wrong place.
    """

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def execution_type(self) -> ExecutionType: ...

    @property
    def phase(self) -> Phase: ...

    def run(self, context: NodeContext) -> NodeResult: ...
