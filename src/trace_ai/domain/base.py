"""The base every domain object inherits, and the clock they all read.

DEC-006 makes schema-validated structured objects the authoritative workflow state rather than a
conversational transcript, and the pipeline's central rule is that agents propose objects while
the application validates and persists them. Both of those live or die on the schema being strict,
so the strictness is configured once here instead of per model.

`extra="forbid"` is the load-bearing setting. An agent returning an object with an invented field
is the ordinary failure mode of structured generation -- a plausible-sounding key that no consumer
reads. Pydantic's default is to drop it silently, which would let a proposal that was not
understood pass validation and travel downstream looking authoritative. Forbidding it turns that
into a `ValidationError` at the boundary, which is the only place it can still be attributed to
the agent that caused it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

__all__ = ["DomainModel", "now"]


def now() -> datetime:
    """The current time, always timezone-aware.

    Every `created_at` and `updated_at` reads this rather than `datetime.now()`. A naive
    datetime compares and serializes as though it were UTC without being marked as such, and
    the first place that surfaces is an ordering comparison between two objects written by
    different code paths -- which is exactly where it is hardest to notice being wrong.
    """
    return datetime.now(UTC)


class DomainModel(BaseModel):
    """Common configuration for every domain object.

    - `extra="forbid"` rejects unknown fields instead of dropping them, so an agent-proposed
      object carrying an invented key fails validation rather than passing silently.
    - `frozen=True` makes instances immutable and hashable. Objects are replaced rather than
      edited in place by the code that holds them; DEC-023's in-place mutation is a persistence
      operation that constructs a new object and records the delta on a `ReviewerDecision`,
      not an attribute assignment somewhere in a node.
    - `validate_assignment=True` is redundant with `frozen=True` today and is set anyway, so a
      model that later opts out of frozen does not silently opt out of validation with it.
    - `str_strip_whitespace=True` normalizes the ragged edges of text extracted from documents,
      where a trailing newline is an artifact of the source format rather than content.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )
