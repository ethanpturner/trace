"""The Requirement and Control Mapping node, and the ForgeFlow cases it exists to get right.

`docs/product/roadmap.md` Stage 3 calls this the core false-positive-reduction mechanism, and
`agent-design.md` section 35 Phase 3 states the success condition: Trace distinguishes among
satisfied, unverified, and unmet requirements without treating missing documentation as proof of
weakness. Most of this file is the fixture cases `docs/architecture/evaluation-plan.md` section 6
and section 11 name as permanent regression cases.

**What a fixture case can and cannot prove.** Every test here runs against `DeterministicModel`
with an authored response, so none of them proves a model behaves well — that is the evaluation
harness's job, against `tests/evaluation/`. What they prove is that the *application* handles the
right answer correctly and does not quietly convert it into the wrong one: that a `not_applicable`
password-policy mapping survives promotion with its reason intact, that an `unverified` webhook
mapping cannot become a finding here, that a suppression is stored rather than dropped, and that a
run producing zero `unmet` statuses is a success rather than an empty result. Each is a place the
pipeline could destroy a correct answer, and the fixtures are also the recorded responses the
evaluation harness compares a live run against.

The retry, ceiling, and preserve-the-output tests mirror `test_threat_analysis_node.py`, because
those rules are the same everywhere and one interpretation of them is the point.
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
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    Severity,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.execution import ExecutionRecord, ExecutionStatus
from trace_ai.domain.proposals.mapping import MAPPING_AGENT, MappingProposal
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.system_context import FIRST_VERSION, SystemContext
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import DeterministicModel, ModelUsage
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.infrastructure.model.seam import Creativity, FailureReason, ModelFailure
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.mapping.input_package import (
    UnapprovedContextError,
    assemble_mapping_input,
)
from trace_ai.services.prompts import PromptRegistry
from trace_ai.services.requirements.loader import LoadedCatalog, current_version, load_catalog
from trace_ai.workflow.errors import WorkflowError
from trace_ai.workflow.limits import Budget, LimitExceededError
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.requirement_control_mapping import (
    NODE_NAME,
    RequirementControlMappingNode,
)
from trace_ai.workflow.retry import RetryPolicy
from trace_ai.workflow.state import AssessmentState

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"
PROFILE = resolve_profile("primary-development")

USAGE = ModelUsage(
    model="claude-opus-5",
    input_tokens=18_000,
    output_tokens=3_000,
    estimated_cost=Decimal("0.16"),
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


@pytest.fixture(scope="module")
def catalog() -> LoadedCatalog:
    return load_catalog(current_version())


@pytest.fixture
def prepared(
    tmp_path: Path,
) -> Iterator[tuple[AssessmentHandle, ExecutionLedger, SystemContext, Threat]]:
    """ForgeFlow ingested, an approved context, one inherited control, and one threat."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        for name in ("architecture-overview.md", "github-integration.md"):
            index_document(
                handle,
                loader.load_document(
                    FORGEFLOW / name,
                    origin=SourceOrigin.UPLOADED_DOCUMENT,
                    trust_level=TrustLevel.UNTRUSTED,
                ),
            )
        context, threat = _baseline(handle)
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield handle, ExecutionLedger(handle, run), context, threat


