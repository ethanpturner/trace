"""Tests for the orchestrator: the transition table, the ceilings, the state, and the ledger.

DEC-016 rejected an orchestration framework, so these are the properties a framework would
otherwise have provided and which now have to be true of ordinary Python. Four of them carry the
weight.

**A transition outside the table is refused.** That is what makes the table worth having: the
pipeline has one path, so a table looks redundant against a list until you ask what refuses
anything else.

**A ceiling stops the run rather than degrading it.** `agent-design.md` section 27 exists because
an uncontrolled loop is the failure mode of an agent pipeline, and a limit that skips a node or
shrinks a request is one that never stops anything.

**A cost ceiling is checked before the call, not after.** A limit enforced afterwards is a record of
overspending.

**A node cannot reach another node.** Routing is the orchestrator's alone, and the mechanism is an
absence — `NodeContext` carries no registry and no orchestrator — so the absence is what is tested.

Everything runs against `DeterministicModel`; no test here needs an API key or makes a call.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.execution import ExecutionStatus, ExecutionType, RunStatus
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import ModelUsage
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.workflow import (
    NODES_BY_PHASE,
    PAUSE_PHASES,
    TRANSITIONS,
    AssessmentState,
    Budget,
    LimitExceededError,
    LimitKind,
    Node,
    NodeContext,
    NodeResult,
    Orchestrator,
    Phase,
    TransitionError,
    check_transition,
    successor,
)


@dataclass(slots=True)
class ScriptedNode:
    """A node that does what a test tells it to and reaches nothing.

    Written per test rather than mocked, because the interesting assertions are about what the
    orchestrator does with a result rather than about how a node was called.
    """

    name: str
    phase: Phase
    execution_type: ExecutionType = ExecutionType.DETERMINISTIC
    version: str = "0.1"
    result: NodeResult = field(default_factory=NodeResult)
    seen: list[NodeContext] = field(default_factory=list)

    def run(self, context: NodeContext) -> NodeResult:
        self.seen.append(context)
        return self.result


@pytest.fixture
def ledger(tmp_path: Path) -> Iterator[ExecutionLedger]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield ExecutionLedger(handle, run)


def state_for(
    ledger: ExecutionLedger, phase: Phase = Phase.ASSESSMENT_INITIALIZATION
) -> AssessmentState:
    started = AssessmentState.begin(
        assessment_id=ledger.run.assessment_id, workflow_run_id=ledger.run.id
    )
    return AssessmentState.model_validate(
        started.model_dump()
        | {"current_phase": phase, "next_action": {"action": "execute_node", "phase": phase}}
    )


def orchestrator(
    ledger: ExecutionLedger, *nodes: Node, budget: Budget | None = None
) -> Orchestrator:
    return Orchestrator(ledger.handle, ledger=ledger, nodes=list(nodes), budget=budget)


# ------------------------------------------------------------------------------------------
# The transition table
# ------------------------------------------------------------------------------------------


def test_the_table_covers_every_phase() -> None:
    """A phase missing from the table is a phase whose transitions are undefined rather than
    forbidden, which is the state DEC-016 replaced."""
    assert set(TRANSITIONS) == set(Phase)
    assert set(NODES_BY_PHASE) == set(Phase)


def test_the_pipeline_is_one_path_from_initialization_to_completion() -> None:
    """Fourteen phases, no analytical branching (DEC-016). Walked rather than listed, so the walk
    fails if the table ever disagrees with itself."""
    walked = [Phase.ASSESSMENT_INITIALIZATION]
    while (following := successor(walked[-1])) is not None:
        walked.append(following)
    assert len(walked) == 14
    assert walked[-1] is Phase.ASSESSMENT_COMPLETION
    assert len(set(walked)) == len(walked), "a phase is visited twice"


def test_a_transition_outside_the_table_is_refused_by_name() -> None:
    """The question after this is raised is which end is wrong, so both are in the message."""
    with pytest.raises(TransitionError, match="context_extraction -> evaluation"):
        check_transition(Phase.CONTEXT_EXTRACTION, Phase.EVALUATION)


def test_a_phase_may_not_transition_to_itself() -> None:
    """The smallest uncontrolled loop `agent-design.md` section 27 asks to be prevented. A retry is
    a second execution within a phase, bounded separately; it is not a transition."""
    for phase in Phase:
        assert phase not in TRANSITIONS[phase]


def test_the_two_checkpoints_are_phases_like_any_other() -> None:
    """DEC-005 makes them structural: workflow-graph nodes rather than runtime conditionals."""
    assert set(PAUSE_PHASES) == {Phase.HUMAN_CONTEXT_REVIEW, Phase.HUMAN_FINDING_REVIEW}
    for checkpoint in PAUSE_PHASES:
        assert checkpoint in TRANSITIONS
        assert successor(checkpoint) is not None


# ------------------------------------------------------------------------------------------
# The state
# ------------------------------------------------------------------------------------------


def test_the_state_advances_only_along_the_table(ledger: ExecutionLedger) -> None:
    state = state_for(ledger)
    assert state.advance(Phase.DOCUMENT_INGESTION).current_phase is Phase.DOCUMENT_INGESTION
    with pytest.raises(TransitionError):
        state.advance(Phase.EVALUATION)


def test_the_state_holds_identifiers_and_no_content(ledger: ExecutionLedger) -> None:
    """`data-model.md` section 31's state-design rule: no source documents, no prompt transcripts,
    no generated objects in the payload. A state carrying content is a second copy of the
    authoritative data, and the two disagree the first time one is written and the other is not."""
    state = state_for(ledger).advance(
        Phase.DOCUMENT_INGESTION, source_document_ids=["src-001", "src-002"]
    )
    payload = json.loads(state.model_dump_json())

    for key, value in payload.items():
        if isinstance(value, list):
            assert all(isinstance(item, str) and len(item) < 40 for item in value), (
                f"{key} holds something longer than an identifier"
            )

    assert "prompt" not in json.dumps(payload).lower()


def test_pausing_names_the_checkpoint_and_the_objects(ledger: ExecutionLedger) -> None:
    """What makes a paused run self-describing (DEC-017)."""
    paused = state_for(ledger, Phase.HUMAN_CONTEXT_REVIEW).paused_for(
        Phase.HUMAN_CONTEXT_REVIEW, ["ctx-001", "ctx-002"]
    )
    assert paused.status is RunStatus.PAUSED
    assert paused.pending_human_review is not None
    assert paused.pending_human_review.object_ids == ["ctx-001", "ctx-002"]
    assert paused.next_action.action == "await_human_review"


def test_a_phase_that_is_not_a_checkpoint_cannot_pause(ledger: ExecutionLedger) -> None:
    """There are two checkpoints and no configuration adds a third (DEC-005, DEC-012)."""
    with pytest.raises(ValueError, match="structural checkpoints"):
        state_for(ledger).paused_for(Phase.CONTEXT_EXTRACTION, ["ctx-001"])


# ------------------------------------------------------------------------------------------
# Nodes, and what they cannot reach
# ------------------------------------------------------------------------------------------


def test_a_node_of_each_execution_type_satisfies_the_protocol() -> None:
    """Section 27's three types share one protocol, so a checkpoint is a node rather than a special
    case in the orchestrator's control flow."""
    for execution_type, phase in (
        (ExecutionType.DETERMINISTIC, Phase.CONTEXT_VALIDATION),
        (ExecutionType.MODEL, Phase.CONTEXT_EXTRACTION),
        (ExecutionType.HUMAN_CHECKPOINT, Phase.HUMAN_CONTEXT_REVIEW),
    ):
        node = ScriptedNode(NODES_BY_PHASE[phase][0], phase, execution_type)
        assert isinstance(node, Node)


