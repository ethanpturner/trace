"""Tests for the Context Extraction node — the first model-assisted step in the pipeline.

Every test runs against `DeterministicModel`. No API key, no network, no cost: the seam exists so
that prompt assembly, schema handling, conversion, retry routing, and the ledger can all be
exercised without a provider, and this is the file that spends that.

The rule that shapes the node is `agent-design.md` section 26's: retry when the *output* failed,
never because the *material* is incomplete. Incomplete material is designed to produce questions,
and a node that retried on it would be asking the same model the same question until it stopped
saying "I don't know" — which is fabrication with extra steps.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import ExecutionStatus, ExecutionType
from trace_ai.domain.proposals import CONTEXT_EXTRACTION_AGENT, ContextExtractionProposal
from trace_ai.domain.question import Question
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.system_context import FIRST_VERSION, SystemContext
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import (
    DeterministicModel,
    FailureReason,
    ModelFailure,
    ModelUsage,
)
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.prompts import PromptRegistry
from trace_ai.workflow.context_extraction import NODE_NAME, ContextExtractionNode
from trace_ai.workflow.errors import ErrorClass, WorkflowError
from trace_ai.workflow.limits import Budget, LimitExceededError
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.retry import RetryPolicy
from trace_ai.workflow.state import AssessmentState

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"
PROFILE = resolve_profile("primary-development")


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[tuple[AssessmentHandle, ExecutionLedger]]:
    """An assessment with two ForgeFlow documents ingested and indexed, and a run open."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        for name in ("architecture-overview.md", "sample-repository-notes.md"):
            index_document(
                handle,
                loader.load_document(
                    FORGEFLOW / name,
                    origin=SourceOrigin.UPLOADED_DOCUMENT,
                    trust_level=TrustLevel.UNTRUSTED,
                ),
            )
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield handle, ExecutionLedger(handle, run)


def evidence_ids(handle: AssessmentHandle) -> list[str]:
    return sorted(reference.id for reference in handle.objects.list(EvidenceReference))[:8]


def proposal(handle: AssessmentHandle, **changes: Any) -> ContextExtractionProposal:
    cited = evidence_ids(handle)[0]
    payload: dict[str, Any] = {
        "system": {
            "system_name": "ForgeFlow",
            "system_purpose": "AI-assisted pull request review",
        },
        "components": [
            {
                "key": "webhook",
                "name": "Webhook Receiver",
                "component_type": "service",
                "evidence_ids": [cited],
            }
        ],
        "claims": [
            {
                "key": "auth",
                "subject_type": "component",
                "subject_key": "webhook",
                "predicate": "authentication_provider",
                "value": "GitHub OAuth",
                "status": ClaimStatus.DOCUMENTED,
                "confidence": ConfidenceLevel.HIGH,
                "evidence_ids": [cited],
            }
        ],
        "questions": [
            {
                "key": "hmac",
                "question": "Does webhook validation include HMAC signature verification?",
                "rationale": "Without it the receiver accepts forged deliveries.",
                "priority": "high",
                "blocking": False,
            }
        ],
        **changes,
    }
    return ContextExtractionProposal.model_validate(payload)


def node(
    handle: AssessmentHandle,
    ledger: ExecutionLedger,
    **changes: Any,
) -> ContextExtractionNode:
    options: dict[str, Any] = {
        "ledger": ledger,
        "index": EvidenceIndex(handle),
        "profile": PROFILE,
        "registry": PromptRegistry(),
        "evidence_ids": evidence_ids(handle),
        "assessment_name": "ForgeFlow",
        **changes,
    }
    return ContextExtractionNode(**options)


def context_for(handle: AssessmentHandle, ledger: ExecutionLedger, model: Any) -> NodeContext:
    return NodeContext(
        handle=handle,
        state=AssessmentState.begin(
            assessment_id=handle.assessment_id, workflow_run_id=ledger.run.id
        ),
        model=model,
    )


USAGE = ModelUsage(
    model="claude-opus-5",
    input_tokens=12_000,
    output_tokens=1_500,
    estimated_cost=Decimal("0.0975"),
)


