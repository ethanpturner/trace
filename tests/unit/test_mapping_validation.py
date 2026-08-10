"""The Mapping Validation node: catalog pinning, the downgrade, and what must read as clean.

`agent-design.md` section 13's ten responsibilities, with two of them carrying most of the weight.

**"Prevent unverified from silently becoming unmet."** The word doing the work is *silently*. The
downgrade itself is DEC-013's; DEC-046 is what makes it visible, and the tests here assert the
record and not only the status — a downgrade that changed a value and left no trace is exactly as
invisible to `evaluation-plan.md` section 8 as no downgrade at all.

**A run of nothing but `unverified` and `not_applicable` passes cleanly.** No error, no trigger, no
flag. `data-model.md` section 19 says a high proportion of `unverified` is the expected result of
assessing ordinary architecture documentation, and this is the test that stops a future warning
from teaching every reader to treat the expected outcome as a defect.

**Some checks are unreachable through the schema, and the tests say which.** `ControlMapping`
refuses a blank rationale and refuses an unevidenced `satisfied`, so those mappings cannot be
constructed. `model_construct` is used deliberately, and only there, to reach the node's second
line of defence. A test using it is a test about a payload that skipped construction — nothing
else in the file needs it, and its appearance is the signal.
"""

from __future__ import annotations

from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.control import Control, ControlType, ImplementationStatus
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, ValidationStatus
from trace_ai.domain.proposals.mapping import MAPPING_AGENT
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.domain.threat import Threat
from trace_ai.services.requirements.loader import LoadedCatalog, current_version, load_catalog
from trace_ai.workflow.errors import ErrorClass
from trace_ai.workflow.mapping_validation import (
    SECTION_12_TRIGGERS,
    UNMET_ON_UNRESOLVED_CONTRADICTION,
    UNMET_WITHOUT_ADDRESSING_FALSE_POSITIVES,
    UNMET_WITHOUT_EVIDENCE,
    apply_downgrades,
    validate_mappings,
)


@pytest.fixture(scope="module")
def catalog() -> LoadedCatalog:
    return load_catalog(current_version())


def a_threat(**changes: Any) -> Threat:
    payload: dict[str, Any] = {
        "id": "thr-001",
        "assessment_id": "asm-001",
        "title": "Forged webhooks trigger unauthorized analysis jobs",
        "description": "An attacker submits webhook requests the receiver acts on.",
        "methodology": "stride-scenario-based",
        "affected_component_ids": ["cmp-001"],
        "affected_asset_ids": ["ast-001"],
        "impact": "Unauthorized jobs",
        "confidence": ConfidenceLevel.MEDIUM,
        "status": ObjectStatus.APPROVED,
        "generated_by": "threat-analysis-v1",
        "created_at": now(),
    }
    payload.update(changes)
    return Threat.model_validate(payload)


def a_control(**changes: Any) -> Control:
    payload: dict[str, Any] = {
        "id": "ctl-001",
        "assessment_id": "asm-001",
        "name": "Managed database encryption at rest",
        "description": "The managed database platform encrypts stored data.",
        "control_type": ControlType.INHERITED,
        "provider_component_id": "cmp-002",
        "protected_asset_ids": ["ast-001"],
        "implementation_status": ImplementationStatus.IMPLEMENTED,
        "validation_status": ValidationStatus.NOT_EVALUATED,
        "evidence_ids": ["evd-001"],
        "generated_by": "context-extraction-v1",
        "created_at": now(),
        "status": ObjectStatus.APPROVED,
    }
    payload.update(changes)
    return Control.model_validate(payload)


