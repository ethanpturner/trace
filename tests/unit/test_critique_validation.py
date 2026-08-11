"""Critique validation, recommendation routing, and the loop the critic must not start.

`agent-design.md` section 27 gives this node its worked example: "The critic may recommend that a
threat be reconsidered. It may not automatically start an unlimited threat-generation and criticism
loop." Three properties carry the file.

**Nothing is executed and nothing is mutated.** A critique produces a routed recommendation and the
target object is untouched. The test compares the target field for field before and after, because
`data-model.md` section 32 requires the lineage from threat through mapping and assessment to
critique to stay traceable, and an in-place mutation destroys the thing the reference points at.

**Re-invocation is counted, and past the budget it goes to a person.** `revise` and `investigate`
send work back; `keep`, `reject`, and `merge` go forward. Which phase a recommendation would
re-enter comes from the subject's type, so the rule is a table rather than a judgment.

**Zero critiques is clean.** No warning, no flag, no trigger. Roadmap Stage 4 gates the critic on
whether it improves results, and a node that treated silence as a problem would be evidence about
the node rather than about the critic.
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
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.critique import (
    Critique,
    CritiqueSubjectType,
    CritiqueType,
    RecommendedAction,
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
from trace_ai.domain.proposals.critical_review import (
    CRITICAL_REVIEW_AGENT,
    CriticalReviewProposal,
)
from trace_ai.domain.proposals.mapping import MAPPING_AGENT
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.workflow.critique_validation import (
    DEFAULT_MAXIMUM_REINVOCATIONS,
    REINVOKING_ACTIONS,
    SECTION_15_TRIGGERS,
    UnvalidatedWriteError,
    persist_critiques,
    validate_critiques,
)
from trace_ai.workflow.errors import ErrorClass
from trace_ai.workflow.phases import Phase

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"

SUBJECT_MODELS: dict[CritiqueSubjectType, type[Any]] = {
    CritiqueSubjectType.THREAT: Threat,
    CritiqueSubjectType.CONTROL: Control,
    CritiqueSubjectType.CONTROL_MAPPING: ControlMapping,
    CritiqueSubjectType.DOCUMENTATION_GAP: DocumentationGap,
}


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[dict[str, Any]]:
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
        objects["handle"] = handle
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
                "evidence_ids": [cited],
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(component)

        threat = Threat.model_validate(
            {
                "id": handle.objects.allocate("thr"),
                "assessment_id": handle.assessment_id,
                "title": "Forged webhooks trigger unauthorized analysis jobs",
                "description": "An attacker submits webhook requests.",
                "methodology": "stride-scenario-based",
                "affected_component_ids": [component.id],
                "affected_asset_ids": ["ast-001"],
                "impact": "Unauthorized jobs",
                "confidence": ConfidenceLevel.MEDIUM,
                "status": ObjectStatus.APPROVED,
                "generated_by": "threat-analysis-v1",
                "created_at": stamped,
            }
        )
        handle.objects.save(threat)

        control = Control.model_validate(
            {
                "id": handle.objects.allocate("ctl"),
                "assessment_id": handle.assessment_id,
                "name": "Managed database encryption at rest",
                "description": "The platform encrypts stored data.",
                "control_type": ControlType.INHERITED,
                "implementation_status": ImplementationStatus.IMPLEMENTED,
                "validation_status": ValidationStatus.NOT_EVALUATED,
                "evidence_ids": [cited],
                "generated_by": "context-extraction-v1",
                "created_at": stamped,
                "status": ObjectStatus.APPROVED,
            }
        )
        handle.objects.save(control)

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
        "control": control,
        "mapping": mapping,
        "gap": gap,
        "evidence_id": cited,
    }


def a_critique(prepared: dict[str, Any], **changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subject_type": CritiqueSubjectType.CONTROL_MAPPING,
        "subject_id": prepared["mapping"].id,
        "critique_type": CritiqueType.IGNORED_INHERITED_CONTROL,
        "description": "The mapping does not credit the documented platform encryption control.",
        "rationale": "The control is inherited and its inheritance is documented.",
        "evidence_ids": [prepared["evidence_id"]],
        "recommended_action": RecommendedAction.REVISE,
        "confidence": ConfidenceLevel.MEDIUM,
    }
    payload.update(changes)
    return payload


def proposal(prepared: dict[str, Any], *critiques: dict[str, Any]) -> CriticalReviewProposal:
    return CriticalReviewProposal.model_validate({"critiques": list(critiques)})


def subjects(prepared: dict[str, Any]) -> list[Any]:
    return [prepared["threat"], prepared["control"], prepared["mapping"], prepared["gap"]]


def validate(prepared: dict[str, Any], response: CriticalReviewProposal, **changes: Any) -> Any:
    options: dict[str, Any] = {
        "subjects": subjects(prepared),
        "subject_models": SUBJECT_MODELS,
        "reviewed_object_count": 4,
        **changes,
    }
    return validate_critiques(response, **options)


# Deterministic, and no framework


def test_the_node_makes_no_model_call_and_imports_no_provider_sdk() -> None:
    text = (PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "critique_validation.py").read_text(
        encoding="utf-8"
    )

    for forbidden in ("anthropic", "StructuredModel", "model.generate", "openai"):
        assert forbidden not in text


def test_the_budget_check_imports_no_orchestration_framework() -> None:
    """DEC-016 settled orchestration as plain Python; this must survive whatever it becomes.

    Imports only. The module docstring names LangGraph in order to say it was rejected, and a
    test that read the prose would fail on the sentence explaining why it passes.
    """
    text = (PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "critique_validation.py").read_text(
        encoding="utf-8"
    )
    imports = [
        line
        for line in text.splitlines()
        if line.startswith(("import ", "from ")) or line.strip().startswith(("import ", "from "))
    ]

    for forbidden in ("langgraph", "langchain", "prefect", "temporal", "celery"):
        assert not [line for line in imports if forbidden in line.lower()]


# Targets


def test_a_target_that_does_not_resolve_is_rejected(prepared: dict[str, Any]) -> None:
    outcome = validate(prepared, proposal(prepared, a_critique(prepared, subject_id="map-909")))

    (error,) = [e for e in outcome.errors if e.field == "subject_id"]
    assert "map-909" in error.message
    assert error.error_class is ErrorClass.MISSING_REQUIRED_RELATIONSHIP
    assert not outcome.valid


def test_a_target_of_a_different_type_is_rejected_with_both_values_named(
    prepared: dict[str, Any],
) -> None:
    outcome = validate(
        prepared,
        proposal(
            prepared,
            a_critique(
                prepared,
                subject_type=CritiqueSubjectType.THREAT,
                subject_id=prepared["mapping"].id,
            ),
        ),
    )

    (error,) = [e for e in outcome.errors if e.field == "subject_type"]
    assert "threat" in error.message
    assert "ControlMapping" in error.message


def test_a_resolving_target_of_the_declared_type_passes(prepared: dict[str, Any]) -> None:
    outcome = validate(prepared, proposal(prepared, a_critique(prepared)))

    assert not outcome.errors


# Severity critiques (DEC-049)


def test_a_severity_critique_against_a_subject_with_no_severity_is_rejected(
    prepared: dict[str, Any],
) -> None:
    outcome = validate(
        prepared,
        proposal(prepared, a_critique(prepared, critique_type=CritiqueType.SEVERITY_OVERSTATED)),
    )

    (error,) = [e for e in outcome.errors if e.field == "critique_type"]
    assert "no severity" in error.message
    assert "DEC-030" in error.rule


def test_a_severity_critique_against_a_documentation_gap_passes(
    prepared: dict[str, Any],
) -> None:
    """DEC-045 makes a gap's rating a real judgment, so disagreeing with it is a real critique."""
    outcome = validate(
        prepared,
        proposal(
            prepared,
            a_critique(
                prepared,
                subject_type=CritiqueSubjectType.DOCUMENTATION_GAP,
                subject_id=prepared["gap"].id,
                critique_type=CritiqueType.SEVERITY_OVERSTATED,
                recommended_action=RecommendedAction.KEEP,
            ),
        ),
    )

    assert not [e for e in outcome.errors if e.field == "critique_type"]


