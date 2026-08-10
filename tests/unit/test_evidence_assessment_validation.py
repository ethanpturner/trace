"""The node `agent-design.md` section 3 left out, and the write path it owns.

DEC-048 records the asymmetry and its repair: every other reasoning agent had a deterministic node
behind it on the diagram and this one did not. It was built anyway, because `data-model.md`
section 33 requires validation after model-generated structured output and section 22 states that
agents never write authoritative records — and neither rule is conditioned on a node being drawn.
Section 3 has since been amended to draw this node and the Critique Validation node beside it.

Two properties carry the file.

**The write is unreachable except through here.** `workflow/evidence_validation.py` contains no
store write at all, so section 22's write model is a property of the import graph rather than a
convention. That is the strongest form available and it is the one test in this file that would
still be worth running if every other assertion were deleted.

**Nothing is corrected.** Mapping Validation may downgrade an unsupported `unmet`, because DEC-013
says so by name. This node has no equivalent authority: a failing assessment is refused, and the
refusal is total rather than partial, because a partial write leaves a mixture nobody decided on.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.control import Control, ControlType, ImplementationStatus
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import (
    EvidenceAssessment,
    Recommendation,
    SubjectType,
)
from trace_ai.domain.proposals.evidence_validation import EvidenceValidationProposal
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.workflow.errors import ErrorClass
from trace_ai.workflow.evidence_assessment_validation import (
    PERMITTED_TRANSITIONS,
    SECTION_14_TRIGGERS,
    UnvalidatedWriteError,
    persist_assessments,
    validate_assessments,
)

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[tuple[AssessmentHandle, Control, SourceObservation]]:
    """ForgeFlow ingested, one control under test, and one recorded contradiction."""
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
        yield (handle, *_subjects(handle))


def _subjects(handle: AssessmentHandle) -> tuple[Control, SourceObservation]:
    stamped = now()
    cited = sorted(reference.id for reference in handle.objects.list(EvidenceReference))[:2]

    with handle.objects.transaction():
        control = Control.model_validate(
            {
                "id": handle.objects.allocate("ctl"),
                "assessment_id": handle.assessment_id,
                "name": "Managed database encryption at rest",
                "description": "The managed database platform encrypts stored data.",
                "control_type": ControlType.INHERITED,
                "implementation_status": ImplementationStatus.IMPLEMENTED,
                "validation_status": ValidationStatus.NOT_EVALUATED,
                "evidence_ids": [cited[0]],
                "generated_by": "context-extraction-v1",
                "created_at": stamped,
                "status": ObjectStatus.CANDIDATE,
            }
        )
        handle.objects.save(control)

        observation = SourceObservation.model_validate(
            {
                "id": handle.objects.allocate("obs"),
                "assessment_id": handle.assessment_id,
                "kind": ObservationKind.CONTRADICTION,
                "summary": "Two documents disagree about retention.",
                "evidence_ids": cited,
                "status": ObjectStatus.CANDIDATE,
                "created_at": stamped,
            }
        )
        handle.objects.save(observation)

    return control, observation


def references(handle: AssessmentHandle) -> list[EvidenceReference]:
    return list(handle.objects.list(EvidenceReference))


def an_assessment(prepared: Any, **changes: Any) -> dict[str, Any]:
    _, control, _ = prepared
    cited = control.evidence_ids[0]
    payload: dict[str, Any] = {
        "subject_type": SubjectType.CONTROL,
        "subject_id": control.id,
        "evidence_ids": [cited],
        "evidence_strengths": {cited: EvidenceStrength.DIRECT},
        "validation_status": ValidationStatus.SUPPORTED,
        "rationale": "The passage names the platform and states that it encrypts stored data.",
        "confidence": ConfidenceLevel.HIGH,
        "recommendation": Recommendation.CONTINUE,
    }
    payload.update(changes)
    return payload


def proposal(prepared: Any, *assessments: dict[str, Any]) -> EvidenceValidationProposal:
    return EvidenceValidationProposal.model_validate(
        {"assessments": list(assessments) if assessments else [an_assessment(prepared)]}
    )


def validate(prepared: Any, response: EvidenceValidationProposal, **changes: Any) -> Any:
    handle, control, observation = prepared
    options: dict[str, Any] = {
        "subjects": [control],
        "references": references(handle),
        "observations": [observation],
        **changes,
    }
    return validate_assessments(response, **options)


# The node is deterministic and owns the write


def test_the_node_makes_no_model_call_and_imports_no_provider_sdk() -> None:
    text = (
        PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "evidence_assessment_validation.py"
    ).read_text(encoding="utf-8")

    for forbidden in ("anthropic", "StructuredModel", "model.generate", "openai"):
        assert forbidden not in text


def test_the_write_path_is_unreachable_from_the_agent_module() -> None:
    """DEC-048's load-bearing property: section 22's write model as an import-graph fact."""
    agent = (PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "evidence_validation.py").read_text(
        encoding="utf-8"
    )

    for forbidden in ("objects.save", "repository.save", ".transaction()", "allocate("):
        assert forbidden not in agent

    assert "evidence_assessment_validation" not in agent


# Subject resolution


def test_a_subject_that_does_not_resolve_is_rejected(prepared: Any) -> None:
    outcome = validate(prepared, proposal(prepared, an_assessment(prepared, subject_id="ctl-909")))

    (error,) = [e for e in outcome.errors if e.field == "subject_id"]
    assert "ctl-909" in error.message
    assert error.error_class is ErrorClass.MISSING_REQUIRED_RELATIONSHIP
    assert not outcome.valid


def test_a_subject_of_a_different_type_is_rejected_with_both_values_named(
    prepared: Any,
) -> None:
    handle, control, _ = prepared
    stamped = now()
    with handle.objects.transaction():
        component = Component.model_validate(
            {
                "id": handle.objects.allocate("cmp"),
                "assessment_id": handle.assessment_id,
                "name": "Analysis Worker",
                "component_type": "background_worker",
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(component)
        threat = Threat.model_validate(
            {
                "id": handle.objects.allocate("thr"),
                "assessment_id": handle.assessment_id,
                "title": "Forged webhooks",
                "description": "An attacker submits webhook requests.",
                "methodology": "stride-scenario-based",
                "affected_component_ids": [component.id],
                "affected_asset_ids": ["ast-001"],
                "impact": "Unauthorized jobs",
                "confidence": ConfidenceLevel.MEDIUM,
                "status": ObjectStatus.CANDIDATE,
                "generated_by": "threat-analysis-v1",
                "created_at": stamped,
            }
        )

    outcome = validate_assessments(
        proposal(
            prepared,
            an_assessment(prepared, subject_type=SubjectType.THREAT, subject_id=control.id),
        ),
        subjects=[control, threat],
        references=references(handle),
    )

    (error,) = [e for e in outcome.errors if e.field == "subject_type"]
    assert "threat" in error.message
    assert "Control" in error.message


def test_a_resolving_subject_of_the_declared_type_passes(prepared: Any) -> None:
    outcome = validate(prepared, proposal(prepared))

    assert not [e for e in outcome.errors if e.field in {"subject_id", "subject_type"}]


# Evidence resolution and model-generated text


def test_an_assessment_referencing_nonexistent_evidence_is_rejected(prepared: Any) -> None:
    bad = an_assessment(
        prepared,
        evidence_ids=["evd-909"],
        evidence_strengths={"evd-909": EvidenceStrength.DIRECT},
    )

    outcome = validate(prepared, proposal(prepared, bad))

    (error,) = [e for e in outcome.errors if e.field == "evidence_ids"]
    assert "evd-909" in error.message


def test_model_generated_text_cited_as_source_evidence_is_rejected(prepared: Any) -> None:
    """Section 14's failure condition, keyed on the reference's own origin."""
    handle, control, _ = prepared
    cited = control.evidence_ids[0]
    original = next(r for r in references(handle) if r.id == cited)
    generated = EvidenceReference.model_validate(
        {**original.model_dump(), "source_origin": SourceOrigin.SYSTEM_GENERATED}
    )

    outcome = validate_assessments(
        proposal(prepared),
        subjects=[control],
        references=[generated],
    )

    (error,) = [e for e in outcome.errors if "model-generated" in e.rule]
    assert cited in error.message


def test_an_uploaded_document_reference_is_accepted(prepared: Any) -> None:
    outcome = validate(prepared, proposal(prepared))

    assert not [e for e in outcome.errors if "model-generated" in e.rule]


# Unsupported claims marked supported


def test_supported_with_no_evidence_is_rejected(prepared: Any) -> None:
    outcome = validate(
        prepared,
        proposal(
            prepared,
            an_assessment(
                prepared,
                validation_status=ValidationStatus.SUPPORTED,
                evidence_ids=[],
                evidence_strengths={},
            ),
        ),
    )

    (error,) = [e for e in outcome.errors if e.field == "validation_status"]
    assert "cites no evidence" in error.message


def test_unsupported_with_no_evidence_is_accepted(prepared: Any) -> None:
    """DEC-009 in this object's vocabulary: `unsupported` says the documents settle nothing."""
    outcome = validate(
        prepared,
        proposal(
            prepared,
            an_assessment(
                prepared,
                validation_status=ValidationStatus.UNSUPPORTED,
                evidence_ids=[],
                evidence_strengths={},
                recommendation=Recommendation.DOCUMENTATION_GAP,
            ),
        ),
    )

    assert not outcome.errors