class Usable(DeterministicModel):
    """The fake, with usage attached so the ledger has something to record."""

    def generate(self, **kwargs: Any) -> Any:
        outcome = super().generate(**kwargs)
        if hasattr(outcome, "usage") and outcome.usage.input_tokens == 0:
            return type(outcome)(
                **{**{f: getattr(outcome, f) for f in outcome.__slots__}, "usage": USAGE}
            )
        return outcome


# ------------------------------------------------------------------------------------------
# What one successful extraction produces
# ------------------------------------------------------------------------------------------


def test_the_node_produces_a_context_and_stops(prepared: Any) -> None:
    """It approves nothing and cannot: the checkpoint that follows is a phase in the transition
    table, not a branch this node could take."""
    handle, ledger = prepared
    model = Usable([proposal(handle)])

    result = node(handle, ledger).run(context_for(handle, ledger, model))

    (system,) = handle.objects.list(SystemContext)
    assert system.version == FIRST_VERSION
    assert system.approved_at is None
    assert system.approved_by is None
    assert not system.is_approved
    assert result.produced_object_ids


def test_every_produced_object_is_a_candidate(prepared: Any) -> None:
    handle, ledger = prepared
    node(handle, ledger).run(context_for(handle, ledger, Usable([proposal(handle)])))

    for component in handle.objects.list(Component):
        assert component.status is ObjectStatus.CANDIDATE


def test_identifiers_are_allocated_by_the_application(prepared: Any) -> None:
    """DEC-018. The proposal carried local keys; these are the store's numbers."""
    handle, ledger = prepared
    node(handle, ledger).run(context_for(handle, ledger, Usable([proposal(handle)])))

    (component,) = handle.objects.list(Component)
    assert component.id.startswith("cmp-")
    (claim,) = handle.objects.list(ContextClaim)
    assert claim.subject_id == component.id


def test_generated_by_is_the_agent_version(prepared: Any) -> None:
    """`agent-design.md` section 33. The agent version, not the model: the same agent can run
    against a different model, and an evaluation needs to tell which changed."""
    handle, ledger = prepared
    node(handle, ledger).run(context_for(handle, ledger, Usable([proposal(handle)])))

    (claim,) = handle.objects.list(ContextClaim)
    assert claim.generated_by == CONTEXT_EXTRACTION_AGENT == "context-extraction-v1"
    (question,) = handle.objects.list(Question)
    assert question.generated_by == CONTEXT_EXTRACTION_AGENT


def test_the_prompt_reaches_the_model_with_the_schema_and_the_fence(prepared: Any) -> None:
    """The composed prompt carries the application's own exported schema and the fenced excerpts;
    the trusted region goes in the system position, above the material it governs."""
    handle, ledger = prepared
    model = Usable([proposal(handle)])
    node(handle, ledger).run(context_for(handle, ledger, model))

    (call,) = model.calls
    assert "<source-content" in call.prompt
    assert '"ProposedComponent"' in call.prompt
    assert call.system is not None
    assert "Source precedence" in call.system
    assert "<source-content" not in call.system


def test_the_extraction_declares_its_creativity(prepared: Any) -> None:
    """Section 29 assigns Context Extraction `Creativity.LOW`. It is declared explicitly like the
    other five agents rather than left to the profile default, so a default change cannot silently
    mis-latitude exactly this one agent."""
    from trace_ai.infrastructure.model.seam import Creativity

    handle, ledger = prepared
    model = Usable([proposal(handle)])
    node(handle, ledger).run(context_for(handle, ledger, model))

    (call,) = model.calls
    assert call.settings is not None
    assert call.settings.creativity is Creativity.LOW


# ------------------------------------------------------------------------------------------
# The retry rule
# ------------------------------------------------------------------------------------------


def test_a_schema_failure_retries_and_then_stops_with_a_classified_error(prepared: Any) -> None:
    handle, ledger = prepared
    failure = ModelFailure(
        reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
        message="the response did not validate",
        usage=USAGE,
        raw_output='{"system": {"system_nam',
    )
    model = Usable([failure, failure, failure])

    with pytest.raises(WorkflowError) as caught:
        node(handle, ledger, retry_policy=RetryPolicy(maximum_retries_per_node=2)).run(
            context_for(handle, ledger, model)
        )

    assert caught.value.error_class is ErrorClass.SCHEMA_VALIDATION_FAILURE
    assert caught.value.attempts == 3
    assert len(model.calls) == 3


