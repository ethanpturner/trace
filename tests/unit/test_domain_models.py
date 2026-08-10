"""Tests for the five context-baseline objects: Component, Actor, Asset, DataFlow, TrustBoundary.

Field sets and required flags are not asserted here. `tests/unit/test_data_model_conformance.py`
compares all five against `data-model.md` sections 11 through 15 in both directions, which is
stronger than a hand-written list and cannot drift from the document. What this file holds is the
behaviour the document asks for and a table cannot express.

Three properties carry most of the weight.

**Vocabularies are open and normalized** (DEC-036). The project's own benchmark uses six component
types the data model never lists, so a closed enum would reject the scenario Trace exists to assess.
What is refused is three spellings of one type, not an unfamiliar type.

**Unknown is said, not implied.** `DataFlow.encryption_in_transit` and `authentication` default to
the string `unknown` and refuse a boolean, and the optional exposure booleans mean "the
documentation does not say" when they are `None`. This is DEC-009 at field level: silence read as
`False` is an asserted weakness nobody evidenced.

**Models do not mint identifiers.** DEC-018 allocates at insert, from a store-held counter. Every
model here requires an identifier of its own object type, so a caller cannot construct an object
that quietly numbers itself and a threat identifier cannot land in a component's field.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.actor import KNOWN_ACTOR_TYPES, Actor
from trace_ai.domain.asset import KNOWN_ASSET_TYPES, Asset
from trace_ai.domain.component import KNOWN_COMPONENT_TYPES, Component
from trace_ai.domain.data_flow import DataFlow, FlowDirection
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.trust_boundary import KNOWN_BOUNDARY_TYPES, TrustBoundary
from trace_ai.domain.vocabulary import UNKNOWN, normalize_term

FIXTURE = PROJECT_ROOT / "demo" / "forgeflow" / "input" / "structured-system-input.yaml"

ASSESSMENT = "asm-001"


def component(**changes: Any) -> Component:
    return Component.model_validate(
        {
            "id": "cmp-001",
            "assessment_id": ASSESSMENT,
            "name": "Webhook Receiver",
            "component_type": "service",
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "status": ObjectStatus.CANDIDATE,
            **changes,
        }
    )


def actor(**changes: Any) -> Actor:
    return Actor.model_validate(
        {
            "id": "act-001",
            "assessment_id": ASSESSMENT,
            "name": "Repository Administrator",
            "actor_type": "administrator",
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            **changes,
        }
    )


def asset(**changes: Any) -> Asset:
    return Asset.model_validate(
        {
            "id": "ast-001",
            "assessment_id": ASSESSMENT,
            "name": "Customer Source Code",
            "asset_type": "source_code",
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "status": ObjectStatus.CANDIDATE,
            **changes,
        }
    )


def data_flow(**changes: Any) -> DataFlow:
    return DataFlow.model_validate(
        {
            "id": "df-001",
            "assessment_id": ASSESSMENT,
            "name": "Webhook delivery",
            "source_component_id": "cmp-001",
            "destination_component_id": "cmp-002",
            "direction": FlowDirection.ONE_WAY,
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "status": ObjectStatus.CANDIDATE,
            **changes,
        }
    )


def trust_boundary(**changes: Any) -> TrustBoundary:
    return TrustBoundary.model_validate(
        {
            "id": "tb-001",
            "assessment_id": ASSESSMENT,
            "name": "Public Internet",
            "boundary_type": "internet_to_application",
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "status": ObjectStatus.CANDIDATE,
            **changes,
        }
    )


BUILDERS = {
    "Component": component,
    "Actor": actor,
    "Asset": asset,
    "DataFlow": data_flow,
    "TrustBoundary": trust_boundary,
}


# --------------------------------------------------------------------------------------------
# Shape common to all five
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_each_object_constructs(name: str) -> None:
    assert isinstance(BUILDERS[name](), BaseModel)


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_each_object_is_frozen(name: str) -> None:
    """`DomainModel` freezes them; a reviewer edit builds a new instance (DEC-023)."""
    with pytest.raises(ValidationError):
        BUILDERS[name]().name = "renamed"  # type: ignore[attr-defined]


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_each_object_rejects_an_invented_field(name: str) -> None:
    """`extra="forbid"` is how an agent-proposed object carrying a made-up field fails."""
    with pytest.raises(ValidationError):
        BUILDERS[name](confidence_score=0.9)


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_no_object_mints_its_own_identifier(name: str) -> None:
    """DEC-018 allocates at insert. A model with a default identifier would be a second source of
    numbers that works everywhere except against the store."""
    with pytest.raises(ValidationError, match="id"):
        BUILDERS[name](id=None)


@pytest.mark.parametrize(
    ("name", "wrong"),
    [
        ("Component", "thr-001"),
        ("Actor", "cmp-001"),
        ("Asset", "cmp-001"),
        ("DataFlow", "tb-001"),
        ("TrustBoundary", "df-001"),
    ],
)
def test_an_identifier_naming_another_object_type_is_rejected(name: str, wrong: str) -> None:
    """The typed identifiers do this, and the error names both object types."""
    with pytest.raises(ValidationError):
        BUILDERS[name](id=wrong)


# --------------------------------------------------------------------------------------------
# Open vocabularies (DEC-036)
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "Web Application",
        "web-application",
        "WEB_APPLICATION",
        "  web application  ",
        "Web/Application",
    ],
)
def test_one_type_spelled_five_ways_normalizes_to_one_term(raw: str) -> None:
    """Drift is the real problem with free text, and it is a spelling problem."""
    assert component(component_type=raw).component_type == "web_application"


def test_an_unlisted_type_is_accepted() -> None:
    """The whole point of DEC-036: the document illustrates rather than enumerates."""
    assert component(component_type="quantum_annealer").component_type == "quantum_annealer"


@pytest.mark.parametrize("value", ["", "   ", "!!", "_", "3-tier"])
def test_a_value_that_is_not_a_term_is_refused(value: str) -> None:
    """Open does not mean anything. A term reduces to lowercase words joined by underscores."""
    with pytest.raises(ValidationError):
        component(component_type=value)


def test_a_boolean_type_is_refused_by_name() -> None:
    """`False` in a vocabulary field records an answer nobody gave, so the message says so."""
    with pytest.raises(ValidationError, match="unknown"):
        component(component_type=False)


@pytest.mark.parametrize(
    ("known", "label"),
    [
        (KNOWN_COMPONENT_TYPES, "component"),
        (KNOWN_ACTOR_TYPES, "actor"),
        (KNOWN_ASSET_TYPES, "asset"),
        (KNOWN_BOUNDARY_TYPES, "boundary"),
    ],
)
def test_every_known_term_is_already_normalized(known: frozenset[str], label: str) -> None:
    """A `KNOWN_*` entry that normalization would change is a documentation entry nothing matches."""
    for term in sorted(known):
        assert normalize_term(term) == term, f"{label} type {term!r} is not in canonical form"


def fixture_component_types() -> list[str]:
    loaded = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    types = sorted({str(entry["type"]) for entry in loaded["components"]})
    assert types, "the ForgeFlow fixture lists no components"
    return types


@pytest.mark.parametrize("component_type", fixture_component_types())
def test_every_forgeflow_component_type_is_accepted(component_type: str) -> None:
    """The argument for an open vocabulary, run against the real fixture rather than a summary of it.

    Six of these seven appear nowhere in `data-model.md` section 11. A closed enum built from the
    document would reject the scenario the project is built to assess.
    """
    assert component(component_type=component_type).component_type == component_type


def test_most_forgeflow_component_types_are_undocumented() -> None:
    """Guards the test above from becoming vacuous if section 11's list ever absorbs the fixture."""
    documented = {
        "user_interface",
        "service",
        "api_gateway",
        "background_worker",
        "data_store",
        "message_queue",
        "identity_provider",
        "external_service",
        "repository_provider",
        "ci_cd_system",
        "secrets_manager",
        "object_storage",
        "administrative_interface",
    }
    unlisted = set(fixture_component_types()) - documented
    assert len(unlisted) >= 5, f"the fixture no longer argues for an open vocabulary: {unlisted}"