# Contradictions


def test_a_contradiction_that_does_not_resolve_is_rejected(prepared: Any) -> None:
    outcome = validate(
        prepared,
        proposal(
            prepared,
            an_assessment(
                prepared,
                validation_status=ValidationStatus.CONTRADICTED,
                contradictions=["obs-909"],
            ),
        ),
    )

    (error,) = [e for e in outcome.errors if e.field == "contradictions"]
    assert "obs-909" in error.message


def test_a_contradiction_in_the_input_and_absent_from_the_output_is_flagged(
    prepared: Any,
) -> None:
    """Section 14: contradictory evidence may not be ignored, and only this node can see it."""
    _, _, observation = prepared

    outcome = validate(prepared, proposal(prepared), supplied_contradiction_ids=[observation.id])

    assert outcome.ignored_contradiction_ids == (observation.id,)
    assert not outcome.clean


def test_an_addressed_contradiction_is_not_flagged(prepared: Any) -> None:
    _, _, observation = prepared

    outcome = validate(
        prepared,
        proposal(
            prepared,
            an_assessment(
                prepared,
                validation_status=ValidationStatus.CONTRADICTED,
                contradictions=[observation.id],
            ),
        ),
        supplied_contradiction_ids=[observation.id],
    )

    assert outcome.ignored_contradiction_ids == ()