def test_the_invalid_output_is_preserved_and_referenced(prepared: Any) -> None:
    """`data-model.md` section 33 requires the invalid output be kept for debugging. It goes to the
    debug area and the execution record names the file; the message never carries it."""
    handle, ledger = prepared
    raw = '{"system": {"system_name": "ForgeFlow"'
    failure = ModelFailure(
        reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
        message="unterminated object",
        usage=USAGE,
        raw_output=raw,
    )

    with pytest.raises(WorkflowError):
        node(handle, ledger, retry_policy=RetryPolicy(maximum_retries_per_node=0)).run(
            context_for(handle, ledger, Usable([failure]))
        )

    (record,) = ledger.records()
    preserved = [value for key, value in record.metadata.items() if key.endswith("_output")]
    assert preserved, "the failed output was not referenced from the execution record"
    assert (handle.artifacts.assessment_root / preserved[0]).read_text(encoding="utf-8") == raw


def test_the_call_conditions_reach_the_execution_record(prepared: Any) -> None:
    """#401: agent-design section 29 says the creativity-to-effort mapping is recorded on the
    `ExecutionRecord`, because a wrong mapping produces plausible output rather than an error.
    The adapter puts the conditions on the outcome's metadata; the node carries them onto the
    record, where a reader can find what the call actually ran at."""

    class WithConditions(Usable):
        def generate(self, **kwargs: Any) -> Any:
            outcome = super().generate(**kwargs)
            return type(outcome)(
                **{
                    **{f: getattr(outcome, f) for f in outcome.__slots__},
                    "metadata": {"effort": "high", "creativity": "low"},
                }
            )

    handle, ledger = prepared
    node(handle, ledger).run(context_for(handle, ledger, WithConditions([proposal(handle)])))

    (record,) = ledger.records()
    assert record.metadata["effort"] == "high"
    assert record.metadata["creativity"] == "low"


def test_the_budget_supplies_the_retry_ceiling_when_no_policy_is_given(prepared: Any) -> None:
    """#397: `maximum_retries_per_node` reaches the attempt loop through the budget. Configured
    zero, the node makes exactly one attempt — before this wiring, the hardcoded default retried
    twice regardless of what the configuration said, and configuring the field changed nothing."""
    handle, ledger = prepared
    failure = ModelFailure(
        reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
        message="the response did not validate",
        usage=USAGE,
        raw_output="{",
    )
    model = Usable([failure, failure, failure])

    with pytest.raises(WorkflowError) as caught:
        node(handle, ledger, budget=Budget(maximum_retries_per_node=0)).run(
            context_for(handle, ledger, model)
        )

    assert caught.value.attempts == 1
    assert len(model.calls) == 1
    (record,) = ledger.records()
    assert record.retry_number == 0


def test_the_execution_record_carries_the_retries_consumed(prepared: Any) -> None:
    """#398: `retry_number` is the retries the execution consumed, not a constant zero. One failed
    attempt and a recovery is one retry. The evaluation's retries metric sums this field, so a
    field nothing set would make the metric structurally zero however many retries happened."""
    handle, ledger = prepared
    failure = ModelFailure(
        reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
        message="the response did not validate",
        usage=USAGE,
        raw_output="{",
    )

    node(handle, ledger).run(context_for(handle, ledger, Usable([failure, proposal(handle)])))

    (record,) = ledger.records()
    assert record.retry_number == 1
    assert record.metadata["attempts"] == 2


def test_incomplete_material_produces_questions_and_no_retry(prepared: Any) -> None:
    """`agent-design.md` section 7, Retry behavior: incomplete context produces questions rather
    than repeated model calls. A node that retried here would be asking the same model the same
    question until it stopped saying "I don't know"."""
    handle, ledger = prepared
    sparse = proposal(
        handle,
        components=[],
        claims=[
            {
                "key": "encryption",
                "subject_type": "system",
                "predicate": "database_encryption",
                "value": None,
                "status": ClaimStatus.UNKNOWN,
                "confidence": ConfidenceLevel.LOW,
                "evidence_ids": [],
            }
        ],
    )
    model = Usable([sparse])

    node(handle, ledger).run(context_for(handle, ledger, model))

    assert len(model.calls) == 1, "an incomplete extraction was retried"
    assert handle.objects.list(Question)
    (claim,) = handle.objects.list(ContextClaim)
    assert claim.status is ClaimStatus.UNKNOWN