def a_mapping(**changes: Any) -> ControlMapping:
    payload: dict[str, Any] = {
        "id": "map-001",
        "assessment_id": "asm-001",
        "threat_id": "thr-001",
        "requirement_id": "req-WEBHOOK-001",
        "applicability_status": ApplicabilityStatus.APPLICABLE,
        "applicability_reason": (
            "The system exposes an endpoint accepting events from an external platform, which is "
            "this requirement's first applicable condition."
        ),
        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
        "confidence": ConfidenceLevel.MEDIUM,
        "generated_by": MAPPING_AGENT,
        "reviewer_status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return ControlMapping.model_validate(payload)


def a_contradiction(**changes: Any) -> SourceObservation:
    payload: dict[str, Any] = {
        "id": "obs-001",
        "assessment_id": "asm-001",
        "kind": ObservationKind.CONTRADICTION,
        "summary": "Two documents disagree about whether webhook signatures are verified.",
        "evidence_ids": ["evd-001", "evd-002"],
        "status": ObjectStatus.CANDIDATE,
        "created_at": now(),
    }
    payload.update(changes)
    return SourceObservation.model_validate(payload)


def validate(catalog: LoadedCatalog, *mappings: ControlMapping, **changes: Any) -> Any:
    options: dict[str, Any] = {
        "catalog_version": catalog.version,
        "requirements": catalog.requirements,
        "threats": [a_threat()],
        **changes,
    }
    return validate_mappings(list(mappings) or [a_mapping()], **options)


# ------------------------------------------------------------------------------------------
# The node is deterministic
# ------------------------------------------------------------------------------------------


def test_the_node_makes_no_model_call_and_imports_no_provider_sdk() -> None:
    """Section 13 classifies this node as deterministic; the source is the evidence."""
    text = (PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "mapping_validation.py").read_text(
        encoding="utf-8"
    )

    for forbidden in ("anthropic", "StructuredModel", "model.generate", "openai"):
        assert forbidden not in text


# ------------------------------------------------------------------------------------------
# Catalog pinning
# ------------------------------------------------------------------------------------------


def test_a_requirement_absent_from_the_pinned_version_is_rejected(
    catalog: LoadedCatalog,
) -> None:
    outcome = validate(catalog, a_mapping(requirement_id="req-NOPE-999"))

    (error,) = [e for e in outcome.errors if e.field == "requirement_id"]
    assert "req-NOPE-999" in error.message
    assert catalog.version in error.message
    assert error.error_class is ErrorClass.MISSING_REQUIRED_RELATIONSHIP
    assert not outcome.valid


def test_a_requirement_from_a_different_catalog_version_is_rejected(
    catalog: LoadedCatalog,
) -> None:
    """Both versions are named: the text may have changed underneath the mapping's rationale."""
    stale = type(catalog.requirements[0]).model_validate(
        {**catalog.by_id()["req-WEBHOOK-001"].model_dump(), "catalog_version": "0.9"}
    )

    outcome = validate_mappings(
        [a_mapping()],
        catalog_version=catalog.version,
        requirements=[stale],
        threats=[a_threat()],
    )

    (error,) = [e for e in outcome.errors if e.field == "requirement_id"]
    assert "0.9" in error.message
    assert catalog.version in error.message


def test_the_pinned_version_is_passed_rather_than_read_from_disk(catalog: LoadedCatalog) -> None:
    """A `0.2/` appearing mid-run cannot change what an in-flight run is validated against."""
    import inspect

    signature = inspect.signature(validate_mappings)

    assert "catalog_version" in signature.parameters
    assert "requirements" in signature.parameters
    assert "root" not in signature.parameters


def test_a_mapping_naming_an_unknown_threat_is_rejected(catalog: LoadedCatalog) -> None:
    outcome = validate(catalog, a_mapping(threat_id="thr-909"))

    assert any("thr-909" in error.message for error in outcome.errors)


def test_a_mapping_naming_an_unknown_control_is_rejected(catalog: LoadedCatalog) -> None:
    outcome = validate(catalog, a_mapping(control_ids=["ctl-404"]), controls=[a_control()])

    (error,) = [e for e in outcome.errors if e.field == "control_ids"]
    assert "ctl-404" in error.message


def test_a_mapping_naming_a_known_control_passes(catalog: LoadedCatalog) -> None:
    outcome = validate(catalog, a_mapping(control_ids=["ctl-001"]), controls=[a_control()])

    assert not [e for e in outcome.errors if e.field == "control_ids"]


# ------------------------------------------------------------------------------------------
# The downgrade (DEC-013, DEC-046)
# ------------------------------------------------------------------------------------------


def test_an_unmet_resting_on_an_unresolved_contradiction_is_downgraded(
    catalog: LoadedCatalog,
) -> None:
    """DEC-013 condition 4, which is one of the two this node can check."""
    unmet = a_mapping(
        satisfaction_status=SatisfactionStatus.UNMET,
        evidence_ids=["evd-001"],
        suppressed_conclusion="that authenticity verification is absent",
        suppressed_by="documentation stating only that requests are validated, where the "
        "mechanism is unstated",
    )

    outcome = validate(catalog, unmet, observations=[a_contradiction()])

    (downgrade,) = outcome.downgrades
    assert downgrade.mapping_id == "map-001"
    assert downgrade.from_status is SatisfactionStatus.UNMET
    assert downgrade.to_status is SatisfactionStatus.UNVERIFIED
    assert downgrade.reason == UNMET_ON_UNRESOLVED_CONTRADICTION


def test_a_resolved_contradiction_does_not_downgrade(catalog: LoadedCatalog) -> None:
    """An approved observation is one a reviewer examined. That is what resolution means."""
    unmet = a_mapping(
        satisfaction_status=SatisfactionStatus.UNMET,
        evidence_ids=["evd-001"],
        suppressed_conclusion="that authenticity verification is absent",
        suppressed_by="documentation stating only that requests are validated, where the "
        "mechanism is unstated",
    )

    outcome = validate(catalog, unmet, observations=[a_contradiction(status=ObjectStatus.APPROVED)])

    assert not outcome.downgrades


def test_an_unmet_that_never_addressed_the_false_positives_is_downgraded(
    catalog: LoadedCatalog,
) -> None:
    """DEC-025's structural check: did the mapping address the field, not is it right."""
    unmet = a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])

    outcome = validate(catalog, unmet)

    (downgrade,) = outcome.downgrades
    assert downgrade.reason == UNMET_WITHOUT_ADDRESSING_FALSE_POSITIVES


