"""Tests for `SystemContext`: the baseline, its key, its approval, and its integrity check.

The field set is held to `data-model.md` section 9 by the conformance guard. Three properties are
asserted here because they are decisions rather than shapes.

**The key is `(assessment_id, version)`.** Section 9 gives this object no `id` and no `status`,
alone among the context objects, and the reason is that it is a sequence of revisions rather than a
thing with a name.

**Approval is data.** `approved_at` and `approved_by` are what make the DEC-005 checkpoint visible
in the record rather than only in the code path that reached it, and `is_approved` reads them and
nothing else.

**A successor cannot inherit an approval.** `next_version` clears both fields, because a revision
the reviewer has not seen is not one the reviewer approved.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from trace_ai.domain.actor import Actor
from trace_ai.domain.asset import Asset
from trace_ai.domain.base import DomainModel
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.data_flow import DataFlow, FlowDirection
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, SourceOrigin
from trace_ai.domain.system_context import FIRST_VERSION, SystemContext
from trace_ai.domain.trust_boundary import TrustBoundary

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
ASSESSMENT = "asm-001"


def context(**changes: Any) -> SystemContext:
    return SystemContext.model_validate(
        {
            "assessment_id": ASSESSMENT,
            "system_name": "ForgeFlow",
            "context_claim_ids": ["ctx-001"],
            "component_ids": ["cmp-001", "cmp-002"],
            "asset_ids": ["ast-001"],
            "actor_ids": ["act-001"],
            "data_flow_ids": ["df-001"],
            "trust_boundary_ids": ["tb-001"],
            "version": FIRST_VERSION,
            **changes,
        }
    )


def population(**changes: Any) -> list[DomainModel]:
    """The objects a complete, consistent context refers to."""
    flow_fields: dict[str, Any] = {
        "id": "df-001",
        "assessment_id": ASSESSMENT,
        "name": "Webhook delivery",
        "source_component_id": "cmp-001",
        "destination_component_id": "cmp-002",
        "direction": FlowDirection.ONE_WAY,
        "crosses_trust_boundary_ids": ["tb-001"],
        "status": ObjectStatus.CANDIDATE,
        **changes,
    }
    return [
        ContextClaim.model_validate(
            {
                "id": "ctx-001",
                "assessment_id": ASSESSMENT,
                "subject_type": "system",
                "predicate": "deployment_model",
                "value": "SaaS",
                "status": ClaimStatus.DOCUMENTED,
                "confidence": ConfidenceLevel.HIGH,
                "evidence_ids": ["evd-001"],
                "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
                "created_at": NOW,
                "updated_at": NOW,
            }
        ),
        Component.model_validate(
            {
                "id": "cmp-001",
                "assessment_id": ASSESSMENT,
                "name": "GitHub",
                "component_type": "repository_provider",
                "status": ObjectStatus.CANDIDATE,
            }
        ),
        Component.model_validate(
            {
                "id": "cmp-002",
                "assessment_id": ASSESSMENT,
                "name": "Webhook Receiver",
                "component_type": "service",
                "status": ObjectStatus.CANDIDATE,
            }
        ),
        Asset.model_validate(
            {
                "id": "ast-001",
                "assessment_id": ASSESSMENT,
                "name": "Customer Source Code",
                "asset_type": "source_code",
                "status": ObjectStatus.CANDIDATE,
            }
        ),
        Actor.model_validate(
            {
                "id": "act-001",
                "assessment_id": ASSESSMENT,
                "name": "Developer",
                "actor_type": "developer",
            }
        ),
        DataFlow.model_validate(flow_fields),
        TrustBoundary.model_validate(
            {
                "id": "tb-001",
                "assessment_id": ASSESSMENT,
                "name": "GitHub Boundary",
                "boundary_type": "organization_to_third_party",
                "status": ObjectStatus.CANDIDATE,
            }
        ),
    ]


# --------------------------------------------------------------------------------------------
# Identity and versioning
# --------------------------------------------------------------------------------------------


def test_the_object_has_no_identifier_and_no_status() -> None:
    """Alone among the context objects. It is keyed by `(assessment_id, version)`, which DEC-034
    states from the identifier side: the scheme governs objects addressed by identifier, and this
    one is addressed by its position in a sequence."""
    assert "id" not in SystemContext.model_fields
    assert "status" not in SystemContext.model_fields
    assert {"assessment_id", "version"} <= set(SystemContext.model_fields)


def test_the_first_context_is_version_one() -> None:
    assert context().version == FIRST_VERSION == 1


def test_version_zero_is_not_a_context() -> None:
    """A context that has not been extracted does not exist, rather than existing emptily."""
    with pytest.raises(ValueError, match="version"):
        context(version=0)


def test_a_successor_increments_and_keeps_the_content() -> None:
    successor = context().next_version()
    assert successor.version == 2
    assert successor.component_ids == ["cmp-001", "cmp-002"]
    assert successor.system_name == "ForgeFlow"


def test_a_successor_cannot_inherit_an_approval() -> None:
    """A revision the reviewer has not seen is not a revision the reviewer approved. One
    implementation, so clearing this cannot be forgotten at a call site."""
    approved = context(approved_at=NOW, approved_by="reviewer@example.com")
    assert approved.is_approved

    successor = approved.next_version()
    assert successor.approved_at is None
    assert successor.approved_by is None
    assert not successor.is_approved


# --------------------------------------------------------------------------------------------
# Approval is data
# --------------------------------------------------------------------------------------------


def test_an_unapproved_context_is_not_approved() -> None:
    assert not context().is_approved


@pytest.mark.parametrize(
    "half",
    [{"approved_at": NOW}, {"approved_by": "reviewer@example.com"}],
)
def test_half_an_approval_is_not_an_approval(half: dict[str, Any]) -> None:
    """A timestamp with no reviewer records that an approval happened and not who made it, which is
    exactly what DEC-005's checkpoint exists to capture."""
    assert not context(**half).is_approved