def test_validation_feedback_reaches_the_second_attempt(prepared: Any) -> None:
    """A second identical call is a second roll of the same dice; what makes the attempt different
    is telling the agent what was wrong."""
    handle, ledger = prepared
    invented = proposal(
        handle,
        components=[
            {
                "key": "webhook",
                "name": "Webhook Receiver",
                "component_type": "service",
                "evidence_ids": ["evd-999"],
            }
        ],
    )
    model = Usable([invented, proposal(handle)])

    node(handle, ledger).run(context_for(handle, ledger, model))

    first, second = model.calls
    assert "Validation feedback" not in first.prompt
    assert "Validation feedback" in second.prompt
    assert "evd-999" in second.prompt


def test_a_proposal_citing_unsupplied_evidence_is_a_retryable_failure(prepared: Any) -> None:
    """`agent-design.md` section 14 lists nonexistent evidence references among the failure
    conditions. The citation validates as a string and resolves to nothing."""
    handle, ledger = prepared
    invented = proposal(
        handle,
        components=[
            {
                "key": "webhook",
                "name": "Webhook Receiver",
                "component_type": "service",
                "evidence_ids": ["evd-999"],
            }
        ],
    )

    with pytest.raises(WorkflowError) as caught:
        node(handle, ledger, retry_policy=RetryPolicy(maximum_retries_per_node=0)).run(
            context_for(handle, ledger, Usable([invented]))
        )
    assert caught.value.error_class is ErrorClass.SCHEMA_VALIDATION_FAILURE


# ------------------------------------------------------------------------------------------
# The ledger and the ceilings
# ------------------------------------------------------------------------------------------


def test_the_execution_record_carries_what_the_call_cost(prepared: Any) -> None:
    handle, ledger = prepared
    node(handle, ledger).run(context_for(handle, ledger, Usable([proposal(handle)])))

    (record,) = ledger.records()
    assert record.execution_type is ExecutionType.MODEL
    assert record.status is ExecutionStatus.COMPLETED
    assert record.node_name == NODE_NAME
    assert record.prompt_version == "extract-context-v1"
    assert record.model_name == "claude-opus-5"
    assert record.input_tokens == 12_000
    assert record.estimated_cost == Decimal("0.0975")
    assert record.output_object_ids


def test_the_run_counters_follow_the_records(prepared: Any) -> None:
    handle, ledger = prepared
    node(handle, ledger).run(context_for(handle, ledger, Usable([proposal(handle)])))

    run = ledger.complete()
    assert run.total_model_calls == 1
    assert run.total_input_tokens == 12_000
    assert run.estimated_cost == Decimal("0.0975")


def test_zero_model_calls_stops_before_the_first_one(prepared: Any) -> None:
    """How a run is made to prove it needs a model rather than assumed to."""
    handle, ledger = prepared
    model = Usable([proposal(handle)])

    with pytest.raises(LimitExceededError):
        node(handle, ledger, budget=Budget(maximum_model_calls=0)).run(
            context_for(handle, ledger, model)
        )

    assert model.calls == []


def test_a_cost_ceiling_stops_before_the_call_rather_than_after_it(prepared: Any) -> None:
    """The check takes a projection of the call about to be made — input from the prompt's length,
    output at the full ceiling — so a limit enforced against it is never crossed. Checked
    afterwards it would be a record of overspending rather than a limit.

    Deliberately pessimistic: a call cannot cost more than the projection, so the tradeoff is that
    a run can stop slightly early. The alternative trades money for tidiness.
    """
    handle, ledger = prepared
    budget = Budget(maximum_cost=Decimal("0.01"))
    model = Usable([proposal(handle)])

    with pytest.raises(LimitExceededError):
        node(handle, ledger, budget=budget).run(context_for(handle, ledger, model))

    assert model.calls == [], "the call was made and then found to be over budget"
    assert budget.cost == Decimal(0)


def test_the_node_refuses_to_run_without_a_model(prepared: Any) -> None:
    """`agent-design.md` section 4 classifies every component deliberately. A model-assisted node
    with no model is misconfigured, and should say so rather than proceed."""
    handle, ledger = prepared
    with pytest.raises(ValueError, match="model-assisted"):
        node(handle, ledger).run(context_for(handle, ledger, None))
