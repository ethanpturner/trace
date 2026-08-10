"""Tests for the Threat Analysis node — the second model-assisted step.

Every test runs against `DeterministicModel`. No API key, no network, no cost.

Three properties are specific to this step and are what most of this file is about.

**It reasons from the approved baseline.** An unapproved context is refused by name, not worked
around. A run producing threats against a context nobody signed off would leave artifacts
indistinguishable from a correct one.

**A threat may only name what it was given.** `agent-design.md` section 10 prohibits inventing
components; the check is against the identifiers the input package actually carried, because only
the package knows what was sent.

**Volume is not quality.** Section 10 warns against six generic threats filling six categories.
One well-grounded threat succeeds with no retry, zero threats is a success, and a set of category
labels is refused.
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
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import ExecutionRecord, ExecutionStatus
from trace_ai.domain.proposals.threat_analysis import (
    THREAT_ANALYSIS_AGENT,
    ThreatAnalysisProposal,
)
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.system_context import FIRST_VERSION, SystemContext
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import (
    DeterministicModel,
    FailureReason,
    ModelFailure,
    ModelUsage,
)
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.seam import Creativity
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.prompts import PromptRegistry
from trace_ai.services.threats.input_package import (
    UnapprovedContextError,
    assemble_threat_input,
)
from trace_ai.workflow.errors import ErrorClass, WorkflowError
from trace_ai.workflow.limits import Budget, LimitExceededError
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.retry import RetryPolicy
from trace_ai.workflow.state import AssessmentState
from trace_ai.workflow.threat_analysis import NODE_NAME, ThreatAnalysisNode

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"
PROFILE = resolve_profile("primary-development")

USAGE = ModelUsage(
    model="claude-opus-5",
    input_tokens=14_000,
    output_tokens=2_000,
    estimated_cost=Decimal("0.12"),
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
def prepared(tmp_path: Path) -> Iterator[tuple[AssessmentHandle, ExecutionLedger, SystemContext]]:
    """An assessment with ForgeFlow documents ingested, an approved context, and a run open."""
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
        context = _approved_context(handle)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield handle, ExecutionLedger(handle, run), context


def _approved_context(handle: AssessmentHandle) -> SystemContext:
    """A small approved baseline: two components, one asset, and the approval that makes it one."""
    stamped = now()
    cited = sorted(reference.id for reference in handle.objects.list(EvidenceReference))[0]

    with handle.objects.transaction():
        webhook = Component.model_validate(
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
        worker = Component.model_validate(
            {
                "id": handle.objects.allocate("cmp"),
                "assessment_id": handle.assessment_id,
                "name": "Analysis Worker",
                "component_type": "background_worker",
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(webhook)
        handle.objects.save(worker)

        capacity = Asset.model_validate(
            {
                "id": handle.objects.allocate("ast"),
                "assessment_id": handle.assessment_id,
                "name": "Analysis capacity",
                "asset_type": "operational_capability",
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(capacity)

        context = SystemContext.model_validate(
            {
                "assessment_id": handle.assessment_id,
                "system_name": "ForgeFlow",
                "system_purpose": "AI-assisted pull request review",
                "component_ids": [webhook.id, worker.id],
                "asset_ids": [capacity.id],
                "actor_ids": [],
                "data_flow_ids": [],
                "trust_boundary_ids": [],
                "context_claim_ids": [],
                "version": FIRST_VERSION + 1,
                "approved_at": stamped,
                "approved_by": "reviewer",
            }
        )
        handle.objects.save(context)
    return context


def evidence_ids(handle: AssessmentHandle) -> list[str]:
    return sorted(reference.id for reference in handle.objects.list(EvidenceReference))[:8]


def component_ids(handle: AssessmentHandle) -> list[str]:
    return sorted(component.id for component in handle.objects.list(Component))


def asset_ids(handle: AssessmentHandle) -> list[str]:
    return sorted(asset.id for asset in handle.objects.list(Asset))


def a_threat(handle: AssessmentHandle, **changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Forged repository webhooks trigger unauthorized analysis jobs",
        "description": (
            "An attacker who can submit unsigned or incorrectly validated webhook requests may "
            "trigger analysis jobs for repositories they do not control."
        ),
        "methodology": "stride-scenario-based",
        "category": ["spoofing", "elevation_of_privilege"],
        "affected_component_ids": component_ids(handle)[:1],
        "affected_asset_ids": asset_ids(handle)[:1],
        "preconditions": ["signature validation is absent or bypassable"],
        "attack_path": ["forge a delivery", "submit it to the receiver"],
        "impact": "Unauthorized jobs and denial of service",
        "confidence": ConfidenceLevel.MEDIUM,
        "evidence_ids": evidence_ids(handle)[:1],
    }
    payload.update(changes)
    return payload


def proposal(handle: AssessmentHandle, *threats: dict[str, Any]) -> ThreatAnalysisProposal:
    return ThreatAnalysisProposal.model_validate(
        {"threats": list(threats) if threats else [a_threat(handle)]}
    )


def node(
    handle: AssessmentHandle,
    ledger: ExecutionLedger,
    context: SystemContext,
    **changes: Any,
) -> ThreatAnalysisNode:
    options: dict[str, Any] = {
        "ledger": ledger,
        "index": EvidenceIndex(handle),
        "profile": PROFILE,
        "registry": PromptRegistry(),
        "context": context,
        "evidence_ids": evidence_ids(handle),
        "assessment_name": "ForgeFlow",
        "threat_methodology": "stride-scenario-based",
        **changes,
    }
    return ThreatAnalysisNode(**options)


def node_context(handle: AssessmentHandle, ledger: ExecutionLedger, model: Any) -> NodeContext:
    return NodeContext(
        handle=handle,
        state=AssessmentState.begin(
            assessment_id=handle.assessment_id, workflow_run_id=ledger.run.id
        ),
        model=model,
    )


# ------------------------------------------------------------------------------------------
# What one successful pass produces
# ------------------------------------------------------------------------------------------


def test_a_single_well_formed_threat_succeeds_with_no_retry(prepared: Any) -> None:
    """Section 10: quality matters more than volume. One threat is a complete answer."""
    handle, ledger, context = prepared
    model = Usable([proposal(handle)])

    result = node(handle, ledger, context).run(node_context(handle, ledger, model))

    assert len(model.calls) == 1
    assert result.metadata["attempts"] == 1
    assert result.metadata["threats"] == 1
    (threat,) = handle.objects.list(Threat)
    assert threat.title.startswith("Forged repository webhooks")


def test_every_produced_threat_is_a_candidate(prepared: Any) -> None:
    handle, ledger, context = prepared
    node(handle, ledger, context).run(node_context(handle, ledger, Usable([proposal(handle)])))

    for threat in handle.objects.list(Threat):
        assert threat.status is ObjectStatus.CANDIDATE


def test_identifiers_are_allocated_by_the_application(prepared: Any) -> None:
    """DEC-018. The proposal carried no identifier; this is the store's number."""
    handle, ledger, context = prepared
    node(handle, ledger, context).run(node_context(handle, ledger, Usable([proposal(handle)])))

    (threat,) = handle.objects.list(Threat)
    assert threat.id.startswith("thr-")
    assert threat.assessment_id == handle.assessment_id