# Status transitions


def test_the_first_evaluation_may_reach_any_status(prepared: Any) -> None:
    """Everything starts `not_evaluated`, so the first classification is unrestricted."""
    assert PERMITTED_TRANSITIONS[ValidationStatus.NOT_EVALUATED] == frozenset(ValidationStatus)


def test_a_transition_is_recorded_rather_than_written_by_validation(prepared: Any) -> None:
    _, control, _ = prepared

    outcome = validate(prepared, proposal(prepared))

    (transition,) = outcome.transitions
    assert transition.subject_id == control.id
    assert transition.from_status is ValidationStatus.NOT_EVALUATED
    assert transition.to_status is ValidationStatus.SUPPORTED
    assert control.validation_status is ValidationStatus.NOT_EVALUATED


def test_re_applying_the_same_status_is_not_a_transition(prepared: Any) -> None:
    handle, control, _ = prepared
    settled = Control.model_validate(
        {**control.model_dump(), "validation_status": ValidationStatus.SUPPORTED}
    )

    outcome = validate_assessments(
        proposal(prepared), subjects=[settled], references=references(handle)
    )

    assert outcome.transitions == ()
    assert not outcome.errors


def test_a_settled_status_reversing_is_an_error(prepared: Any) -> None:
    handle, control, _ = prepared
    settled = Control.model_validate(
        {**control.model_dump(), "validation_status": ValidationStatus.UNSUPPORTED}
    )

    outcome = validate_assessments(
        proposal(prepared), subjects=[settled], references=references(handle)
    )

    (error,) = [e for e in outcome.errors if e.field == "validation_status"]
    assert "unsupported" in error.message
    assert "supported" in error.message
    assert not outcome.valid


