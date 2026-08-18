"""Tests for `DomainModel`, the strictness every domain object inherits.

DEC-006 makes schema-validated objects the authoritative workflow state, and the pipeline's
central rule is that agents propose objects while the application validates and persists them.
Neither survives a permissive schema. If an unknown field is dropped instead of rejected, a
proposal that was not understood travels downstream looking exactly like one that was.

That is not a hypothetical failure mode of structured generation, it is the ordinary one: a model
returns a plausible extra key -- `severity_rationale`, `confidence_score` -- that no consumer
reads. Pydantic's default is to discard it without a word. `extra="forbid"` turns it into a
`ValidationError` at the boundary, which is the only point where it can still be attributed to the
agent that produced it.

These tests use throwaway subclasses rather than real domain objects. `DomainModel` has no fields
of its own, and the behaviour under test is the configuration it hands down. Issue #43.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from trace_ai.domain.base import DomainModel, now
from trace_ai.domain.enums import ObjectStatus, Severity


class Sample(DomainModel):
    """A minimal object standing in for a real one."""

    name: str
    status: ObjectStatus = ObjectStatus.DRAFT


def test_a_declared_field_is_accepted() -> None:
    sample = Sample(name="forgeflow")
    assert sample.name == "forgeflow"
    assert sample.status is ObjectStatus.DRAFT


def test_an_unknown_field_is_rejected() -> None:
    """The setting the agent boundary depends on.

    An agent proposing `{"name": ..., "confidence_score": 0.8}` must fail here rather than be
    silently reduced to `{"name": ...}`.
    """
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Sample(name="forgeflow", confidence_score=0.8)  # type: ignore[call-arg]


def test_the_rejection_names_the_offending_field() -> None:
    """A rejection that does not say what was wrong cannot be acted on by whoever gets the log."""
    with pytest.raises(ValidationError) as caught:
        Sample(name="forgeflow", invented_key="x")  # type: ignore[call-arg]
    assert "invented_key" in str(caught.value)


def test_instances_are_immutable() -> None:
    sample = Sample(name="forgeflow")
    with pytest.raises(ValidationError, match="frozen"):
        sample.name = "changed"  # type: ignore[misc]


def test_instances_are_hashable() -> None:
    """Frozen models can go in a set, which is what deduplication and lineage tracking need."""
    assert len({Sample(name="a"), Sample(name="a"), Sample(name="b")}) == 2


def test_a_wrong_type_is_rejected_rather_than_coerced() -> None:
    with pytest.raises(ValidationError):
        Sample(name="forgeflow", status="not_a_status")  # type: ignore[arg-type]


def test_surrounding_whitespace_is_stripped() -> None:
    """Text extracted from a document arrives with the source format's ragged edges attached.

    A trailing newline on a quoted passage is an artifact of where it was cut, not content, and
    it would otherwise reach a content hash and make two identical passages differ.
    """
    assert Sample(name="  forgeflow\n").name == "forgeflow"


def test_the_configuration_is_what_it_claims_to_be() -> None:
    """Read the settings directly, so a later edit to one of them fails here and not somewhere
    subtle three objects downstream."""
    config = DomainModel.model_config
    assert config["extra"] == "forbid"
    assert config["frozen"] is True
    assert config["validate_assignment"] is True
    assert config["str_strip_whitespace"] is True


def test_a_subclass_inherits_the_configuration_without_restating_it() -> None:
    """Every later domain object gets this by subclassing and nothing else."""
    for key in ("extra", "frozen", "validate_assignment", "str_strip_whitespace"):
        assert Sample.model_config[key] == DomainModel.model_config[key]


def test_a_subclass_that_adds_config_keeps_the_strict_settings() -> None:
    """Pydantic merges `model_config` down the hierarchy; this asserts it rather than assuming."""

    class WithExtraConfig(DomainModel):
        model_config = DomainModel.model_config | {"populate_by_name": True}

        name: str

    assert WithExtraConfig.model_config["extra"] == "forbid"
    with pytest.raises(ValidationError):
        WithExtraConfig(name="x", surprise=1)  # type: ignore[call-arg]


class Finding(DomainModel):
    """Stands in for the real object at the point a reviewer edits it."""

    id: str
    severity: Severity


def test_model_copy_does_not_validate_the_update() -> None:
    """Pinned because it is surprising, and because it sits on the one path that needs it least.

    DEC-023 makes a reviewer edit a mutation in place: the object keeps its identity, its fields
    change, and the delta goes on a `ReviewerDecision`. Under a frozen model that means building
    the edited object, and `model_copy(update=...)` is the API that appears designed for it.

    It performs no validation. An invalid enum value survives as a bare string, and DEC-020
    persists generated objects as JSON payloads -- so it reaches the database, warned about only
    by a serializer message nobody reads. The reviewer-edit path is the only path on which a
    human-supplied value enters a domain object, which makes it the worst possible place to skip
    the schema.

    This test does not endorse the behaviour. It records it, so that a change in pydantic that
    fixes it is noticed rather than silently relied upon.
    """
    finding = Finding(id="fnd-001", severity=Severity.UNASSIGNED)
    edited = finding.model_copy(update={"severity": "not_a_severity"})

    assert edited.severity == "not_a_severity"
    assert not isinstance(edited.severity, Severity)


def test_model_copy_bypasses_extra_forbid() -> None:
    """The same hole, in the setting this class exists for.

    The invented key does not reach `model_dump()`, so it never persists -- but it is live on the
    instance, and code that reads it works.
    """
    finding = Finding(id="fnd-001", severity=Severity.UNASSIGNED)
    edited = finding.model_copy(update={"invented_field": 1})

    assert edited.invented_field == 1  # type: ignore[attr-defined]
    assert "invented_field" not in edited.model_dump()


def test_revalidating_is_the_edit_path_that_holds() -> None:
    """`model_validate` over the merged dict re-runs the whole schema, which is the point."""
    finding = Finding(id="fnd-001", severity=Severity.UNASSIGNED)

    with pytest.raises(ValidationError):
        Finding.model_validate({**finding.model_dump(), "severity": "not_a_severity"})

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Finding.model_validate({**finding.model_dump(), "invented_field": 1})

    edited = Finding.model_validate({**finding.model_dump(), "severity": "high"})
    assert edited.severity is Severity.HIGH
    assert edited.id == finding.id, "an edit keeps the object's identity (DEC-023)"


def test_validate_assignment_is_inert_under_frozen() -> None:
    """Stated so the config is not misread as offering protection it does not offer here.

    `frozen=True` raises before any validator runs, so `validate_assignment=True` never fires.
    It is set for the model that later opts out of frozen, not for this one.
    """
    finding = Finding(id="fnd-001", severity=Severity.UNASSIGNED)
    with pytest.raises(ValidationError) as caught:
        finding.severity = Severity.HIGH  # type: ignore[misc]
    assert caught.value.errors()[0]["type"] == "frozen_instance"


def test_now_is_timezone_aware() -> None:
    stamp = now()
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() == timedelta(0)


def test_now_is_close_to_the_real_clock() -> None:
    """Cheap proof it reads the clock rather than returning a constant."""
    assert abs(now() - datetime.now(UTC)) < timedelta(seconds=5)


def test_now_advances() -> None:
    first, second = now(), now()
    assert second >= first


def test_a_naive_datetime_is_not_what_now_returns() -> None:
    """The distinction this helper exists for.

    A naive datetime compares and serializes as though it were UTC without being marked as such.
    The first place that shows up is an ordering comparison between objects written by different
    code paths, which is the hardest place to notice it.
    """
    with pytest.raises(TypeError):
        _ = now() < datetime.now()  # a deliberately naive call; the mismatch is the point


def test_stored_type_defaults_to_the_class_name() -> None:
    """DEC-090: the store keys rows on `stored_type`, defaulting to the class name for every
    subclass, so nothing changes for a class that does not rename."""
    assert Sample.stored_type == "Sample"
    assert Sample(name="x").stored_type == "Sample"


def test_stored_type_is_a_one_line_override() -> None:
    class Renamed(Sample):
        stored_type = "Sample"

    assert Renamed.stored_type == "Sample", "a rename keeps reading rows written under the old name"


def test_row_key_is_the_identifier_and_id_less_objects_must_override() -> None:
    class WithId(DomainModel):
        id: str

    assert WithId(id="fnd-001").row_key() == "fnd-001"

    class NoId(DomainModel):
        name: str

    with pytest.raises(ValueError, match="does not override row_key"):
        NoId(name="anonymous").row_key()