def test_is_approved_is_not_a_field() -> None:
    """Derived from the record, so it cannot disagree with it — and so the conformance guard, which
    compares fields against section 9, does not see an invented one."""
    assert "is_approved" not in SystemContext.model_fields


# --------------------------------------------------------------------------------------------
# Referential integrity
# --------------------------------------------------------------------------------------------


def test_a_consistent_context_reports_nothing() -> None:
    assert context().validate_against(population()) == []


def test_every_dangling_identifier_is_reported_not_just_the_first() -> None:
    """A reviewer fixing a context wants the whole list. Raising on the first mistake turns one
    review pass into as many passes as there are mistakes."""
    problems = context(
        component_ids=["cmp-001", "cmp-404", "cmp-405"],
        asset_ids=["ast-404"],
    ).validate_against(population())

    assert len(problems) == 4  # two components, one asset, and the flow's unlisted destination
    assert any("cmp-404" in problem for problem in problems)
    assert any("cmp-405" in problem for problem in problems)
    assert any("ast-404" in problem for problem in problems)


def test_a_dangling_identifier_names_its_list_and_the_type_it_should_have_been() -> None:
    problems = context(actor_ids=["act-404"]).validate_against(population())
    assert problems == ["actor_ids: act-404 does not resolve to a Actor"]


def test_an_object_from_another_assessment_is_reported() -> None:
    """The assessment-data boundary in `current-architecture.md` section 12, failing quietly: the
    identifier resolves, the object is real, and it belongs to somebody else's assessment."""
    objects = population()
    objects[1] = Component.model_validate(
        {
            "id": "cmp-001",
            "assessment_id": "asm-002",
            "name": "Someone else's GitHub",
            "component_type": "repository_provider",
            "status": ObjectStatus.CANDIDATE,
        }
    )
    problems = context().validate_against(objects)
    assert any("belongs to assessment asm-002" in problem for problem in problems)


def test_a_flow_whose_source_component_is_unlisted_is_reported() -> None:
    """The flow is real and its endpoint is real; what is missing is the reviewer having approved
    that component as part of this context."""
    problems = context(component_ids=["cmp-002"]).validate_against(population())
    assert any(
        "source_component_id cmp-001 is not in component_ids" in problem for problem in problems
    )


def test_a_flow_crossing_an_unlisted_boundary_is_reported() -> None:
    problems = context(trust_boundary_ids=[]).validate_against(population())
    assert any(
        "crosses trust boundary tb-001, which is not in trust_boundary_ids" in problem
        for problem in problems
    )


def test_a_flow_that_does_not_resolve_is_reported_once() -> None:
    """Reported as dangling, and not again as a flow with unlisted endpoints — one mistake should
    produce one message."""
    problems = context(data_flow_ids=["df-404"]).validate_against(population())
    assert problems == ["data_flow_ids: df-404 does not resolve to a DataFlow"]


def test_an_empty_context_validates_against_nothing() -> None:
    """A context extracted from documents that yielded no components is empty rather than invalid.
    Whether it is useful is a reviewer's judgment at checkpoint 1."""
    empty = SystemContext.model_validate(
        {
            "assessment_id": ASSESSMENT,
            "system_name": "ForgeFlow",
            "context_claim_ids": [],
            "component_ids": [],
            "asset_ids": [],
            "actor_ids": [],
            "data_flow_ids": [],
            "trust_boundary_ids": [],
            "version": FIRST_VERSION,
        }
    )
    assert empty.validate_against([]) == []


def test_the_identifier_lists_must_be_stated_even_when_empty() -> None:
    """Section 9 marks all six `Required: Yes`. An absent list and an empty list are different
    claims about an extraction, and only one of them is something a reviewer can approve."""
    payload = context().model_dump()
    del payload["data_flow_ids"]
    with pytest.raises(ValueError, match="data_flow_ids"):
        SystemContext.model_validate(payload)


# --------------------------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------------------------


def test_list_ordering_survives_a_json_round_trip() -> None:
    """The lists are ordered as the extractor produced them, and a reviewer reading a diff between
    two revisions should see content changes rather than reordering."""
    original = context(component_ids=["cmp-003", "cmp-001", "cmp-002"])
    restored = SystemContext.model_validate_json(original.model_dump_json())
    assert restored.component_ids == ["cmp-003", "cmp-001", "cmp-002"]
    assert restored == original