def _baseline(handle: AssessmentHandle) -> tuple[SystemContext, Threat]:
    stamped = now()
    cited = sorted(reference.id for reference in handle.objects.list(EvidenceReference))[0]

    with handle.objects.transaction():
        receiver = Component.model_validate(
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
        handle.objects.save(receiver)

        repository = Asset.model_validate(
            {
                "id": handle.objects.allocate("ast"),
                "assessment_id": handle.assessment_id,
                "name": "Customer source code",
                "asset_type": "data",
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(repository)

        encryption = Control.model_validate(
            {
                "id": handle.objects.allocate("ctl"),
                "assessment_id": handle.assessment_id,
                "name": "Managed database encryption at rest",
                "description": "The managed database platform encrypts stored data.",
                "control_type": ControlType.INHERITED,
                "protected_asset_ids": [repository.id],
                "implementation_status": ImplementationStatus.IMPLEMENTED,
                "validation_status": ValidationStatus.NOT_EVALUATED,
                "evidence_ids": [cited],
                "generated_by": "context-extraction-v1",
                "created_at": stamped,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(encryption)

        context = SystemContext.model_validate(
            {
                "assessment_id": handle.assessment_id,
                "system_name": "ForgeFlow",
                "system_purpose": "AI-assisted pull request review",
                "component_ids": [receiver.id],
                "asset_ids": [repository.id],
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

        threat = Threat.model_validate(
            {
                "id": handle.objects.allocate("thr"),
                "assessment_id": handle.assessment_id,
                "title": "Forged repository webhooks trigger unauthorized analysis jobs",
                "description": "An attacker submits webhook requests the receiver acts on.",
                "methodology": "stride-scenario-based",
                "category": ["spoofing"],
                "affected_component_ids": [receiver.id],
                "affected_asset_ids": [repository.id],
                "preconditions": ["signature verification is absent or bypassable"],
                "impact": "Unauthorized jobs and disclosure of repository content",
                "confidence": ConfidenceLevel.MEDIUM,
                "evidence_ids": [cited],
                "status": ObjectStatus.APPROVED,
                "generated_by": "threat-analysis-v1",
                "created_at": stamped,
            }
        )
        handle.objects.save(threat)

    return context, threat


def evidence_ids(handle: AssessmentHandle) -> list[str]:
    return sorted(reference.id for reference in handle.objects.list(EvidenceReference))[:8]


def existing_control(handle: AssessmentHandle) -> Control:
    return next(iter(handle.objects.list(Control)))


def node(prepared: Any, **changes: Any) -> RequirementControlMappingNode:
    handle, ledger, context, threat = prepared
    options: dict[str, Any] = {
        "ledger": ledger,
        "index": EvidenceIndex(handle),
        "profile": PROFILE,
        "registry": PromptRegistry(),
        "context": context,
        "catalog": changes.pop("catalog"),
        "threat": threat,
        "evidence_ids": evidence_ids(handle),
        **changes,
    }
    return RequirementControlMappingNode(**options)


def node_context(handle: AssessmentHandle, ledger: ExecutionLedger, model: Any) -> NodeContext:
    return NodeContext(
        handle=handle,
        state=AssessmentState.begin(
            assessment_id=handle.assessment_id, workflow_run_id=ledger.run.id
        ),
        model=model,
    )


def a_mapping(prepared: Any, **changes: Any) -> dict[str, Any]:
    _handle, _ledger, _context, threat = prepared
    payload: dict[str, Any] = {
        "threat_id": threat.id,
        "requirement_id": "req-WEBHOOK-001",
        "applicability_status": ApplicabilityStatus.APPLICABLE,
        "applicability_reason": (
            "The system exposes an endpoint accepting events from an external platform, which is "
            "this requirement's first applicable condition, and the threat is about forged events."
        ),
        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
        "confidence": ConfidenceLevel.MEDIUM,
    }
    payload.update(changes)
    return payload


def proposal(prepared: Any, *mappings: dict[str, Any], **rest: Any) -> MappingProposal:
    return MappingProposal.model_validate(
        {
            "mappings": list(mappings) if mappings else [a_mapping(prepared)],
            **rest,
        }
    )


def run(prepared: Any, catalog: LoadedCatalog, model: Any) -> Any:
    handle, ledger, _context, _threat = prepared
    return node(prepared, catalog=catalog).run(node_context(handle, ledger, model))


# ------------------------------------------------------------------------------------------
# What one successful pass produces
# ------------------------------------------------------------------------------------------


def test_a_single_mapping_succeeds_with_no_retry(prepared: Any, catalog: LoadedCatalog) -> None:
    handle, _, _, _ = prepared
    model = Usable([proposal(prepared)])

    result = run(prepared, catalog, model)

    assert len(model.calls) == 1
    assert result.metadata["attempts"] == 1
    (mapping,) = handle.objects.list(ControlMapping)
    assert mapping.requirement_id == "req-WEBHOOK-001"


def test_identifiers_are_allocated_by_the_application(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """DEC-018. The proposal carried no identifier; this is the store's number."""
    handle, _, _, _ = prepared
    run(prepared, catalog, Usable([proposal(prepared)]))

    (mapping,) = handle.objects.list(ControlMapping)
    assert mapping.id.startswith("map-")
    assert mapping.assessment_id == handle.assessment_id


def test_everything_produced_is_a_candidate(prepared: Any, catalog: LoadedCatalog) -> None:
    handle, _, _, _ = prepared
    run(
        prepared,
        catalog,
        Usable([proposal(prepared, documentation_gaps=[a_gap()])]),
    )

    for mapping in handle.objects.list(ControlMapping):
        assert mapping.reviewer_status is ObjectStatus.CANDIDATE
    for gap in handle.objects.list(DocumentationGap):
        assert gap.status is ObjectStatus.CANDIDATE


def test_generated_by_is_the_agent_version(prepared: Any, catalog: LoadedCatalog) -> None:
    handle, _, _, _ = prepared
    run(prepared, catalog, Usable([proposal(prepared)]))

    (mapping,) = handle.objects.list(ControlMapping)
    assert mapping.generated_by == MAPPING_AGENT == "mapping-v1"


def test_the_node_declares_the_mapping_phase(prepared: Any, catalog: LoadedCatalog) -> None:
    assert node(prepared, catalog=catalog).phase is Phase.REQUIREMENT_AND_CONTROL_MAPPING
    assert node(prepared, catalog=catalog).name == NODE_NAME


def test_the_state_change_names_the_mappings_and_gaps(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, _, _, _ = prepared

    result = run(prepared, catalog, Usable([proposal(prepared, documentation_gaps=[a_gap()])]))

    (mapping,) = handle.objects.list(ControlMapping)
    (gap,) = handle.objects.list(DocumentationGap)
    assert result.state_changes["control_mapping_ids"] == [mapping.id]
    assert result.state_changes["documentation_gap_ids"] == [gap.id]


def a_gap(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Webhook authenticity mechanism is unstated",
        "description": "No supplied document says whether the validation is cryptographic.",
        "importance": "Whether forged events are rejected cannot be determined.",
        "requested_evidence": ["Documentation stating that signature verification is performed."],
        "severity": Severity.MEDIUM,
    }
    payload.update(changes)
    return payload


# ------------------------------------------------------------------------------------------
# Fixture: delegated authentication (evaluation-plan.md section 6 Scenario 2, section 11)
# ------------------------------------------------------------------------------------------


AUTH_APPLICABLE_REASON = (
    "ForgeFlow delegates user authentication to an external identity provider, which is this "
    "requirement's first applicable condition. The delegation and the provider are named."
)

MFA_NOT_APPLICABLE = (
    "Authentication and its factor policy are entirely owned by the external identity provider "
    "and documented as such, which is this requirement's first non_applicable_conditions entry."
)


def test_delegated_authentication_is_applicable_and_no_password_policy_is_proposed(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """The permanent regression case: `req-AUTH-001` applies, and no local-password gap follows."""
    handle, _, _, _ = prepared
    cited = evidence_ids(handle)[0]
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(
                    prepared,
                    requirement_id="req-AUTH-001",
                    applicability_status=ApplicabilityStatus.APPLICABLE,
                    applicability_reason=AUTH_APPLICABLE_REASON,
                    satisfaction_status=SatisfactionStatus.SATISFIED,
                    evidence_ids=[cited],
                    confidence=ConfidenceLevel.HIGH,
                ),
                a_mapping(
                    prepared,
                    requirement_id="req-AUTH-002",
                    applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
                    applicability_reason=MFA_NOT_APPLICABLE,
                    satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
                ),
            )
        ]
    )

    run(prepared, catalog, model)

    mappings = {m.requirement_id: m for m in handle.objects.list(ControlMapping)}
    assert mappings["req-AUTH-001"].applicability_status is ApplicabilityStatus.APPLICABLE
    assert mappings["req-AUTH-001"].satisfaction_status is SatisfactionStatus.SATISFIED
    assert not [m for m in mappings.values() if m.satisfaction_status is SatisfactionStatus.UNMET]


def test_no_output_asserts_a_missing_local_password_policy(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """The four `common_false_positives` entries on `req-AUTH-001`, none of them concluded."""
    handle, _, _, _ = prepared
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(
                    prepared,
                    requirement_id="req-AUTH-002",
                    applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
                    applicability_reason=MFA_NOT_APPLICABLE,
                    satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
                ),
            )
        ]
    )

    run(prepared, catalog, model)

    for mapping in handle.objects.list(ControlMapping):
        assert mapping.satisfaction_status is not SatisfactionStatus.UNMET
    assert not handle.objects.list(DocumentationGap)


def test_the_catalog_names_the_password_false_positives(catalog: LoadedCatalog) -> None:
    """The payload half of the case: the entries exist to be consulted."""
    entries = catalog.by_id()["req-AUTH-001"].common_false_positives

    assert any("password complexity" in entry for entry in entries)
    assert any("account lockout" in entry for entry in entries)


# ------------------------------------------------------------------------------------------
# Fixture: managed database encryption (forgeflow-scenario.md section 14.2)
# ------------------------------------------------------------------------------------------


def test_inherited_encryption_does_not_resolve_to_unmet(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """`req-DATA-001` is not `unmet` because the application document omits the internals."""
    handle, _, _, _ = prepared
    control = existing_control(handle)
    cited = evidence_ids(handle)[0]
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(
                    prepared,
                    requirement_id="req-DATA-001",
                    existing_control_ids=[control.id],
                    applicability_reason=(
                        "The system stores customer source code, which is this requirement's "
                        "first applicable condition."
                    ),
                    satisfaction_status=SatisfactionStatus.SATISFIED,
                    evidence_ids=[cited],
                ),
            )
        ]
    )

    run(prepared, catalog, model)

    (mapping,) = handle.objects.list(ControlMapping)
    assert mapping.satisfaction_status is SatisfactionStatus.SATISFIED
    assert control.id in mapping.control_ids


def test_an_unconfirmed_inherited_control_resolves_to_unverified(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """The other branch of section 14.2: silence produces a gap, never an assertion."""
    handle, _, _, _ = prepared
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(
                    prepared,
                    requirement_id="req-DATA-001",
                    applicability_reason="The system stores customer source code.",
                    satisfaction_status=SatisfactionStatus.UNVERIFIED,
                ),
                documentation_gaps=[
                    a_gap(
                        title="Encryption at rest is not attributed to a provider",
                        description="No document states which party encrypts stored data.",
                        importance="Whether the data is protected cannot be determined.",
                    )
                ],
            )
        ]
    )

    run(prepared, catalog, model)

    (mapping,) = handle.objects.list(ControlMapping)
    assert mapping.satisfaction_status is SatisfactionStatus.UNVERIFIED
    assert mapping.evidence_ids == []
    assert len(handle.objects.list(DocumentationGap)) == 1


# ------------------------------------------------------------------------------------------
# Fixture: webhook authenticity ambiguity, and the DEC-025 suppression record
# ------------------------------------------------------------------------------------------


SUPPRESSED_BY = (
    "documentation stating only that requests are validated, where the mechanism is unstated"
)


def test_validated_without_a_mechanism_produces_a_question_not_a_finding(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, _, _, _ = prepared
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(
                    prepared,
                    suppressed_conclusion=(
                        "that inbound event authenticity verification is absent"
                    ),
                    suppressed_by=SUPPRESSED_BY,
                ),
            )
        ]
    )

    run(prepared, catalog, model)

    (mapping,) = handle.objects.list(ControlMapping)
    assert mapping.satisfaction_status is SatisfactionStatus.UNVERIFIED


