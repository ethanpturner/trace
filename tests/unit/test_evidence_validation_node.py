"""The Evidence Validation node, and the three ForgeFlow cases it exists to get right.

Every test runs against `DeterministicModel` with an authored response, so none proves a model
behaves well. What they prove is that the *application* keeps the right answer intact and rejects
the wrong one deterministically where it can — which for this agent is a narrow but load-bearing
set:

**The misquotation check.** Section 14 makes "the rationale misquotes or materially changes
evidence" invalid output, and `data-model.md` section 8 fixes an `EvidenceReference`'s text at
creation, so a divergence is the agent's. This is the one section 14 failure condition that is
fully decidable, and the proposal carries `quoted_text` so it can be decided.

**Contradictions cannot be passed over.** "Contradictory evidence is ignored" is a set-level
failure: no individual assessment is wrong for staying silent about a contradiction another one
handles, so the check is that every supplied contradiction is named by *someone*.

**`unsupported` is never retried.** Section 14's four retry conditions are shape conditions.
Retrying a classification would ask the agent to find support that does not exist, which is
section 26's fabrication-on-the-third-attempt in this agent's terms.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import Recommendation, SubjectType
from trace_ai.domain.execution import ExecutionRecord, ExecutionStatus
from trace_ai.domain.proposals.evidence_validation import (
    EVIDENCE_VALIDATION_AGENT,
    EvidenceValidationProposal,
)
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import DeterministicModel, ModelUsage
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.seam import Creativity, FailureReason, ModelFailure
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.evidence.validation_package import (
    UnknownSubjectError,
    assemble_evidence_input,
)
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.prompts import PromptRegistry
from trace_ai.workflow.errors import WorkflowError
from trace_ai.workflow.evidence_validation import (
    NODE_NAME,
    EvidenceValidationNode,
    unaddressed_contradictions,
)
from trace_ai.workflow.limits import Budget, LimitExceededError
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.retry import RetryPolicy
from trace_ai.workflow.state import AssessmentState

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"
PROFILE = resolve_profile("primary-development")

USAGE = ModelUsage(
    model="claude-opus-5",
    input_tokens=9_000,
    output_tokens=1_500,
    estimated_cost=Decimal("0.08"),
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


@pytest.fixture
def prepared(
    tmp_path: Path,
) -> Iterator[tuple[AssessmentHandle, ExecutionLedger, ContextClaim, SourceObservation]]:
    """ForgeFlow ingested, one context claim under test, and one recorded contradiction."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        for name in ("architecture-overview.md", "operations-guide.md"):
            index_document(
                handle,
                loader.load_document(
                    FORGEFLOW / name,
                    origin=SourceOrigin.UPLOADED_DOCUMENT,
                    trust_level=TrustLevel.UNTRUSTED,
                ),
            )
        claim, observation = _subjects(handle)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield handle, ExecutionLedger(handle, run), claim, observation


