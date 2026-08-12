"""What a single-pass baseline returns: findings drawn straight from the documents (DEC-074).

The baselines exist to answer roadmap Stage 4's decision gate — does the multi-stage pipeline
beat a simpler prompt? — so their output is scored by the same structural matcher the pipeline's
findings are (DEC-056). A baseline has no context model and allocates no identifiers, so it names
its affected component by the name the documents use and cites the requirement it bears on
directly. `extra="forbid"` makes an invented field a validation failure, which is what the
schema-validity rate measures: a baseline that cannot produce valid structured output records
that as a result, not an excuse.

This is not a schema any Trace agent emits — findings are the pipeline's deterministic output, not
an agent proposal. It is the finding-shaped target the baseline is forced to, so the comparison
scores the same object type on both sides.
"""

from __future__ import annotations

from pydantic import Field

from trace_ai.domain.base import DomainModel

__all__ = ["BaselineFinding", "BaselineFindings"]


class BaselineFinding(DomainModel):
    """One finding a baseline proposes, named the way the documents name things."""

    requirement_id: str = Field(min_length=1)
    """The requirement this finding bears on, cited from the catalog the baseline was given."""

    affected_component: str = Field(min_length=1)
    """The affected component, by the name the source documents use (DEC-056 matches on it)."""

    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_quote: str = Field(min_length=1)
    """A passage the baseline says supports the finding. Recorded so a reviewer can check whether
    the baseline is resting a conclusion on absence — which is the whole thing Trace avoids."""


class BaselineFindings(DomainModel):
    """One baseline response: every finding it drew from the documents in a single pass.

    An empty list is valid — a baseline that finds nothing is a baseline that finds nothing, and
    scoring rewards that where the truth set expects nothing.
    """

    findings: list[BaselineFinding] = Field(default_factory=list)
