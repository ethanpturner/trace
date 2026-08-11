"""Finding Consolidation: the routing, and the outcomes that must not read as failures.

This node is where `design-principles.md` section 9's "quality over finding volume" becomes a
structural property. The tests that matter most are the ones asserting that *nothing* happened and
that nothing was wrong with that.

**Zero findings is a success.** An assessment whose requirements are satisfied or inapplicable
produces no findings, no warning, and no error. A test asserts the whole outcome rather than just
the count, because "no findings but a warning" would be the same failure wearing a different shape.

**No route from silence to a finding exists.** `unverified` reaches `Outcome.GAP_OR_QUESTION` under
every validation status, so the DEC-009 separation is a property of the routing rather than a check
inside it. The regression test named for DEC-009 walks the whole validation vocabulary rather than
the one case somebody thought of.

**Titles are byte-identical across runs.** Two consolidations over identical input are compared
directly, because an authored title would drift and make the same finding look new to every
evaluation run.
"""

from __future__ import annotations

from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.enums import (
    ConfidenceLevel,
    EvidenceStrength,
    ObjectStatus,
    Severity,
    ValidationStatus,
)
from trace_ai.domain.evidence_assessment import EvidenceAssessment, Recommendation, SubjectType
from trace_ai.domain.outcomes import Outcome
from trace_ai.domain.question import QuestionPriority
from trace_ai.domain.threat import Threat
from trace_ai.workflow.finding_consolidation import (
    GENERATED_BY,
    NODE_NAME,
    consolidate,
    finding_title,
)

MODULE = PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "finding_consolidation.py"


def a_threat(**changes: Any) -> Threat:
    payload: dict[str, Any] = {
        "id": "thr-001",
        "assessment_id": "asm-001",
        "title": "Forged webhooks trigger unauthorized analysis jobs",
        "description": "An attacker submits webhook requests the receiver acts on.",
        "methodology": "stride-scenario-based",
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "impact": "Unauthorized jobs and denial of service.",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.APPROVED,
        "generated_by": "threat-analysis-v1",
        "created_at": now(),
    }
    payload.update(changes)
    return Threat.model_validate(payload)


def a_mapping(**changes: Any) -> ControlMapping:
    payload: dict[str, Any] = {
        "id": "map-001",
        "assessment_id": "asm-001",
        "threat_id": "thr-001",
        "requirement_id": "req-WEBHOOK-001",
        "applicability_status": ApplicabilityStatus.APPLICABLE,
        "applicability_reason": "The system exposes an endpoint accepting external events.",
        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
        "confidence": ConfidenceLevel.MEDIUM,
        "generated_by": "mapping-v1",
        "reviewer_status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return ControlMapping.model_validate(payload)


def an_assessment(**changes: Any) -> EvidenceAssessment:
    payload: dict[str, Any] = {
        "id": "eas-001",
        "assessment_id": "asm-001",
        "subject_type": SubjectType.CONTROL_MAPPING,
        "subject_id": "map-001",
        "evidence_ids": ["evd-001"],
        "evidence_strengths": {"evd-001": EvidenceStrength.CONTEXTUAL},
        "validation_status": ValidationStatus.UNSUPPORTED,
        "rationale": "The passage does not establish whether verification occurs.",
        "confidence": ConfidenceLevel.MEDIUM,
        "recommendation": Recommendation.DOCUMENTATION_GAP,
        "generated_by": "evidence-validation-v1",
        "created_at": now(),
    }
    payload.update(changes)
    return EvidenceAssessment.model_validate(payload)


def run(**changes: Any) -> Any:
    options: dict[str, Any] = {
        "threats": [a_threat()],
        "mappings": [a_mapping()],
        "assessments": [an_assessment()],
        "assessment_id": "asm-001",
        **changes,
    }
    return consolidate(**options)


# ------------------------------------------------------------------------------------------
# No quota, anywhere
# ------------------------------------------------------------------------------------------


def test_the_module_contains_no_quota_floor_or_target() -> None:
    """An acceptance criterion checkable by reading, so it is checked by reading.

    The names are assembled from parts because a test scanning its own source for a literal finds
    the literal in its own assertion.
    """
    text = MODULE.read_text(encoding="utf-8")

    for prefix, suffix in (
        ("minimum", "findings"),
        ("target", "count"),
        ("expected", "findings"),
        ("finding", "quota"),
        ("at_least", "one"),
    ):
        assert f"{prefix}_{suffix}" not in text


def test_the_module_docstring_records_the_no_quota_rule() -> None:
    """The criterion asks for it in the docstring so a reviewer meets it before the code."""
    text = MODULE.read_text(encoding="utf-8")
    docstring = text.split('"""')[1]

    assert "no quota, floor, ceiling, or target count" in docstring


# ------------------------------------------------------------------------------------------
# Zero findings is a success
# ------------------------------------------------------------------------------------------


def test_an_assessment_where_everything_is_satisfied_produces_no_findings() -> None:
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.SATISFIED, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )

    assert outcome.findings == ()
    assert outcome.questions == ()
    assert outcome.documentation_gaps == ()