def test_generated_by_is_the_agent_version(prepared: Any) -> None:
    handle, ledger, context = prepared
    node(handle, ledger, context).run(node_context(handle, ledger, Usable([proposal(handle)])))

    (threat,) = handle.objects.list(Threat)
    assert threat.generated_by == THREAT_ANALYSIS_AGENT == "threat-analysis-v1"


def test_producing_no_threats_is_a_success(prepared: Any) -> None:
    """An architecture that genuinely supports none is a legitimate outcome (section 10).

    A node that treated this as a failure would retry, and retrying for volume is how a model is
    taught that producing something is the way to stop being asked.
    """
    handle, ledger, context = prepared
    model = Usable([ThreatAnalysisProposal.model_validate({"threats": []})])

    result = node(handle, ledger, context).run(node_context(handle, ledger, model))

    assert len(model.calls) == 1
    assert result.metadata["threats"] == 0
    assert not handle.objects.list(Threat)


def test_the_state_change_names_the_candidate_threats(prepared: Any) -> None:
    handle, ledger, context = prepared

    result = node(handle, ledger, context).run(
        node_context(handle, ledger, Usable([proposal(handle)]))
    )

    (threat,) = handle.objects.list(Threat)
    assert result.state_changes["candidate_threat_ids"] == [threat.id]


