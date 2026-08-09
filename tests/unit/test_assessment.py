"""Tests for `Assessment` and `AssessmentConfiguration`.

Field names and required-ness are checked by `test_data_model_conformance.py`, which reads
`data-model.md` sections 5 and 6 directly. This file covers what the document cannot: the
invariants, the types the conformance guard deliberately does not compare, and one absence.

**The absence is the most important test here.** `AssessmentConfiguration` has no
`require_context_review` and no `require_finding_review`. Earlier versions of section 6 declared
both; DEC-012 removed them and DEC-005 makes the checkpoints structural. A field here would be the
switch that defeats that, whatever it defaulted to -- so the test asserts both names are refused,
and `extra="forbid"` is what makes the refusal real rather than a convention. Issue #49.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trace_ai.domain.assessment import (
    ARCHITECTURE_VERSION,
    DATA_MODEL_VERSION,
    DEFAULT_MAXIMUM_RETRIES_PER_NODE,
    WORKFLOW_VERSION,
    Assessment,
    AssessmentConfiguration,
    EvidenceThreshold,
    default_configuration,
    new_assessment,
)
from trace_ai.domain.base import now
from trace_ai.domain.enums import ObjectStatus


def a_configuration(**overrides: object) -> AssessmentConfiguration:
    return default_configuration("primary-development", "stride-scenario-based", **overrides)


# ------------------------------------------------------------------------------------------
# The checkpoints are not configurable
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["require_context_review", "require_finding_review"])
def test_a_checkpoint_setting_is_refused(field: str) -> None:
    """DEC-005 makes the checkpoints structural; DEC-012 removed these two fields.

    They are workflow-graph nodes rather than runtime conditionals, so no configuration value
    advances the pipeline past an unapproved one. Reintroducing either field would be the switch
    that defeats DEC-005 regardless of what it defaulted to, and `extra="forbid"` is what turns
    that from a convention into a `ValidationError`.
    """
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AssessmentConfiguration.model_validate(
            {
                "model_profile": "primary-development",
                "threat_methodology": "stride-scenario-based",
                "maximum_retries_per_node": 2,
                "retain_debug_artifacts": False,
                "enable_external_tracing": False,
                "evidence_threshold": "direct-or-confirmed",
                field: False,
            }
        )


def test_no_field_name_mentions_a_checkpoint_or_a_review() -> None:
    """A rename would pass the test above. This catches `skip_review`, `checkpoints_enabled`."""
    suspicious = [
        name
        for name in AssessmentConfiguration.model_fields
        if any(word in name for word in ("review", "checkpoint", "approval", "human"))
    ]
    assert not suspicious, f"{suspicious} looks like a checkpoint switch; see DEC-005 and DEC-012"


# ------------------------------------------------------------------------------------------
# AssessmentConfiguration
# ------------------------------------------------------------------------------------------


def test_the_documented_example_constructs_as_written() -> None:
    """Section 6's example, verbatim."""
    configuration = AssessmentConfiguration.model_validate(
        {
            "model_profile": "primary-development",
            "threat_methodology": "stride-scenario-based",
            "maximum_model_calls": 40,
            "maximum_cost": "8.00",
            "maximum_retries_per_node": 2,
            "retain_debug_artifacts": True,
            "enable_external_tracing": False,
            "evidence_threshold": "direct-or-confirmed",
        }
    )
    assert configuration.maximum_cost == Decimal("8.00")
    assert configuration.evidence_threshold is EvidenceThreshold.DIRECT_OR_CONFIRMED


def test_maximum_cost_is_decimal_and_exact() -> None:
    """A cost limit compared through binary floating point is wrong where it matters.

    `8.00` is not representable as a float, so a run costing exactly the limit would halt or not
    depending on rounding nobody chose. Section 6 types it `decimal` and section 27 types
    `estimated_cost` the same way.
    """
    configuration = a_configuration(maximum_cost=Decimal("5.10"))
    assert isinstance(configuration.maximum_cost, Decimal)
    assert configuration.maximum_cost == Decimal("5.10")
    assert str(configuration.maximum_cost) == "5.10", "the scale is preserved, not normalized"


def test_maximum_cost_does_not_pass_through_float() -> None:
    """Three tenths added three times is the classic demonstration; Decimal must not do it."""
    configuration = a_configuration(maximum_cost=Decimal("0.30"))
    total = configuration.maximum_cost
    assert total is not None
    assert total * 3 == Decimal("0.90")