def test_a_node_is_given_no_way_to_reach_another_node(ledger: ExecutionLedger) -> None:
    """Routing is the orchestrator's alone (`agent-design.md` section 27), and the mechanism is an
    absence: a node that could reach a peer could build the loop the section prevents."""
    node = ScriptedNode("context-validation", Phase.CONTEXT_VALIDATION)
    orchestrator(ledger, node).run(state_for(ledger, Phase.CONTEXT_VALIDATION))

    (context,) = node.seen
    fields = set(type(context).__dataclass_fields__)
    assert fields == {"handle", "state", "model"}
    for forbidden in ("orchestrator", "nodes", "registry", "enqueue", "run_node"):
        assert not hasattr(context, forbidden)


def test_a_node_registered_against_an_undeclared_phase_is_refused(ledger: ExecutionLedger) -> None:
    """A node in the wrong phase runs correctly and in the wrong place."""
    with pytest.raises(ValueError, match="context_validation"):
        orchestrator(ledger, ScriptedNode("threat-analysis", Phase.CONTEXT_VALIDATION))


def test_two_nodes_may_not_claim_one_name(ledger: ExecutionLedger) -> None:
    """A phase runs every node the table declares for it; a *name* is registered exactly once."""
    with pytest.raises(ValueError, match="already has a node named"):
        orchestrator(
            ledger,
            ScriptedNode("document-ingestion", Phase.DOCUMENT_INGESTION),
            ScriptedNode("document-ingestion", Phase.DOCUMENT_INGESTION),
        )