def test_an_unmet_that_names_the_entry_survives(catalog: LoadedCatalog) -> None:
    entry = catalog.by_id()["req-WEBHOOK-001"].common_false_positives[0]
    unmet = a_mapping(
        satisfaction_status=SatisfactionStatus.UNMET,
        evidence_ids=["evd-001"],
        applicability_reason=(
            f"The requirement applies. The documentation describes the absence directly rather "
            f"than being silent, so the entry '{entry}' does not cover this case."
        ),
    )

    outcome = validate(catalog, unmet)

    assert not outcome.downgrades


def test_an_unmet_carrying_a_suppression_record_survives(catalog: LoadedCatalog) -> None:
    """`suppressed_by` is itself evidence that the field was consulted."""
    unmet = a_mapping(
        satisfaction_status=SatisfactionStatus.UNMET,
        evidence_ids=["evd-001"],
        suppressed_conclusion="that secret storage is undescribed",
        suppressed_by="absent description of secret storage where verification itself is "
        "documented",
    )

    outcome = validate(catalog, unmet)

    assert not outcome.downgrades


def test_an_unmet_with_no_evidence_is_downgraded(catalog: LoadedCatalog) -> None:
    """The schema refuses this first; the node is the second line (module docstring)."""
    unmet = ControlMapping.model_construct(
        **{
            **a_mapping().model_dump(),
            "satisfaction_status": SatisfactionStatus.UNMET,
            "evidence_ids": [],
        }
    )

    outcome = validate(catalog, unmet)

    (downgrade,) = outcome.downgrades
    assert downgrade.reason == UNMET_WITHOUT_EVIDENCE


def test_the_downgrade_is_recorded_on_the_mapping_and_not_only_applied(
    catalog: LoadedCatalog,
) -> None:
    """The assertion the issue asks for: the record exists, not only that the status changed."""
    unmet = a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
    outcome = validate(catalog, unmet)

    (applied,) = apply_downgrades([unmet], outcome)

    assert applied.satisfaction_status is SatisfactionStatus.UNVERIFIED
    assert applied.downgraded_from is SatisfactionStatus.UNMET
    assert applied.downgrade_reason == UNMET_WITHOUT_ADDRESSING_FALSE_POSITIVES


def test_applying_a_downgrade_builds_a_new_object_rather_than_mutating(
    catalog: LoadedCatalog,
) -> None:
    """`CLAUDE.md`: frozen objects, `model_validate`, never `model_copy`."""
    unmet = a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
    outcome = validate(catalog, unmet)

    (applied,) = apply_downgrades([unmet], outcome)

    assert unmet.satisfaction_status is SatisfactionStatus.UNMET
    assert applied is not unmet
    assert applied.id == unmet.id


def test_a_downgrade_keeps_the_cited_evidence(catalog: LoadedCatalog) -> None:
    """A reviewer disagreeing with the downgrade needs the passages the agent thought relevant."""
    unmet = a_mapping(satisfaction_status=SatisfactionStatus.UNMET, evidence_ids=["evd-001"])
    outcome = validate(catalog, unmet)

    (applied,) = apply_downgrades([unmet], outcome)

    assert applied.evidence_ids == ["evd-001"]