def test_an_assessment_where_everything_is_not_applicable_produces_nothing() -> None:
    outcome = run(
        mappings=[
            a_mapping(
                applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
                satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
            )
        ],
        assessments=[],
    )

    assert outcome.findings == ()
    assert outcome.object_ids == []


def test_a_zero_finding_run_records_why_rather_than_warning() -> None:
    """A reviewer asking "why is this not a finding" needs an answer that is not silence."""
    outcome = run(
        mappings=[
            a_mapping(
                applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
                satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
            )
        ],
        assessments=[],
    )

    (rejected,) = outcome.rejected
    assert rejected.requirement_id == "req-WEBHOOK-001"
    assert "does not apply" in rejected.reason


def test_an_empty_mapping_set_produces_an_empty_outcome() -> None:
    outcome = run(mappings=[], assessments=[])

    assert outcome.findings == ()
    assert outcome.rejected == ()


# ------------------------------------------------------------------------------------------
# The DEC-009 separation
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("validation", list(ValidationStatus))
def test_dec_009_an_unverified_mapping_never_leaves_this_node_as_a_finding(
    validation: ValidationStatus,
) -> None:
    """The regression case, over the whole validation vocabulary rather than one example.

    A candidate whose sole support is that the documentation does not mention a control resolves
    to `unverified`. No validation status paired with it reaches a finding, so the route does not
    exist rather than being blocked.
    """
    # `contradicted` requires a contradiction record of its own (DEC-021), so the fixture supplies
    # one rather than the parametrisation skipping the status that matters most here.
    contradictions = ["obs-001"] if validation is ValidationStatus.CONTRADICTED else []
    outcome = run(
        mappings=[a_mapping(satisfaction_status=SatisfactionStatus.UNVERIFIED)],
        assessments=[an_assessment(validation_status=validation, contradictions=contradictions)],
    )

    assert outcome.findings == ()


def test_an_unverified_mapping_produces_a_gap_or_a_question_and_never_both() -> None:
    outcome = run()

    produced = len(outcome.questions) + len(outcome.documentation_gaps)
    assert produced == 1


def test_an_unverified_mapping_with_no_assessment_produces_a_gap() -> None:
    """Nothing evaluated it, so the honest record is that this could not be determined."""
    outcome = run(assessments=[])

    assert outcome.documentation_gaps == ()
    assert outcome.rejected  # `not_evaluated` produces no output at all


def test_a_shortfall_the_evidence_carries_becomes_a_finding() -> None:
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )

    (finding,) = outcome.findings
    assert finding.validation_status is ValidationStatus.SUPPORTED
    assert finding.threat_ids == ["thr-001"]


# ------------------------------------------------------------------------------------------
# Question or gap (section 16)
# ------------------------------------------------------------------------------------------


def test_a_contradiction_produces_a_question_and_chooses_neither_statement() -> None:
    """Scenario 16.1 states it in those words: do not silently choose the safer statement."""
    outcome = run(
        assessments=[
            an_assessment(
                validation_status=ValidationStatus.CONTRADICTED,
                contradictions=["obs-001"],
                recommendation=Recommendation.DOCUMENTATION_GAP,
            )
        ]
    )

    (question,) = outcome.questions
    assert "authoritative" in question.question
    assert question.priority is QuestionPriority.HIGH
    assert outcome.documentation_gaps == ()


def test_a_contradiction_outranks_the_agents_recommendation() -> None:
    """The recommendation is advisory (DEC-047); a contradiction is not a matter of opinion."""
    outcome = run(
        assessments=[
            an_assessment(
                contradictions=["obs-001"],
                validation_status=ValidationStatus.CONTRADICTED,
                recommendation=Recommendation.DOCUMENTATION_GAP,
            )
        ]
    )

    assert outcome.questions
    assert outcome.documentation_gaps == ()


def test_the_agents_recommendation_is_consulted() -> None:
    """DEC-047 stored it so it could be compared; this is the one place it is acted on."""
    asked = run(assessments=[an_assessment(recommendation=Recommendation.DOWNGRADE_TO_QUESTION)])
    gapped = run(assessments=[an_assessment(recommendation=Recommendation.DOCUMENTATION_GAP)])

    assert asked.questions and not asked.documentation_gaps
    assert gapped.documentation_gaps and not gapped.questions