def test_a_two_node_phase_runs_both_in_the_declared_order(ledger: ExecutionLedger) -> None:
    """`NODES_BY_PHASE` names the order, so registration order decides nothing — the same
    reasoning that once refused a second node per phase, kept under the table's authority."""
    order: list[str] = []

    @dataclass(slots=True)
    class Ordered:
        name: str
        phase: Phase
        execution_type: ExecutionType = ExecutionType.DETERMINISTIC
        version: str = "0.1"

        def run(self, context: NodeContext) -> NodeResult:
            order.append(self.name)
            return NodeResult()

    outcome = orchestrator(
        ledger,
        Ordered("evidence-indexing", Phase.DOCUMENT_INGESTION),  # registered backwards
        Ordered("document-ingestion", Phase.DOCUMENT_INGESTION),
    ).run(state_for(ledger, Phase.DOCUMENT_INGESTION))

    assert order == ["document-ingestion", "evidence-indexing"]
    assert outcome.state.errors == ["no node is registered for phase context_extraction"]


def test_a_declared_node_left_unregistered_stops_the_run(ledger: ExecutionLedger) -> None:
    """Half a phase is a skipped node wearing a completed phase's clothes."""
    outcome = orchestrator(
        ledger, ScriptedNode("document-ingestion", Phase.DOCUMENT_INGESTION)
    ).run(state_for(ledger, Phase.DOCUMENT_INGESTION))

    assert outcome.state.status is RunStatus.FAILED
    assert "declares node 'evidence-indexing'" in outcome.state.errors[0]


def test_a_later_node_sees_what_an_earlier_one_recorded(ledger: ExecutionLedger) -> None:
    """`state_changes` are absorbed between the nodes of one phase, not held for the advance."""
    first = ScriptedNode(
        "document-ingestion",
        Phase.DOCUMENT_INGESTION,
        result=NodeResult(state_changes={"source_document_ids": ["src-001"]}),
    )
    second = ScriptedNode("evidence-indexing", Phase.DOCUMENT_INGESTION)
    orchestrator(ledger, first, second).run(state_for(ledger, Phase.DOCUMENT_INGESTION))

    assert second.seen[0].state.source_document_ids == ["src-001"]


def test_a_deterministic_node_is_given_no_model(ledger: ExecutionLedger) -> None:
    """Not a precaution: a deterministic node with a model is one that could quietly become
    model-assisted, and `agent-design.md` section 4 classifies every component deliberately."""
    node = ScriptedNode("context-validation", Phase.CONTEXT_VALIDATION)
    orchestrator(ledger, node).run(state_for(ledger, Phase.CONTEXT_VALIDATION))
    assert node.seen[0].model is None


# ------------------------------------------------------------------------------------------
# Ceilings
# ------------------------------------------------------------------------------------------


def test_zero_model_calls_stops_before_the_first_one(ledger: ExecutionLedger) -> None:
    """How a run is made to prove it needs a model rather than assumed to."""
    node = ScriptedNode("context-extraction", Phase.CONTEXT_EXTRACTION, ExecutionType.MODEL)
    outcome = orchestrator(ledger, node, budget=Budget(maximum_model_calls=0)).run(
        state_for(ledger, Phase.CONTEXT_EXTRACTION)
    )

    assert outcome.stopped_because == LimitKind.MODEL_CALLS.value
    assert outcome.state.status is RunStatus.FAILED
    assert node.seen == [], "the node ran despite the ceiling"


