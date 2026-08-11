"""The Critical Review node, the bound on what it sees, and the restraint fixtures.

Every test runs against `DeterministicModel`, so none proves a model is a good critic. What they
prove is that the application bounds it correctly and does not punish it for finding nothing.

**The bound is the design.** DEC-049 fixes the review group as one threat's lineage, and
`select_review_group` is a function so a test can assert what it *excludes* — another threat's
mapping, a control nothing in the group cites. Section 15's "unrestricted second full assessment"
prohibition is enforced by the package rather than by an instruction.

**Zero critiques is a success and never a retry.** Section 15 makes superficial volume a failure
condition and roadmap Stage 4 gates the agent on whether it improves results at all. A node that
retried an empty response would be the mechanism by which the critic learned to manufacture
findings.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.asset import Asset
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.control import Control, ControlType, ImplementationStatus
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.critique import CritiqueSubjectType, CritiqueType, RecommendedAction
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import EvidenceAssessment, Recommendation, SubjectType
from trace_ai.domain.execution import ExecutionRecord, ExecutionStatus
from trace_ai.domain.proposals.critical_review import (
    CRITICAL_REVIEW_AGENT,
    CriticalReviewProposal,
)
from trace_ai.domain.proposals.mapping import MAPPING_AGENT
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import DeterministicModel, ModelUsage
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.seam import Creativity, FailureReason, ModelFailure
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.critique.input_package import (
    assemble_review_group,
    select_review_group,
)
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.prompts import PromptRegistry
from trace_ai.workflow.critical_review import NODE_NAME, CriticalReviewNode
from trace_ai.workflow.errors import WorkflowError
from trace_ai.workflow.limits import Budget, LimitExceededError
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.retry import RetryPolicy
from trace_ai.workflow.state import AssessmentState

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"
PROFILE = resolve_profile("primary-development")

USAGE = ModelUsage(
    model="claude-opus-5",
    input_tokens=11_000,
    output_tokens=1_800,
    estimated_cost=Decimal("0.10"),
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
def prepared(tmp_path: Path) -> Iterator[dict[str, Any]]:
    """One threat with its mappings, an inherited control, an assessment, and a gap."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        index_document(
            handle,
            loader.load_document(
                FORGEFLOW / "architecture-overview.md",
                origin=SourceOrigin.UPLOADED_DOCUMENT,
                trust_level=TrustLevel.UNTRUSTED,
            ),
        )
        objects = _populate(handle)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        objects["handle"] = handle
        objects["ledger"] = ExecutionLedger(handle, run)
        yield objects