def test_mappings_with_no_downgrade_pass_through_unchanged(catalog: LoadedCatalog) -> None:
    first, second = a_mapping(), a_mapping(id="map-002", requirement_id="req-AUTH-001")

    applied = apply_downgrades([first, second], validate(catalog, first, second))

    assert applied == [first, second]


def test_a_downgrade_record_cannot_be_half_written() -> None:
    """DEC-046: the pair moves together, like DEC-025's."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="DEC-046"):
        ControlMapping.model_validate(
            {**a_mapping().model_dump(), "downgraded_from": SatisfactionStatus.UNMET}
        )


def test_a_downgrade_that_changed_nothing_is_refused() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="changed nothing"):
        ControlMapping.model_validate(
            {
                **a_mapping().model_dump(),
                "downgraded_from": SatisfactionStatus.UNVERIFIED,
                "downgrade_reason": "no",
            }
        )


def test_conditions_2_and_3_are_not_checked_here(catalog: LoadedCatalog) -> None:
    """DEC-046: both read `EvidenceAssessment`, which this phase runs before.

    The failure this pins is the tempting one: treating a missing assessment as a failed condition
    would downgrade every `unmet` in every run and look like a strict evidence rule.
    """
    entry = catalog.by_id()["req-WEBHOOK-001"].common_false_positives[0]
    unmet = a_mapping(
        satisfaction_status=SatisfactionStatus.UNMET,
        evidence_ids=["evd-001"],
        applicability_reason=f"The requirement applies and '{entry}' does not cover this case.",
    )

    outcome = validate(catalog, unmet)

    assert not outcome.downgrades


# ------------------------------------------------------------------------------------------
# Rationales, permitted states, and the schema's second line
# ------------------------------------------------------------------------------------------


def test_a_blank_applicability_reason_is_rejected(catalog: LoadedCatalog) -> None:
    """The schema refuses this first; the node is the second line (module docstring)."""
    blank = ControlMapping.model_construct(
        **{**a_mapping().model_dump(), "applicability_reason": "   "}
    )

    outcome = validate(catalog, blank)

    (error,) = [e for e in outcome.errors if e.field == "applicability_reason"]
    assert "blank" in error.message
    assert not outcome.valid


def test_an_unevidenced_satisfied_is_rejected(catalog: LoadedCatalog) -> None:
    unevidenced = ControlMapping.model_construct(
        **{
            **a_mapping().model_dump(),
            "satisfaction_status": SatisfactionStatus.SATISFIED,
            "evidence_ids": [],
        }
    )

    outcome = validate(catalog, unevidenced)

    (error,) = [e for e in outcome.errors if e.field == "evidence_ids"]
    assert "DEC-009" in error.message


def test_a_not_applicable_requirement_cannot_be_unmet(catalog: LoadedCatalog) -> None:
    """Section 12's "ignore non-applicability conditions" prohibition, from the other side."""
    contradictory = a_mapping(
        applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
        satisfaction_status=SatisfactionStatus.UNMET,
        evidence_ids=["evd-001"],
    )

    outcome = validate(catalog, contradictory)

    assert any(e.field == "satisfaction_status" for e in outcome.errors)


def test_a_not_applicable_requirement_may_be_not_applicable(catalog: LoadedCatalog) -> None:
    consistent = a_mapping(
        applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
        satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
    )

    outcome = validate(catalog, consistent)

    assert not outcome.errors


# ------------------------------------------------------------------------------------------
# Duplicates, conflicts, and discrimination
# ------------------------------------------------------------------------------------------


def test_duplicate_mappings_are_surfaced_and_not_deduplicated(catalog: LoadedCatalog) -> None:
    first = a_mapping()
    second = a_mapping(id="map-002")

    outcome = validate(catalog, first, second)

    (duplicate,) = outcome.duplicates
    assert duplicate.threat_id == "thr-001"
    assert duplicate.requirement_id == "req-WEBHOOK-001"
    assert duplicate.mapping_ids == ("map-001", "map-002")


def test_a_duplicate_does_not_block(catalog: LoadedCatalog) -> None:
    outcome = validate(catalog, a_mapping(), a_mapping(id="map-002"))

    assert outcome.valid