def test_a_cost_ceiling_is_checked_before_the_call_that_would_cross_it() -> None:
    """Checked afterwards, a cost ceiling is a record of overspending rather than a limit."""
    budget = Budget(maximum_cost=Decimal("1.00"))
    budget.spend_model_call(Decimal("0.90"))

    budget.check_model_call(estimated_cost=Decimal("0.05"))
    with pytest.raises(LimitExceededError) as caught:
        budget.check_model_call(estimated_cost=Decimal("0.20"))
    assert caught.value.kind is LimitKind.COST


def test_the_node_execution_ceiling_stops_a_loop() -> None:
    budget = Budget(maximum_node_executions=1)
    budget.check_node_execution()
    budget.spend_node_execution()
    with pytest.raises(LimitExceededError) as caught:
        budget.check_node_execution()
    assert caught.value.kind is LimitKind.NODE_EXECUTIONS


def test_the_duration_ceiling_stops_a_run_that_is_stuck() -> None:
    budget = Budget(maximum_duration_seconds=60.0)
    started = now()
    budget.check_duration(started_at=started, at=started + timedelta(seconds=30))
    with pytest.raises(LimitExceededError) as caught:
        budget.check_duration(started_at=started, at=started + timedelta(seconds=61))
    assert caught.value.kind is LimitKind.DURATION


def test_a_resumed_run_does_not_inherit_the_paused_hours(ledger: ExecutionLedger) -> None:
    """#396: DEC-017 pauses by exiting and waiting costs nothing, so the duration ceiling bounds
    the active segment rather than the wall clock since the run first began. A ledger whose run
    row started hours ago is exactly what a resume after a long review looks like; it must run,
    not stop on its first step with maximum_workflow_duration."""
    run = ledger.run
    ledger.run = type(run).model_validate(
        {**run.model_dump(), "started_at": now() - timedelta(hours=2)}
    )

    outcome = orchestrator(
        ledger,
        ScriptedNode("document-ingestion", Phase.DOCUMENT_INGESTION),
        ScriptedNode("evidence-indexing", Phase.DOCUMENT_INGESTION),
    ).run(state_for(ledger, Phase.DOCUMENT_INGESTION), stop_before=Phase.CONTEXT_EXTRACTION)

    assert outcome.stopped_because == "stopped_before_context_extraction"
    assert outcome.state.status is not RunStatus.FAILED
    assert not outcome.state.errors


def test_the_retry_ceiling_travels_as_the_budget_policy() -> None:
    """DEC-084 / #397: the budget does not check retries; it issues the policy the node's attempt
    loop runs under, so the configured value is the operative one and zero means zero. An explicit
    policy still wins — a test that says "no retries" means it — and the built-in default applies
    only when there is neither."""
    from trace_ai.workflow import RetryPolicy
    from trace_ai.workflow.errors import ErrorClass
    from trace_ai.workflow.limits import resolve_retry_policy

    budget = Budget(maximum_retries_per_node=0)
    policy = budget.retry_policy()
    assert policy.maximum_retries_per_node == 0
    assert not policy.should_retry(ErrorClass.SCHEMA_VALIDATION_FAILURE, attempt_number=0)

    assert resolve_retry_policy(None, budget).maximum_retries_per_node == 0
    explicit = RetryPolicy(maximum_retries_per_node=5)
    assert resolve_retry_policy(explicit, budget) is explicit
    assert resolve_retry_policy(None, None).maximum_retries_per_node == 2


def test_an_absent_ceiling_is_none_rather_than_a_large_number() -> None:
    """An absent limit and a generous limit are different statements about a run."""
    remaining = Budget().remaining()
    assert remaining.model_calls_remaining is None
    assert remaining.cost_remaining is None