# ------------------------------------------------------------------------------------------
# The approved baseline
# ------------------------------------------------------------------------------------------


def test_an_unapproved_context_is_refused(prepared: Any) -> None:
    """`current-architecture.md` section 5.6. Threat analysis reasons from what was approved."""
    handle, ledger, context = prepared
    unapproved = SystemContext.model_validate(
        {**context.model_dump(), "approved_at": None, "approved_by": None}
    )

    with pytest.raises(UnapprovedContextError, match="not approved"):
        node(handle, ledger, unapproved).run(
            node_context(handle, ledger, Usable([proposal(handle)]))
        )


def test_the_package_carries_the_architecture_in_the_trusted_region(prepared: Any) -> None:
    handle, _ledger, context = prepared

    package = assemble_threat_input(
        handle,
        context=context,
        index=EvidenceIndex(handle),
        evidence_ids=evidence_ids(handle),
        profile=PROFILE,
        assessment_name="ForgeFlow",
        threat_methodology="stride-scenario-based",
    )

    assert "Webhook Receiver" in package.trusted
    assert "Analysis Worker" in package.trusted
    assert package.component_ids == tuple(component_ids(handle))


def test_a_rejected_object_is_absent_from_the_package(prepared: Any) -> None:
    """DEC-040 recomputes membership at approval, so a rejected object is not in the lists.

    The package reads the lists rather than the store; re-listing would put it back.
    """
    handle, _ledger, context = prepared
    kept = context.component_ids[0]
    narrowed = SystemContext.model_validate({**context.model_dump(), "component_ids": [kept]})

    package = assemble_threat_input(
        handle,
        context=narrowed,
        index=EvidenceIndex(handle),
        evidence_ids=evidence_ids(handle),
        profile=PROFILE,
        assessment_name="ForgeFlow",
        threat_methodology="stride-scenario-based",
    )

    assert package.component_ids == (kept,)
    assert "Analysis Worker" not in package.trusted


# ------------------------------------------------------------------------------------------
# Grounding: a threat may only name what it was given
# ------------------------------------------------------------------------------------------


def test_a_threat_naming_an_unknown_component_is_a_validation_failure(prepared: Any) -> None:
    """Not a silent drop. Section 10 prohibits inventing components."""
    handle, ledger, context = prepared
    invented = proposal(handle, a_threat(handle, affected_component_ids=["cmp-999"]))
    model = Usable([invented, invented, invented])

    with pytest.raises(WorkflowError) as raised:
        node(handle, ledger, context).run(node_context(handle, ledger, model))

    assert raised.value.error_class is ErrorClass.MISSING_REQUIRED_RELATIONSHIP
    assert not handle.objects.list(Threat)


def test_the_correction_names_every_unknown_identifier_at_once(prepared: Any) -> None:
    """One retry carries the whole correction rather than one identifier per attempt."""
    handle, ledger, context = prepared
    invented = proposal(
        handle,
        a_threat(handle, affected_component_ids=["cmp-998", "cmp-999"], evidence_ids=["evd-997"]),
    )

    with pytest.raises(WorkflowError) as raised:
        node(handle, ledger, context).run(
            node_context(handle, ledger, Usable([invented, invented, invented]))
        )

    message = str(raised.value)
    for unknown in ("cmp-998", "cmp-999", "evd-997"):
        assert unknown in message