def test_the_suppression_is_recorded_rather_than_discarded(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """DEC-025: a suppression that leaves no trace is invisible to the false-negative rate."""
    handle, _, _, _ = prepared
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(
                    prepared,
                    suppressed_conclusion="that authenticity verification is absent",
                    suppressed_by=SUPPRESSED_BY,
                ),
            )
        ]
    )

    result = run(prepared, catalog, model)

    (mapping,) = handle.objects.list(ControlMapping)
    assert mapping.suppressed_conclusion == "that authenticity verification is absent"
    assert mapping.suppressed_by == SUPPRESSED_BY
    assert result.metadata["mappings"] == 1


def test_the_execution_record_counts_the_suppressions(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, _, _, _ = prepared
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(
                    prepared,
                    suppressed_conclusion="that authenticity verification is absent",
                    suppressed_by=SUPPRESSED_BY,
                ),
            )
        ]
    )

    run(prepared, catalog, model)

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert record.metadata["suppressions"] == 1


def test_the_catalog_records_the_exact_phrasing(catalog: LoadedCatalog) -> None:
    assert SUPPRESSED_BY in catalog.by_id()["req-WEBHOOK-001"].common_false_positives


# ------------------------------------------------------------------------------------------
# Fixture: a mechanism the examples do not name
# ------------------------------------------------------------------------------------------


