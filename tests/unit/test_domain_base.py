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
from trace_ai.domain.enums import ObjectStatus


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