def test_remaining_budget_reaches_the_state(ledger: ExecutionLedger) -> None:
    """Section 31's `execution_limits` block is what a reader of a paused run consults."""
    node = ScriptedNode("context-validation", Phase.CONTEXT_VALIDATION)
    outcome = orchestrator(ledger, node, budget=Budget(maximum_model_calls=5)).run(
        state_for(ledger, Phase.CONTEXT_VALIDATION)
    )
    assert outcome.state.execution_limits.model_calls_remaining == 5


# ------------------------------------------------------------------------------------------
# The ledger and the run counters
# ------------------------------------------------------------------------------------------


def test_one_record_is_written_per_node_execution(ledger: ExecutionLedger) -> None:
    nodes = [
        ScriptedNode("context-validation", Phase.CONTEXT_VALIDATION),
        ScriptedNode(
            "human-context-review",
            Phase.HUMAN_CONTEXT_REVIEW,
            ExecutionType.HUMAN_CHECKPOINT,
            result=NodeResult(awaiting_review=["ctx-001"]),
        ),
    ]
    orchestrator(ledger, *nodes).run(state_for(ledger, Phase.CONTEXT_VALIDATION))

    records = ledger.records()
    assert [record.node_name for record in records] == [
        "context-validation",
        "human-context-review",
    ]
    assert all(record.status is ExecutionStatus.COMPLETED for record in records)


def test_model_usage_reaches_the_record_and_the_run(ledger: ExecutionLedger) -> None:
    """`WorkflowRun.total_model_calls` is a measurement of what was written rather than a tally
    kept beside it."""
    usage = ModelUsage(
        model="claude-opus-5",
        input_tokens=1_200,
        output_tokens=300,
        estimated_cost=Decimal("0.0135"),
    )
    node = ScriptedNode(
        "context-extraction",
        Phase.CONTEXT_EXTRACTION,
        ExecutionType.MODEL,
        result=NodeResult(model_usages=[usage], prompt_version="extract-context-v1"),
    )
    orchestrator(ledger, node).run(state_for(ledger, Phase.CONTEXT_EXTRACTION))

    (record,) = ledger.records()
    assert record.execution_type is ExecutionType.MODEL
    assert record.model_name == "claude-opus-5"
    assert record.prompt_version == "extract-context-v1"
    assert (record.input_tokens, record.output_tokens) == (1_200, 300)

    run = ledger.complete()
    assert run.total_model_calls == 1
    assert run.total_input_tokens == 1_200
    assert run.estimated_cost == Decimal("0.0135")


def test_a_run_that_calls_no_model_reports_zero_rather_than_nothing(
    ledger: ExecutionLedger,
) -> None:
    orchestrator(ledger, ScriptedNode("context-validation", Phase.CONTEXT_VALIDATION)).run(
        state_for(ledger, Phase.CONTEXT_VALIDATION)
    )
    assert ledger.complete().total_model_calls == 0


# ------------------------------------------------------------------------------------------
# Running
# ------------------------------------------------------------------------------------------


def test_a_checkpoint_pauses_the_run_and_the_loop_exits(ledger: ExecutionLedger) -> None:
    """DEC-017: pausing is stopping. Nothing is held in memory across a human review."""
    checkpoint = ScriptedNode(
        "human-context-review",
        Phase.HUMAN_CONTEXT_REVIEW,
        ExecutionType.HUMAN_CHECKPOINT,
        result=NodeResult(awaiting_review=["ctx-001", "ctx-002"]),
    )
    later = ScriptedNode("threat-analysis", Phase.THREAT_GENERATION, ExecutionType.MODEL)

    outcome = orchestrator(ledger, checkpoint, later).run(
        state_for(ledger, Phase.HUMAN_CONTEXT_REVIEW)
    )

    assert outcome.paused
    assert outcome.stopped_because == "paused"
    assert later.seen == [], "the run continued past a checkpoint"
    assert ledger.run.status is RunStatus.PAUSED
    assert ledger.run.current_node == Phase.HUMAN_CONTEXT_REVIEW.value


def test_a_run_reaching_completion_closes_the_run(ledger: ExecutionLedger) -> None:
    node = ScriptedNode("evaluation", Phase.EVALUATION)
    outcome = orchestrator(ledger, node).run(state_for(ledger, Phase.EVALUATION))
    assert outcome.completed
    assert ledger.run.status is RunStatus.COMPLETED