def test_requires_confirmation_may_move_anywhere(prepared: Any) -> None:
    """A confirmation arriving is the event the status exists to wait for."""
    handle, control, _ = prepared
    waiting = Control.model_validate(
        {**control.model_dump(), "validation_status": ValidationStatus.REQUIRES_CONFIRMATION}
    )

    outcome = validate_assessments(
        proposal(prepared), subjects=[waiting], references=references(handle)
    )

    assert not outcome.errors
    (transition,) = outcome.transitions
    assert transition.to_status is ValidationStatus.SUPPORTED


def test_a_subject_with_no_validation_status_has_no_transition(prepared: Any) -> None:
    """Only `Control` carries one. That is a fact about the schema, not a problem."""
    handle, control, _ = prepared
    stamped = now()
    with handle.objects.transaction():
        component = Component.model_validate(
            {
                "id": handle.objects.allocate("cmp"),
                "assessment_id": handle.assessment_id,
                "name": "Analysis Worker",
                "component_type": "background_worker",
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(component)
        threat = Threat.model_validate(
            {
                "id": handle.objects.allocate("thr"),
                "assessment_id": handle.assessment_id,
                "title": "Forged webhooks",
                "description": "An attacker submits webhook requests.",
                "methodology": "stride-scenario-based",
                "affected_component_ids": [component.id],
                "affected_asset_ids": ["ast-001"],
                "impact": "Unauthorized jobs",
                "confidence": ConfidenceLevel.MEDIUM,
                "status": ObjectStatus.CANDIDATE,
                "generated_by": "threat-analysis-v1",
                "created_at": stamped,
            }
        )

    outcome = validate_assessments(
        proposal(
            prepared,
            an_assessment(prepared, subject_type=SubjectType.THREAT, subject_id=threat.id),
        ),
        subjects=[control, threat],
        references=references(handle),
    )

    assert outcome.transitions == ()
    assert not outcome.errors


# Persistence


def test_a_validated_assessment_is_written(prepared: Any) -> None:
    handle, _, _ = prepared
    response = proposal(prepared)
    outcome = validate(prepared, response)

    written, updated = persist_assessments(handle, response, outcome)

    assert len(written) == 1
    assert written[0].id.startswith("eas-")
    assert handle.objects.list(EvidenceAssessment)
    assert len(updated) == 1
    assert updated[0].validation_status is ValidationStatus.SUPPORTED


def test_the_transition_is_applied_to_the_stored_control(prepared: Any) -> None:
    handle, control, _ = prepared
    response = proposal(prepared)

    persist_assessments(handle, response, validate(prepared, response))

    assert handle.objects.get(Control, control.id).validation_status is ValidationStatus.SUPPORTED


def test_nothing_is_written_when_validation_failed(prepared: Any) -> None:
    handle, _, _ = prepared
    response = proposal(prepared, an_assessment(prepared, subject_id="ctl-909"))
    outcome = validate(prepared, response)

    with pytest.raises(UnvalidatedWriteError):
        persist_assessments(handle, response, outcome)

    assert not handle.objects.list(EvidenceAssessment)


def test_the_refusal_is_total_rather_than_partial(prepared: Any) -> None:
    """One bad assessment blocks the good ones; a mixture is a state nobody decided on."""
    handle, _, _ = prepared
    response = proposal(
        prepared, an_assessment(prepared), an_assessment(prepared, subject_id="ctl-909")
    )
    outcome = validate(prepared, response)

    with pytest.raises(UnvalidatedWriteError):
        persist_assessments(handle, response, outcome)

    assert not handle.objects.list(EvidenceAssessment)


def test_identifiers_are_allocated_by_the_application(prepared: Any) -> None:
    handle, _, _ = prepared
    response = proposal(prepared, an_assessment(prepared), an_assessment(prepared))

    written, _ = persist_assessments(handle, response, validate(prepared, response))

    assert [assessed.id for assessed in written] == ["eas-001", "eas-002"]
    assert all(assessed.assessment_id == handle.assessment_id for assessed in written)


def test_the_recommendation_survives_persistence(prepared: Any) -> None:
    """DEC-047: stored beside DEC-013's outcome so the two can be compared."""
    handle, _, _ = prepared
    response = proposal(
        prepared, an_assessment(prepared, recommendation=Recommendation.DOCUMENTATION_GAP)
    )

    written, _ = persist_assessments(handle, response, validate(prepared, response))

    assert written[0].recommendation is Recommendation.DOCUMENTATION_GAP


def test_nothing_is_corrected(prepared: Any) -> None:
    """Mapping Validation may downgrade; this node has no such authority (DEC-048)."""
    handle, _, _ = prepared
    response = proposal(
        prepared, an_assessment(prepared, validation_status=ValidationStatus.PARTIALLY_SUPPORTED)
    )

    written, _ = persist_assessments(handle, response, validate(prepared, response))

    assert written[0].validation_status is ValidationStatus.PARTIALLY_SUPPORTED


# Human-review triggers


def test_a_contradicted_conclusion_raises_the_first_trigger(prepared: Any) -> None:
    _, _, observation = prepared

    outcome = validate(
        prepared,
        proposal(
            prepared,
            an_assessment(
                prepared,
                validation_status=ValidationStatus.CONTRADICTED,
                contradictions=[observation.id],
            ),
        ),
    )

    assert SECTION_14_TRIGGERS[0] in [trigger.name for trigger in outcome.triggers]


def test_a_partially_supported_conclusion_raises_the_partial_support_trigger(
    prepared: Any,
) -> None:
    outcome = validate(
        prepared,
        proposal(
            prepared,
            an_assessment(prepared, validation_status=ValidationStatus.PARTIALLY_SUPPORTED),
        ),
    )

    assert SECTION_14_TRIGGERS[2] in [trigger.name for trigger in outcome.triggers]


def test_an_undocumented_inherited_control_raises_the_reviewer_knowledge_trigger(
    prepared: Any,
) -> None:
    handle, control, _ = prepared
    claimed = Control.model_validate(
        {
            **control.model_dump(),
            "implementation_status": ImplementationStatus.CLAIMED,
            "evidence_ids": [],
        }
    )

    outcome = validate_assessments(
        proposal(prepared), subjects=[claimed], references=references(handle)
    )

    assert SECTION_14_TRIGGERS[3] in [trigger.name for trigger in outcome.triggers]


def test_every_section_14_trigger_is_named() -> None:
    assert len(SECTION_14_TRIGGERS) == 4
    assert len(set(SECTION_14_TRIGGERS)) == 4


# The expected shape


def test_an_assessment_set_with_no_unsupported_classification_passes_cleanly(
    prepared: Any,
) -> None:
    """Under DEC-009 that is an expected outcome, not a sign the agent did nothing."""
    outcome = validate(prepared, proposal(prepared))

    assert outcome.valid
    assert outcome.clean
    assert not outcome.errors
    assert not outcome.triggers


def test_a_set_of_nothing_but_unsupported_also_passes_cleanly(prepared: Any) -> None:
    outcome = validate(
        prepared,
        proposal(
            prepared,
            an_assessment(
                prepared,
                validation_status=ValidationStatus.UNSUPPORTED,
                evidence_ids=[],
                evidence_strengths={},
                recommendation=Recommendation.DOCUMENTATION_GAP,
            ),
        ),
    )

    assert outcome.clean


def test_an_empty_assessment_set_passes_cleanly(prepared: Any) -> None:
    outcome = validate(prepared, EvidenceValidationProposal.model_validate({}))

    assert outcome.clean
    assert outcome.transitions == ()