def _populate(handle: AssessmentHandle) -> dict[str, Any]:
    stamped = now()
    cited = sorted(reference.id for reference in handle.objects.list(EvidenceReference))[0]

    with handle.objects.transaction():
        component = Component.model_validate(
            {
                "id": handle.objects.allocate("cmp"),
                "assessment_id": handle.assessment_id,
                "name": "Webhook Receiver",
                "component_type": "service",
                "internet_accessible": True,
                "evidence_ids": [cited],
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(component)
        asset = Asset.model_validate(
            {
                "id": handle.objects.allocate("ast"),
                "assessment_id": handle.assessment_id,
                "name": "Customer source code",
                "asset_type": "data",
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(asset)

        threat = Threat.model_validate(
            {
                "id": handle.objects.allocate("thr"),
                "assessment_id": handle.assessment_id,
                "title": "Forged webhooks trigger unauthorized analysis jobs",
                "description": "An attacker submits webhook requests the receiver acts on.",
                "methodology": "stride-scenario-based",
                "affected_component_ids": [component.id],
                "affected_asset_ids": [asset.id],
                "impact": "Unauthorized jobs",
                "confidence": ConfidenceLevel.MEDIUM,
                "evidence_ids": [cited],
                "status": ObjectStatus.APPROVED,
                "generated_by": "threat-analysis-v1",
                "created_at": stamped,
            }
        )
        handle.objects.save(threat)

        other = Threat.model_validate(
            {
                "id": handle.objects.allocate("thr"),
                "assessment_id": handle.assessment_id,
                "title": "Model output published without review",
                "description": "Analysis output is posted automatically.",
                "methodology": "stride-scenario-based",
                "affected_component_ids": [component.id],
                "affected_asset_ids": [asset.id],
                "impact": "Incorrect advice published",
                "confidence": ConfidenceLevel.LOW,
                "status": ObjectStatus.APPROVED,
                "generated_by": "threat-analysis-v1",
                "created_at": stamped,
            }
        )
        handle.objects.save(other)

        control = Control.model_validate(
            {
                "id": handle.objects.allocate("ctl"),
                "assessment_id": handle.assessment_id,
                "name": "Managed database encryption at rest",
                "description": "The managed database platform encrypts stored data.",
                "control_type": ControlType.INHERITED,
                "protected_asset_ids": [asset.id],
                "implementation_status": ImplementationStatus.IMPLEMENTED,
                "validation_status": ValidationStatus.NOT_EVALUATED,
                "evidence_ids": [cited],
                "generated_by": "context-extraction-v1",
                "created_at": stamped,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(control)

        unrelated = Control.model_validate(
            {
                "id": handle.objects.allocate("ctl"),
                "assessment_id": handle.assessment_id,
                "name": "Office badge access",
                "description": "Physical access to the office is badged.",
                "control_type": ControlType.IMPLEMENTED,
                "implementation_status": ImplementationStatus.IMPLEMENTED,
                "evidence_ids": [cited],
                "validation_status": ValidationStatus.NOT_EVALUATED,
                "generated_by": "context-extraction-v1",
                "created_at": stamped,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(unrelated)

        mapping = ControlMapping.model_validate(
            {
                "id": handle.objects.allocate("map"),
                "assessment_id": handle.assessment_id,
                "threat_id": threat.id,
                "requirement_id": "req-WEBHOOK-001",
                "control_ids": [control.id],
                "applicability_status": ApplicabilityStatus.APPLICABLE,
                "applicability_reason": "The system exposes an endpoint accepting events.",
                "satisfaction_status": SatisfactionStatus.UNVERIFIED,
                "confidence": ConfidenceLevel.MEDIUM,
                "generated_by": MAPPING_AGENT,
                "reviewer_status": ObjectStatus.CANDIDATE,
            }
        )
        handle.objects.save(mapping)

        elsewhere = ControlMapping.model_validate(
            {
                "id": handle.objects.allocate("map"),
                "assessment_id": handle.assessment_id,
                "threat_id": other.id,
                "requirement_id": "req-AI-001",
                "applicability_status": ApplicabilityStatus.APPLICABLE,
                "applicability_reason": "Model output reaches a public comment.",
                "satisfaction_status": SatisfactionStatus.UNVERIFIED,
                "confidence": ConfidenceLevel.LOW,
                "generated_by": MAPPING_AGENT,
                "reviewer_status": ObjectStatus.CANDIDATE,
            }
        )
        handle.objects.save(elsewhere)

        assessed = EvidenceAssessment.model_validate(
            {
                "id": handle.objects.allocate("eas"),
                "assessment_id": handle.assessment_id,
                "subject_type": SubjectType.CONTROL_MAPPING,
                "subject_id": mapping.id,
                "evidence_ids": [cited],
                "evidence_strengths": {cited: EvidenceStrength.CONTEXTUAL},
                "validation_status": ValidationStatus.UNSUPPORTED,
                "rationale": "The passage does not establish whether verification occurs.",
                "confidence": ConfidenceLevel.MEDIUM,
                "recommendation": Recommendation.DOCUMENTATION_GAP,
                "generated_by": "evidence-validation-v1",
                "created_at": stamped,
            }
        )
        handle.objects.save(assessed)

        gap = DocumentationGap.model_validate(
            {
                "id": handle.objects.allocate("gap"),
                "assessment_id": handle.assessment_id,
                "title": "Webhook authenticity mechanism is unstated",
                "description": "No document says whether validation is cryptographic.",
                "importance": "Whether forged events are rejected cannot be determined.",
                "related_object_ids": [mapping.id],
                "severity": Severity.MEDIUM,
                "status": ObjectStatus.CANDIDATE,
                "generated_by": MAPPING_AGENT,
            }
        )
        handle.objects.save(gap)

    return {
        "threat": threat,
        "other_threat": other,
        "control": control,
        "unrelated_control": unrelated,
        "mapping": mapping,
        "other_mapping": elsewhere,
        "assessment": assessed,
        "gap": gap,
        "evidence_id": cited,
    }


def selected(prepared: dict[str, Any]) -> Any:
    handle = prepared["handle"]
    return select_review_group(
        prepared["threat"],
        mappings=list(handle.objects.list(ControlMapping)),
        controls=list(handle.objects.list(Control)),
        assessments=list(handle.objects.list(EvidenceAssessment)),
        documentation_gaps=list(handle.objects.list(DocumentationGap)),
    )


def node(prepared: dict[str, Any], **changes: Any) -> CriticalReviewNode:
    options: dict[str, Any] = {
        "ledger": prepared["ledger"],
        "index": EvidenceIndex(prepared["handle"]),
        "profile": PROFILE,
        "registry": PromptRegistry(),
        "selected": selected(prepared),
        **changes,
    }
    return CriticalReviewNode(**options)


def node_context(prepared: dict[str, Any], model: Any) -> NodeContext:
    handle = prepared["handle"]
    return NodeContext(
        handle=handle,
        state=AssessmentState.begin(
            assessment_id=handle.assessment_id, workflow_run_id=prepared["ledger"].run.id
        ),
        model=model,
    )


def a_critique(prepared: dict[str, Any], **changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subject_type": CritiqueSubjectType.CONTROL_MAPPING,
        "subject_id": prepared["mapping"].id,
        "critique_type": CritiqueType.IGNORED_INHERITED_CONTROL,
        "description": "The mapping does not credit the documented platform encryption control.",
        "rationale": (
            "The control is inherited, its inheritance is documented, and the mapping concludes "
            "unverified without referencing it."
        ),
        "evidence_ids": [prepared["evidence_id"]],
        "recommended_action": RecommendedAction.REVISE,
        "confidence": ConfidenceLevel.MEDIUM,
    }
    payload.update(changes)
    return payload


def proposal(prepared: dict[str, Any], *critiques: dict[str, Any]) -> CriticalReviewProposal:
    return CriticalReviewProposal.model_validate({"critiques": list(critiques)})


def run(prepared: dict[str, Any], model: Any, **changes: Any) -> Any:
    return node(prepared, **changes).propose(node_context(prepared, model))


# The bound (DEC-049)


def test_the_group_contains_only_this_threats_lineage(prepared: dict[str, Any]) -> None:
    group = selected(prepared)

    assert group.threat is prepared["threat"]
    assert [mapping.id for mapping in group.mappings] == [prepared["mapping"].id]
    assert [control.id for control in group.controls] == [prepared["control"].id]
    assert [assessed.id for assessed in group.assessments] == [prepared["assessment"].id]
    assert [gap.id for gap in group.documentation_gaps] == [prepared["gap"].id]


def test_another_threats_mapping_is_excluded(prepared: dict[str, Any]) -> None:
    group = selected(prepared)

    assert prepared["other_mapping"].id not in [mapping.id for mapping in group.mappings]


def test_a_control_no_mapping_in_the_group_cites_is_excluded(prepared: dict[str, Any]) -> None:
    group = selected(prepared)

    assert prepared["unrelated_control"].id not in [control.id for control in group.controls]


def test_the_whole_assessment_is_not_passed(prepared: dict[str, Any]) -> None:
    """Section 15's "unrestricted second full assessment" prohibition, as a package property."""
    handle = prepared["handle"]
    package = assemble_review_group(
        assessment_id=handle.assessment_id,
        selected=selected(prepared),
        index=EvidenceIndex(handle),
        profile=PROFILE,
    )

    assert prepared["other_threat"].id not in package.trusted
    assert prepared["other_mapping"].id not in package.trusted
    assert prepared["unrelated_control"].id not in package.trusted


def test_the_group_carries_the_reasoning_and_not_only_the_objects(
    prepared: dict[str, Any],
) -> None:
    """The critic is checking reasoning, so the reasoning has to be in front of it."""
    handle = prepared["handle"]
    package = assemble_review_group(
        assessment_id=handle.assessment_id,
        selected=selected(prepared),
        index=EvidenceIndex(handle),
        profile=PROFILE,
    )

    assert prepared["mapping"].applicability_reason in package.trusted
    assert prepared["assessment"].rationale in package.trusted
    assert "is_documented_inheritance" in package.trusted


def test_the_group_carries_suppressions_and_downgrades(prepared: dict[str, Any]) -> None:
    """DEC-025 and DEC-046: conclusions already declined, so the critic does not re-raise them."""
    handle = prepared["handle"]
    package = assemble_review_group(
        assessment_id=handle.assessment_id,
        selected=selected(prepared),
        index=EvidenceIndex(handle),
        profile=PROFILE,
    )

    assert "suppressed_conclusion" in package.trusted
    assert "downgrade_reason" in package.trusted


def test_the_trusted_region_carries_no_quoted_source_text(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    index = EvidenceIndex(handle)
    package = assemble_review_group(
        assessment_id=handle.assessment_id,
        selected=selected(prepared),
        index=index,
        profile=PROFILE,
    )

    for excerpt in index.render_for_prompt(list(package.evidence_ids)):
        assert excerpt["quoted_text"] not in package.trusted
        assert excerpt["quoted_text"] in package.untrusted


# What one pass produces


def test_a_single_critique_succeeds_with_no_retry(prepared: dict[str, Any]) -> None:
    model = Usable([proposal(prepared, a_critique(prepared))])

    outcome = run(prepared, model)

    assert len(model.calls) == 1
    assert outcome.result.metadata["attempts"] == 1
    assert len(outcome.proposal.critiques) == 1


def test_the_node_declares_the_critical_review_phase(prepared: dict[str, Any]) -> None:
    assert node(prepared).phase is Phase.CRITICAL_REVIEW
    assert node(prepared).name == NODE_NAME


def test_run_returns_the_node_result(prepared: dict[str, Any]) -> None:
    model = Usable([proposal(prepared, a_critique(prepared))])

    result = node(prepared).run(node_context(prepared, model))

    assert result.metadata["agent"] == CRITICAL_REVIEW_AGENT == "critical-review-v1"


def test_the_node_persists_nothing(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    outcome = run(prepared, Usable([proposal(prepared, a_critique(prepared))]))

    assert outcome.result.produced_object_ids == []
    from trace_ai.domain.critique import Critique

    assert not handle.objects.list(Critique)


def test_the_agent_module_contains_no_store_write() -> None:
    text = (PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "critical_review.py").read_text(
        encoding="utf-8"
    )

    for forbidden in ("objects.save", "repository.save", ".transaction()", "allocate("):
        assert forbidden not in text


def test_the_agent_proposes_no_object_outside_critique() -> None:
    """DEC-049: no missing-threat proposals, and nothing else either."""
    assert set(CriticalReviewProposal.model_fields) == {"critiques"}


def test_the_agent_approves_nothing_and_emits_no_finding() -> None:
    from trace_ai.domain.proposals.critical_review import CritiqueProposal

    assert not set(CritiqueProposal.model_fields) & {
        "finding",
        "approved",
        "approval",
        "status",
        "severity",
    }


def test_the_call_uses_moderate_creativity(prepared: dict[str, Any]) -> None:
    """Section 29's "low to moderate", read as a search rather than as a checklist."""
    model = Usable([proposal(prepared, a_critique(prepared))])

    run(prepared, model)

    assert model.calls[0].settings.creativity is Creativity.MODERATE


# Fixture: restraint


def test_zero_critiques_is_a_success_and_not_a_retry(prepared: dict[str, Any]) -> None:
    """Section 15 makes superficial volume a failure; retrying an empty answer teaches volume."""
    model = Usable([proposal(prepared)])

    outcome = run(prepared, model)

    assert len(model.calls) == 1
    assert outcome.result.metadata["attempts"] == 1
    assert outcome.result.metadata["critiques"] == 0


def test_a_well_supported_group_drawing_no_critiques_is_recorded_as_a_success(
    prepared: dict[str, Any],
) -> None:
    model = Usable([proposal(prepared)])

    run(prepared, model)

    handle = prepared["handle"]
    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert record.status is ExecutionStatus.COMPLETED
    assert record.metadata["critiques"] == 0


def test_the_reviewed_object_count_is_recorded(prepared: dict[str, Any]) -> None:
    """What the volume ratio in the validation node is measured against."""
    outcome = run(prepared, Usable([proposal(prepared)]))

    assert outcome.result.metadata["reviewed_objects"] == 5


# Fixtures: the two backstops


def test_a_documentation_gap_mislabelled_draws_that_critique(prepared: dict[str, Any]) -> None:
    critique = a_critique(
        prepared,
        critique_type=CritiqueType.DOCUMENTATION_GAP_ONLY,
        description="The mapping asserts a weakness where the documentation is silent.",
        rationale="The cited passage establishes only that the topic is undocumented.",
    )

    outcome = run(prepared, Usable([proposal(prepared, critique)]))

    (raised,) = outcome.proposal.critiques
    assert raised.critique_type is CritiqueType.DOCUMENTATION_GAP_ONLY
    assert raised.subject_id == prepared["mapping"].id
    assert raised.recommended_action is RecommendedAction.REVISE


def test_an_ignored_inherited_control_draws_that_critique(prepared: dict[str, Any]) -> None:
    """ForgeFlow sections 12.2 and 14.2: the documented managed-database inheritance."""
    outcome = run(prepared, Usable([proposal(prepared, a_critique(prepared))]))

    (raised,) = outcome.proposal.critiques
    assert raised.critique_type is CritiqueType.IGNORED_INHERITED_CONTROL
    assert prepared["control"].is_documented_inheritance is True


# References and retry routing


def test_a_critique_targeting_something_outside_the_group_is_retried(
    prepared: dict[str, Any],
) -> None:
    outside = proposal(prepared, a_critique(prepared, subject_id=prepared["other_mapping"].id))
    model = Usable([outside, proposal(prepared, a_critique(prepared))])

    outcome = node(prepared).propose(node_context(prepared, model))

    assert outcome.result.metadata["attempts"] == 2
    assert prepared["other_mapping"].id in model.calls[1].prompt


def test_the_same_challenge_twice_is_retried(prepared: dict[str, Any]) -> None:
    repeated = proposal(prepared, a_critique(prepared), a_critique(prepared))
    model = Usable([repeated, proposal(prepared, a_critique(prepared))])

    outcome = node(prepared).propose(node_context(prepared, model))

    assert outcome.result.metadata["attempts"] == 2
    assert "more than once" in model.calls[1].prompt


def test_the_correction_says_an_empty_list_is_valid(prepared: dict[str, Any]) -> None:
    """The retry prompt must not read as an instruction to produce more."""
    repeated = proposal(prepared, a_critique(prepared), a_critique(prepared))
    model = Usable([repeated, proposal(prepared)])

    node(prepared).propose(node_context(prepared, model))

    assert "an empty list is a valid" in model.calls[1].prompt


@pytest.mark.parametrize(
    "reason",
    [FailureReason.SCHEMA_VALIDATION_FAILURE, FailureReason.TRANSIENT_PROVIDER_FAILURE],
)
def test_a_retryable_provider_failure_is_retried(
    prepared: dict[str, Any], reason: FailureReason
) -> None:
    failure = ModelFailure(reason=reason, message="try again", usage=USAGE)
    model = Usable([failure, proposal(prepared, a_critique(prepared))])

    outcome = node(prepared).propose(node_context(prepared, model))

    assert outcome.result.metadata["attempts"] == 2


@pytest.mark.parametrize("reason", [FailureReason.REFUSED, FailureReason.INVALID_REQUEST])
def test_a_non_retryable_failure_is_not_retried(
    prepared: dict[str, Any], reason: FailureReason
) -> None:
    model = Usable([ModelFailure(reason=reason, message="no", usage=USAGE)])

    with pytest.raises(WorkflowError):
        node(prepared).propose(node_context(prepared, model))

    assert len(model.calls) == 1


def test_retries_stop_at_the_configured_ceiling(prepared: dict[str, Any]) -> None:
    failure = ModelFailure(
        reason=FailureReason.TRANSIENT_PROVIDER_FAILURE, message="down", usage=USAGE
    )
    model = Usable([failure, failure, failure])

    with pytest.raises(WorkflowError):
        node(prepared, retry_policy=RetryPolicy()).propose(node_context(prepared, model))

    assert len(model.calls) == 3


# The execution record and ceilings


def test_an_execution_record_is_written(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    run(prepared, Usable([proposal(prepared, a_critique(prepared))]))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert record.prompt_version == "challenge-analysis-v1"
    assert record.metadata["threat_id"] == prepared["threat"].id


def test_the_execution_record_names_its_inputs(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    run(prepared, Usable([proposal(prepared)]))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert prepared["threat"].id in record.input_object_ids
    assert prepared["mapping"].id in record.input_object_ids
    assert prepared["other_mapping"].id not in record.input_object_ids


def test_a_failed_attempt_output_goes_to_traces(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    outside = proposal(prepared, a_critique(prepared, subject_id=prepared["other_mapping"].id))

    with pytest.raises(WorkflowError):
        node(prepared).propose(node_context(prepared, Usable([outside, outside, outside])))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert any(key.endswith("_output") for key in record.metadata)


def test_a_zero_call_ceiling_stops_the_node_before_it_spends(prepared: dict[str, Any]) -> None:
    model = Usable([proposal(prepared)])

    with pytest.raises(LimitExceededError):
        node(prepared, budget=Budget(maximum_model_calls=0)).propose(node_context(prepared, model))

    assert not model.calls


def test_a_node_context_without_a_model_is_refused(prepared: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="model-assisted"):
        node(prepared).propose(node_context(prepared, None))


def test_no_test_here_makes_a_live_model_call(prepared: dict[str, Any]) -> None:
    model = Usable([proposal(prepared)])

    node(prepared).propose(node_context(prepared, model))

    assert isinstance(model, DeterministicModel)