def test_conflicting_satisfaction_statuses_are_flagged(catalog: LoadedCatalog) -> None:
    first = a_mapping()
    second = a_mapping(
        id="map-002",
        satisfaction_status=SatisfactionStatus.SATISFIED,
        evidence_ids=["evd-001"],
    )

    outcome = validate(catalog, first, second)

    (conflict,) = outcome.conflicts
    assert conflict.mapping_ids == ("map-001", "map-002")
    assert conflict.statuses == ("satisfied", "unverified")


def test_two_mappings_agreeing_are_a_duplicate_and_not_a_conflict(
    catalog: LoadedCatalog,
) -> None:
    outcome = validate(catalog, a_mapping(), a_mapping(id="map-002"))

    assert outcome.duplicates
    assert not outcome.conflicts


def test_every_requirement_applicable_for_one_threat_is_flagged(
    catalog: LoadedCatalog,
) -> None:
    """Section 12's failure condition: applicability with no discrimination."""
    mappings = [
        a_mapping(id=f"map-{index:03d}", requirement_id=requirement)
        for index, requirement in enumerate(
            ["req-WEBHOOK-001", "req-AUTH-001", "req-DATA-001"], start=1
        )
    ]

    outcome = validate(catalog, *mappings)

    assert outcome.undiscriminated_threat_ids == ("thr-001",)


def test_one_not_applicable_among_them_clears_the_flag(catalog: LoadedCatalog) -> None:
    mappings = [
        a_mapping(),
        a_mapping(
            id="map-002",
            requirement_id="req-AUTH-001",
            applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
            satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
        ),
    ]

    outcome = validate(catalog, *mappings)

    assert not outcome.undiscriminated_threat_ids


def test_a_single_applicable_mapping_is_not_undiscriminated(catalog: LoadedCatalog) -> None:
    """One mapping for a whole catalog *is* discrimination: it declined the rest."""
    outcome = validate(catalog, a_mapping())

    assert not outcome.undiscriminated_threat_ids


# ------------------------------------------------------------------------------------------
# Suppressions survive (DEC-025)
# ------------------------------------------------------------------------------------------


def test_a_suppression_survives_validation(catalog: LoadedCatalog) -> None:
    entry = catalog.by_id()["req-WEBHOOK-001"].common_false_positives[0]
    suppressed = a_mapping(
        suppressed_conclusion="that authenticity verification is absent",
        suppressed_by=entry,
    )

    outcome = validate(catalog, suppressed)

    (suppression,) = outcome.suppressions
    assert suppression.mapping_id == "map-001"
    assert suppression.requirement_id == "req-WEBHOOK-001"
    assert suppression.entry == entry


def test_a_suppression_survives_a_downgrade_on_the_same_mapping(
    catalog: LoadedCatalog,
) -> None:
    suppressed = a_mapping(
        satisfaction_status=SatisfactionStatus.UNMET,
        evidence_ids=["evd-001"],
        suppressed_conclusion="that authenticity verification is absent",
        suppressed_by=catalog.by_id()["req-WEBHOOK-001"].common_false_positives[0],
    )
    outcome = validate(catalog, suppressed, observations=[a_contradiction()])

    (applied,) = apply_downgrades([suppressed], outcome)

    assert applied.suppressed_by
    assert applied.downgrade_reason
    assert outcome.suppressions


def test_a_mapping_without_a_suppression_produces_no_record(catalog: LoadedCatalog) -> None:
    outcome = validate(catalog, a_mapping())

    assert not outcome.suppressions


# ------------------------------------------------------------------------------------------
# Human-review triggers (agent-design.md section 12)
# ------------------------------------------------------------------------------------------


def test_contradictory_evidence_raises_the_first_trigger(catalog: LoadedCatalog) -> None:
    outcome = validate(
        catalog, a_mapping(evidence_ids=["evd-001"]), observations=[a_contradiction()]
    )

    names = [trigger.name for trigger in outcome.triggers]
    assert SECTION_12_TRIGGERS[0] in names


def test_an_undocumented_inherited_control_raises_the_scope_trigger(
    catalog: LoadedCatalog,
) -> None:
    """DEC-026: a platform control nothing establishes is a question, not an assertion."""
    claimed = a_control(
        implementation_status=ImplementationStatus.CLAIMED,
        evidence_ids=[],
    )

    outcome = validate(catalog, a_mapping(control_ids=["ctl-001"]), controls=[claimed])

    names = [trigger.name for trigger in outcome.triggers]
    assert SECTION_12_TRIGGERS[1] in names