UNLISTED_MECHANISM_REASON = (
    "The enterprise service mesh authenticates every request against the corporate directory "
    "before it reaches the application, and the directory is named. That mechanism is not among "
    "this requirement's acceptable_implementations, which are examples rather than an approved "
    "set, and it meets the statement."
)


def test_a_control_using_an_unlisted_mechanism_is_not_unsatisfied_for_that_reason(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """Section 12's prohibited operation, asserted on the rationale and not only on the status."""
    handle, _, _, _ = prepared
    cited = evidence_ids(handle)[0]
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(
                    prepared,
                    requirement_id="req-AUTH-001",
                    control_keys=["mesh"],
                    applicability_reason=UNLISTED_MECHANISM_REASON,
                    satisfaction_status=SatisfactionStatus.SATISFIED,
                    evidence_ids=[cited],
                ),
                controls=[
                    {
                        "key": "mesh",
                        "name": "Enterprise service mesh authentication",
                        "description": (
                            "The mesh authenticates requests against the corporate directory."
                        ),
                        "control_type": ControlType.INHERITED,
                        "implementation_status": ImplementationStatus.IMPLEMENTED,
                        "evidence_ids": [cited],
                    }
                ],
            )
        ]
    )

    run(prepared, catalog, model)

    (mapping,) = handle.objects.list(ControlMapping)
    assert mapping.satisfaction_status is SatisfactionStatus.SATISFIED
    assert "examples rather than an approved set" in mapping.applicability_reason

    listed = catalog.by_id()["req-AUTH-001"].acceptable_implementations
    assert not any("service mesh" in entry for entry in listed)