def test_every_emitted_threat_references_a_supplied_component_and_asset(prepared: Any) -> None:
    handle, ledger, context = prepared
    node(handle, ledger, context).run(node_context(handle, ledger, Usable([proposal(handle)])))

    (threat,) = handle.objects.list(Threat)
    assert set(threat.affected_component_ids) <= set(context.component_ids)
    assert set(threat.affected_asset_ids) <= set(context.asset_ids)


def test_an_unknown_reference_retries_and_then_succeeds(prepared: Any) -> None:
    """`missing_required_relationship` is retryable: it is a shape error the agent can be told."""
    handle, ledger, context = prepared
    invented = proposal(handle, a_threat(handle, affected_component_ids=["cmp-999"]))
    model = Usable([invented, proposal(handle)])

    result = node(handle, ledger, context).run(node_context(handle, ledger, model))

    assert result.metadata["attempts"] == 2
    assert len(handle.objects.list(Threat)) == 1
    assert "cmp-999" in model.calls[1].prompt


# ------------------------------------------------------------------------------------------
# Generic category labels (agent-design.md section 39, Fixture tests)
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title", ["Tampering", "tampering", "Elevation of Privilege", "Prompt Injection"]
)
def test_a_generic_category_label_is_rejected(prepared: Any, title: str) -> None:
    """ "Generic STRIDE labels are rejected" — `agent-design.md` section 39."""
    handle, ledger, context = prepared
    generic = proposal(handle, a_threat(handle, title=title))

    with pytest.raises(WorkflowError) as raised:
        node(handle, ledger, context).run(
            node_context(handle, ledger, Usable([generic, generic, generic]))
        )

    assert raised.value.error_class is ErrorClass.SCHEMA_VALIDATION_FAILURE
    assert not handle.objects.list(Threat)


def test_six_threats_named_after_six_categories_are_all_rejected(prepared: Any) -> None:
    """The failure mode section 10 names directly: one generic threat per category."""
    handle, ledger, context = prepared
    checklist = proposal(
        handle,
        *(
            a_threat(handle, title=category.replace("_", " ").title())
            for category in (
                "spoofing",
                "tampering",
                "repudiation",
                "information_disclosure",
                "denial_of_service",
                "elevation_of_privilege",
            )
        ),
    )

    with pytest.raises(WorkflowError) as raised:
        node(handle, ledger, context).run(
            node_context(handle, ledger, Usable([checklist, checklist, checklist]))
        )

    assert "Tampering" in str(raised.value)
    assert "Spoofing" in str(raised.value)


def test_a_real_scenario_title_containing_a_category_word_is_kept(prepared: Any) -> None:
    """The check catches the label, not the word. A title is a sentence; a label is a term."""
    handle, ledger, context = prepared
    kept = proposal(
        handle,
        a_threat(handle, title="Elevation of privilege through an unscoped installation token"),
    )

    node(handle, ledger, context).run(node_context(handle, ledger, Usable([kept])))

    assert len(handle.objects.list(Threat)) == 1


# ------------------------------------------------------------------------------------------
# Retry routing (agent-design.md section 26)
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [FailureReason.SCHEMA_VALIDATION_FAILURE, FailureReason.TRANSIENT_PROVIDER_FAILURE],
)
def test_a_retryable_provider_failure_is_retried(prepared: Any, reason: FailureReason) -> None:
    handle, ledger, context = prepared
    failure = ModelFailure(reason=reason, message="try again", usage=USAGE)
    model = Usable([failure, proposal(handle)])

    result = node(handle, ledger, context).run(node_context(handle, ledger, model))

    assert result.metadata["attempts"] == 2
    assert len(handle.objects.list(Threat)) == 1