def _subjects(handle: AssessmentHandle) -> tuple[ContextClaim, SourceObservation]:
    stamped = now()
    cited = sorted(reference.id for reference in handle.objects.list(EvidenceReference))[:2]

    with handle.objects.transaction():
        component = Component.model_validate(
            {
                "id": handle.objects.allocate("cmp"),
                "assessment_id": handle.assessment_id,
                "name": "Analysis Worker",
                "component_type": "background_worker",
                "evidence_ids": [cited[0]],
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(component)

        claim = ContextClaim.model_validate(
            {
                "id": handle.objects.allocate("ctx"),
                "assessment_id": handle.assessment_id,
                "subject_type": "component",
                "subject_id": component.id,
                "predicate": "retains source files for",
                "value": "no time at all; they are deleted immediately after analysis",
                "status": "documented",
                "confidence": ConfidenceLevel.MEDIUM,
                "evidence_ids": [cited[0]],
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "created_at": stamped,
                "updated_at": stamped,
            }
        )
        handle.objects.save(claim)

        observation = SourceObservation.model_validate(
            {
                "id": handle.objects.allocate("obs"),
                "assessment_id": handle.assessment_id,
                "kind": ObservationKind.CONTRADICTION,
                "summary": (
                    "The product overview says source files are deleted immediately after "
                    "analysis; the operations guide says artifacts are retained for 30 days."
                ),
                "evidence_ids": cited,
                "status": ObjectStatus.CANDIDATE,
                "created_at": stamped,
            }
        )
        handle.objects.save(observation)

    return claim, observation


def node(prepared: Any, **changes: Any) -> EvidenceValidationNode:
    handle, ledger, claim, observation = prepared
    options: dict[str, Any] = {
        "ledger": ledger,
        "index": EvidenceIndex(handle),
        "profile": PROFILE,
        "registry": PromptRegistry(),
        "subjects": [claim],
        "observations": [observation],
        **changes,
    }
    return EvidenceValidationNode(**options)


def node_context(handle: AssessmentHandle, ledger: ExecutionLedger, model: Any) -> NodeContext:
    return NodeContext(
        handle=handle,
        state=AssessmentState.begin(
            assessment_id=handle.assessment_id, workflow_run_id=ledger.run.id
        ),
        model=model,
    )


def an_assessment(prepared: Any, **changes: Any) -> dict[str, Any]:
    handle, _, claim, observation = prepared
    cited = sorted(reference.id for reference in handle.objects.list(EvidenceReference))[0]
    payload: dict[str, Any] = {
        "subject_type": SubjectType.CONTEXT_CLAIM,
        "subject_id": claim.id,
        "evidence_ids": [cited],
        "evidence_strengths": {cited: EvidenceStrength.DIRECT},
        "validation_status": ValidationStatus.CONTRADICTED,
        "rationale": (
            "One passage states immediate deletion and another states thirty-day retention. "
            "Which is authoritative is not established by either."
        ),
        "contradictions": [observation.id],
        "confidence": ConfidenceLevel.MEDIUM,
        "recommendation": Recommendation.DOWNGRADE_TO_QUESTION,
    }
    payload.update(changes)
    return payload


def proposal(prepared: Any, *assessments: dict[str, Any]) -> EvidenceValidationProposal:
    return EvidenceValidationProposal.model_validate(
        {"assessments": list(assessments) if assessments else [an_assessment(prepared)]}
    )


def run(prepared: Any, model: Any, **changes: Any) -> Any:
    handle, ledger, _, _ = prepared
    return node(prepared, **changes).propose(node_context(handle, ledger, model))


# What one successful pass produces


def test_a_single_assessment_succeeds_with_no_retry(prepared: Any) -> None:
    model = Usable([proposal(prepared)])

    outcome = run(prepared, model)

    assert len(model.calls) == 1
    assert outcome.result.metadata["attempts"] == 1
    assert len(outcome.proposal.assessments) == 1


def test_the_node_declares_the_evidence_validation_phase(prepared: Any) -> None:
    assert node(prepared).phase is Phase.EVIDENCE_VALIDATION
    assert node(prepared).name == NODE_NAME


def test_run_returns_the_node_result(prepared: Any) -> None:
    handle, ledger, _, _ = prepared
    model = Usable([proposal(prepared)])

    result = node(prepared).run(node_context(handle, ledger, model))

    assert result.metadata["agent"] == EVIDENCE_VALIDATION_AGENT == "evidence-validation-v1"


def test_the_node_persists_nothing(prepared: Any) -> None:
    """Section 22's write model: the agent proposes and the deterministic step writes."""
    handle, _, _, _ = prepared
    before = len(handle.objects.list(ContextClaim))

    outcome = run(prepared, Usable([proposal(prepared)]))

    assert outcome.result.produced_object_ids == []
    assert len(handle.objects.list(ContextClaim)) == before


def test_the_agent_module_contains_no_store_write() -> None:
    """A test the next issue's node depends on: there is no write path through this module."""
    text = (PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "evidence_validation.py").read_text(
        encoding="utf-8"
    )

    for forbidden in ("objects.save", "repository.save", ".transaction()", "allocate("):
        assert forbidden not in text


def test_the_agent_emits_no_finding_and_approves_nothing() -> None:
    """Section 14 prohibits approving findings; DEC-005 reserves approval for the checkpoint.

    `finding` is a legitimate *subject* type — section 20 names it — so the assertion is on the
    proposal's fields rather than on the schema text, where the word appears for that reason.
    """
    from trace_ai.domain.proposals.evidence_validation import EvidenceAssessmentProposal

    assert set(EvidenceValidationProposal.model_fields) == {"assessments"}
    assert not set(EvidenceAssessmentProposal.model_fields) & {
        "finding",
        "findings",
        "approved",
        "approval",
        "status",
        "reviewer_status",
        "severity",
    }


def test_the_call_uses_low_creativity(prepared: Any) -> None:
    model = Usable([proposal(prepared)])

    run(prepared, model)

    assert model.calls[0].settings.creativity is Creativity.LOW


# The package (section 23)


def test_the_package_carries_the_conclusion_the_evidence_and_the_contradiction(
    prepared: Any,
) -> None:
    handle, _, claim, observation = prepared

    package = assemble_evidence_input(
        assessment_id=handle.assessment_id,
        subjects=[claim],
        index=EvidenceIndex(handle),
        observations=[observation],
        profile=PROFILE,
    )

    assert package.subject_ids == (claim.id,)
    assert package.contradiction_ids == (observation.id,)
    assert set(observation.evidence_ids) <= set(package.evidence_ids)


def test_the_package_does_not_restate_the_evidence_policy(prepared: Any) -> None:
    """The shared prompt block carries it; a payload copy would be a second thing to keep right."""
    handle, _, claim, observation = prepared

    package = assemble_evidence_input(
        assessment_id=handle.assessment_id,
        subjects=[claim],
        index=EvidenceIndex(handle),
        observations=[observation],
        profile=PROFILE,
    )

    assert "Evidence policy" not in package.trusted


def test_the_trusted_region_carries_no_quoted_source_text(prepared: Any) -> None:
    handle, _, claim, observation = prepared
    index = EvidenceIndex(handle)

    package = assemble_evidence_input(
        assessment_id=handle.assessment_id,
        subjects=[claim],
        index=index,
        observations=[observation],
        profile=PROFILE,
    )

    for excerpt in index.render_for_prompt(list(package.evidence_ids)):
        assert excerpt["quoted_text"] not in package.trusted
        assert excerpt["quoted_text"] in package.untrusted


def test_a_subject_the_package_cannot_describe_is_refused(prepared: Any) -> None:
    handle, _, _, observation = prepared

    with pytest.raises(UnknownSubjectError, match="SourceObservation"):
        assemble_evidence_input(
            assessment_id=handle.assessment_id,
            subjects=[observation],
            index=EvidenceIndex(handle),
            profile=PROFILE,
        )


def test_the_subject_entry_carries_no_workflow_status(prepared: Any) -> None:
    """How far a conclusion has travelled must not be able to raise its classification."""
    handle, _, claim, _ = prepared

    package = assemble_evidence_input(
        assessment_id=handle.assessment_id,
        subjects=[claim],
        index=EvidenceIndex(handle),
        profile=PROFILE,
    )

    assert "reviewer_status" not in package.trusted
    assert "generated_by" not in package.trusted


# Fixture: the source-retention contradiction (scenario section 16.1)


def test_the_retention_contradiction_produces_a_contradicted_assessment(prepared: Any) -> None:
    outcome = run(prepared, Usable([proposal(prepared)]))

    (assessed,) = outcome.proposal.assessments
    assert assessed.validation_status is ValidationStatus.CONTRADICTED
    assert assessed.contradictions


def test_no_winner_is_silently_chosen(prepared: Any) -> None:
    """Scenario section 16.1 states the requirement in those words."""
    outcome = run(prepared, Usable([proposal(prepared)]))

    (assessed,) = outcome.proposal.assessments
    assert assessed.validation_status is not ValidationStatus.SUPPORTED
    assert assessed.recommendation is Recommendation.DOWNGRADE_TO_QUESTION


def test_a_contradiction_left_unaddressed_is_retried(prepared: Any) -> None:
    """Section 14: contradictory evidence may not be ignored."""
    handle, ledger, _, _ = prepared
    ignoring = proposal(
        prepared,
        an_assessment(
            prepared,
            validation_status=ValidationStatus.UNSUPPORTED,
            contradictions=[],
        ),
    )
    model = Usable([ignoring, proposal(prepared)])

    outcome = node(prepared).propose(node_context(handle, ledger, model))

    assert outcome.result.metadata["attempts"] == 2


def test_the_correction_names_the_ignored_contradiction(prepared: Any) -> None:
    handle, ledger, _, observation = prepared
    ignoring = proposal(
        prepared,
        an_assessment(prepared, validation_status=ValidationStatus.UNSUPPORTED, contradictions=[]),
    )
    model = Usable([ignoring, proposal(prepared)])

    node(prepared).propose(node_context(handle, ledger, model))

    assert observation.id in model.calls[1].prompt


def test_unaddressed_contradictions_is_a_set_level_check(prepared: Any) -> None:
    """No single assessment is wrong for staying silent about one another handles."""
    handle, _, _, observation = prepared
    cited = sorted(r.id for r in handle.objects.list(EvidenceReference))[0]
    two = proposal(
        prepared,
        an_assessment(prepared),
        an_assessment(
            prepared,
            validation_status=ValidationStatus.UNSUPPORTED,
            evidence_ids=[cited],
            evidence_strengths={cited: EvidenceStrength.CONTEXTUAL},
            contradictions=[],
            recommendation=Recommendation.DOCUMENTATION_GAP,
        ),
    )

    assert unaddressed_contradictions(two, [observation.id]) == ()


# Fixture: missing documentation is not a weakness


def test_silence_produces_a_question_or_a_gap_and_never_a_weakness(prepared: Any) -> None:
    handle, _, _, _ = prepared
    cited = sorted(r.id for r in handle.objects.list(EvidenceReference))[0]
    silent = proposal(
        prepared,
        an_assessment(
            prepared,
            validation_status=ValidationStatus.UNSUPPORTED,
            evidence_ids=[cited],
            evidence_strengths={cited: EvidenceStrength.CONTEXTUAL},
            missing_evidence=["documentation stating that signature verification is performed"],
            recommendation=Recommendation.DOCUMENTATION_GAP,
        ),
    )

    outcome = run(prepared, Usable([silent]))

    (assessed,) = outcome.proposal.assessments
    assert assessed.validation_status is ValidationStatus.UNSUPPORTED
    assert assessed.recommendation in {
        Recommendation.DOCUMENTATION_GAP,
        Recommendation.DOWNGRADE_TO_QUESTION,
    }
    assert assessed.missing_evidence


def test_an_unsupported_classification_never_triggers_a_retry(prepared: Any) -> None:
    """Section 26 in this agent's terms: retrying it asks for support that does not exist."""
    handle, _, _, _ = prepared
    cited = sorted(r.id for r in handle.objects.list(EvidenceReference))[0]
    model = Usable(
        [
            proposal(
                prepared,
                an_assessment(
                    prepared,
                    validation_status=ValidationStatus.UNSUPPORTED,
                    evidence_ids=[cited],
                    evidence_strengths={cited: EvidenceStrength.CONTEXTUAL},
                    contradictions=[],
                    recommendation=Recommendation.DOCUMENTATION_GAP,
                ),
            )
        ]
    )

    outcome = run(prepared, model, observations=[])

    assert len(model.calls) == 1
    assert outcome.result.metadata["attempts"] == 1


def test_an_assessment_set_with_no_unsupported_classification_is_a_success(
    prepared: Any,
) -> None:
    outcome = run(prepared, Usable([proposal(prepared)]))

    assert outcome.result.metadata["assessments"] == 1
    assert not [
        assessed
        for assessed in outcome.proposal.assessments
        if assessed.validation_status is ValidationStatus.UNSUPPORTED
    ]


def test_an_empty_assessment_set_is_a_success(prepared: Any) -> None:
    model = Usable([EvidenceValidationProposal.model_validate({})])

    outcome = run(prepared, model, observations=[])

    assert len(model.calls) == 1
    assert outcome.result.metadata["assessments"] == 0


# Fixture: repeated claims do not raise a classification


def test_two_assessments_from_one_reference_are_each_judged_on_that_reference(
    prepared: Any,
) -> None:
    """Section 14: evidence quantity is not evidence quality.

    Two conclusions resting on the same single passage produce two assessments, each citing that
    one reference. Nothing in the schema or the node lets the second raise the first, and the test
    is that the shared reference stays one identifier rather than becoming two citations.
    """
    handle, _, _, _ = prepared
    cited = sorted(r.id for r in handle.objects.list(EvidenceReference))[0]
    repeated = proposal(
        prepared,
        an_assessment(prepared),
        an_assessment(
            prepared,
            validation_status=ValidationStatus.UNSUPPORTED,
            evidence_ids=[cited],
            evidence_strengths={cited: EvidenceStrength.CONTEXTUAL},
            contradictions=[],
            rationale="The same sentence is the only support, and it is contextual.",
            recommendation=Recommendation.REVISE,
        ),
    )

    outcome = run(prepared, Usable([repeated]))

    first, second = outcome.proposal.assessments
    assert cited in first.evidence_ids
    assert second.evidence_ids == [cited]
    assert second.evidence_strengths[cited] is EvidenceStrength.CONTEXTUAL


# The misquotation check (section 14)


def test_a_matching_quotation_passes(prepared: Any) -> None:
    handle, _, _, _ = prepared
    cited = sorted(r.id for r in handle.objects.list(EvidenceReference))[0]
    stored = EvidenceIndex(handle).render_for_prompt([cited])[0]["quoted_text"]
    words = " ".join(stored.split()[:4])

    outcome = run(
        prepared,
        Usable([proposal(prepared, an_assessment(prepared, quoted_text={cited: words}))]),
    )

    assert outcome.result.metadata["attempts"] == 1


def test_a_changed_quotation_is_retried(prepared: Any) -> None:
    """Section 8 fixes the text at creation, so any divergence is the agent's."""
    handle, ledger, _, _ = prepared
    cited = sorted(r.id for r in handle.objects.list(EvidenceReference))[0]
    misquoted = proposal(
        prepared,
        an_assessment(prepared, quoted_text={cited: "the platform encrypts nothing at all"}),
    )
    model = Usable([misquoted, proposal(prepared)])

    outcome = node(prepared).propose(node_context(handle, ledger, model))

    assert outcome.result.metadata["attempts"] == 2
    assert "not in the passage" in model.calls[1].prompt


def test_repeated_misquotation_stops_the_run(prepared: Any) -> None:
    handle, ledger, _, _ = prepared
    cited = sorted(r.id for r in handle.objects.list(EvidenceReference))[0]
    misquoted = proposal(
        prepared, an_assessment(prepared, quoted_text={cited: "nothing like the passage"})
    )

    with pytest.raises(WorkflowError):
        node(prepared).propose(
            node_context(handle, ledger, Usable([misquoted, misquoted, misquoted]))
        )


# References and retry routing


def test_an_assessment_about_something_not_supplied_is_retried(prepared: Any) -> None:
    handle, ledger, _, _ = prepared
    invalid = proposal(prepared, an_assessment(prepared, subject_id="ctx-909"))
    model = Usable([invalid, proposal(prepared)])

    outcome = node(prepared).propose(node_context(handle, ledger, model))

    assert outcome.result.metadata["attempts"] == 2
    assert "ctx-909" in model.calls[1].prompt


@pytest.mark.parametrize(
    "reason",
    [FailureReason.SCHEMA_VALIDATION_FAILURE, FailureReason.TRANSIENT_PROVIDER_FAILURE],
)
def test_a_retryable_provider_failure_is_retried(prepared: Any, reason: FailureReason) -> None:
    handle, ledger, _, _ = prepared
    failure = ModelFailure(reason=reason, message="try again", usage=USAGE)
    model = Usable([failure, proposal(prepared)])

    outcome = node(prepared).propose(node_context(handle, ledger, model))

    assert outcome.result.metadata["attempts"] == 2


@pytest.mark.parametrize("reason", [FailureReason.REFUSED, FailureReason.INVALID_REQUEST])
def test_a_non_retryable_failure_is_not_retried(prepared: Any, reason: FailureReason) -> None:
    handle, ledger, _, _ = prepared
    model = Usable([ModelFailure(reason=reason, message="no", usage=USAGE)])

    with pytest.raises(WorkflowError):
        node(prepared).propose(node_context(handle, ledger, model))

    assert len(model.calls) == 1


def test_retries_stop_at_the_configured_ceiling(prepared: Any) -> None:
    handle, ledger, _, _ = prepared
    failure = ModelFailure(
        reason=FailureReason.TRANSIENT_PROVIDER_FAILURE, message="down", usage=USAGE
    )
    model = Usable([failure, failure, failure])

    with pytest.raises(WorkflowError):
        node(prepared, retry_policy=RetryPolicy()).propose(node_context(handle, ledger, model))

    assert len(model.calls) == 3


# The execution record and ceilings


def test_an_execution_record_is_written_for_a_successful_invocation(prepared: Any) -> None:
    handle, _, _, _ = prepared
    run(prepared, Usable([proposal(prepared)]))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert record.status is ExecutionStatus.COMPLETED
    assert record.prompt_version == "validate-evidence-v1"
    assert record.metadata["assessments"] == 1


def test_the_execution_record_names_its_inputs(prepared: Any) -> None:
    handle, _, claim, observation = prepared
    run(prepared, Usable([proposal(prepared)]))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert claim.id in record.input_object_ids
    assert observation.id in record.input_object_ids


def test_a_failed_attempt_output_goes_to_traces(prepared: Any) -> None:
    handle, ledger, _, _ = prepared
    invalid = proposal(prepared, an_assessment(prepared, subject_id="ctx-909"))

    with pytest.raises(WorkflowError):
        node(prepared).propose(node_context(handle, ledger, Usable([invalid, invalid, invalid])))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert any(key.endswith("_output") for key in record.metadata)


def test_a_zero_call_ceiling_stops_the_node_before_it_spends(prepared: Any) -> None:
    handle, ledger, _, _ = prepared
    model = Usable([proposal(prepared)])

    with pytest.raises(LimitExceededError):
        node(prepared, budget=Budget(maximum_model_calls=0)).propose(
            node_context(handle, ledger, model)
        )

    assert not model.calls


def test_a_node_context_without_a_model_is_refused(prepared: Any) -> None:
    handle, ledger, _, _ = prepared

    with pytest.raises(ValueError, match="model-assisted"):
        node(prepared).propose(node_context(handle, ledger, None))


def test_no_test_here_makes_a_live_model_call(prepared: Any) -> None:
    handle, ledger, _, _ = prepared
    model = Usable([proposal(prepared)])

    node(prepared).propose(node_context(handle, ledger, model))

    assert isinstance(model, DeterministicModel)