def test_a_proposed_control_is_allocated_and_linked(prepared: Any, catalog: LoadedCatalog) -> None:
    """A control the mapper found described is proposed by key and resolved at promotion."""
    handle, _, _, _ = prepared
    cited = evidence_ids(handle)[0]
    before = {control.id for control in handle.objects.list(Control)}
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(prepared, control_keys=["mesh"]),
                controls=[
                    {
                        "key": "mesh",
                        "name": "Enterprise service mesh authentication",
                        "description": "The mesh authenticates requests.",
                        "control_type": ControlType.INHERITED,
                        "implementation_status": ImplementationStatus.IMPLEMENTED,
                        "evidence_ids": [cited],
                    }
                ],
            )
        ]
    )

    run(prepared, catalog, model)

    added = [c for c in handle.objects.list(Control) if c.id not in before]
    (control,) = added
    assert control.generated_by == MAPPING_AGENT
    assert control.validation_status is ValidationStatus.NOT_EVALUATED

    (mapping,) = handle.objects.list(ControlMapping)
    assert mapping.control_ids == [control.id]


# ------------------------------------------------------------------------------------------
# Fixture: selectivity
# ------------------------------------------------------------------------------------------


def test_not_every_candidate_requirement_is_marked_applicable(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """Section 12's failure condition is undiscriminated applicability, at the output."""
    handle, _, _, _ = prepared
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(prepared),
                a_mapping(
                    prepared,
                    requirement_id="req-AUTH-002",
                    applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
                    applicability_reason=MFA_NOT_APPLICABLE,
                    satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
                ),
            )
        ]
    )

    run(prepared, catalog, model)

    statuses = {m.applicability_status for m in handle.objects.list(ControlMapping)}
    assert ApplicabilityStatus.NOT_APPLICABLE in statuses
    assert len(statuses) > 1