def test_retries_stop_at_the_configured_ceiling(prepared: Any) -> None:
    """`maximum_retries_per_node: 2` — three attempts in total, then the run stops."""
    handle, ledger, context = prepared
    failure = ModelFailure(
        reason=FailureReason.TRANSIENT_PROVIDER_FAILURE, message="down", usage=USAGE
    )
    model = Usable([failure, failure, failure])

    with pytest.raises(WorkflowError):
        node(handle, ledger, context, retry_policy=RetryPolicy()).run(
            node_context(handle, ledger, model)
        )

    assert len(model.calls) == 3


@pytest.mark.parametrize(
    "reason",
    [FailureReason.REFUSED, FailureReason.INVALID_REQUEST],
)
def test_a_non_retryable_failure_is_not_retried(prepared: Any, reason: FailureReason) -> None:
    """Section 26: retry the attempt, never the conclusion."""
    handle, ledger, context = prepared
    failure = ModelFailure(reason=reason, message="no", usage=USAGE)
    model = Usable([failure])

    with pytest.raises(WorkflowError):
        node(handle, ledger, context).run(node_context(handle, ledger, model))

    assert len(model.calls) == 1


def test_a_low_threat_count_never_triggers_a_retry(prepared: Any) -> None:
    """Section 10 addresses this directly: the node does not ask again for more."""
    handle, ledger, context = prepared
    model = Usable([ThreatAnalysisProposal.model_validate({"threats": []})])

    node(handle, ledger, context).run(node_context(handle, ledger, model))

    assert len(model.calls) == 1


# ------------------------------------------------------------------------------------------
# The execution record
# ------------------------------------------------------------------------------------------


def test_an_execution_record_is_written_for_a_successful_invocation(prepared: Any) -> None:
    handle, ledger, context = prepared
    node(handle, ledger, context).run(node_context(handle, ledger, Usable([proposal(handle)])))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert record.status is ExecutionStatus.COMPLETED
    assert record.metadata["threats"] == 1
    assert record.prompt_version == "generate-scenario-threats-v1"


def test_an_execution_record_is_written_for_a_failed_invocation(prepared: Any) -> None:
    handle, ledger, context = prepared
    failure = ModelFailure(reason=FailureReason.REFUSED, message="no", usage=USAGE)

    with pytest.raises(WorkflowError):
        node(handle, ledger, context).run(node_context(handle, ledger, Usable([failure])))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert record.status is ExecutionStatus.FAILED


def test_a_failed_attempt_output_goes_to_traces_and_not_into_the_error(prepared: Any) -> None:
    """`agent-design.md` section 27. A failed attempt's raw output is model text."""
    handle, ledger, context = prepared
    invented = proposal(handle, a_threat(handle, affected_component_ids=["cmp-999"]))

    with pytest.raises(WorkflowError):
        node(handle, ledger, context).run(
            node_context(handle, ledger, Usable([invented, invented, invented]))
        )

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert any(key.endswith("_output") for key in record.metadata)


# ------------------------------------------------------------------------------------------
# Settings and ceilings
# ------------------------------------------------------------------------------------------


def test_the_call_uses_moderate_creativity(prepared: Any) -> None:
    """Section 29's one non-`low` setting in the MVP, applied to a copy of the run's profile."""
    handle, ledger, context = prepared
    model = Usable([proposal(handle)])

    node(handle, ledger, context).run(node_context(handle, ledger, model))

    assert model.calls[0].settings.creativity is Creativity.MODERATE
    assert PROFILE.settings.creativity is not Creativity.MODERATE


def test_a_zero_call_ceiling_stops_the_node_before_it_spends(prepared: Any) -> None:
    handle, ledger, context = prepared
    model = Usable([proposal(handle)])

    with pytest.raises(LimitExceededError):
        node(handle, ledger, context, budget=Budget(maximum_model_calls=0)).run(
            node_context(handle, ledger, model)
        )

    assert not model.calls


def test_a_deterministic_node_context_without_a_model_is_refused(prepared: Any) -> None:
    handle, ledger, context = prepared

    with pytest.raises(ValueError, match="model-assisted"):
        node(handle, ledger, context).run(node_context(handle, ledger, None))