# Routing: nothing is executed, nothing is mutated


def test_the_target_is_unchanged_field_for_field(prepared: dict[str, Any]) -> None:
    """Section 32's lineage rule: a mutation destroys the thing the reference points at."""
    before = prepared["mapping"].model_dump()

    validate(prepared, proposal(prepared, a_critique(prepared)))

    assert prepared["mapping"].model_dump() == before


def test_the_stored_target_is_unchanged_after_persistence(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    before = handle.objects.get(ControlMapping, prepared["mapping"].id).model_dump()
    response = proposal(prepared, a_critique(prepared))

    persist_critiques(handle, response, validate(prepared, response))

    assert handle.objects.get(ControlMapping, prepared["mapping"].id).model_dump() == before


def test_a_recommendation_is_recorded_against_its_target(prepared: dict[str, Any]) -> None:
    outcome = validate(prepared, proposal(prepared, a_critique(prepared)))

    (routed,) = outcome.recommendations
    assert routed.subject_id == prepared["mapping"].id
    assert routed.action is RecommendedAction.REVISE


def test_the_persist_function_loads_no_target(prepared: dict[str, Any]) -> None:
    """The no-rewrite prohibition as a property of the function rather than of a rule."""
    text = (PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "critique_validation.py").read_text(
        encoding="utf-8"
    )
    body = text[text.index("def persist_critiques") :]

    assert "repository.get(" not in body
    assert "model_validate({**" not in body


# Loop prevention (section 27)


def test_the_two_reinvoking_actions_are_revise_and_investigate() -> None:
    assert {RecommendedAction.REVISE, RecommendedAction.INVESTIGATE} == REINVOKING_ACTIONS


@pytest.mark.parametrize(
    "subject_type, key, phase",
    [
        (CritiqueSubjectType.THREAT, "threat", Phase.THREAT_GENERATION),
        (
            CritiqueSubjectType.CONTROL_MAPPING,
            "mapping",
            Phase.REQUIREMENT_AND_CONTROL_MAPPING,
        ),
        (CritiqueSubjectType.CONTROL, "control", Phase.REQUIREMENT_AND_CONTROL_MAPPING),
    ],
)
def test_a_revise_recommendation_names_the_phase_it_would_re_enter(
    prepared: dict[str, Any], subject_type: CritiqueSubjectType, key: str, phase: Phase
) -> None:
    outcome = validate(
        prepared,
        proposal(
            prepared,
            a_critique(prepared, subject_type=subject_type, subject_id=prepared[key].id),
        ),
    )

    (routed,) = outcome.recommendations
    assert routed.reinvokes_phase is phase


@pytest.mark.parametrize(
    "action", [RecommendedAction.KEEP, RecommendedAction.REJECT, RecommendedAction.MERGE]
)
def test_a_forward_recommendation_re_enters_no_phase(
    prepared: dict[str, Any], action: RecommendedAction
) -> None:
    outcome = validate(
        prepared, proposal(prepared, a_critique(prepared, recommended_action=action))
    )

    (routed,) = outcome.recommendations
    assert routed.reinvokes_phase is None
    assert routed.executable is True


def test_a_recommendation_about_a_documentation_gap_routes_forward(
    prepared: dict[str, Any],
) -> None:
    """Finding Consolidation runs after critical review, so a gap recommendation is not a loop."""
    outcome = validate(
        prepared,
        proposal(
            prepared,
            a_critique(
                prepared,
                subject_type=CritiqueSubjectType.DOCUMENTATION_GAP,
                subject_id=prepared["gap"].id,
            ),
        ),
    )

    (routed,) = outcome.recommendations
    assert routed.reinvokes_phase is None


def test_re_invocations_past_the_budget_go_to_human_review(prepared: dict[str, Any]) -> None:
    response = proposal(
        prepared,
        a_critique(prepared),
        a_critique(
            prepared,
            subject_type=CritiqueSubjectType.THREAT,
            subject_id=prepared["threat"].id,
            critique_type=CritiqueType.WEAK_ATTACK_PATH,
        ),
        a_critique(
            prepared,
            subject_type=CritiqueSubjectType.CONTROL,
            subject_id=prepared["control"].id,
            critique_type=CritiqueType.UNSUPPORTED_CLAIM,
        ),
    )

    outcome = validate(prepared, response, maximum_reinvocations=2)

    executable = [r for r in outcome.recommendations if r.reinvokes_phase and r.executable]
    assert len(executable) == 2
    assert len(outcome.deferred_to_review) == 1
    assert "budget is spent" in outcome.deferred_to_review[0].reason


def test_a_zero_budget_defers_every_re_invocation(prepared: dict[str, Any]) -> None:
    outcome = validate(prepared, proposal(prepared, a_critique(prepared)), maximum_reinvocations=0)

    assert outcome.deferred_to_review
    assert outcome.recommendations[0].executable is False


def test_the_default_budget_is_small(prepared: dict[str, Any]) -> None:
    """Section 27's concern is an unbounded loop; the number's job is to be small."""
    assert DEFAULT_MAXIMUM_REINVOCATIONS == 2


def test_a_deferred_recommendation_raises_the_reviewer_decision_trigger(
    prepared: dict[str, Any],
) -> None:
    outcome = validate(prepared, proposal(prepared, a_critique(prepared)), maximum_reinvocations=0)

    assert SECTION_15_TRIGGERS[2] in [trigger.name for trigger in outcome.triggers]


# Volume


def test_volume_above_the_ratio_is_flagged(prepared: dict[str, Any]) -> None:
    """Section 15's superficial-volume failure condition, measured rather than asserted."""
    response = proposal(
        prepared,
        a_critique(prepared),
        a_critique(prepared, critique_type=CritiqueType.UNSUPPORTED_CLAIM),
        a_critique(prepared, critique_type=CritiqueType.WEAK_ATTACK_PATH),
        a_critique(prepared, critique_type=CritiqueType.MISSING_PRECONDITION),
        a_critique(prepared, critique_type=CritiqueType.GENERIC_RECOMMENDATION),
    )

    outcome = validate(prepared, response, reviewed_object_count=4)

    assert outcome.volume_exceeded
    assert outcome.volume_ratio == pytest.approx(1.25)


def test_volume_within_the_ratio_is_not_flagged(prepared: dict[str, Any]) -> None:
    outcome = validate(prepared, proposal(prepared, a_critique(prepared)))

    assert not outcome.volume_exceeded
    assert outcome.volume_ratio == pytest.approx(0.25)


def test_the_ratio_is_a_parameter(prepared: dict[str, Any]) -> None:
    outcome = validate(prepared, proposal(prepared, a_critique(prepared)), volume_ratio=0.1)

    assert outcome.volume_exceeded


def test_a_zero_reviewed_count_does_not_divide_by_zero(prepared: dict[str, Any]) -> None:
    outcome = validate(prepared, proposal(prepared), reviewed_object_count=0)

    assert outcome.volume_ratio == 0.0


# Duplicates


def test_the_same_type_against_the_same_target_twice_is_detected(
    prepared: dict[str, Any],
) -> None:
    outcome = validate(prepared, proposal(prepared, a_critique(prepared), a_critique(prepared)))

    assert outcome.duplicate_keys == (
        (prepared["mapping"].id, CritiqueType.IGNORED_INHERITED_CONTROL.value),
    )


def test_two_different_types_against_one_target_are_not_duplicates(
    prepared: dict[str, Any],
) -> None:
    outcome = validate(
        prepared,
        proposal(
            prepared,
            a_critique(prepared),
            a_critique(prepared, critique_type=CritiqueType.UNSUPPORTED_CLAIM),
        ),
    )

    assert outcome.duplicate_keys == ()


# Human-review triggers


def test_a_contradictory_analysis_critique_raises_the_conflicting_interpretation_trigger(
    prepared: dict[str, Any],
) -> None:
    outcome = validate(
        prepared,
        proposal(prepared, a_critique(prepared, critique_type=CritiqueType.CONTRADICTORY_ANALYSIS)),
    )

    assert SECTION_15_TRIGGERS[1] in [trigger.name for trigger in outcome.triggers]


def test_a_missing_evidence_critique_raises_the_architecture_gap_trigger(
    prepared: dict[str, Any],
) -> None:
    outcome = validate(
        prepared,
        proposal(prepared, a_critique(prepared, critique_type=CritiqueType.MISSING_EVIDENCE)),
    )

    assert SECTION_15_TRIGGERS[3] in [trigger.name for trigger in outcome.triggers]


def test_a_severity_critique_raises_the_high_severity_trigger(
    prepared: dict[str, Any],
) -> None:
    outcome = validate(
        prepared,
        proposal(
            prepared,
            a_critique(
                prepared,
                subject_type=CritiqueSubjectType.DOCUMENTATION_GAP,
                subject_id=prepared["gap"].id,
                critique_type=CritiqueType.SEVERITY_UNDERSTATED,
                recommended_action=RecommendedAction.KEEP,
            ),
        ),
    )

    assert SECTION_15_TRIGGERS[0] in [trigger.name for trigger in outcome.triggers]


def test_every_section_15_trigger_is_named() -> None:
    assert len(SECTION_15_TRIGGERS) == 4
    assert len(set(SECTION_15_TRIGGERS)) == 4


# Persistence and lineage


def test_a_validated_critique_is_written(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    response = proposal(prepared, a_critique(prepared))

    written = persist_critiques(handle, response, validate(prepared, response))

    assert len(written) == 1
    assert written[0].id.startswith("crq-")
    assert written[0].generated_by == CRITICAL_REVIEW_AGENT
    assert written[0].status is ObjectStatus.CANDIDATE


def test_lineage_from_critique_to_target_is_queryable(prepared: dict[str, Any]) -> None:
    """Section 32: the chain stays traceable because the critique holds a reference."""
    handle = prepared["handle"]
    response = proposal(prepared, a_critique(prepared))
    persist_critiques(handle, response, validate(prepared, response))

    (stored,) = handle.objects.list(Critique)
    assert stored.subject_id == prepared["mapping"].id
    assert handle.objects.get(ControlMapping, stored.subject_id).threat_id == (
        prepared["threat"].id
    )


def test_nothing_is_written_when_validation_failed(prepared: dict[str, Any]) -> None:
    handle = prepared["handle"]
    response = proposal(prepared, a_critique(prepared), a_critique(prepared, subject_id="map-909"))

    with pytest.raises(UnvalidatedWriteError):
        persist_critiques(handle, response, validate(prepared, response))

    assert not handle.objects.list(Critique)


# Zero critiques


def test_zero_critiques_is_a_valid_passing_outcome(prepared: dict[str, Any]) -> None:
    """Roadmap Stage 4 gates the critic; a node that flagged silence would gate the node."""
    outcome = validate(prepared, proposal(prepared))

    assert outcome.valid
    assert outcome.clean
    assert outcome.recommendations == ()
    assert not outcome.volume_exceeded


def test_persisting_zero_critiques_writes_nothing_and_raises_nothing(
    prepared: dict[str, Any],
) -> None:
    handle = prepared["handle"]
    response = proposal(prepared)

    written = persist_critiques(handle, response, validate(prepared, response))

    assert written == []
    assert not handle.objects.list(Critique)