def test_a_float_cost_does_not_arrive_as_its_binary_expansion() -> None:
    """The concrete difference between `Decimal` and `float` at this field.

    `Decimal(0.1)` -- constructed from the float -- is 0.1000000000000000055511151231257827. A
    limit carrying that value compares wrong against a total computed any other way.
    """
    configuration = a_configuration(maximum_cost=0.1)
    assert configuration.maximum_cost == Decimal("0.1")
    # `from_float` rather than `Decimal(0.1)`: ruff flags the latter, for this reason.
    assert configuration.maximum_cost != Decimal.from_float(0.1)


def test_a_negative_cost_is_rejected() -> None:
    with pytest.raises(ValidationError):
        a_configuration(maximum_cost=Decimal("-1"))


def test_a_zero_call_limit_is_rejected() -> None:
    """A limit of zero halts before the first call, which is a misconfiguration not a policy."""
    with pytest.raises(ValidationError):
        a_configuration(maximum_model_calls=0)


def test_the_optional_limits_default_to_absent() -> None:
    configuration = a_configuration()
    assert configuration.maximum_model_calls is None
    assert configuration.maximum_cost is None


def test_evidence_threshold_accepts_only_the_two_dec_013_values() -> None:
    assert {member.value for member in EvidenceThreshold} == {"direct-or-confirmed", "permissive"}
    with pytest.raises(ValidationError):
        a_configuration(evidence_threshold="lenient")


def test_the_default_configuration_matches_the_corpus() -> None:
    """The defaults live in a factory, not on the fields, because section 6 marks them required."""
    configuration = default_configuration("primary-development", "stride-scenario-based")
    assert configuration.maximum_retries_per_node == DEFAULT_MAXIMUM_RETRIES_PER_NODE == 2
    assert configuration.evidence_threshold is EvidenceThreshold.DIRECT_OR_CONFIRMED
    assert configuration.enable_external_tracing is False
    assert configuration.retain_debug_artifacts is False


def test_external_tracing_is_off_by_default() -> None:
    """Section 5.17: sending prompt content and source data outward is a decision, not a default."""
    assert default_configuration("p", "t").enable_external_tracing is False


def test_a_required_field_must_be_supplied() -> None:
    """Section 6 marks these required, so the model does not fill them in."""
    with pytest.raises(ValidationError):
        AssessmentConfiguration.model_validate({"model_profile": "p", "threat_methodology": "t"})


def test_the_configuration_is_immutable() -> None:
    with pytest.raises(ValidationError, match="frozen"):
        a_configuration().maximum_retries_per_node = 5  # type: ignore[misc]


# ------------------------------------------------------------------------------------------
# Assessment
# ------------------------------------------------------------------------------------------


def test_the_documented_example_assessment_constructs() -> None:
    """Section 5's example: `asm-001`, `pending_review`, version `0.1`, three tags."""
    assessment = new_assessment(
        "asm-001",
        "ForgeFlow Security Review",
        a_configuration(),
        description="Review of a fictional GitHub-integrated developer platform",
        status=ObjectStatus.PENDING_REVIEW,
        requirements_catalog_version="0.1",
        active_workflow_run_id="run-001",
        tags=["demo", "isc2", "developer-platform"],
    )

    assert assessment.id == "asm-001"
    assert assessment.status is ObjectStatus.PENDING_REVIEW
    assert assessment.architecture_version == "0.1"
    assert assessment.tags == ["demo", "isc2", "developer-platform"]


def test_the_factory_stamps_the_build_versions() -> None:
    """So no assessment records a version somebody typed."""
    assessment = new_assessment("asm-001", "Review", a_configuration())
    assert assessment.architecture_version == ARCHITECTURE_VERSION
    assert assessment.data_model_version == DATA_MODEL_VERSION
    assert assessment.workflow_version == WORKFLOW_VERSION


def test_the_factory_does_not_mint_an_identifier() -> None:
    """DEC-018 assigns at insert, from the store's counter, not at construction.

    The identifier is a parameter for that reason: the caller allocates it inside the transaction
    that persists the object. A factory that minted one would be a second source of numbers.
    """
    import inspect

    parameters = list(inspect.signature(new_assessment).parameters)
    assert parameters[0] == "assessment_id"