def test_a_compensating_control_raises_the_business_judgment_trigger(
    catalog: LoadedCatalog,
) -> None:
    compensating = a_control(
        control_type=ControlType.COMPENSATING,
        implementation_status=ImplementationStatus.IMPLEMENTED,
    )

    outcome = validate(catalog, a_mapping(control_ids=["ctl-001"]), controls=[compensating])

    names = [trigger.name for trigger in outcome.triggers]
    assert SECTION_12_TRIGGERS[2] in names


@pytest.mark.parametrize(
    "status",
    [ApplicabilityStatus.UNKNOWN, ApplicabilityStatus.CONDITIONALLY_APPLICABLE],
)
def test_unsettled_applicability_raises_the_deployment_trigger(
    catalog: LoadedCatalog, status: ApplicabilityStatus
) -> None:
    outcome = validate(catalog, a_mapping(applicability_status=status))

    names = [trigger.name for trigger in outcome.triggers]
    assert SECTION_12_TRIGGERS[3] in names


def test_a_claimed_control_on_an_unverified_mapping_raises_the_platform_trigger(
    catalog: LoadedCatalog,
) -> None:
    claimed = a_control(
        control_type=ControlType.IMPLEMENTED,
        implementation_status=ImplementationStatus.CLAIMED,
        evidence_ids=[],
    )

    outcome = validate(catalog, a_mapping(control_ids=["ctl-001"]), controls=[claimed])

    names = [trigger.name for trigger in outcome.triggers]
    assert SECTION_12_TRIGGERS[4] in names


def test_every_section_12_trigger_is_named(catalog: LoadedCatalog) -> None:
    """Five triggers in the document, five constants, in the document's order."""
    assert len(SECTION_12_TRIGGERS) == 5
    assert len(set(SECTION_12_TRIGGERS)) == 5


# ------------------------------------------------------------------------------------------
# The expected shape of most assessments
# ------------------------------------------------------------------------------------------


def test_a_run_of_unverified_and_not_applicable_passes_cleanly(catalog: LoadedCatalog) -> None:
    """DEC-009's ordinary outcome, and it must not read as a defect (data-model.md section 19)."""
    mappings = [
        a_mapping(),
        a_mapping(
            id="map-002",
            requirement_id="req-AUTH-001",
            applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
            applicability_reason="ForgeFlow maintains no credential store of its own.",
            satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
        ),
        a_mapping(id="map-003", requirement_id="req-DATA-001"),
    ]

    outcome = validate(catalog, *mappings)

    assert outcome.valid
    assert outcome.clean
    assert not outcome.errors
    assert not outcome.triggers
    assert not outcome.downgrades
    assert not outcome.duplicates
    assert not outcome.conflicts
    assert not outcome.undiscriminated_threat_ids


def test_an_empty_mapping_set_passes_cleanly(catalog: LoadedCatalog) -> None:
    outcome = validate_mappings(
        [],
        catalog_version=catalog.version,
        requirements=catalog.requirements,
        threats=[a_threat()],
    )

    assert outcome.clean


def test_a_set_that_is_entirely_unverified_is_still_clean(catalog: LoadedCatalog) -> None:
    """A ratio rule here would be the mechanism by which the honest answer became a warning.

    Six requirements, every one applicable and every one unverified, with one `not_applicable`
    so the discrimination flag has no purchase. Under DEC-009 this is what most assessments
    against most documentation look like, and nothing here reports it.
    """
    identifiers = [requirement.id for requirement in catalog.requirements[:6]]
    mappings = [
        a_mapping(id=f"map-{index:03d}", requirement_id=identifier)
        for index, identifier in enumerate(identifiers, start=1)
    ]
    mappings.append(
        a_mapping(
            id="map-099",
            requirement_id=catalog.requirements[6].id,
            applicability_status=ApplicabilityStatus.NOT_APPLICABLE,
            satisfaction_status=SatisfactionStatus.NOT_APPLICABLE,
        )
    )

    outcome = validate(catalog, *mappings)

    assert outcome.clean
    assert all(
        mapping.satisfaction_status
        in {SatisfactionStatus.UNVERIFIED, SatisfactionStatus.NOT_APPLICABLE}
        for mapping in mappings
    )