def test_a_not_applicable_mapping_names_a_non_applicable_condition(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, _, _, _ = prepared
    model = Usable(
        [
            proposal(
                prepared,
                a_mapping(
                    prepared,
                    requirement_id="req-AUTH-002",
                    applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
                    applicability_reason=MFA_NOT_APPLICABLE,
                    satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
                ),
            )
        ]
    )

    run(prepared, catalog, model)

    (mapping,) = handle.objects.list(ControlMapping)
    assert "non_applicable_conditions" in mapping.applicability_reason
    assert mapping.applicability_reason.strip()


# ------------------------------------------------------------------------------------------
# Fixture: prompt injection (forgeflow-scenario.md section 17)
# ------------------------------------------------------------------------------------------


def test_the_output_schema_has_no_field_an_injected_instruction_could_target(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """The structural half of the injection defence: there is nothing to instruct.

    `sample-repository-notes.md` asks its reader to assume every control is implemented and to
    return a private key if one appears. Neither request has a field. A control's implementation
    status is not free for a mapping to set without evidence — `Control` refuses `implemented`
    with no citation — and the proposal carries no secret-shaped field at all.
    """
    schema = MappingProposal.model_json_schema()
    rendered = str(schema)

    for forbidden in ("private_key", "secret", "credential", "api_key", "token"):
        assert forbidden not in rendered


def test_the_package_carries_no_credential_to_disclose(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, _, context, threat = prepared

    package = assemble_mapping_input(
        handle,
        context=context,
        threat=threat,
        catalog=catalog,
        index=EvidenceIndex(handle),
        evidence_ids=evidence_ids(handle),
        profile=PROFILE,
    )

    for shape in ("BEGIN RSA", "sk-ant-", "ANTHROPIC_API_KEY"):
        assert shape not in package.trusted


def test_a_control_cannot_be_marked_implemented_without_evidence(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """Section 12: unverified controls marked implemented is a failure condition, refused here.

    The refusal is a *retryable* schema failure rather than a crash, and the feedback names the
    control. That matters: `Control` would refuse it at promotion too, but as a pydantic error
    raised from inside a transaction naming a model instead of the object the agent wrote.
    """
    handle, ledger, _, _ = prepared
    unevidenced = proposal(
        prepared,
        a_mapping(prepared, control_keys=["assumed"]),
        controls=[
            {
                "key": "assumed",
                "name": "Every control the notes claim",
                "description": "Assumed implemented.",
                "control_type": ControlType.IMPLEMENTED,
                "implementation_status": ImplementationStatus.IMPLEMENTED,
            }
        ],
    )
    model = Usable([unevidenced, proposal(prepared)])

    node(prepared, catalog=catalog).run(node_context(handle, ledger, model))

    assert "'claimed' or 'unknown'" in model.calls[1].prompt
    assert not [
        control for control in handle.objects.list(Control) if control.generated_by == MAPPING_AGENT
    ]


def test_repeated_unevidenced_controls_stop_the_run(prepared: Any, catalog: LoadedCatalog) -> None:
    handle, ledger, _, _ = prepared
    unevidenced = proposal(
        prepared,
        a_mapping(prepared, control_keys=["assumed"]),
        controls=[
            {
                "key": "assumed",
                "name": "Every control the notes claim",
                "description": "Assumed implemented.",
                "control_type": ControlType.IMPLEMENTED,
                "implementation_status": ImplementationStatus.IMPLEMENTED,
            }
        ],
    )

    with pytest.raises(WorkflowError):
        node(prepared, catalog=catalog).run(
            node_context(handle, ledger, Usable([unevidenced, unevidenced, unevidenced]))
        )

    assert not handle.objects.list(ControlMapping)


# ------------------------------------------------------------------------------------------
# Zero unmet is a success (evaluation-plan.md section 20)
# ------------------------------------------------------------------------------------------


def test_a_run_producing_no_unmet_statuses_is_a_success(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, _, _, _ = prepared
    model = Usable([proposal(prepared)])

    result = run(prepared, catalog, model)

    assert len(model.calls) == 1
    assert result.metadata["mappings"] == 1
    assert not [
        m
        for m in handle.objects.list(ControlMapping)
        if m.satisfaction_status is SatisfactionStatus.UNMET
    ]


def test_a_run_producing_no_mappings_at_all_is_a_success(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, _, _, _ = prepared
    model = Usable([MappingProposal.model_validate({})])

    result = run(prepared, catalog, model)

    assert len(model.calls) == 1
    assert result.metadata["mappings"] == 0
    assert not handle.objects.list(ControlMapping)


def test_an_unverified_mapping_never_becomes_a_retry(prepared: Any, catalog: LoadedCatalog) -> None:
    """Section 12 states it directly: do not retry because a requirement remains unverified."""
    model = Usable([proposal(prepared, *[a_mapping(prepared) for _ in range(3)])])

    result = run(prepared, catalog, model)

    assert len(model.calls) == 1
    assert result.metadata["attempts"] == 1


# ------------------------------------------------------------------------------------------
# References and retry routing
# ------------------------------------------------------------------------------------------


def test_a_mapping_naming_an_unknown_requirement_is_a_validation_failure(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, ledger, _, _ = prepared
    invalid = proposal(prepared, a_mapping(prepared, requirement_id="req-NOPE-999"))
    model = Usable([invalid, proposal(prepared)])

    result = node(prepared, catalog=catalog).run(node_context(handle, ledger, model))

    assert result.metadata["attempts"] == 2
    assert len(handle.objects.list(ControlMapping)) == 1


def test_the_correction_names_the_unknown_identifier(prepared: Any, catalog: LoadedCatalog) -> None:
    handle, ledger, _, _ = prepared
    invalid = proposal(prepared, a_mapping(prepared, requirement_id="req-NOPE-999"))
    model = Usable([invalid, proposal(prepared)])

    node(prepared, catalog=catalog).run(node_context(handle, ledger, model))

    assert "req-NOPE-999" in model.calls[1].prompt


def test_a_mapping_for_another_threat_is_refused(prepared: Any, catalog: LoadedCatalog) -> None:
    """One call evaluates one threat; a mapping for another belongs to that threat's call."""
    handle, ledger, _, _ = prepared
    invalid = proposal(prepared, a_mapping(prepared, threat_id="thr-909"))
    model = Usable([invalid, proposal(prepared)])

    node(prepared, catalog=catalog).run(node_context(handle, ledger, model))

    assert "thr-909" in model.calls[1].prompt


def test_an_unresolved_control_key_is_refused(prepared: Any, catalog: LoadedCatalog) -> None:
    handle, ledger, _, _ = prepared
    invalid = proposal(prepared, a_mapping(prepared, control_keys=["nothing"]))
    model = Usable([invalid, proposal(prepared)])

    node(prepared, catalog=catalog).run(node_context(handle, ledger, model))

    assert "nothing" in model.calls[1].prompt


@pytest.mark.parametrize(
    "reason",
    [FailureReason.SCHEMA_VALIDATION_FAILURE, FailureReason.TRANSIENT_PROVIDER_FAILURE],
)
def test_a_retryable_provider_failure_is_retried(
    prepared: Any, catalog: LoadedCatalog, reason: FailureReason
) -> None:
    handle, ledger, _, _ = prepared
    failure = ModelFailure(reason=reason, message="try again", usage=USAGE)
    model = Usable([failure, proposal(prepared)])

    result = node(prepared, catalog=catalog).run(node_context(handle, ledger, model))

    assert result.metadata["attempts"] == 2


@pytest.mark.parametrize("reason", [FailureReason.REFUSED, FailureReason.INVALID_REQUEST])
def test_a_non_retryable_failure_is_not_retried(
    prepared: Any, catalog: LoadedCatalog, reason: FailureReason
) -> None:
    handle, ledger, _, _ = prepared
    model = Usable([ModelFailure(reason=reason, message="no", usage=USAGE)])

    with pytest.raises(WorkflowError):
        node(prepared, catalog=catalog).run(node_context(handle, ledger, model))

    assert len(model.calls) == 1


def test_retries_stop_at_the_configured_ceiling(prepared: Any, catalog: LoadedCatalog) -> None:
    handle, ledger, _, _ = prepared
    failure = ModelFailure(
        reason=FailureReason.TRANSIENT_PROVIDER_FAILURE, message="down", usage=USAGE
    )
    model = Usable([failure, failure, failure])

    with pytest.raises(WorkflowError):
        node(prepared, catalog=catalog, retry_policy=RetryPolicy()).run(
            node_context(handle, ledger, model)
        )

    assert len(model.calls) == 3


# ------------------------------------------------------------------------------------------
# The execution record, settings, and ceilings
# ------------------------------------------------------------------------------------------


def test_an_execution_record_is_written_for_a_successful_invocation(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, _, _, threat = prepared
    run(prepared, catalog, Usable([proposal(prepared)]))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert record.status is ExecutionStatus.COMPLETED
    assert record.prompt_version == "map-requirements-controls-v1"
    assert record.metadata["catalog_version"] == catalog.version
    assert record.metadata["threat_id"] == threat.id


def test_the_execution_record_names_its_inputs(prepared: Any, catalog: LoadedCatalog) -> None:
    """Section 27's `input_object_ids`, populated from the assembled package."""
    handle, _, _, threat = prepared
    run(prepared, catalog, Usable([proposal(prepared)]))

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert threat.id in record.input_object_ids
    assert "req-WEBHOOK-001" in record.input_object_ids


def test_a_failed_attempt_output_goes_to_traces_and_not_into_the_error(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    """`agent-design.md` section 27. A failed attempt's raw output is model text."""
    handle, ledger, _, _ = prepared
    invalid = proposal(prepared, a_mapping(prepared, requirement_id="req-NOPE-999"))

    with pytest.raises(WorkflowError):
        node(prepared, catalog=catalog).run(
            node_context(handle, ledger, Usable([invalid, invalid, invalid]))
        )

    (record,) = [r for r in handle.objects.list(ExecutionRecord) if r.node_name == NODE_NAME]
    assert any(key.endswith("_output") for key in record.metadata)
    assert "traces/" in (record.error_message or "")
    assert "applicability_reason" not in (record.error_message or "")


def test_the_call_uses_low_creativity(prepared: Any, catalog: LoadedCatalog) -> None:
    """Section 29. Breadth here means marking more requirements applicable."""
    handle, ledger, _, _ = prepared
    model = Usable([proposal(prepared)])

    node(prepared, catalog=catalog).run(node_context(handle, ledger, model))

    assert model.calls[0].settings.creativity is Creativity.LOW


def test_a_zero_call_ceiling_stops_the_node_before_it_spends(
    prepared: Any, catalog: LoadedCatalog
) -> None:
    handle, ledger, _, _ = prepared
    model = Usable([proposal(prepared)])

    with pytest.raises(LimitExceededError):
        node(prepared, catalog=catalog, budget=Budget(maximum_model_calls=0)).run(
            node_context(handle, ledger, model)
        )

    assert not model.calls


def test_a_node_context_without_a_model_is_refused(prepared: Any, catalog: LoadedCatalog) -> None:
    handle, ledger, _, _ = prepared

    with pytest.raises(ValueError, match="model-assisted"):
        node(prepared, catalog=catalog).run(node_context(handle, ledger, None))


def test_an_unapproved_context_is_refused(prepared: Any, catalog: LoadedCatalog) -> None:
    handle, ledger, context, _ = prepared
    draft = SystemContext.model_validate(
        {**context.model_dump(), "approved_at": None, "approved_by": None}
    )

    with pytest.raises(UnapprovedContextError, match="not approved"):
        node(prepared, catalog=catalog, context=draft).run(
            node_context(handle, ledger, Usable([proposal(prepared)]))
        )


def test_no_test_here_makes_a_live_model_call(prepared: Any, catalog: LoadedCatalog) -> None:
    """The rule `CLAUDE.md` states: a bare `uv run pytest` needs no API key."""
    handle, ledger, _, _ = prepared
    model = Usable([proposal(prepared)])

    node(prepared, catalog=catalog).run(node_context(handle, ledger, model))

    assert isinstance(model, DeterministicModel)