def test_the_factory_starts_an_assessment_as_a_draft() -> None:
    assert new_assessment("asm-001", "Review", a_configuration()).status is ObjectStatus.DRAFT


def test_timestamps_are_timezone_aware() -> None:
    assessment = new_assessment("asm-001", "Review", a_configuration())
    assert assessment.created_at.tzinfo is not None
    assert assessment.updated_at.tzinfo is not None


def test_a_naive_timestamp_is_rejected() -> None:
    """A naive datetime serializes as though it were UTC without being marked as such."""
    with pytest.raises(ValidationError, match="timezone-aware"):
        new_assessment("asm-001", "Review", a_configuration(), created_at=datetime(2026, 8, 9))


def test_updated_at_may_not_precede_created_at() -> None:
    stamp = now()
    with pytest.raises(ValidationError, match="earlier than created_at"):
        new_assessment(
            "asm-001",
            "Review",
            a_configuration(),
            created_at=stamp,
            updated_at=stamp - timedelta(seconds=1),
        )


def test_updated_at_may_equal_created_at() -> None:
    """Which is what a freshly created assessment looks like."""
    assessment = new_assessment("asm-001", "Review", a_configuration())
    assert assessment.updated_at == assessment.created_at


def test_status_accepts_only_object_status_members() -> None:
    with pytest.raises(ValidationError):
        new_assessment("asm-001", "Review", a_configuration(), status="in_progress")


def test_the_identifier_must_name_an_assessment() -> None:
    """`thr-007` in an `Assessment.id` is the mistake the typed identifiers exist to catch."""
    with pytest.raises(ValidationError, match="names a Threat"):
        new_assessment("thr-007", "Review", a_configuration())


def test_the_workflow_run_identifier_must_name_a_workflow_run() -> None:
    with pytest.raises(ValidationError):
        new_assessment("asm-001", "Review", a_configuration(), active_workflow_run_id="exe-001")


def test_an_undocumented_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        new_assessment("asm-001", "Review", a_configuration(), severity_policy="strict")


def test_an_assessment_round_trips_through_json() -> None:
    """DEC-020 persists it as a JSON payload, so this is the storage path."""
    original = new_assessment(
        "asm-001",
        "ForgeFlow Security Review",
        a_configuration(maximum_cost=Decimal("8.00")),
        tags=["demo"],
    )
    restored = Assessment.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.configuration.maximum_cost == Decimal("8.00")
    assert restored.created_at.tzinfo is not None


def test_a_decimal_survives_the_json_round_trip_exactly() -> None:
    """The property `float` would quietly lose between write and read."""
    original = new_assessment("asm-001", "Review", a_configuration(maximum_cost=Decimal("0.10")))
    restored = Assessment.model_validate_json(original.model_dump_json())
    assert str(restored.configuration.maximum_cost) == "0.10"


def test_constructing_an_assessment_needs_no_environment() -> None:
    """No `.env`, no key, no network. The exit criterion is that the foundation runs without one."""
    import os

    saved = dict(os.environ)
    try:
        os.environ.clear()
        assert new_assessment("asm-001", "Review", a_configuration()).id == "asm-001"
    finally:
        os.environ.update(saved)


def test_the_assessment_is_immutable() -> None:
    assessment = new_assessment("asm-001", "Review", a_configuration())
    with pytest.raises(ValidationError, match="frozen"):
        assessment.name = "Renamed"  # type: ignore[misc]


def test_the_configuration_is_carried_by_value() -> None:
    """Section 5 nests the configuration rather than referencing it by identifier.

    So it has no identifier of its own, and is not separately persisted -- it travels inside the
    assessment's JSON payload.
    """
    assert "id" not in AssessmentConfiguration.model_fields
    assert Assessment.model_fields["configuration"].annotation is AssessmentConfiguration


def test_utc_timestamps_compare_across_offsets() -> None:
    """A stored assessment and a fresh one must order correctly regardless of local offset."""
    earlier = datetime(2026, 8, 9, 14, 0, tzinfo=UTC)
    assessment = new_assessment(
        "asm-001", "Review", a_configuration(), created_at=earlier, updated_at=now()
    )
    assert assessment.updated_at > assessment.created_at