# --------------------------------------------------------------------------------------------
# Unknown is said, not implied (DEC-009 at field level)
# --------------------------------------------------------------------------------------------


def test_transport_security_defaults_to_an_explicit_unknown() -> None:
    """Section 14: unknown encryption is `unknown`, not `false` and not absent."""
    flow = data_flow()
    assert flow.encryption_in_transit == UNKNOWN
    assert flow.authentication == UNKNOWN


def test_an_unknown_flow_serializes_as_unknown_rather_than_null_or_false() -> None:
    """The serialized form is what reaches the report, the store, and the evaluation."""
    dumped = data_flow().model_dump()
    for field in ("encryption_in_transit", "authentication"):
        assert dumped[field] == UNKNOWN
        assert dumped[field] is not None
        assert dumped[field] is not False


@pytest.mark.parametrize("field", ["encryption_in_transit", "authentication"])
@pytest.mark.parametrize("value", [False, True, None])
def test_transport_security_refuses_a_boolean_or_null(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        data_flow(**{field: value})


@pytest.mark.parametrize(
    ("builder", "field"),
    [
        ("Component", "internet_accessible"),
        ("Component", "externally_managed"),
        ("DataFlow", "internet_exposed"),
    ],
)
def test_an_undocumented_boolean_is_none_rather_than_false(builder: str, field: str) -> None:
    """Three states, not two: documented true, documented false, and not stated. Code that reads
    `None` as `False` turns an undocumented exposure into an internal component."""
    assert getattr(BUILDERS[builder](), field) is None


def test_direction_carries_an_unknown_value() -> None:
    """`direction` is required, and a required field with no honest value gets guessed. A guessed
    `one_way` silently removes a threat nobody ruled out (DEC-036)."""
    assert data_flow(direction="unknown").direction is FlowDirection.UNKNOWN


def test_direction_is_closed() -> None:
    """The counter-example that keeps DEC-036's rule honest: section 14 names the values."""
    with pytest.raises(ValidationError):
        data_flow(direction="duplex")


# --------------------------------------------------------------------------------------------
# Per-object rules
# --------------------------------------------------------------------------------------------


def test_a_flow_from_a_component_to_itself_is_rejected() -> None:
    """Section 14's own validation rule: source and destination must be different components."""
    with pytest.raises(ValidationError, match="between two components"):
        data_flow(source_component_id="cmp-003", destination_component_id="cmp-003")


def test_a_flow_referencing_a_boundary_by_the_wrong_prefix_is_rejected() -> None:
    with pytest.raises(ValidationError):
        data_flow(crosses_trust_boundary_ids=["cmp-002"])


def test_an_actor_carries_no_status_field() -> None:
    """Section 13's table has none, and the other four context objects do. Adding one here would be
    a data-model change; the conformance guard would fail it, and this says why."""
    assert "status" not in Actor.model_fields
    with pytest.raises(ValidationError):
        actor(status=ObjectStatus.CANDIDATE)


def test_an_asset_links_components_by_identifier() -> None:
    assert asset(component_ids=["cmp-001", "cmp-002"]).component_ids == ["cmp-001", "cmp-002"]


def test_a_boundary_with_no_components_on_either_side_is_allowed() -> None:
    """A boundary is real before anyone has worked out which components sit on each side of it.
    Whether it is useful is the validation node's question, not the schema's."""
    boundary = trust_boundary()
    assert boundary.inside_component_ids == []
    assert boundary.outside_component_ids == []


def test_boundary_controls_are_names_rather_than_control_identifiers() -> None:
    """Section 15 types `controls` as free text: the extracted `Control` objects come later."""
    assert trust_boundary(controls=["WAF", "mutual TLS"]).controls == ["WAF", "mutual TLS"]


def test_evidence_identifiers_are_checked_on_every_object() -> None:
    """Ten objects carry `evidence_ids`, and a wrong-prefix identifier there would produce a
    conclusion citing something that is not evidence."""
    for name, builder in sorted(BUILDERS.items()):
        accepted = builder(evidence_ids=["evd-001"]).model_dump()
        assert accepted["evidence_ids"] == ["evd-001"], name
        with pytest.raises(ValidationError):
            builder(evidence_ids=["src-001"])