# ------------------------------------------------------------------------------------------
# Crash safety: an unclassified failure is recorded, and state is persisted
# ------------------------------------------------------------------------------------------


@dataclass(slots=True)
class RaisingNode:
    """A node that raises something the taxonomy does not classify."""

    name: str
    phase: Phase
    error: BaseException
    execution_type: ExecutionType = ExecutionType.DETERMINISTIC
    version: str = "0.1"

    def run(self, context: NodeContext) -> NodeResult:
        raise self.error


def test_an_unclassified_node_error_fails_the_run_rather_than_escaping(
    ledger: ExecutionLedger,
) -> None:
    """A node raising a bare RuntimeError used to escape the loop and leave the run row `running`
    forever. It is now `unexpected_application_failure`, recorded on the run and the state."""
    node = RaisingNode(
        "context-validation", Phase.CONTEXT_VALIDATION, RuntimeError("a bug, not a provider")
    )
    outcome = orchestrator(ledger, node).run(state_for(ledger, Phase.CONTEXT_VALIDATION))

    assert outcome.state.status is RunStatus.FAILED
    assert outcome.stopped_because == "unexpected_application_failure"
    assert "a bug, not a provider" in outcome.state.errors[-1]
    assert ledger.run.status is RunStatus.FAILED
    assert ledger.run.error_summary is not None


def test_a_failed_run_persists_a_resumable_state_file(ledger: ExecutionLedger) -> None:
    """`_stop` writes the state so `resume_assessment` can restart from the failed phase rather than
    re-running the whole pipeline."""
    from trace_ai.workflow.checkpoint import load_state

    node = RaisingNode("context-validation", Phase.CONTEXT_VALIDATION, RuntimeError("boom"))
    orchestrator(ledger, node).run(state_for(ledger, Phase.CONTEXT_VALIDATION))

    persisted = load_state(ledger.handle, ledger.run.id)
    assert persisted.status is RunStatus.FAILED
    assert persisted.current_phase is Phase.CONTEXT_VALIDATION


def test_a_completed_run_persists_a_completed_state_file(ledger: ExecutionLedger) -> None:
    """The state file used to be frozen at the last pause forever; a completed run says completed."""
    from trace_ai.workflow.checkpoint import load_state

    node = ScriptedNode("evaluation", Phase.EVALUATION)
    orchestrator(ledger, node).run(state_for(ledger, Phase.EVALUATION))

    persisted = load_state(ledger.handle, ledger.run.id)
    assert persisted.status is RunStatus.COMPLETED


def test_state_is_persisted_on_every_phase_transition(ledger: ExecutionLedger) -> None:
    """A crash between phases leaves an accurate record of where the run reached."""
    from trace_ai.workflow.checkpoint import load_state

    first = ScriptedNode("context-validation", Phase.CONTEXT_VALIDATION)
    # The phase after context validation is a checkpoint, which pauses; the persisted state then
    # reflects the advance out of context validation rather than the initial phase.
    orchestrator(ledger, first).run(state_for(ledger, Phase.CONTEXT_VALIDATION))

    persisted = load_state(ledger.handle, ledger.run.id)
    assert persisted.current_phase is not Phase.CONTEXT_VALIDATION


def test_a_missing_node_stops_the_run_rather_than_skipping_the_phase(
    ledger: ExecutionLedger,
) -> None:
    """Skipping would be the graceful degradation section 27 rules out: a pipeline that keeps going
    is the failure mode, not the recovery."""
    outcome = orchestrator(ledger).run(state_for(ledger, Phase.CONTEXT_VALIDATION))
    assert outcome.state.status is RunStatus.FAILED
    assert "no node is registered" in outcome.state.errors[0]


def test_state_changes_from_a_node_reach_the_next_phase(ledger: ExecutionLedger) -> None:
    node = ScriptedNode(
        "context-validation",
        Phase.CONTEXT_VALIDATION,
        result=NodeResult(state_changes={"context_claim_ids": ["ctx-001"]}),
    )
    outcome = orchestrator(ledger, node).run(state_for(ledger, Phase.CONTEXT_VALIDATION))
    assert outcome.state.context_claim_ids == ["ctx-001"]