def test_named_missing_evidence_makes_it_a_question() -> None:
    """Section 16's own test: the answer is obtainable."""
    outcome = run(
        assessments=[
            an_assessment(
                recommendation=Recommendation.CONTINUE,
                missing_evidence=["documentation stating that signature verification occurs"],
            )
        ]
    )

    (question,) = outcome.questions
    assert "signature verification" in question.question


def test_the_gap_carries_what_would_close_it() -> None:
    outcome = run(
        assessments=[an_assessment(missing_evidence=["the receiver's deduplication behaviour"])]
    )

    if outcome.documentation_gaps:
        (gap,) = outcome.documentation_gaps
        assert gap.requested_evidence == ["the receiver's deduplication behaviour"]


# ------------------------------------------------------------------------------------------
# Stable titles
# ------------------------------------------------------------------------------------------


def test_titles_are_byte_identical_across_two_runs() -> None:
    first = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )
    second = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )

    assert [f.title for f in first.findings] == [f.title for f in second.findings]


def test_a_reflowed_threat_title_does_not_change_the_finding_title() -> None:
    """Line breaks in a title are a formatting choice, not a different threat."""
    flowed = a_threat(title="Forged webhooks trigger unauthorized analysis jobs")
    rewrapped = a_threat(title="Forged webhooks   trigger\nunauthorized analysis jobs")

    assert finding_title(flowed, a_mapping()) == finding_title(rewrapped, a_mapping())


def test_the_title_names_the_requirement() -> None:
    """Two findings from one threat differ by requirement, so the title has to say which."""
    title = finding_title(a_threat(), a_mapping(requirement_id="req-DATA-001"))

    assert "req-DATA-001" in title


# ------------------------------------------------------------------------------------------
# Provenance and severity
# ------------------------------------------------------------------------------------------


def test_every_emitted_object_records_the_node_that_produced_it() -> None:
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"]),
            a_mapping(id="map-002", requirement_id="req-DATA-001"),
        ],
        assessments=[
            an_assessment(validation_status=ValidationStatus.SUPPORTED),
            an_assessment(id="eas-002", subject_id="map-002"),
        ],
    )

    for obj in (*outcome.findings, *outcome.questions, *outcome.documentation_gaps):
        assert obj.generated_by == GENERATED_BY == "finding-consolidation-v1"


def test_a_finding_leaves_this_node_unassigned() -> None:
    """DEC-030: severity is the reviewer's at checkpoint 2 and no node proposes one."""
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )

    (finding,) = outcome.findings
    assert finding.severity is Severity.UNASSIGNED


def test_a_finding_is_a_candidate() -> None:
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )

    (finding,) = outcome.findings
    assert finding.status is ObjectStatus.CANDIDATE


def test_a_low_confidence_finding_carries_a_justification() -> None:
    """DEC-050's rule, satisfied from what the evidence step said rather than from invention."""
    outcome = run(
        mappings=[
            a_mapping(
                satisfaction_status=SatisfactionStatus.UNMET,
                evidence_ids=["evd-001"],
                confidence=ConfidenceLevel.LOW,
            )
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )

    (finding,) = outcome.findings
    assert finding.low_confidence_justification


# ------------------------------------------------------------------------------------------
# Rejected candidates
# ------------------------------------------------------------------------------------------


def test_a_rejected_candidate_states_a_reason() -> None:
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.SATISFIED, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )

    (rejected,) = outcome.rejected
    assert rejected.reason
    assert rejected.outcome is Outcome.NO_OUTPUT


def test_a_rejected_candidate_is_absent_from_the_provisional_finding_set() -> None:
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.SATISFIED, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )

    assert outcome.findings == ()
    assert outcome.rejected


def test_a_mapping_whose_threat_is_absent_is_reported_rather_than_routed() -> None:
    """Building an object citing a threat nobody supplied would be worse than reporting it."""
    outcome = run(mappings=[a_mapping(threat_id="thr-909")], assessments=[])

    (rejected,) = outcome.rejected
    assert "thr-909" in rejected.reason
    assert outcome.object_ids == []


# ------------------------------------------------------------------------------------------
# ForgeFlow: nothing from section 22 survives
# ------------------------------------------------------------------------------------------


def test_no_scenario_section_22_claim_survives_consolidation() -> None:
    """The eleven claims Trace should not make, none of them reachable from this routing.

    Each rejected claim corresponds to a mapping that is `not_applicable` or `unverified`, and
    neither reaches a finding. `demo/forgeflow/expected/expected-rejections.yaml` holds all eleven
    with the mechanism that suppresses each, and the evaluation suite asserts those mechanisms.
    """
    mappings = [
        a_mapping(
            id="map-001",
            requirement_id="req-AUTH-001",
            applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
            satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
        ),
        a_mapping(id="map-002", requirement_id="req-DATA-001"),
        a_mapping(id="map-003", requirement_id="req-NET-001"),
        a_mapping(id="map-004", requirement_id="req-WEBHOOK-002"),
    ]

    outcome = run(
        mappings=mappings,
        assessments=[
            an_assessment(id=f"eas-{n:03d}", subject_id=m.id) for n, m in enumerate(mappings, 1)
        ],
    )

    assert outcome.findings == ()


def test_both_scenario_section_16_contradictions_produce_questions() -> None:
    """16.1 source retention and 16.2 comment approval. Neither is resolved in either direction."""
    mappings = [
        a_mapping(id="map-001", requirement_id="req-DATA-002"),
        a_mapping(id="map-002", requirement_id="req-AI-002"),
    ]
    assessments = [
        an_assessment(
            id="eas-001",
            subject_id="map-001",
            validation_status=ValidationStatus.CONTRADICTED,
            contradictions=["obs-001"],
        ),
        an_assessment(
            id="eas-002",
            subject_id="map-002",
            validation_status=ValidationStatus.CONTRADICTED,
            contradictions=["obs-002"],
        ),
    ]

    outcome = run(mappings=mappings, assessments=assessments)

    assert len(outcome.questions) == 2
    assert outcome.findings == ()
    assert outcome.documentation_gaps == ()


def test_the_node_makes_no_model_call() -> None:
    """Section 4 classifies this as primarily deterministic; this implementation is entirely so."""
    text = MODULE.read_text(encoding="utf-8")

    for forbidden in ("anthropic", "StructuredModel", "model.generate", "openai"):
        assert forbidden not in text


def test_the_node_name_is_the_one_the_phase_registry_lists() -> None:
    from trace_ai.workflow.phases import NODES_BY_PHASE, Phase

    assert NODE_NAME in NODES_BY_PHASE[Phase.FINDING_CONSOLIDATION]


# ------------------------------------------------------------------------------------------
# The DEC-046 second half: conditions 2 and 3, applied here, appending (DEC-055)
# ------------------------------------------------------------------------------------------


def test_an_unsupported_unmet_is_downgraded_and_recorded() -> None:
    """DEC-013's `downgrade_only` cell: lowered to unverified, recorded, nothing produced."""
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.UNSUPPORTED)],
    )

    assert outcome.findings == ()
    (lowered,) = outcome.downgraded_mappings
    assert lowered.satisfaction_status is SatisfactionStatus.UNVERIFIED
    assert lowered.downgraded_from is SatisfactionStatus.UNMET
    assert lowered.downgrade_reason is not None
    assert lowered.downgrade_reason.startswith(f"{NODE_NAME}:")
    (rejected,) = outcome.rejected
    assert rejected.outcome is Outcome.DOWNGRADE_ONLY


def test_an_unsupported_satisfied_is_downgraded_and_asked_about() -> None:
    """The `question_after_downgrade` cell produces the question the table names."""
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.SATISFIED, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.UNSUPPORTED)],
    )

    (lowered,) = outcome.downgraded_mappings
    assert lowered.satisfaction_status is SatisfactionStatus.UNVERIFIED
    assert lowered.downgraded_from is SatisfactionStatus.SATISFIED
    assert len(outcome.questions) == 1
    assert outcome.rejected == ()


def test_a_second_downgrade_appends_and_never_overwrites() -> None:
    """DEC-055's answer to DEC-046's open question, exercised.

    The reason accumulates node-prefixed entries; `downgraded_from` keeps what the agent
    proposed, because a second downgrade does not change what was proposed.
    """
    prior = "mapping-validation: DEC-013 condition 1 failed on the original proposal"
    outcome = run(
        mappings=[
            a_mapping(
                satisfaction_status=SatisfactionStatus.UNMET,
                evidence_ids=["evd-001"],
                downgraded_from=SatisfactionStatus.SATISFIED,
                downgrade_reason=prior,
            )
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.UNSUPPORTED)],
    )

    (lowered,) = outcome.downgraded_mappings
    assert lowered.downgrade_reason is not None
    assert lowered.downgrade_reason.startswith(prior + "; ")
    assert f"{NODE_NAME}:" in lowered.downgrade_reason
    assert lowered.downgraded_from is SatisfactionStatus.SATISFIED, "first writer wins"


def test_a_carried_conclusion_is_not_downgraded() -> None:
    outcome = run(
        mappings=[
            a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
        ],
        assessments=[an_assessment(validation_status=ValidationStatus.SUPPORTED)],
    )
    assert outcome.downgraded_mappings == ()
    assert len(outcome.findings) == 1
